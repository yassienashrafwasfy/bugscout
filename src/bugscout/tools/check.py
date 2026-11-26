"""Oracles: check_crash, check_schema, check_rule, compare_with_git_version."""
from __future__ import annotations

import json
import re
import shlex

import jsonschema

from ..models import err, ok
from ..runners import git_ref, parsers, sandbox
from ..runtime import tool
from ..store import assets, runs, tree
from . import _exec as X
from .run import _finish, _test_node, _target_action


def _node(run_id: str, expl_node_id: str) -> dict | None:
    n = tree.get_node(expl_node_id)
    return n if n and str(n["run_id"]) == run_id else None


def _attach_check(node_id: str, name: str, outcome: dict) -> None:
    n = tree.get_node(node_id)
    checks = dict((n["result"] or {}).get("oracle_checks") or {})
    checks[name] = outcome
    tree.merge_result(node_id, {"oracle_checks": checks})


# ------------------------------------------------------------------ check_crash
@tool("check_crash")
def check_crash(run_id: str, expl_node_id: str) -> dict:
    """Classify a node's outcome: exception / timeout / HTTP 5xx -> bug candidate."""
    n = _node(run_id, expl_node_id)
    if not n or not n["result"]:
        return err("node not found or has no result yet")
    r = n["result"]
    out: dict = {"candidate": False}
    fail = r.get("failure")
    resp = r.get("response") or {}
    ev = r.get("evidence") or {}
    if fail and fail.get("type") and fail["type"] != "RuleViolation":
        out = {"candidate": True, "oracle": "crash", "kind": "exception", "exception": fail["type"], "message": fail["message"][:200],
               "frames": fail.get("frames", []), "severity_hint": "medium"}
    elif (resp.get("status_code") or 0) >= 500:
        out = {"candidate": True, "oracle": "http_5xx", "kind": "http", "status_code": resp["status_code"],
               "excerpt": (resp.get("text") or "")[:200], "severity_hint": "medium"}
    elif resp.get("timeout") or (r.get("timed_out")):
        out = {"candidate": True, "oracle": "crash", "kind": "timeout", "severity_hint": "medium"}
    elif r.get("verdict") == "fail" and ev.get("message"):
        msg = ev["message"]
        exc = (re.match(r"([A-Za-z_]+(?:Error|Exception|Exit|Warning)?)\b", msg) or [None, "Exception"])[1]
        if exc == "AssertionError" or msg.startswith("assert"):
            out = {"candidate": True, "oracle": "rule", "kind": "assertion", "message": msg[:200], "severity_hint": "medium"}
        else:
            out = {"candidate": True, "oracle": "crash", "kind": "exception", "exception": exc, "message": msg[:200], "severity_hint": "medium"}
    _attach_check(expl_node_id, "crash", out)
    if out["candidate"]:
        return ok(f"bug candidate ({out['oracle']}): {out.get('exception') or out.get('status_code') or out.get('kind')}", out,
                  ["check_flaky (if a test) -> record_bug"])
    return ok("no crash / 5xx / timeout", out)


# ------------------------------------------------------------------ check_schema
def _response_schema(ep: dict | None, status: int) -> tuple[dict | None, bool]:
    """(schema or None, documented?)"""
    if not ep:
        return None, False
    resps = ep["props"].get("responses") or {}
    r = resps.get(str(status)) or resps.get("default")
    if r is None:
        return None, False
    content = (r.get("content") or {})
    for ct in ("application/json", "application/*+json", "*/*"):
        if ct in content and content[ct].get("schema") is not None:
            return content[ct]["schema"], True
    return None, True


@tool("check_schema")
def check_schema(run_id: str, expl_node_id: str) -> dict:
    """Validate an HTTP node's response against the OpenAPI schema (jsonschema); also flags undocumented status codes."""
    n = _node(run_id, expl_node_id)
    if not n or not n["result"]:
        return err("node not found or has no result yet")
    r = n["result"]
    req, resp = r.get("request") or {}, r.get("response") or {}
    if not req or resp.get("status_code") is None:
        return err("node has no HTTP request/response (use on http_request / run_schemathesis nodes)")
    tmpl = req.get("template") or req.get("path")
    ep = assets.get_by_key(run_id, f"{str(req.get('method')).upper()} {tmpl}")
    schema, documented = _response_schema(ep, resp["status_code"])
    problems = []
    if ep and not documented:
        problems.append({"kind": "undocumented_status", "message": f"status {resp['status_code']} is not documented for {ep['key']}"})
    body = resp.get("json")
    if body is None and resp.get("text"):
        try:
            body = json.loads(resp["text"])
        except (json.JSONDecodeError, TypeError):
            body = None
    if schema is not None and body is not None:
        v = jsonschema.Draft202012Validator(schema)
        for e in list(v.iter_errors(body))[:5]:
            problems.append({"kind": "schema_violation", "path": "/".join(map(str, e.absolute_path)), "message": e.message[:200]})
    out = {"candidate": bool(problems), "oracle": "schema", "problems": problems, "severity_hint": "medium",
           "validated": schema is not None and body is not None}
    _attach_check(expl_node_id, "schema", out)
    if problems:
        return ok(f"schema mismatch: {problems[0]['message'][:120]}", out, ["check_flaky -> record_bug"])
    return ok("response conforms to the schema" if out["validated"] else "nothing to validate (no schema/body)", out)


# ------------------------------------------------------------------ check_rule
@tool("check_rule", executing=True, action=lambda kw: {
    "key": next((r["target"] for r in runs.get_run(kw["run_id"])["charter"]["rules"] if r["name"] == kw.get("rule_name")), None)})
def check_rule(run_id: str, rule_name: str, max_examples: int = 300) -> dict:
    """Turn a charter rule into a Hypothesis test and run it."""
    ch = X.charter(run_id)
    rule = next((r for r in ch["rules"] if r["name"] == rule_name), None)
    if not rule:
        return err(f"no rule named '{rule_name}'; rules: {[r['name'] for r in ch['rules']]}")
    target = assets.get_by_key(run_id, rule["target"])
    cmd = (f"python /opt/bugscout/tm_hyp.py --target {shlex.quote(rule['target'])} --out $OUT --max-examples {int(max_examples)} "
           f"--property {shlex.quote(rule['property'])}")
    if rule.get("assume"):
        cmd += f" --assume {shlex.quote(rule['assume'])}"
    if rule.get("strategy"):
        cmd += f" --strategies {shlex.quote(rule['strategy'])}"
    node = _test_node(run_id, f"rule {rule_name}", str(target["id"]) if target else None, {"tool": "check_rule", "rule": rule_name})
    res, text = X.run_to_json(run_id, cmd, timeout=170)
    d = parsers.jloads(text)
    nid = str(node["id"])
    if not d:
        _finish(nid, "error", {"tool": "check_rule", "stderr": X.tail(res.stderr)})
        return err("rule run produced no result", {"expl_node_id": nid, "stderr": X.tail(res.stderr)})
    if d["status"] == "no_strategy":
        _finish(nid, "error", {"tool": "check_rule", "reason": d["reason"]})
        return err(d["reason"] + " (add rule.strategy)", {"expl_node_id": nid})
    if d["status"] == "passed":
        _finish(nid, "pass", {"tool": "check_rule", "examples_run": d["examples_run"]})
        return ok(f"rule '{rule_name}' holds for {d['examples_run']} examples", {"expl_node_id": nid})
    oracle = "rule" if d["kind"] == "rule" else "crash"
    _finish(nid, "fail", {"tool": "check_rule", "oracle_candidates": [oracle], "rule": rule_name, "failure": d["failure"],
                          "example": d["example"],
                          "repro": {"kind": "call", "target": rule["target"], "kwargs": d["example_json"],
                                    "property": rule["property"] if oracle == "rule" else None,
                                    "expect_exception": d["failure"]["type"] if oracle == "crash" else None}})
    return ok(f"rule '{rule_name}' VIOLATED with {d['example']}", {"expl_node_id": nid, "oracle": oracle, "example": d["example"]},
              [f"check_flaky / record_bug(expl_node_id='{nid}', oracle='{oracle}')"])


# ------------------------------------------------------------------ compare_with_git_version
def _call_in(container, spec_target: str, kwargs: dict) -> dict:
    out = f"{sandbox.OUT}/cmp_{abs(hash((spec_target, json.dumps(kwargs, sort_keys=True, default=str)))) % 10**8}.json"
    r = sandbox.exec_in(container, f"python /opt/bugscout/tm_call.py --target {shlex.quote(spec_target)} "
                                   f"--kwargs {shlex.quote(json.dumps(kwargs))} --out {out}", timeout=60)
    return parsers.jloads(sandbox.read_file(container, out)) or {"ok": False, "exception": {"type": "NoResult", "message": r.stderr[-200:]}}


def _same(old: dict, new: dict) -> bool:
    if old.get("ok") != new.get("ok"):
        return False
    if old.get("ok"):
        return old.get("result") == new.get("result")
    return old["exception"]["type"] == new["exception"]["type"] and old["exception"].get("message") == new["exception"].get("message")


@tool("compare_with_git_version", executing=True,
      action=lambda kw: {"key": (kw.get("test_ref") or {}).get("target")})
def compare_with_git_version(run_id: str, test_ref: dict) -> dict:
    """Differential test against the reference commit (charter reference.git_ref, default HEAD~1).
    test_ref is ONE of: {"target": "pkg.mod:f", "kwargs": {...}} | {"target":..., "inputs": [{...}, ...]} |
    {"from_node": "<expl_node_id>"} (reuse a failing node's repro) | {"pytest": "selector"} (compare per-test outcomes).
    Runs the same thing on old code (separate container, git worktree cached per run) and on the current code; any
    difference is a regression candidate (oracle diff_git)."""
    ch = X.charter(run_id)
    ref = ch["reference"]["git_ref"]
    old_c, sha = git_ref.ensure_ref_container(run_id, ch["target"]["repo_path"], ref)
    new_c = sandbox.get(run_id)
    diffs, compared = [], 0
    if "pytest" in test_ref:
        sel = test_ref["pytest"]
        if not re.fullmatch(r"[\w./\-:\[\]=, *]+", sel):
            return err("bad pytest selector")
        old_o, new_o = pytest_outcomes(old_c, new_c, sel)
        res = {"old": old_o, "new": new_o}
        for nodeid, outcome in res["new"].items():
            compared += 1
            if res["old"].get(nodeid) != outcome:
                diffs.append({"test": nodeid, "old": res["old"].get(nodeid, "missing"), "new": outcome})
        target, repro = None, {"kind": "pytest_diff", "selector": sel}
    else:
        if "from_node" in test_ref:
            src = _node(run_id, test_ref["from_node"])
            rp = ((src or {}).get("result") or {}).get("repro") or {}
            if rp.get("kind") != "call":
                return err("from_node must reference a node whose repro is a function call")
            target, inputs = rp["target"], [rp["kwargs"]]
        else:
            target = test_ref.get("target")
            inputs = test_ref.get("inputs") or [test_ref.get("kwargs", {})]
        if not target:
            return err("test_ref needs target+kwargs, target+inputs, from_node or pytest")
        for kw in inputs:
            compared += 1
            old, new = _call_in(old_c, target, kw), _call_in(new_c, target, kw)
            if not _same(old, new):
                diffs.append({"kwargs": kw, "old": _brief(old), "new": _brief(new)})
        repro = {"kind": "call_diff", "target": target, "kwargs": diffs[0]["kwargs"] if diffs else None}
    tgt = assets.get_by_key(run_id, target) if target else None
    node = _test_node(run_id, f"diff vs {ref}: {target or test_ref.get('pytest')}", str(tgt["id"]) if tgt else None,
                      {"tool": "compare_with_git_version", "ref": ref, "sha": sha[:10]})
    nid = str(node["id"])
    _finish(nid, "fail" if diffs else "pass", {"tool": "compare_with_git_version", "ref": ref, "sha": sha[:10],
            "oracle_candidates": ["diff_git"] if diffs else [], "diffs": diffs[:5], "compared": compared, "repro": repro if diffs else None})
    if diffs:
        return ok(f"REGRESSION CANDIDATE: {len(diffs)}/{compared} input(s) behave differently from {ref}",
                  {"expl_node_id": nid, "diffs": diffs[:3]}, ["decide whether the change is intended; record_bug(oracle='diff_git')"])
    return ok(f"identical behaviour on {compared} input(s) vs {ref}", {"expl_node_id": nid})


def pytest_outcomes(old_c, new_c, sel: str) -> tuple[dict, dict]:
    """Run a pytest selector on the old and the current code; {nodeid: outcome} for each."""
    _copy_gen(new_c, old_c)
    res = []
    for label, c in (("old", old_c), ("new", new_c)):
        out = f"{sandbox.OUT}/cmp_{label}.json"
        sandbox.exec_in(c, f"python -m pytest {sel} -p no:randomly -p no:cacheprovider --benchmark-disable --timeout=60 -q "
                           f"--json-report --json-report-file={out} --json-report-omit=collectors", timeout=170)
        res.append({t["nodeid"]: t["outcome"] for t in parsers.parse_pytest_report(sandbox.read_file(c, out))["tests"]})
    return res[0], res[1]


def _brief(r: dict) -> dict:
    return {"ok": True, "result": r.get("result")} if r.get("ok") else {"ok": False, "exception": f"{r['exception']['type']}: {r['exception'].get('message', '')[:80]}"}


def _copy_gen(src_c, dst_c) -> None:
    """Copy generated tests from the bench to the old-code container so the same tests run on both."""
    import io
    import tarfile
    try:
        stream, _ = src_c.get_archive(sandbox.GEN)
    except Exception:
        return
    data = b"".join(stream)
    dst_c.exec_run(["mkdir", "-p", "/work"], user="root")
    dst_c.put_archive("/work", data)
    dst_c.exec_run(["chown", "-R", "1000:1000", sandbox.GEN], user="root")
