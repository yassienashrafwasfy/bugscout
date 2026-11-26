"""Run tests: write_test, run_pytest, run_hypothesis, run_schemathesis, http_request."""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import re
import shlex
import uuid
from urllib.parse import urlparse

from ..guards import destructive, escalation
from ..models import err, ok
from ..runners import parsers, sandbox
from ..runtime import tool
from ..store import assets, runs, tree
from ..store.db import J, q
from . import _exec as X


def _target_action(kw: dict) -> dict:
    n = assets.get_node(kw["target_asset_id"]) if kw.get("target_asset_id") else None
    return {"key": n["key"] if n else None, "expl_node_id": kw.get("expl_node_id") or kw.get("parent_id")}


def _test_node(run_id: str, title: str, target_asset_id: str | None, action: dict, parent_id: str | None = None,
               expl_node_id: str | None = None) -> dict:
    if expl_node_id:
        n = tree.get_node(expl_node_id)
        if not n or str(n["run_id"]) != run_id:
            raise ValueError("unknown expl_node_id for this run")
        if n["status"] == "frontier":
            tree.update(expl_node_id, status="in_progress")
        return n
    parent = parent_id or str(tree.root_goal(run_id)["id"])
    return tree.add_node(run_id, "test", title, parent_id=parent, status="in_progress", target_asset_id=target_asset_id, action=action)


def _finish(node_id: str, verdict: str, result: dict) -> None:
    """pass -> done. fail/error stays in_progress so the host triages (check_* -> check_flaky -> record_bug)."""
    result = {"verdict": verdict, **result}
    tree.update(node_id, status="done" if verdict == "pass" else None, result=result)


# ------------------------------------------------------------------ write_test
@tool("write_test", executing=True, action=_target_action)
def write_test(run_id: str, target_asset_id: str, code: str, kind: str = "unit", title: str | None = None,
               parent_id: str | None = None) -> dict:
    """Save a host-written pytest file in the sandbox (/work/gen) and create a `test` node. kind: unit | property | rule."""
    if kind not in ("unit", "property", "rule"):
        return err("kind must be unit | property | rule")
    target = assets.get_node(target_asset_id)
    if not target or str(target["run_id"]) != run_id:
        return err("unknown target_asset_id for this run")
    try:
        mod = ast.parse(code)
    except SyntaxError as e:
        return err(f"test code does not parse: {e}")
    if not any(isinstance(n, ast.FunctionDef) and n.name.startswith("test") for n in ast.walk(mod)):
        return err("test code defines no test_* function")
    slug = re.sub(r"\W+", "_", target["key"]).strip("_")[:40]
    fname = f"test_{kind}_{slug}_{hashlib.sha1(code.encode()).hexdigest()[:6]}.py"
    path = f"{sandbox.GEN}/{fname}"
    sandbox.put_files(sandbox.get(run_id), {path: code})
    node = _test_node(run_id, title or f"{kind} test for {target['key']}", target_asset_id,
                      {"tool": "write_test", "file": path, "kind": kind}, parent_id)
    runs.add_artifact(run_id, "generated_test", {"file": path, "code": code, "node": str(node["id"])})
    assets.set_props(target_asset_id, {"has_generated_test": True})
    return ok("test written", {"expl_node_id": str(node["id"]), "file": path, "selector": path},
              [f"run_pytest(selector='{path}', expl_node_id='{node['id']}')"])


# ------------------------------------------------------------------ run_pytest
def _pytest_cmd(selector: str | None, out: str, extra: str = "") -> str:
    sel = selector or "$(ls -d tests test 2>/dev/null) /work/gen"
    return (f"python -m pytest {sel} -p no:randomly -p no:cacheprovider --benchmark-disable --timeout=60 -q "
            f"--json-report --json-report-file={out} --json-report-omit=collectors {extra}")


def _safe_selector(selector: str | None) -> str | None:
    if not selector:
        return None
    if not re.fullmatch(r"[\w./\-:\[\]=, *]+", selector):
        raise ValueError("selector may only contain path / node id characters")
    return " ".join(shlex.quote(p) for p in selector.split())


@tool("run_pytest", executing=True, action=lambda kw: {"expl_node_id": kw.get("expl_node_id")})
def run_pytest(run_id: str, selector: str | None = None, expl_node_id: str | None = None, timeout: int = 170) -> dict:
    """Run existing and/or generated tests in the sandbox (pytest-json-report + pytest-timeout). Pass/fail per test."""
    sel = _safe_selector(selector)
    res, text = X.run_to_json(run_id, _pytest_cmd(sel, "$OUT"), timeout=timeout)
    rep = parsers.parse_pytest_report(text)
    if not rep["tests"] and not rep["summary"]:
        return err("pytest produced no report", {"stdout": X.tail(res.stdout), "stderr": X.tail(res.stderr), "exit_code": res.code})
    aid = runs.add_artifact(run_id, "pytest_report", rep)
    for t in rep["tests"]:
        q("""INSERT INTO test_record (run_id, test_id, file, status) VALUES (%s,%s,%s,'active')
             ON CONFLICT (run_id, test_id) DO NOTHING""", (run_id, t["nodeid"], t["nodeid"].split("::")[0]))
    failed = [t for t in rep["tests"] if t["outcome"] in ("failed", "error")]
    fail_nodes = []
    for t in failed[:25]:
        existing = q("SELECT id FROM expl_node WHERE run_id=%s AND kind='test' AND action->>'nodeid'=%s", (run_id, t["nodeid"]))
        if existing:
            nid = str(existing[0]["id"])
        else:
            n = tree.add_node(run_id, "test", f"pytest {t['nodeid']}", parent_id=str(tree.root_goal(run_id)["id"]),
                              status="in_progress", action={"tool": "run_pytest", "nodeid": t["nodeid"]})
            nid = str(n["id"])
        tree.update(nid, result={"verdict": "fail", "tool": "run_pytest", "evidence": {
            "nodeid": t["nodeid"], "message": t["message"], "longrepr": t["longrepr"][-800:], "path": t["crash_path"],
            "line": t["crash_line"]}, "repro": {"kind": "pytest", "nodeid": t["nodeid"]}})
        fail_nodes.append({"expl_node_id": nid, "nodeid": t["nodeid"], "message": (t["message"] or "")[:160]})
    if expl_node_id:
        verdict = "fail" if failed else "pass"
        _finish(expl_node_id, verdict, {"tool": "run_pytest", "summary": rep["summary"], "artifact_id": aid,
                                       "repro": {"kind": "pytest", "nodeid": failed[0]["nodeid"]} if failed else None})
    s = rep["summary"]
    return ok(f"{s.get('passed', 0)} passed, {s.get('failed', 0)} failed, {s.get('error', 0)} errors",
              {"summary": s, "failures": fail_nodes, "artifact_id": aid, "duration": rep.get("duration")},
              ["check_flaky on failures, then check_crash / record_bug"] if failed else ["run_coverage"])


# ------------------------------------------------------------------ run_hypothesis
@tool("run_hypothesis", executing=True, action=_target_action)
def run_hypothesis(run_id: str, target_asset_id: str, strategy_code: str | None = None, max_examples: int = 200,
                   expl_node_id: str | None = None, assume: str | None = None, property: str | None = None) -> dict:
    """Property-based test of one function. Strategies come from type hints unless `strategy_code` (JSON {param: "st.xxx()"}) is given.
    The shrunk failing example is stored in the node result."""
    target = assets.get_node(target_asset_id)
    if not target or target["type"] != "function" or ":" not in target["key"] or target["props"].get("class"):
        return err("target must be a module-level function asset")
    cmd = f"python /opt/bugscout/tm_hyp.py --target {shlex.quote(target['key'])} --out $OUT --max-examples {int(max_examples)}"
    if strategy_code:
        try:
            json.loads(strategy_code)
        except json.JSONDecodeError:
            return err('strategy_code must be JSON like {"x": "st.integers(0, 10)"}')
        cmd += f" --strategies {shlex.quote(strategy_code)}"
    if assume:
        cmd += f" --assume {shlex.quote(assume)}"
    if property:
        cmd += f" --property {shlex.quote(property)}"
    node = _test_node(run_id, f"hypothesis: {target['key']}", target_asset_id, {"tool": "run_hypothesis", "max_examples": max_examples},
                      None, expl_node_id)
    res, text = X.run_to_json(run_id, cmd, timeout=170)
    d = parsers.jloads(text)
    nid = str(node["id"])
    if not d:
        _finish(nid, "error", {"tool": "run_hypothesis", "timed_out": res.timed_out, "stderr": X.tail(res.stderr)})
        return err("hypothesis run produced no result" + (" (timed out)" if res.timed_out else ""),
                   {"expl_node_id": nid, "stderr": X.tail(res.stderr)})
    if d["status"] == "no_strategy":
        _finish(nid, "error", {"tool": "run_hypothesis", "reason": d["reason"]})
        return err(d["reason"], {"expl_node_id": nid})
    if d["status"] == "passed":
        _finish(nid, "pass", {"tool": "run_hypothesis", "examples_run": d["examples_run"]})
        assets.set_props(target_asset_id, {"tested": True})
        return ok(f"no counterexample in {d['examples_run']} examples", {"expl_node_id": nid, "examples_run": d["examples_run"]})
    fail = d["failure"]
    cand = "rule" if d["kind"] == "rule" else "crash"
    _finish(nid, "fail", {"tool": "run_hypothesis", "oracle_candidates": [cand], "failure": fail, "example": d["example"],
                          "examples_run": d["examples_run"],
                          "repro": {"kind": "call", "target": target["key"], "kwargs": d["example_json"],
                                    "expect_exception": fail["type"] if cand == "crash" else None,
                                    "property": property if cand == "rule" else None}})
    assets.set_props(target_asset_id, {"tested": True})
    return ok(f"FAILED: {fail['type']}: {fail['message'][:100]} with {d['example']}",
              {"expl_node_id": nid, "example": d["example"], "exception": fail["type"], "frames": fail["frames"]},
              [f"check_crash(expl_node_id='{nid}')", "check_flaky / record_bug"])


# ------------------------------------------------------------------ http_request
def _base_url(ch: dict) -> str:
    return ch["target"].get("base_url") or f"http://sut:{ch['target'].get('port', 8000)}"


def _http_action(kw: dict) -> dict:
    ch = runs.get_run(kw["run_id"])["charter"]
    return {"method": kw.get("method", "GET"), "path": kw.get("path", "/"), "host": _base_url(ch), "requests": 1,
            "expl_node_id": kw.get("expl_node_id")}


def do_http(run_id: str, method: str, path: str, headers: dict | None, body, timeout: int = 20) -> dict:
    ch = X.charter(run_id)
    req = {"method": method.upper(), "url": _base_url(ch).rstrip("/") + path, "headers": headers or {}, "body": body, "timeout": timeout}
    rid = uuid.uuid4().hex[:8]
    sandbox.put_files(sandbox.get(run_id), {f"{sandbox.OUT}/req_{rid}.json": json.dumps(req)})
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_http.py {sandbox.OUT}/req_{rid}.json --out $OUT", timeout=timeout + 10)
    runs.bump_budget(run_id, requests=1)
    return parsers.jloads(text) or {"error": "NoResult", "message": X.tail(res.stderr)}


@tool("http_request", executing=True, action=_http_action)
def http_request(run_id: str, method: str, path: str, headers: dict | None = None, body: dict | list | str | None = None,
                 expl_node_id: str | None = None, parent_id: str | None = None) -> dict:
    """One HTTP request to the system under test, issued from inside the sandbox network. Guarded (scope, destructive, budget)."""
    if not path.startswith("/") or "://" in path or path.startswith("//"):
        return err("path must be a relative URL path starting with '/' (the host comes from the charter)")
    tmpl, opid = destructive.template_for(run_id, method, path)
    ep = assets.get_by_key(run_id, f"{method.upper()} {tmpl}")
    node = _test_node(run_id, f"{method.upper()} {path}", str(ep["id"]) if ep else None,
                      {"tool": "http_request", "method": method.upper(), "path": path, "template": tmpl}, parent_id, expl_node_id)
    resp = do_http(run_id, method, path, headers, body)
    sc = resp.get("status_code")
    request = {"method": method.upper(), "path": path, "template": tmpl, "headers": headers or {}, "body": body}
    evidence = {k: resp.get(k) for k in ("status_code", "text", "json", "elapsed_ms", "error", "message")}
    cand = []
    if sc is not None and sc >= 500:
        cand.append("http_5xx")
    if resp.get("timeout"):
        cand.append("crash")
    verdict = "fail" if cand else "pass"
    _finish(str(node["id"]), verdict, {"tool": "http_request", "request": request, "response": evidence,
                                      "oracle_candidates": cand, "repro": {"kind": "http", **request}})
    if ep:
        assets.set_props(str(ep["id"]), {"tested": True})
    summary = f"{method.upper()} {path} -> {sc if sc is not None else resp.get('error')}"
    return ok(summary, {"expl_node_id": str(node["id"]), "status_code": sc, "json": resp.get("json"),
                        "text": (resp.get("text") or "")[:500] if resp.get("json") is None else None,
                        "elapsed_ms": resp.get("elapsed_ms"), "error": resp.get("error")},
              [f"check_schema(expl_node_id='{node['id']}')", f"check_crash(expl_node_id='{node['id']}')"])


# ------------------------------------------------------------------ run_schemathesis
CHECK_ORACLE = {"not_a_server_error": "http_5xx", "response_schema_conformance": "schema", "status_code_conformance": "schema",
                "content_type_conformance": "schema", "response_headers_conformance": "schema"}


def parse_schemathesis_ndjson(text: str) -> dict:
    """NDJSON event stream -> {requests, per_endpoint: {label: {requests, failures: {key: {...}}}}}."""
    per: dict[str, dict] = {}
    total = 0
    for line in (text or "").splitlines():
        ev = parsers.jloads(line.strip())
        if not ev or "ScenarioFinished" not in ev:
            continue
        rec = ev["ScenarioFinished"].get("recorder") or {}
        label = rec.get("label")
        if not label:
            continue
        e = per.setdefault(label, {"requests": 0, "failures": {}})
        inter = rec.get("interactions") or {}
        e["requests"] += len(inter)
        total += len(inter)
        for cid, checks in (rec.get("checks") or {}).items():
            i = inter.get(cid)
            for c in checks:
                if c.get("status") != "failure":
                    continue
                f = (c.get("failure_info") or {}).get("failure", {})
                code = i["response"]["status_code"] if i else None
                key = f"{c['name']}|{f.get('code')}|{code}"
                g = e["failures"].setdefault(key, {"check": c["name"], "code": f.get("code"), "title": f.get("title"),
                                                   "message": (f.get("message") or "")[:300], "status_code": code,
                                                   "count": 0, "examples": []})
                g["count"] += 1
                if i and len(g["examples"]) < 2:
                    body = i["request"].get("body")
                    raw = i["response"].get("content", {}).get("$base64") if i["response"].get("content") else None
                    g["examples"].append({"method": i["request"]["method"],
                                          "path": re.sub(r"^https?://[^/]+", "", i["request"]["uri"]),
                                          "headers": {}, "body": base64.b64decode(body["$base64"]).decode("utf-8", "replace") if isinstance(body, dict) and "$base64" in body else None,
                                          "response_status": code,
                                          "response_text": base64.b64decode(raw).decode("utf-8", "replace")[:1500] if raw else None})
    return {"requests": total, "per_endpoint": per}


@tool("run_schemathesis", executing=True, action=lambda kw: {"requests": int(kw.get("max_examples", 150)) // 3, "expl_node_id": kw.get("expl_node_id")})
def run_schemathesis(run_id: str, endpoint_filter: str | None = None, max_examples: int = 150, seed: int | None = None) -> dict:
    """Fuzz the API from its OpenAPI document. Checks: not_a_server_error, response_schema_conformance, status_code_conformance.
    Destructive endpoints and out-of-scope endpoints are filtered out (and a destructive one raises an escalation)."""
    ch = X.charter(run_id)
    scope, t = ch["scope"], ch["target"]
    if not t.get("openapi"):
        return err("charter has no target.openapi")
    eps = assets.list_nodes(run_id, "endpoint")
    if not eps:
        return err("no endpoints in the asset graph; call import_openapi first")
    allowed, skipped_scope, skipped_destructive = [], [], []
    for ep in eps:
        p = ep["props"]
        if endpoint_filter and not re.search(endpoint_filter, ep["key"]):
            continue
        if not p.get("in_scope", True):
            skipped_scope.append(ep["key"])
            continue
        if destructive.is_destructive(p["method"], p["path"], p.get("operation_id")) and not scope.get("allow_destructive"):
            k = escalation.action_key("destructive", p["method"], p["path"])
            if not escalation.approved(run_id, "destructive", k):
                escalation.escalate(run_id, "destructive", f"{p['method']} {p['path']} may be destructive; allow fuzzing it?",
                                    None, key=k, context={"method": p["method"], "path_template": p["path"]})
                skipped_destructive.append(ep["key"])
                continue
        allowed.append(ep)
    if not allowed:
        return ok("nothing to fuzz after scope/destructive filtering", {"skipped_destructive": skipped_destructive,
                                                                    "skipped_out_of_scope": skipped_scope})
    names = "|".join(re.escape(e["key"]) for e in allowed)
    outdir = f"{sandbox.OUT}/st_{uuid.uuid4().hex[:6]}"
    cmd = (f"schemathesis run {shlex.quote(t['openapi'])} --url {shlex.quote(_base_url(ch))} "
           f"--checks not_a_server_error,response_schema_conformance,status_code_conformance "
           f"--max-examples {int(max_examples)} --phases examples,coverage,fuzzing --continue-on-failure --workers 1 "
           f"--include-name-regex {shlex.quote('^(' + names + ')$')} --report ndjson --report-dir {outdir}"
           + (f" --seed {int(seed)}" if seed is not None else "") + " > /dev/null 2>&1; cat " + outdir + "/*.ndjson")
    res = sandbox.run(run_id, cmd, timeout=170)
    parsed = parse_schemathesis_ndjson(res.stdout)
    runs.bump_budget(run_id, requests=parsed["requests"])
    aid = runs.add_artifact(run_id, "schemathesis_report", parsed)
    by_key = {e["key"]: e for e in allowed}
    fail_nodes, passed = [], 0
    for label, e in parsed["per_endpoint"].items():
        ep = by_key.get(label)
        eid = str(ep["id"]) if ep else None
        if not e["failures"]:
            n = tree.add_node(run_id, "test", f"schemathesis {label}", parent_id=str(tree.root_goal(run_id)["id"]), status="done",
                              target_asset_id=eid, action={"tool": "run_schemathesis"},
                              result={"verdict": "pass", "requests": e["requests"]})
            passed += 1
            if ep:
                assets.set_props(eid, {"tested": True})
            continue
        for g in e["failures"].values():
            ex = g["examples"][0] if g["examples"] else {}
            oracle = CHECK_ORACLE.get(g["check"], "schema")
            n = tree.add_node(
                run_id, "test", f"schemathesis {label}: {g['title']} ({g['check']})", parent_id=str(tree.root_goal(run_id)["id"]),
                status="in_progress", target_asset_id=eid, action={"tool": "run_schemathesis", "check": g["check"]},
                result={"verdict": "fail", "tool": "run_schemathesis", "oracle_candidates": [oracle], "check": g["check"],
                        "response": {"status_code": g["status_code"], "text": ex.get("response_text"), "message": g["message"]},
                        "request": {"method": ex.get("method"), "path": ex.get("path"), "template": label.split(" ", 1)[1]},
                        "occurrences": g["count"],
                        "repro": {"kind": "http", "method": ex.get("method"), "path": ex.get("path"), "headers": {},
                                  "body": ex.get("body"), "check": g["check"]}})
            fail_nodes.append({"expl_node_id": str(n["id"]), "endpoint": label, "check": g["check"], "status_code": g["status_code"],
                               "occurrences": g["count"], "example": f"{ex.get('method')} {ex.get('path')}"})
            if ep:
                assets.set_props(eid, {"tested": True})
    return ok(f"{parsed['requests']} requests; {len(fail_nodes)} failure group(s) on {len(parsed['per_endpoint'])} endpoint(s)",
              {"requests": parsed["requests"], "failures": fail_nodes, "endpoints_clean": passed, "artifact_id": aid,
               "skipped_destructive": skipped_destructive, "skipped_out_of_scope": skipped_scope},
              ["check_crash / check_schema on each failure node, then check_flaky + record_bug"] if fail_nodes else None)
