"""Security tools: run_secrets_scan, run_pip_audit (passive) and probe_authz, probe_injection, probe_http_hardening (active).

Passive tools read files / call an advisory database and store findings like the static tools do. Active probes send a FIXED,
versioned payload corpus (security_checks.py) to the system under test from inside the sandbox network, only with safe methods
(GET), only to endpoints in scope, and never more requests than the budget and `security.max_probe_requests` allow. They do not
record bugs: each hit becomes a candidate test node with a replayable repro, which the triager confirms through `record_bug`.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
import uuid
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from .. import security_checks as sc
from ..guards import escalation
from ..guards import scope as scope_guard
from ..models import err, ok
from ..runners import parsers, sandbox
from ..runtime import tool
from ..store import assets, findings, runs
from . import _exec as X
from .run import _base_url, _finish, _test_node

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
MAX_FILE = 512 * 1024
SAFE_METHODS = ("GET",)
OSV = "https://api.osv.dev/v1"


def _fp(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:20]


def _sec(ch: dict) -> dict:
    return ch.get("security") or {}


def _add_static(run_id: str, oracle: str, severity: str, title: str, fingerprint: str, asset_id: str | None, escalations: list) -> bool:
    f, new = findings.add_static_finding_once(run_id, "static_issue", oracle, severity, title, asset_id, fingerprint)
    if new:
        esc = escalation.on_serious_finding(run_id, f)
        if esc:
            escalations.append(esc["escalation_id"])
    return new


# ------------------------------------------------------------------ run_secrets_scan
def _repo_files(repo: Path, excludes: list[str]):
    for p in sorted(repo.rglob("*")):
        rel = p.relative_to(repo)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        if any(scope_guard.fnmatchcase(rel.as_posix(), pat) for pat in excludes):
            continue
        try:
            if p.stat().st_size > MAX_FILE:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:2048]:
            continue
        yield rel.as_posix(), data.decode("utf-8", "replace")


def _history_hits(repo: Path, max_commits: int) -> list[dict]:
    """Secrets that were ever added in the last commits (they stay in history even after the file is cleaned)."""
    if not (repo / ".git").exists():
        return []
    try:
        out = subprocess.run(["git", "-C", str(repo), "log", "-p", "-U0", "--no-color", f"-n{max_commits}", "--format=@@%h"],
                             capture_output=True, text=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    hits, sha, file = [], "", ""
    for line in out.splitlines():
        if line.startswith("@@"):
            sha = line[2:]
        elif line.startswith("+++ b/"):
            file = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for h in sc.scan_text(line[1:]):
                hits.append({**h, "file": file, "commit": sha})
    return hits


@tool("run_secrets_scan")
def run_secrets_scan(run_id: str, include_history: bool = True, max_commits: int = 100) -> dict:
    """Hard-coded secrets (private keys, cloud/GitHub/Slack tokens, passwords in code or URLs) in the target repo and its recent git
    history. Values are redacted in findings. Reads files only; nothing is executed. Placeholders like 'changeme' are ignored."""
    ch = X.charter(run_id)
    repo = Path(ch["target"]["repo_path"])
    if not repo.is_dir():
        return err(f"repo_path {repo} is not a directory")
    exclude = (ch["scope"] or {}).get("exclude") or []
    escalations: list[str] = []
    seen: set[str] = set()
    new = total = 0
    for rel, text in _repo_files(repo, exclude):
        for h in sc.scan_text(text):
            total += 1
            fp = _fp("secrets", h["name"], rel, h["snippet"])
            seen.add(fp)
            node = X.attach_asset(run_id, rel, h["line"]) if rel.endswith(".py") else None
            new += _add_static(run_id, "secrets", h["severity"], f"{h['name']} in {rel}:{h['line']}  {h['snippet']}", fp,
                               str(node["id"]) if node else None, escalations)
    in_history = 0
    if include_history:
        for h in _history_hits(repo, max_commits):
            fp = _fp("secrets", h["name"], h["file"], h["snippet"])
            if fp in seen:
                continue
            seen.add(fp)
            in_history += 1
            new += _add_static(run_id, "secrets", h["severity"],
                               f"{h['name']} in git history ({h['commit']}, {h['file']})  {h['snippet']}", fp, None, escalations)
    X.refresh_issue_counts(run_id)
    return ok(f"secrets: {total} in the working tree, {in_history} only in history, {new} new finding(s)",
              {"working_tree": total, "history_only": in_history, "new_findings": new, "serious_escalations": escalations},
              ["rotate any real secret: removing it from the code does not remove it from git history"])


# ------------------------------------------------------------------ run_pip_audit
def _pin_ok(spec: str) -> tuple[str, str] | None:
    m = re.match(r"^\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*==\s*([A-Za-z0-9_.\-+!]+)", spec)
    return (m.group(1).lower().replace("_", "-"), m.group(2)) if m else None


def collect_dependencies(repo: Path) -> dict[str, str]:
    """name -> exact version, from uv.lock, requirements*.txt and pinned entries in pyproject.toml."""
    deps: dict[str, str] = {}
    for f in sorted(repo.glob("requirements*.txt")):
        for line in f.read_text(errors="replace").splitlines():
            pin = _pin_ok(line.split("#")[0])
            if pin:
                deps[pin[0]] = pin[1]
    py = repo / "pyproject.toml"
    if py.is_file():
        try:
            proj = tomllib.loads(py.read_text()).get("project", {})
            specs = list(proj.get("dependencies", [])) + [d for g in proj.get("optional-dependencies", {}).values() for d in g]
            for s in specs:
                pin = _pin_ok(s)
                if pin:
                    deps.setdefault(pin[0], pin[1])
        except tomllib.TOMLDecodeError:
            pass
    lock = repo / "uv.lock"
    if lock.is_file():
        try:
            for p in tomllib.loads(lock.read_text()).get("package", []):
                if p.get("name") and p.get("version") and p.get("source", {}).get("registry"):
                    deps[p["name"].lower().replace("_", "-")] = p["version"]
        except tomllib.TOMLDecodeError:
            pass
    return deps


def _osv_client() -> httpx.Client:      # replaced in tests
    return httpx.Client(timeout=20)


def _osv_severity(v: dict) -> str:
    raw = str((v.get("database_specific") or {}).get("severity") or "").upper()
    return {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium", "MEDIUM": "medium", "LOW": "low"}.get(raw, "medium")


def _fixed_in(v: dict) -> str | None:
    for a in v.get("affected", []):
        for r in a.get("ranges", []):
            for e in r.get("events", []):
                if "fixed" in e:
                    return e["fixed"]
    return None


@tool("run_pip_audit")
def run_pip_audit(run_id: str, max_advisories: int = 25) -> dict:
    """Known vulnerabilities (OSV database) in the target's PINNED dependencies (uv.lock, requirements*.txt, pyproject). Sends package
    names and versions to api.osv.dev, so it only runs when the charter sets security.osv_lookup=true."""
    ch = X.charter(run_id)
    if not _sec(ch).get("osv_lookup"):
        return ok("skipped: security.osv_lookup is false. This tool sends your dependency names and versions to api.osv.dev; "
                  "set it to true in the charter if you accept that.", {"skipped": True})
    repo = Path(ch["target"]["repo_path"])
    deps = collect_dependencies(repo)
    if not deps:
        return ok("no pinned dependencies found (uv.lock, requirements*.txt, pinned pyproject entries)", {"packages": 0})
    names = sorted(deps)
    try:
        with _osv_client() as c:
            r = c.post(f"{OSV}/querybatch", json={"queries": [{"package": {"name": n, "ecosystem": "PyPI"}, "version": deps[n]} for n in names]})
            r.raise_for_status()
            hits = [(n, v["id"]) for n, res in zip(names, r.json().get("results", [])) for v in (res or {}).get("vulns", [])]
            details = {}
            for n, vid in hits[:max_advisories]:
                d = c.get(f"{OSV}/vulns/{vid}")
                if d.status_code == 200:
                    details[(n, vid)] = d.json()
    except (httpx.HTTPError, ValueError) as e:
        return err(f"could not query OSV: {type(e).__name__}: {str(e)[:150]}")
    escalations: list[str] = []
    new = 0
    for (n, vid), v in details.items():
        fixed = _fixed_in(v)
        title = f"{n} {deps[n]} has {vid}: {(v.get('summary') or '')[:90]}" + (f" (fixed in {fixed})" if fixed else "")
        new += _add_static(run_id, "dependency", _osv_severity(v), title, _fp("dependency", n, deps[n], vid), None, escalations)
    return ok(f"checked {len(names)} packages: {len(hits)} advisory match(es), {new} new finding(s)",
              {"packages": len(names), "advisories": len(hits), "detailed": len(details), "new_findings": new, "serious_escalations": escalations},
              ["upgrade to the fixed versions, then re-run"])


# ------------------------------------------------------------------ active probes: shared plumbing
def _probe_action(kw: dict) -> dict:
    ch = runs.get_run(kw["run_id"])["charter"]
    return {"host": _base_url(ch), "requests": 0, "expl_node_id": kw.get("parent_id")}


def _remaining_requests(run_id: str, ch: dict) -> int:
    run = runs.get_run(run_id)
    left = ch["budget"]["max_requests"] - int((run["budget_used"] or {}).get("requests", 0))
    return max(0, min(int(_sec(ch).get("max_probe_requests", 300)), left))


def _send(run_id: str, ch: dict, reqs: list[dict]) -> dict[str, dict]:
    """Run a batch from inside the sandbox network. reqs: {id, method, path, headers, body}."""
    if not reqs:
        return {}
    base = _base_url(ch).rstrip("/")
    batch = {"requests": [{"id": r["id"], "method": r["method"], "url": base + r["path"], "headers": r.get("headers") or {},
                           "body": r.get("body")} for r in reqs], "timeout": 15}
    bid = uuid.uuid4().hex[:8]
    sandbox.put_files(sandbox.get(run_id), {f"{sandbox.OUT}/batch_{bid}.json": json.dumps(batch)})
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_batch.py {sandbox.OUT}/batch_{bid}.json --out $OUT",
                              timeout=15 * len(reqs) + 30)
    runs.bump_budget(run_id, requests=len(reqs))
    return (parsers.jloads(text) or {}).get("results") or {}


def _endpoints(run_id: str, only: list[str] | None, ch: dict) -> list[dict]:
    out = []
    for ep in assets.list_nodes(run_id, "endpoint"):
        p = ep["props"]
        label = f"{p['method']} {p['path']}"
        if p["method"] not in SAFE_METHODS or not p.get("in_scope", True):
            continue
        if only and label not in only and p["path"] not in only:
            continue
        if not scope_guard.in_scope(ch["scope"], scope_guard.endpoint_candidates(p["method"], p["path"])):
            continue
        out.append(ep)
    return out


def _path_for(ep: dict, overrides: dict, query: dict | None = None, ids: dict | None = None) -> str:
    """Concrete path+query: path params from `overrides` or a harmless sample, other params only if required or overridden."""
    props = ep["props"]
    vals, q = {}, {}
    for prm in props.get("params", []):
        name, where = prm.get("name"), prm.get("in")
        if name in overrides:
            v = overrides[name]
        elif where == "path" or prm.get("required"):
            v = sc.sample_value(prm.get("schema"))
        else:
            continue
        (vals if where == "path" else q)[name] = v
    path = sc.fill_path(props["path"], vals)
    q.update(query or {})
    return path + ("?" + urlencode(q, quote_via=quote) if q else "")


def _auth_header(ch: dict, user: str | None = None) -> dict:
    s = _sec(ch)
    tokens = s.get("tokens") or {}
    name = user or next(iter(tokens), None)
    return {s.get("auth_header", "Authorization"): tokens[name]} if name in tokens else {}


def _candidate(run_id: str, ch: dict, ep: dict | None, cls: str, ev: dict, request: dict, severity: str | None = None,
               param: str | None = None, parent_id: str | None = None) -> dict:
    cwe, label, default_sev = sc.CLASSES[cls]
    template = f"{ep['props']['method']} {ep['props']['path']}" if ep else request.get("template", request["path"])
    title = f"{label} in {template}" + (f" (parameter '{param}')" if param else "")
    repro = {"kind": "http", "method": request["method"], "path": request["path"], "headers": request.get("headers") or {}, "body": None,
             "check": "security", "expect": ev["expect"]}
    node = _test_node(run_id, f"[security] {title}", str(ep["id"]) if ep else None,
                      {"tool": "probe", "class": cls, "method": request["method"], "path": request["path"], "template": template}, parent_id)
    meta = {"class": cls, "cwe": cwe, "param": param, "template": template, "evidence": ev["evidence"], "corpus": sc.CORPUS_VERSION}
    _finish(str(node["id"]), "fail", {"tool": "probe", "request": {k: request[k] for k in ("method", "path")},
                                      "security": meta, "oracle_candidates": ["security"], "repro": repro})
    return {"expl_node_id": str(node["id"]), "class": cls, "cwe": cwe, "severity_hint": severity or default_sev, "endpoint": template,
            "param": param, "evidence": ev["evidence"], "title": title}


def _summary(kind: str, cands: list, sent: int, skipped: list) -> dict:
    return ok(f"{kind}: {len(cands)} candidate(s) from {sent} request(s)",
              {"requests_sent": sent, "candidates": cands, "skipped": skipped, "corpus_version": sc.CORPUS_VERSION},
              ["triager: confirm each candidate with record_bug(oracle='security', severity=..., expl_node_id=...)"] if cands else None)


# ------------------------------------------------------------------ probe_injection
@tool("probe_injection", executing=True, action=_probe_action)
def probe_injection(run_id: str, endpoints: list[str] | None = None, parent_id: str | None = None) -> dict:
    """Fixed payload corpus (SQL / path traversal / OS command / reflected XSS) against the free-text parameters of in-scope GET
    endpoints. Needs evidence in the response (database error, /etc/passwd content, a computed 9359, a reflected tag), not just a 500.
    Returns candidates; confirm them with record_bug(oracle='security'). `endpoints`: labels like 'GET /search' (default all)."""
    ch = X.charter(run_id)
    cap = _remaining_requests(run_id, ch)
    plan, reqs, skipped = [], [], []
    for ei, ep in enumerate(_endpoints(run_id, endpoints, ch)):
        hdr = _auth_header(ch) if ep["props"].get("security") else {}
        for pi, prm in enumerate(p for p in ep["props"].get("params", []) if sc.attackable(p)):
            names = ["control", *sc.PAYLOADS]
            if len(reqs) + len(names) > cap:
                skipped.append(f"{ep['props']['method']} {ep['props']['path']}?{prm['name']}: request cap reached")
                continue
            for name in names:
                value = "bscoutcontrol" if name == "control" else sc.PAYLOADS[name]
                rid = f"{ei}:{pi}:{name}"
                reqs.append({"id": rid, "method": "GET", "headers": hdr, "path": _path_for(ep, {prm["name"]: value})})
            plan.append((ep, prm, ei, pi))
    results = _send(run_id, ch, reqs)
    by_id = {r["id"]: r for r in reqs}
    cands = []
    for ep, prm, ei, pi in plan:
        resp = {n: results.get(f"{ei}:{pi}:{n}") for n in ["control", *sc.PAYLOADS]}
        if not resp["control"] or "error" in resp["control"]:
            skipped.append(f"{ep['props']['method']} {ep['props']['path']}?{prm['name']}: control request failed")
            continue
        for ev in sc.analyse_injection({k: v for k, v in resp.items() if v and "error" not in v}):
            req = by_id[f"{ei}:{pi}:{ev['probe']}"]
            cands.append(_candidate(run_id, ch, ep, ev["class"], ev, {"method": "GET", "path": req["path"], "headers": req["headers"]},
                                    param=prm["name"], parent_id=parent_id))
    return _summary("probe_injection", cands, len(reqs), skipped)


# ------------------------------------------------------------------ probe_authz
@tool("probe_authz", executing=True, action=_probe_action)
def probe_authz(run_id: str, endpoints: list[str] | None = None, parent_id: str | None = None) -> dict:
    """(1) endpoints whose OpenAPI declares security but that answer 2xx without credentials; (2) broken object-level authorization:
    with charter security.tokens + security.owned, user B reading a resource that user A owns. Without those the second check is skipped."""
    ch = X.charter(run_id)
    s = _sec(ch)
    cap = _remaining_requests(run_id, ch)
    eps = _endpoints(run_id, endpoints, ch)
    reqs, plan, skipped = [], [], []
    for ei, ep in enumerate(eps):
        pr = ep["props"]
        if pr.get("security") and not any(scope_guard.fnmatchcase(pr["path"], pat) for pat in s.get("public_paths", [])) and len(reqs) < cap:
            reqs.append({"id": f"unauth:{ei}", "method": "GET", "headers": {}, "path": _path_for(ep, {})})
            plan.append(("unauth", ei, ep, None))
    tokens, owned = s.get("tokens") or {}, s.get("owned") or {}
    if not (tokens and owned):
        skipped.append("BOLA check skipped: set security.tokens and security.owned in the charter")
    by_label = {f"{e['props']['method']} {e['props']['path']}": e for e in eps} | {e["props"]["path"]: e for e in eps}
    for owner, per_tpl in owned.items():
        for tpl, ids in (per_tpl or {}).items():
            ep = by_label.get(tpl)
            if not ep:
                skipped.append(f"owned path {tpl} is not an in-scope GET endpoint")
                continue
            pname = next((p["name"] for p in ep["props"].get("params", []) if p.get("in") == "path"), None)
            for rid_ in ids:
                path = _path_for(ep, {pname: rid_} if pname else {})
                for other in tokens:
                    if other != owner and owner in tokens and len(reqs) + 2 <= cap:
                        k = f"bola:{len(plan)}"
                        reqs += [{"id": k + ":ctl", "method": "GET", "headers": _auth_header(ch, owner), "path": path},
                                 {"id": k + ":atk", "method": "GET", "headers": _auth_header(ch, other), "path": path}]
                        plan.append(("bola", k, ep, (owner, other, path)))
    results = _send(run_id, ch, reqs)
    by_id = {r["id"]: r for r in reqs}
    cands = []
    for kind, ref, ep, extra in plan:
        if kind == "unauth":
            resp = results.get(f"unauth:{ref}")
            if resp and sc.is_2xx(resp):
                req = by_id[f"unauth:{ref}"]
                cands.append(_candidate(run_id, ch, ep, "missing_auth",
                                        {"evidence": f"declares security {ep['props']['security']} but returned {resp['status_code']} with no credentials",
                                         "expect": {"status_2xx": True}},
                                        {"method": "GET", "path": req["path"], "headers": {}}, parent_id=parent_id))
        else:
            owner, other, path = extra
            ctl, atk = results.get(ref + ":ctl"), results.get(ref + ":atk")
            if not (ctl and sc.is_2xx(ctl)):
                skipped.append(f"{owner}'s own request for {path} did not succeed ({sc.status_of(ctl)}): cannot judge")
            elif atk and sc.is_2xx(atk):
                cands.append(_candidate(run_id, ch, ep, "bola",
                                        {"evidence": f"{other} read {owner}'s resource {path} (HTTP {atk['status_code']})",
                                         "expect": {"status_2xx": True}},
                                        {"method": "GET", "path": path, "headers": by_id[ref + ":atk"]["headers"]}, parent_id=parent_id))
    return _summary("probe_authz", cands, len(reqs), skipped)


# ------------------------------------------------------------------ probe_http_hardening
@tool("probe_http_hardening", executing=True, action=_probe_action)
def probe_http_hardening(run_id: str, parent_id: str | None = None) -> dict:
    """Security headers (nosniff; framing protection on HTML) and CORS (does an unknown Origin get allowed?), on one safe in-scope GET
    endpoint. Three requests."""
    ch = X.charter(run_id)
    eps = [e for e in _endpoints(run_id, None, ch) if not any(p.get("required") and p.get("in") == "query" for p in e["props"].get("params", []))]
    eps.sort(key=lambda e: (e["props"]["path"] != "/health", len(e["props"].get("params", [])), e["props"]["path"]))
    if not eps:
        return err("no in-scope GET endpoint to probe")
    ep = eps[0]
    path = _path_for(ep, {})
    hdr = _auth_header(ch) if ep["props"].get("security") else {}
    origin = {"Origin": sc.EVIL_ORIGIN}
    reqs = [{"id": "plain", "method": "GET", "headers": hdr, "path": path},
            {"id": "cors", "method": "GET", "headers": {**hdr, **origin}, "path": path},
            {"id": "preflight", "method": "OPTIONS", "headers": {**origin, "Access-Control-Request-Method": "GET"}, "path": path}]
    res = _send(run_id, ch, reqs)
    cands = []
    if res.get("plain") and (ev := sc.analyse_headers(res["plain"])):
        cands.append(_candidate(run_id, ch, ep, "headers", ev, {"method": "GET", "path": path, "headers": hdr}, parent_id=parent_id))
    for rid in ("cors", "preflight"):
        if res.get(rid) and (ev := sc.analyse_cors(res[rid])):
            cands.append(_candidate(run_id, ch, ep, "cors", ev, {"method": "GET", "path": path, "headers": {**hdr, **origin}}, parent_id=parent_id))
            break
    return _summary("probe_http_hardening", cands, len(reqs), [])
