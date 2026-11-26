"""Docker sandbox: ALL target code executes here, never on the host.

Containers carry labels (bugscout.run, bugscout.role) so state survives a server restart.
  bench : long-lived workbench where tests / tools run.  /work/repo = copy of the target, /work/out = reports
  sut   : the API under test (kind rest_api/both), alias `sut` on an internal (no-internet) network
  ref   : copy of an older git ref, used for differential testing and perf-regression comparison
"""
from __future__ import annotations

import io
import os
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import APIError, ImageNotFound, NotFound

from .. import config

_client: docker.DockerClient | None = None
EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".hypothesis"}
WORK, REPO, OUT, GEN = "/work", "/work/repo", "/work/out", "/work/gen"
PY_ENV = {"PYTHONPATH": f"{REPO}:{REPO}/src:{GEN}", "PYTHONDONTWRITEBYTECODE": "1", "HYPOTHESIS_STORAGE_DIRECTORY": "/tmp/hyp"}


@dataclass
class ExecResult:
    code: int
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False


def client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def short(run_id: str) -> str:
    return str(run_id).replace("-", "")[:10]


def net_name(run_id: str) -> str:
    return f"bugscout-{short(run_id)}-net"


# ---------------------------------------------------------------- image
def _sandbox_hash() -> str:
    """Hash of the Dockerfile + shims: a stale image is rebuilt automatically (layers are cached, so this is cheap)."""
    import hashlib
    h = hashlib.sha1()
    for f in sorted(Path(config.SANDBOX_DIR).rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            h.update(f.relative_to(config.SANDBOX_DIR).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def ensure_image(build: bool | None = None) -> str:
    want = _sandbox_hash()
    try:
        img = client().images.get(config.DOCKER_IMAGE)
        if (img.labels or {}).get("bugscout.hash") == want or os.environ.get("BUGSCOUT_SKIP_IMAGE_CHECK") == "1":
            return "present"
        state = "rebuilt"
    except ImageNotFound:
        state = "built"
    if not (config.AUTO_BUILD_IMAGE if build is None else build):
        raise RuntimeError(f"sandbox image {config.DOCKER_IMAGE} missing/stale; run `docker compose --profile build build`")
    # the docker CLI (BuildKit) reuses the layer cache; the SDK's legacy builder would redo the slow pip layer
    import subprocess
    p = subprocess.run(["docker", "build", "-t", config.DOCKER_IMAGE, "--build-arg", f"BUGSCOUT_HASH={want}", str(config.SANDBOX_DIR)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("sandbox image build failed: " + (p.stderr or p.stdout)[-600:])
    return state


# ---------------------------------------------------------------- files
def _tar_dir(src: Path, arc_prefix: str = "") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        def filt(ti: tarfile.TarInfo):
            parts = set(Path(ti.name).parts)
            if parts & EXCLUDE_DIRS:
                return None
            ti.uid = ti.gid = 1000
            ti.uname = ti.gname = "tester"
            return ti
        tf.add(str(src), arcname=arc_prefix or ".", filter=filt)
    return buf.getvalue()


def _tar_files(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for path, content in files.items():
            data = content.encode() if isinstance(content, str) else content
            ti = tarfile.TarInfo(path.lstrip("/"))
            ti.size, ti.mtime, ti.uid, ti.gid, ti.mode = len(data), int(time.time()), 1000, 1000, 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def put_dir(container, src: Path, dest: str) -> None:
    """Copy host dir `src` to `dest` inside the container (replacing it)."""
    container.exec_run(["sh", "-c", f"rm -rf {dest} && mkdir -p {dest}"], user="root")
    container.put_archive(dest, _tar_dir(Path(src)))
    container.exec_run(["chown", "-R", "1000:1000", dest], user="root")


def put_files(container, files: dict[str, str | bytes]) -> None:
    """files: absolute container path -> content. Parent dirs created."""
    dirs = sorted({os.path.dirname(p) for p in files})
    container.exec_run(["mkdir", "-p", *dirs], user="root")
    container.put_archive("/", _tar_files(files))
    container.exec_run(["chown", "-R", "1000:1000", *dirs], user="root")


def read_file(container, path: str) -> str | None:
    try:
        stream, _ = container.get_archive(path)
    except NotFound:
        return None
    buf = io.BytesIO(b"".join(stream))
    with tarfile.open(fileobj=buf) as tf:
        m = tf.next()
        f = tf.extractfile(m) if m else None
        return f.read().decode("utf-8", "replace") if f else None


# ---------------------------------------------------------------- containers
def _limits() -> dict:
    return {"nano_cpus": int(config.CONTAINER_CPUS * 1e9), "mem_limit": config.CONTAINER_MEMORY,
            "memswap_limit": config.CONTAINER_MEMORY}


def _create(run_id: str, role: str, network: str | None, aliases: list[str] | None = None, cmd=None,
            ptrace: bool = False, name_suffix: str = "") -> docker.models.containers.Container:
    kwargs = dict(
        image=config.DOCKER_IMAGE, command=cmd or ["sleep", "infinity"], detach=True,
        name=f"bugscout-{short(run_id)}-{role}{name_suffix}", labels={"bugscout.run": str(run_id), "bugscout.role": role},
        working_dir=REPO, user="tester", environment=dict(PY_ENV),
        cap_drop=["ALL"],
        # root is only used by the harness for chown/rm/pkill; the tools themselves run as uid 1000 with no caps
        cap_add=["CHOWN", "DAC_OVERRIDE", "FOWNER", "KILL"] + (["SYS_PTRACE"] if ptrace else []), security_opt=["no-new-privileges"],
        pids_limit=512, tmpfs={"/tmp": "rw,exec,size=256m"}, **_limits(),
    )
    kwargs["network_mode"] = network or "none"
    c = client().containers.create(**kwargs)
    if network and aliases:   # re-attach with DNS aliases (e.g. `sut`) before the process starts
        net = client().networks.get(network)
        net.disconnect(c)
        net.connect(c, aliases=aliases)
    c.start()
    c.exec_run(["mkdir", "-p", OUT, GEN, "/tmp/hyp"], user="root")
    c.exec_run(["chown", "-R", "1000:1000", WORK, "/tmp/hyp"], user="root")
    return c


def get(run_id: str, role: str = "bench"):
    found = client().containers.list(all=True, filters={"label": [f"bugscout.run={run_id}", f"bugscout.role={role}"]})
    if not found:
        raise RuntimeError(f"no '{role}' container for run {run_id}")
    c = found[0]
    if c.status != "running":
        c.start()
    return c


def has(run_id: str, role: str) -> bool:
    return bool(client().containers.list(all=True, filters={"label": [f"bugscout.run={run_id}", f"bugscout.role={role}"]}))


def ensure_network(run_id: str):
    name = net_name(run_id)
    try:
        return client().networks.get(name)
    except NotFound:
        return client().networks.create(name, driver="bridge", internal=True, labels={"bugscout.run": str(run_id)})


def provision(run_id: str, charter) -> dict:
    """Create bench (+ sut for APIs). No network at all unless there is an API under test."""
    t = charter.target
    info = {"image": ensure_image()}
    repo = Path(t.repo_path)
    if not repo.is_dir():
        raise RuntimeError(f"repo_path {t.repo_path} does not exist")
    api = t.kind in ("rest_api", "both")
    net = ensure_network(run_id).name if api else None
    bench = _create(run_id, "bench", net)
    put_dir(bench, repo, REPO)
    info["bench"] = bench.short_id
    if api:
        sut = _create(run_id, "sut", net, aliases=["sut"], ptrace=True, cmd=["sleep", "infinity"])
        put_dir(sut, repo, REPO)
        start_sut(run_id, t.start_cmd, t.port)
        info["sut"] = sut.short_id
        info["network"] = net
    return info


def start_sut(run_id: str, start_cmd: str, port: int = 8000, wait_s: int = 40) -> None:
    sut = get(run_id, "sut")
    sut.exec_run(["sh", "-c", "pkill -f uvicorn || true"], user="root")
    sut.exec_run(["sh", "-c", f"cd {REPO} && nohup {start_cmd} --port {port} > /tmp/sut.log 2>&1 &"], user="tester")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        r = get(run_id, "bench").exec_run(["python", "-c", f"import socket;socket.create_connection(('sut',{port}),1)"])
        if r.exit_code == 0:
            return
        time.sleep(1)
    log = sut.exec_run(["sh", "-c", "tail -20 /tmp/sut.log"]).output.decode("utf-8", "replace")
    raise RuntimeError(f"sut did not come up on :{port}: {log}")


def exec_in(container, cmd: list[str] | str, timeout: int | None = None, workdir: str = REPO,
            env: dict | None = None, user: str = "tester") -> ExecResult:
    """Run a command with a hard timeout enforced INSIDE the container (coreutils `timeout`)."""
    timeout = timeout or config.DEFAULT_TIMEOUT_S
    argv = ["sh", "-c", cmd] if isinstance(cmd, str) else cmd
    argv = ["timeout", "-k", "5", str(timeout), *argv]
    t0 = time.time()
    r = container.exec_run(argv, workdir=workdir, environment=env or {}, user=user, demux=True)
    out, errb = r.output if r.output else (b"", b"")
    dt = time.time() - t0
    code = r.exit_code if r.exit_code is not None else -1
    return ExecResult(code, (out or b"").decode("utf-8", "replace"), (errb or b"").decode("utf-8", "replace"), dt,
                      timed_out=code in (124, 137) and dt >= timeout - 1)


def run(run_id: str, cmd, timeout: int | None = None, role: str = "bench", workdir: str = REPO,
        env: dict | None = None) -> ExecResult:
    return exec_in(get(run_id, role), cmd, timeout, workdir, env)


def reset(run_id: str, repo_src: str) -> None:
    """Restore a pristine copy of the target and clear reports/generated tests."""
    bench = get(run_id, "bench")
    put_dir(bench, Path(repo_src), REPO)
    bench.exec_run(["sh", "-c", f"rm -rf {OUT}/* {GEN}/*"], user="root")


def new_ref_container(run_id: str, src_dir: Path, tag: str) -> docker.models.containers.Container:
    """Separate container holding an older version of the code (no network)."""
    name = f"bugscout-{short(run_id)}-ref-{tag}"
    try:
        client().containers.get(name).remove(force=True)
    except NotFound:
        pass
    c = _create(run_id, "ref", None, name_suffix=f"-{tag}")
    put_dir(c, src_dir, REPO)
    return c


def destroy_run(run_id: str) -> dict:
    removed = []
    for c in client().containers.list(all=True, filters={"label": [f"bugscout.run={run_id}"]}):
        removed.append(c.name)
        try:
            c.remove(force=True)
        except APIError:
            pass
    try:
        client().networks.get(net_name(run_id)).remove()
    except (NotFound, APIError):
        pass
    return {"removed": removed}
