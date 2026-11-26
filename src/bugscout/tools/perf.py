"""Performance tools: time complexity, benchmarks (+ regression vs the previous commit), CPU / memory / API profiling."""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import statistics
import uuid

from ..models import err, ok
from ..runners import git_ref, parsers, sandbox
from ..runtime import tool
from ..store import assets, findings, runs, tree
from . import _exec as X
from .perf_util import big_o_rank as rank_of
from .check import _copy_gen
from .run import _base_url, _safe_selector, _test_node, _finish, _target_action


def _perf(run_id: str) -> dict:
    return X.charter(run_id)["perf"]


def _allowed(perf: dict, key: str) -> str:
    return perf["max_big_o"].get(key) or perf["max_big_o"].get("default") or "O(n log n)"


def _fn_asset(run_id: str, path: str | None, line: int | None, name: str | None = None) -> dict | None:
    """Map a profile frame (absolute /work/repo path + line) onto a function asset."""
    if not path:
        return None
    f = parsers.rel(path)
    n = assets.enclosing_function(run_id, f, line or 0) if line else None
    if n and (name is None or n["key"].endswith(":" + name) or n["key"].endswith("." + name)):
        return n
    for cand in assets.list_nodes(run_id, "function"):
        if cand["props"].get("file") == f and cand["key"].split(":")[-1].split(".")[-1] == (name or "").split(".")[-1]:
            return cand
    return None


def _add_finding_once(run_id: str, kind: str, oracle: str, severity: str, title: str, asset_id: str | None, fp_parts: str,
                      expl_node_id: str | None = None, repro: dict | None = None) -> tuple[dict, bool]:
    fp = hashlib.sha1(f"{oracle}|{fp_parts}".encode()).hexdigest()[:20]
    ex = findings.by_fingerprint(run_id, fp)
    if ex:
        return findings.bump_occurrences(str(ex["id"])), False
    return findings.add_finding(run_id, kind, oracle, severity, title, expl_node_id=expl_node_id, asset_id=asset_id,
                                fingerprint=fp, repro=repro), True


# ------------------------------------------------------------------ time complexity
@tool("measure_time_complexity", executing=True, action=_target_action)
def measure_time_complexity(run_id: str, target_asset_id: str, input_generator: str | None = None,
                            sizes: list[int] | None = None) -> dict:
    """Empirical time complexity (big_O): calls the function at growing n (median of repeats), fits O(1)..O(2^n).
    `input_generator` = python code defining gen(n) -> the first argument; without it the input is built from the type hint
    (list[int], str, dict, int). A fit worse than perf.max_big_o for the function is a `complexity` finding; noisy fits are
    marked uncertain and never become findings."""
    t = assets.get_node(target_asset_id)
    if not t or str(t["run_id"]) != run_id or t["type"] != "function":
        return err("target_asset_id must be a function asset of this run")
    perf = _perf(run_id)
    cmd = f"python /opt/bugscout/tm_bigo.py --target {shlex.quote(t['key'])} --out $OUT --max-seconds {float(perf['max_seconds_per_call'])}"
    if sizes:
        if len(sizes) < 5 or len(sizes) > 14 or any(not isinstance(n, int) or n < 1 or n > 10**7 for n in sizes):
            return err("sizes: 5-14 ints between 1 and 10^7")
        cmd += " --sizes " + ",".join(str(n) for n in sizes)
    if input_generator:
        if "def gen" not in input_generator:
            return err("input_generator must define gen(n)")
        gen_path = f"{sandbox.OUT}/gen_bigo.py"
        sandbox.put_files(sandbox.get(run_id), {gen_path: input_generator})
        cmd += f" --gen {gen_path}"
    res, text = X.run_to_json(run_id, cmd, timeout=int(perf["max_seconds_per_call"]) + 30)
    d = parsers.jloads(text)
    if not d:
        return err("complexity measurement produced no result", {"stderr": X.tail(res.stderr), "timed_out": res.timed_out})
    if d["status"] == "no_generator":
        return err(d["reason"], next_actions=["pass input_generator='def gen(n): ...'"])
    if d["status"] != "ok":
        return err(f"not enough measurements ({len(d['points'])}); the function may be too slow for the per-call cap", {"points": d["points"]})
    big_o = d["best"]
    allowed = _allowed(perf, t["key"])
    ar = rank_of(allowed)
    ranks = [rank_of(c) for c in d["plausible"]]
    # a fit is uncertain when it is poor, or when the plausible classes straddle the allowed bound (noise decides the verdict)
    uncertain = bool(d["poor_fit"] or (ar >= 0 and any(r > ar for r in ranks) and any(r <= ar for r in ranks)))
    assets.set_props(target_asset_id, {"big_o": big_o, "big_o_fit_residual": round(d["residual"], 4), "big_o_plausible": d["plausible"], "big_o_uncertain": uncertain,
                                       "big_o_allowed": allowed, "worse_than_allowed_big_o": False})
    worse = (not uncertain) and ar >= 0 and all(r > ar for r in ranks)
    fid = None
    if worse:
        assets.set_props(target_asset_id, {"worse_than_allowed_big_o": True})
        f, _ = _add_finding_once(run_id, "warning", "complexity", "medium",
                                 f"{t['key']} measured {big_o}, allowed {allowed}", target_asset_id, t["key"],
                                 repro={"kind": "complexity", "target": t["key"], "points": d["points"]})
        fid = str(f["id"])
    runs.add_artifact(run_id, "complexity", {"target": t["key"], **d})
    verdict = "worse than allowed" if worse else ("uncertain fit" if uncertain else "within allowed")
    return ok(f"{t['key']}: {big_o}{' (uncertain)' if uncertain else ''}, allowed {allowed} -> {verdict}",
              {"big_o": big_o, "plausible": d["plausible"], "allowed": allowed, "uncertain": uncertain, "residual": d["residual"], "finding_id": fid,
               "points": [{"n": p["n"], "ms": round(p["seconds"] * 1000, 3)} for p in d["points"]], "truncated": d["truncated"]})


# ------------------------------------------------------------------ benchmarks
def _bench_cmd(selector: str, out: str) -> str:
    return (f"python -m pytest {selector} --benchmark-only --benchmark-json={out} --benchmark-save-data --benchmark-min-rounds=5 "
            f"--benchmark-max-time=0.4 --benchmark-warmup=on -p no:randomly -p no:cacheprovider --timeout=120 -q")


def _bench_stats(text: str | None) -> dict[str, dict]:
    d = parsers.jloads(text, {}) or {}
    out = {}
    for b in d.get("benchmarks", []):
        data = sorted(b["stats"].get("data") or [])
        p95 = data[min(len(data) - 1, int(0.95 * len(data)))] if data else b["stats"]["max"]
        out[b["fullname"]] = {"name": b["name"], "median_ms": b["stats"]["median"] * 1000, "p95_ms": p95 * 1000,
                              "min_ms": b["stats"]["min"] * 1000, "rounds": b["stats"]["rounds"]}
    return out


def _bench_target(run_id: str, container, fullname: str, name: str) -> dict | None:
    """benchmark(fn, ...) in the test file tells which function it measures."""
    src = sandbox.read_file(container, f"{sandbox.REPO}/{fullname.split('::')[0]}") or ""
    m = re.search(r"(?<![\w.])benchmark\(\s*([\w.]+)", src)
    if not m:
        return None
    fn = m.group(1).split(".")[-1]
    cands = [n for n in assets.list_nodes(run_id, "function") if n["key"].split(":")[-1].split(".")[-1] == fn]
    return cands[0] if cands else None


@tool("run_benchmark", executing=True, action=lambda kw: {"expl_node_id": kw.get("expl_node_id")})
def run_benchmark(run_id: str, selector: str = "tests", expl_node_id: str | None = None) -> dict:
    """pytest-benchmark wall-time stats (median, p95, min) per benchmark; stored as runtime_ms_p50/p95 on the function it times."""
    sel = _safe_selector(selector) or "tests"
    res, text = X.run_to_json(run_id, _bench_cmd(sel, "$OUT"), timeout=170)
    stats = _bench_stats(text)
    if not stats:
        return err("no benchmarks ran (tests must use the `benchmark` fixture)", {"stdout": X.tail(res.stdout), "stderr": X.tail(res.stderr)})
    c = sandbox.get(run_id)
    out = []
    for fullname, s in stats.items():
        tgt = _bench_target(run_id, c, fullname, s["name"])
        if tgt:
            assets.set_props(str(tgt["id"]), {"runtime_ms_p50": round(s["median_ms"], 4), "runtime_ms_p95": round(s["p95_ms"], 4)})
        out.append({"benchmark": fullname, "target": tgt["key"] if tgt else None, **{k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}})
    runs.add_artifact(run_id, "benchmark", {"results": out})
    if expl_node_id:
        _finish(expl_node_id, "pass", {"tool": "run_benchmark", "results": out})
    return ok(f"{len(out)} benchmark(s)", {"results": out}, ["compare_benchmark_with_git_version"])


@tool("compare_benchmark_with_git_version", executing=True, action=lambda kw: {})
def compare_benchmark_with_git_version(run_id: str, selector: str = "tests", repeats: int = 3) -> dict:
    """Same benchmark on the reference commit and the current code, alternated `repeats` (3) times to rule out noise.
    A median slowdown above perf.regression_threshold (20%) seen in a majority of repeats -> `perf_regression` finding."""
    ch = X.charter(run_id)
    perf, ref = ch["perf"], ch["reference"]["git_ref"]
    sel = _safe_selector(selector) or "tests"
    repeats = max(3, min(int(repeats), 5))
    old_c, sha = git_ref.ensure_ref_container(run_id, ch["target"]["repo_path"], ref)
    new_c = sandbox.get(run_id)
    _copy_gen(new_c, old_c)
    ratios: dict[str, list[float]] = {}
    last: dict[str, dict] = {}
    for i in range(repeats):
        order = (("old", old_c), ("new", new_c)) if i % 2 == 0 else (("new", new_c), ("old", old_c))
        got = {}
        for label, c in order:
            out = f"{sandbox.OUT}/bench_{label}_{i}.json"
            sandbox.exec_in(c, _bench_cmd(sel, out), timeout=120)
            got[label] = _bench_stats(sandbox.read_file(c, out))
        for full, n in got["new"].items():
            o = got["old"].get(full)
            if o and o["median_ms"] > 0:
                ratios.setdefault(full, []).append(n["median_ms"] / o["median_ms"])
                last[full] = {"old_ms": round(o["median_ms"], 4), "new_ms": round(n["median_ms"], 4)}
    if not ratios:
        return err("no benchmark ran on both versions", {"ref": ref})
    thr = 1 + float(perf["regression_threshold"])
    results, flagged = [], []
    for full, rs in ratios.items():
        med = statistics.median(rs)
        votes = sum(r > thr for r in rs)
        regression = med > thr and votes * 2 > len(rs)
        row = {"benchmark": full, "ratios": [round(r, 2) for r in rs], "median_ratio": round(med, 2), "regression": regression, **last[full]}
        results.append(row)
        if regression:
            tgt = _bench_target(run_id, new_c, full, full.split("::")[-1])
            node = _test_node(run_id, f"perf diff vs {ref}: {full}", str(tgt["id"]) if tgt else None, {"tool": "compare_benchmark_with_git_version"})
            _finish(str(node["id"]), "fail", {"tool": "compare_benchmark_with_git_version", "oracle_candidates": ["perf_regression"],
                                              "repro": {"kind": "pytest_diff", "selector": sel}, "benchmark": row})
            f, new = _add_finding_once(run_id, "bug", "perf_regression", "medium",
                                       f"{full.split('::')[-1]} is {med:.1f}x slower than {ref} ({last[full]['old_ms']} -> {last[full]['new_ms']} ms)",
                                       str(tgt["id"]) if tgt else None, full, expl_node_id=str(node["id"]),
                                       repro={"kind": "pytest_diff", "selector": sel, "ratios": row["ratios"]})
            row["finding_id"] = str(f["id"])
            if tgt:
                assets.set_props(str(tgt["id"]), {"perf_regression": True, "runtime_ratio_vs_ref": round(med, 2)})
            flagged.append(row)
    summary = (f"{len(flagged)} perf regression(s) vs {ref}" if flagged else f"no perf regression vs {ref} (threshold {perf['regression_threshold']:.0%})")
    return ok(summary, {"ref": ref, "sha": sha[:10], "repeats": repeats, "results": results})


# ------------------------------------------------------------------ profiling
def _profile_cmd(mode: str, target: dict) -> tuple[str, str | None]:
    if "call" in target:
        if not re.fullmatch(r"[\w.]+:[\w.]+", target["call"]):
            raise ValueError("call must look like pkg.mod:function")
        return f"--call {shlex.quote(target['call'])} --kwargs {shlex.quote(json.dumps(target.get('kwargs') or {}))}", target["call"]
    if "pytest" in target:
        _safe_selector(target["pytest"])      # validates the characters
        return f"--pytest {shlex.quote(target['pytest'])}", None
    if "script" in target:
        s = target["script"]
        if not re.fullmatch(r"[\w./\-]+\.py", s) or ".." in s or s.startswith("/"):
            raise ValueError("script must be a relative .py path inside the repo")
        return f"--script {shlex.quote(s)}", None
    raise ValueError("target needs one of: call (+kwargs), pytest, script")


def _profile(run_id: str, mode: str, target: dict, timeout: int) -> tuple[dict | None, str | None, dict | None]:
    try:
        args, call = _profile_cmd(mode, target)
    except ValueError as e:
        return None, str(e), None
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_profile.py {mode} --out $OUT {args}", timeout=timeout)
    d = parsers.jloads(text)
    if not d or d.get("status") != "ok":
        return None, "profiling produced no result", {"stderr": X.tail(res.stderr, 800), "timed_out": res.timed_out,
                                                      "oom_or_killed": res.code in (137, -9)}
    tgt = assets.get_by_key(run_id, call) if call else None
    return d, None, {"target_asset": tgt, "call": call}


@tool("profile_cpu", executing=True, action=lambda kw: {"key": (kw.get("target") or {}).get("call")})
def profile_cpu(run_id: str, target: dict) -> dict:
    """pyinstrument CPU profile of {"call": "pkg.mod:f", "kwargs": {...}} | {"pytest": selector} | {"script": "path.py"}.
    Top 10 self-time functions; `profile_self_pct` stored on function assets; one above perf.hotspot_pct (30%) is a `hotspot`
    warning plus an `idea` node to investigate it."""
    perf = _perf(run_id)
    d, e, meta = _profile(run_id, "cpu", target, timeout=int(perf["max_seconds_per_call"]) + 60)
    if e:
        return err(e, meta)
    top = d["top_project"] or d["top"]
    hot = []
    for r in top:
        a = _fn_asset(run_id, r.get("path"), r.get("line"), r["function"])
        r["asset_key"] = a["key"] if a else None
        if a:
            assets.set_props(str(a["id"]), {"profile_self_pct": r["self_pct"]})
            if r["self_pct"] > perf["hotspot_pct"]:
                hot.append((a, r))
    root = str(tree.root_goal(run_id)["id"])
    for a, r in hot:
        _add_finding_once(run_id, "warning", "hotspot", "low", f"{a['key']} uses {r['self_pct']:.0f}% of CPU time", str(a["id"]), a["key"])
        sig = hashlib.sha1(f"hotspot|{a['key']}".encode()).hexdigest()
        tree.add_idea_dedup(run_id, root, f"investigate hotspot {a['key']}", f"{r['self_pct']:.0f}% of profiled CPU time", str(a["id"]), sig, 0.6)
    runs.add_artifact(run_id, "cpu_profile", {"target": target, **d})
    rows = [{"function": r["function"], "file": r["file"], "self_pct": r["self_pct"], "asset_key": r.get("asset_key")} for r in top]
    lead = rows[0] if rows else None
    return ok(f"top: {lead['function']} {lead['self_pct']}%" if lead else "no project frames in the profile",
              {"top": rows, "total_seconds": round(d["total_seconds"], 3), "hotspots": [a["key"] for a, _ in hot]},
              ["measure_time_complexity on the hotspot"] if hot else None)


@tool("profile_memory", executing=True, action=lambda kw: {"key": (kw.get("target") or {}).get("call")})
def profile_memory(run_id: str, target: dict) -> dict:
    """memray peak memory + top allocators for {"call"|"pytest"|"script"}. Above perf.max_memory_mb -> `memory` finding."""
    perf = _perf(run_id)
    d, e, meta = _profile(run_id, "mem", target, timeout=int(perf["max_seconds_per_call"]) + 60)
    if e:
        return err(e, meta)
    peak = d["peak_mb"]
    tgt = meta["target_asset"]
    if not tgt and d["top_allocators"]:
        r0 = d["top_allocators"][0]
        tgt = _fn_asset(run_id, f"{sandbox.REPO}/{r0['file']}", r0["line"], r0["function"])
    if tgt:
        assets.set_props(str(tgt["id"]), {"peak_memory_mb": peak})
    fid = None
    confirmed = None
    if peak > perf["max_memory_mb"]:
        # a finding is only filed after a second measurement also exceeds the limit (single peaks can be noise)
        d2, e2, _ = _profile(run_id, "mem", target, timeout=int(perf["max_seconds_per_call"]) + 60)
        peak2 = d2["peak_mb"] if d2 else None
        confirmed = bool(d2) and peak2 > perf["max_memory_mb"]
        if confirmed:
            peak = min(peak, peak2)
    if confirmed:
        label = (tgt["key"] if tgt else json.dumps(target, sort_keys=True))
        f, _ = _add_finding_once(run_id, "bug", "memory", "medium", f"{label} peaks at {peak:.0f} MB (limit {perf['max_memory_mb']:.0f} MB)",
                                 str(tgt["id"]) if tgt else None, label, repro={"kind": "memory", "target": target, "peak_mb": peak})
        fid = str(f["id"])
    runs.add_artifact(run_id, "memory_profile", {"target": target, **d})
    return ok(f"peak {peak:.0f} MB (limit {perf['max_memory_mb']:.0f} MB)" + (" -> memory finding" if fid else (" (not confirmed on rerun)" if confirmed is False else "")),
              {"peak_mb": peak, "confirmed_on_rerun": confirmed, "limit_mb": perf["max_memory_mb"], "finding_id": fid, "top_allocators": d["top_allocators"][:5]})


def _api_action(kw: dict) -> dict:
    ch = runs.get_run(kw["run_id"])["charter"]
    ep = kw.get("endpoint", "")
    method, _, path = ep.partition(" ") if " " in ep else ("GET", "", ep)
    return {"method": method.upper(), "path": path or ep, "host": _base_url(ch), "requests": min(int(kw.get("n_requests", 200)), 2000)}


@tool("profile_api", executing=True, action=_api_action)
def profile_api(run_id: str, endpoint: str, n_requests: int = 200) -> dict:
    """Small GET load (httpx, 4 threads, from the bench container) against one endpoint while py-spy samples the server process.
    `endpoint` is a concrete path like "/items/1" (or "GET /items/1"). Guarded like http_request; GET only.
    Returns latency p50/p95 and the hottest project frames, mapped to handler assets."""
    ch = X.charter(run_id)
    if ch["target"]["kind"] != "rest_api":
        return err("profile_api needs a rest_api target")
    method, _, path = endpoint.partition(" ") if " " in endpoint else ("GET", "", endpoint)
    if method.upper() != "GET" or not path.startswith("/") or "://" in path:
        return err("endpoint must be a GET path like '/items/1'")
    n = max(10, min(int(n_requests), 2000))
    sut, bench = sandbox.get(run_id, "sut"), sandbox.get(run_id, "bench")
    pid_r = sut.exec_run(["sh", "-c", "pgrep -f 'uvicorn' | head -1"], user="tester")
    pid = (pid_r.output or b"").decode().strip()
    spy_ok = bool(pid.isdigit())
    if spy_ok:
        sut.exec_run(["sh", "-c", f"rm -f /work/out/spy.json; nohup py-spy record -p {pid} -r 200 -f speedscope -o /work/out/spy.json >/tmp/spy.log 2>&1 &"],
                      user="root")      # only py-spy runs as root (it needs CAP_SYS_PTRACE, which non-root execs do not inherit)
        import time
        time.sleep(1.5)
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_load.py --url {shlex.quote(_base_url(ch).rstrip('/') + path)} --n {n} --out $OUT", timeout=120)
    runs.bump_budget(run_id, requests=n)
    load = parsers.jloads(text)
    if not load:
        return err("load generator failed", {"stderr": X.tail(res.stderr)})
    hot, spy_note = [], None
    if spy_ok:
        sut.exec_run(["sh", "-c", "pkill -INT py-spy; for i in $(seq 1 30); do grep -q 'Wrote speedscope' /tmp/spy.log && break; sleep 0.5; done; chmod a+r /work/out/spy.json 2>/dev/null"], user="root")
        raw = sandbox.read_file(sut, "/work/out/spy.json")
        if raw:
            hot = _speedscope_hot(run_id, raw)
        else:
            spy_note = "py-spy produced no output: " + ((sut.exec_run(["sh", "-c", "tail -3 /tmp/spy.log"]).output or b"").decode()[-200:])
    else:
        spy_note = "server process not found; latency only"
    tmpl, _ = __import__("bugscout.guards.destructive", fromlist=["x"]).template_for(run_id, "GET", path)
    ep = assets.get_by_key(run_id, f"GET {tmpl}")
    if ep:
        assets.set_props(str(ep["id"]), {"latency_p50_ms": round(load["p50_ms"] or 0, 2), "latency_p95_ms": round(load["p95_ms"] or 0, 2)})
    runs.add_artifact(run_id, "api_profile", {"endpoint": path, "load": load, "hot": hot})
    return ok(f"GET {path}: p50 {load['p50_ms']:.1f} ms, p95 {load['p95_ms']:.1f} ms, {load['errors']} errors, {len(hot)} hot frame(s)",
              {"load": load, "hot_frames": hot[:8], "note": spy_note})


def _speedscope_hot(run_id: str, raw: str) -> list[dict]:
    """Samples -> hottest frames. Each sample is attributed to the innermost project frame on its stack (the handler plus
    whatever it called); samples that never touch project code are reported by their leaf frame, flagged project=False."""
    d = json.loads(raw)
    frames = d["shared"]["frames"]
    proj: dict[int, float] = {}
    other: dict[int, float] = {}
    total = 0.0
    for p in d["profiles"]:
        for stack, w in zip(p["samples"], p["weights"]):
            total += w
            inner = next((i for i in reversed(stack) if (frames[i].get("file") or "").startswith(sandbox.REPO)), None)
            if inner is not None:
                proj[inner] = proj.get(inner, 0) + w
            elif stack:
                other[stack[-1]] = other.get(stack[-1], 0) + w
    total = total or 1.0
    rows = []
    for idx, t in sorted(proj.items(), key=lambda kv: -kv[1])[:10]:
        fr = frames[idx]
        a = _fn_asset(run_id, fr.get("file"), fr.get("line"), fr["name"])
        if a:
            assets.set_props(str(a["id"]), {"profile_self_pct": round(100 * t / total, 2)})
        rows.append({"function": fr["name"], "file": parsers.rel(fr["file"]), "line": fr.get("line"), "pct": round(100 * t / total, 2),
                     "project": True, "asset_key": a["key"] if a else None})
    if not rows:     # the handler is too cheap to show up: say where the time goes instead
        for idx, t in sorted(other.items(), key=lambda kv: -kv[1])[:5]:
            fr = frames[idx]
            rows.append({"function": fr["name"], "file": fr.get("file"), "line": fr.get("line"), "pct": round(100 * t / total, 2),
                         "project": False, "asset_key": None})
    return rows
