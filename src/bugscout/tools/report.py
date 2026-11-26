"""Report tools. (Phase 1 ships a minimal build_report; Phase 6 completes it.)"""
from __future__ import annotations

from ..store import findings, tree


def build_report(run_id: str) -> dict:
    from .report_data import collect
    return collect(run_id)


# ---- escalation tools (Phase 4)
from ..guards import escalation as esc_mod  # noqa: E402
from ..models import err, ok  # noqa: E402
from ..runtime import tool  # noqa: E402
from ..store import runs  # noqa: E402

REASONS = ["destructive", "stuck", "serious_bug", "out_of_scope", "budget"]


@tool("ask_human", count_step=False)
def ask_human(run_id: str, question: str, reason: str = "stuck", expl_node_id: str | None = None) -> dict:
    """Create an escalation manually. Pauses only the given branch."""
    if reason not in REASONS:
        return err(f"reason must be one of {REASONS}")
    return esc_mod.escalate(run_id, reason, question, expl_node_id)


@tool("get_escalations", count_step=False)
def get_escalations(run_id: str, status: str = "pending") -> dict:
    """Pending questions for the human (status='all' for history)."""
    rows = runs.list_escalations(run_id, None if status == "all" else status)
    return ok(f"{len(rows)} escalation(s)", {"escalations": [
        {"id": str(e["id"]), "reason": e["reason"], "question": e["question"], "status": e["status"], "answer": e["answer"],
         "expl_node_id": str(e["expl_node_id"]) if e["expl_node_id"] else None} for e in rows]})


@tool("answer_escalation", count_step=False)
def answer_escalation(run_id: str, escalation_id: str, answer: str, approve: bool) -> dict:
    """A human answers: approve=True unblocks the branch (and confirms a serious bug); False denies."""
    e = runs.get_escalation(escalation_id)
    if not e or str(e["run_id"]) != run_id:
        return err("unknown escalation for this run")
    e = runs.answer_escalation(escalation_id, answer, approve)
    esc_mod.resolve(e, approve)
    return ok("approved: branch unblocked" if approve else "denied", {"id": escalation_id, "status": e["status"]})


# ================================================================== Phase 6: fingerprint / record_bug / report
import hashlib  # noqa: E402
import re  # noqa: E402
import json  # noqa: E402
import shlex  # noqa: E402

from ..guards import destructive  # noqa: E402
from ..models import SEVERITIES  # noqa: E402
from ..runners import parsers, sandbox  # noqa: E402
from ..store import assets, findings, tree  # noqa: E402
from . import _exec as X  # noqa: E402


def compute_fingerprint(data: dict) -> str:
    """crash: sha1(exception type + top 3 in-project frames (file:func) + target key).
    HTTP: sha1(method + path template + status + error type)."""
    kind = data.get("kind") or ("http" if data.get("method") else "crash")
    if kind == "http":
        parts = ["http", str(data.get("method", "")).upper(), data.get("path_template") or data.get("path", ""),
                 str(data.get("status", "")), data.get("error_type") or data.get("check") or ""]
    else:
        frames = [f"{f['file']}:{f['func']}" if isinstance(f, dict) else str(f) for f in (data.get("frames") or [])][-3:]
        parts = [kind, data.get("exception_type") or data.get("oracle") or "", *frames, data.get("target") or ""]
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:20]


@tool("fingerprint_bug", count_step=False)
def fingerprint_bug(run_id: str, data: dict) -> dict:
    """Deterministic bug fingerprint. crash: {exception_type, frames:[{file,func}], target}. http: {method, path_template, status, error_type}."""
    return ok("fingerprint", {"fingerprint": compute_fingerprint(data)})


def _node_fingerprint_data(node: dict, oracle: str) -> dict:
    r = node["result"] or {}
    target = None
    if node["target_asset_id"]:
        t = assets.get_node(str(node["target_asset_id"]))
        target = t["key"] if t else None
    rp = r.get("repro") or {}
    if oracle == "security":
        sec = r.get("security") or {}
        return {"kind": "http", "method": "", "path_template": sec.get("template") or rp.get("path"), "status": "",
                "error_type": f"sec:{sec.get('class')}:{sec.get('param') or ''}"}
    if rp.get("kind") in ("call", "call_diff"):
        target = rp.get("target") or target
    if oracle in ("http_5xx", "schema") or rp.get("kind") == "http":
        req = r.get("request") or rp
        resp = r.get("response") or {}
        if oracle == "schema":
            probs = (r.get("oracle_checks", {}).get("schema", {}) or {}).get("problems") or []
            err_t = (probs[0]["kind"] if probs else r.get("check")) or "schema"
        else:
            err_t = (r.get("oracle_checks", {}).get("crash", {}) or {}).get("kind") or "5xx"
        return {"kind": "http", "method": req.get("method"), "path_template": req.get("template") or req.get("path"),
                "status": resp.get("status_code"), "error_type": err_t}
    fail = r.get("failure") or {}
    chk = (r.get("oracle_checks") or {}).get("crash") or {}
    if oracle == "diff_git":
        return {"kind": "diff", "oracle": "diff_git", "target": target}
    if oracle == "rule":
        return {"kind": "rule", "oracle": f"rule:{r.get('rule') or (rp.get('property') or '')}", "target": target}
    return {"kind": "crash", "exception_type": fail.get("type") or chk.get("exception") or (r.get("evidence") or {}).get("message", "")[:40],
            "frames": fail.get("frames") or chk.get("frames") or [], "target": target or (r.get("evidence") or {}).get("nodeid")}


def _repro_action(kw: dict) -> dict:
    node = tree.get_node(kw["expl_node_id"]) if kw.get("expl_node_id") else None
    rp = (kw.get("repro") or ((node or {}).get("result") or {}).get("repro") or {})
    if rp.get("kind") == "http":
        ch = runs.get_run(kw["run_id"])["charter"]
        from .run import _base_url
        return {"method": rp.get("method"), "path": rp.get("path"), "host": _base_url(ch), "requests": 1, "expl_node_id": kw["expl_node_id"]}
    return {"expl_node_id": kw.get("expl_node_id")}


def _http_reproduces(run_id: str, rp: dict, oracle: str, original: dict) -> tuple[bool, dict]:
    from .check import _response_schema
    from .run import do_http
    import jsonschema
    body = rp.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
    resp = do_http(run_id, rp["method"], rp["path"], rp.get("headers"), body)
    sc = resp.get("status_code")
    if oracle == "security":
        from ..security_checks import eval_expect
        if not rp.get("expect"):
            return False, {"error": "a security repro needs an `expect` block (what in the response proves the problem)"}
        return eval_expect(resp, rp["expect"])
    if oracle == "http_5xx" or rp.get("check") == "not_a_server_error":
        return (sc or 0) >= 500, {"status_code": sc}
    if oracle == "schema" or rp.get("check") in ("response_schema_conformance", "status_code_conformance"):
        tmpl, _ = destructive.template_for(run_id, rp["method"], rp["path"])
        ep = assets.get_by_key(run_id, f"{rp['method'].upper()} {tmpl}")
        schema, documented = _response_schema(ep, sc or 0)
        if ep and not documented:
            return True, {"status_code": sc, "problem": "undocumented status"}
        js = resp.get("json")
        if schema is not None and js is not None:
            errs = list(jsonschema.Draft202012Validator(schema).iter_errors(js))
            return bool(errs), {"status_code": sc, "problem": errs[0].message[:120] if errs else None}
        return False, {"status_code": sc}
    return sc == (original.get("response") or {}).get("status_code"), {"status_code": sc}


def _reproduce(run_id: str, node: dict, oracle: str, rp: dict) -> tuple[bool, dict]:
    kind = rp.get("kind")
    if kind == "call":
        prop = f" --property {shlex.quote(rp['property'])}" if rp.get("property") else ""
        res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_call.py --target {shlex.quote(rp['target'])} "
                                          f"--kwargs {shlex.quote(json.dumps(rp['kwargs']))}{prop} --out $OUT", timeout=60)
        d = parsers.jloads(text) or {}
        if rp.get("property"):
            return (d.get("ok") and d.get("property_ok") is False) or (not d.get("ok") and rp.get("expect_exception") == d["exception"]["type"]), d
        exp = rp.get("expect_exception")
        if d.get("ok") is False:
            return (exp is None or d["exception"]["type"] == exp), {"exception": d["exception"]["type"]}
        return False, {"ok": True}
    if kind == "http":
        return _http_reproduces(run_id, rp, oracle, node["result"] or {})
    if kind == "pytest":
        res, text = X.run_to_json(run_id, f"python -m pytest {shlex.quote(rp['nodeid'])} -p no:randomly -p no:cacheprovider --benchmark-disable "
                                          f"--timeout=60 -q --json-report --json-report-file=$OUT --json-report-omit=collectors", timeout=120)
        rep = parsers.parse_pytest_report(text)
        failed = any(t["outcome"] in ("failed", "error") for t in rep["tests"])
        return failed, {"outcomes": [t["outcome"] for t in rep["tests"]]}
    if kind == "call_diff":
        from .check import _call_in, _same
        from ..runners import git_ref
        ch = X.charter(run_id)
        old_c, _ = git_ref.ensure_ref_container(run_id, ch["target"]["repo_path"], ch["reference"]["git_ref"])
        old, new = _call_in(old_c, rp["target"], rp["kwargs"]), _call_in(sandbox.get(run_id), rp["target"], rp["kwargs"])
        return (not _same(old, new)), {}
    if kind == "pytest_diff":
        from .check import pytest_outcomes
        from ..runners import git_ref
        sel = rp.get("selector") or ""
        if not re.fullmatch(r"[\w./\-:\[\]=, *]+", sel):
            return False, {"error": "bad selector in repro"}
        ch = X.charter(run_id)
        old_c, _ = git_ref.ensure_ref_container(run_id, ch["target"]["repo_path"], ch["reference"]["git_ref"])
        old, new = pytest_outcomes(old_c, sandbox.get(run_id), sel)
        diffs = {k: {"old": old.get(k, "missing"), "new": v} for k, v in new.items() if old.get(k) != v}
        return bool(diffs), {"differing_tests": list(diffs)[:5]}
    return False, {"error": "unsupported repro kind"}


@tool("record_bug", executing=True, action=_repro_action)
def record_bug(run_id: str, expl_node_id: str, oracle: str, severity: str, title: str, repro: dict | None = None) -> dict:
    """Record a bug. The repro is RE-RUN once first: if it does not reproduce the node is marked flaky instead.
    Then fingerprint + dedup (same fingerprint -> occurrences++), and high/critical -> needs_confirmation + escalation."""
    from ..models import ORACLES
    if oracle not in ORACLES:
        return err(f"oracle must be one of {ORACLES}")
    if severity not in SEVERITIES:
        return err(f"severity must be one of {SEVERITIES}")
    node = tree.get_node(expl_node_id)
    if not node or str(node["run_id"]) != run_id:
        return err("unknown expl_node_id for this run")
    r = node["result"] or {}
    rp = repro or r.get("repro")
    if not rp:
        return err("no repro: the node has none and none was passed (minimal input + how to replay)")
    reproduced, evidence = _reproduce(run_id, node, oracle, rp)
    if not reproduced:
        tree.update(expl_node_id, status="flaky", flaky_score=0.5)
        tree.merge_result(expl_node_id, {"rerun": {"reproduced": False, "evidence": evidence}})
        return ok("did NOT reproduce on rerun: marked flaky, not recorded as a bug",
                  {"recorded": False, "flaky": True, "evidence": evidence}, ["check_flaky for tests; otherwise find a deterministic repro"])
    fp = compute_fingerprint(_node_fingerprint_data(node, oracle))
    occ = int(r.get("occurrences", 1) or 1)
    existing = findings.by_fingerprint(run_id, fp)
    if existing:
        f = findings.bump_occurrences(str(existing["id"]), occ)
        tree.update(expl_node_id, status="duplicate", result={**r, "duplicate_of_finding": str(existing["id"]), "rerun": {"reproduced": True}})
        return ok(f"duplicate of an existing finding (occurrences={f['occurrences']})",
                  {"recorded": False, "duplicate": True, "finding_id": str(existing["id"]), "occurrences": f["occurrences"]})
    f = findings.add_finding(run_id, "bug", oracle, severity, title, expl_node_id=expl_node_id,
                             asset_id=str(node["target_asset_id"]) if node["target_asset_id"] else None, fingerprint=fp,
                             repro=rp)
    if occ > 1:
        f = findings.bump_occurrences(str(f["id"]), occ - 1)
    tree.merge_result(expl_node_id, {"rerun": {"reproduced": True, "evidence": evidence}, "finding_id": str(f["id"])})
    from ..guards import escalation
    esc = escalation.on_serious_finding(run_id, f, expl_node_id)
    if esc:
        return ok(f"bug recorded ({severity}) - needs human confirmation", {"recorded": True, "finding_id": str(f["id"]), "fingerprint": fp,
                  "needs_confirmation": True, "escalation_id": esc["escalation_id"]})
    tree.update(expl_node_id, status="confirmed_bug")
    return ok(f"bug recorded ({severity}, {oracle})", {"recorded": True, "finding_id": str(f["id"]), "fingerprint": fp, "occurrences": f["occurrences"]},
              ["add_test_idea for related code (copies of this bug: query_graph duplicates_of)"])


def render_md(d: dict, run_id: str) -> str:
    L = [f"# Testing report: run {run_id[:8]}", ""]
    L.append(f"Budget used: {d['budget_used']}. Tree: {d['tree']}.\n")
    L.append(f"## Bugs ({len(d['bugs'])})")
    for b in d["bugs"]:
        L.append(f"- **[{b['severity']}] {b['title']}** (oracle: {b['oracle']}, occurrences: {b['occurrences']}, status: {b['status']})")
    if d["perf_regressions"]:
        L.append(f"\n## Performance regressions ({len(d['perf_regressions'])})")
        L += [f"- {b['title']}" for b in d["perf_regressions"]]
    if d["perf_findings"]:
        L.append(f"\n## Performance findings ({len(d['perf_findings'])})")
        L += [f"- [{b['oracle']}] {b['title']}" for b in d["perf_findings"]]
    L.append(f"\n## Flaky tests ({len(d['flaky_tests'])})")
    L += [f"- {t}" for t in d["flaky_tests"]]
    L.append(f"\n## Duplicate tests ({len(d['duplicate_tests'])})")
    L += [f"- {t}" for t in d["duplicate_tests"]]
    by_o: dict[str, int] = {}
    for f in d["static_issues"]:
        by_o[f["oracle"]] = by_o.get(f["oracle"], 0) + 1
    L.append(f"\n## Static issues ({len(d['static_issues'])}) by tool: {by_o}")
    L += [f"- [{f['severity']}] {f['title'][:140]}" for f in d["static_issues"] if f["severity"] in ("high", "medium")][:10]
    c = d["coverage"]
    L.append(f"\n## Coverage: {('line %s%%, branch %s%%' % (c['line_pct'], c['branch_pct'])) if c else 'not measured'}")
    L += [f"- least covered: {x['key']} ({x['branch']:.0%})" for x in d["least_covered"]]
    L.append(f"\n## Mutation score: {d['mutation_score'] if d['mutation_score'] is not None else 'not measured'}")
    L.append("\n## Complexity hotspots")
    L += [f"- {x['key']}: {x['complexity']} (rank {x['rank']})" for x in d["complexity_hotspots"]]
    L.append(f"\n## Duplication: {d['duplication_pct']}%" if d["duplication_pct"] is not None else "\n## Duplication: not measured")
    L += [f"- {w['title']}" for w in d["warnings"] if w["oracle"] == "duplication"]
    L.append(f"\n## Dead code ({len(d['dead_code'])})")
    L += [f"- {x['key']} ({x['confidence']}% confidence, {'confirmed' if x['confirmed'] else 'needs confirmation'})" for x in d["dead_code"]]
    L.append("\n## Time complexity")
    L += [f"- {x['key']}: {x['big_o']}{' (uncertain)' if x['uncertain'] else ''} (allowed {x['allowed']})" for x in d["time_complexity"]]
    L.append("\n## CPU hotspots")
    L += [f"- {x['key']}: {x['self_pct']}% self time" for x in d["cpu_hotspots"]]
    L.append("\n## Memory")
    L += [f"- {x['key']}: peak {x['peak_mb']} MB" for x in d["memory"]]
    if d["open_escalations"]:
        L.append(f"\n## Open escalations ({len(d['open_escalations'])})")
        L += [f"- [{e['reason']}] {e['question']}" for e in d["open_escalations"]]
    return "\n".join(L)


@tool("get_report", count_step=False)
def get_report(run_id: str, format: str = "md") -> dict:
    """Summary: deduped bugs, flaky tests, static issues, coverage, mutation, complexity, duplication, dead code,
    time complexity, CPU/memory hotspots, performance regressions. The full report is stored (artifact + run://{id}/report)."""
    d = build_report(run_id)
    md = render_md(d, run_id)
    aid = runs.add_artifact(run_id, "report", {"markdown": md, "data": d})
    if format == "json":
        return ok("report (json)", {**d, "artifact_id": aid})
    inline = md if len(md) < 5200 else md[:5200] + "\n… (truncated; read resource run://%s/report for the full text)" % run_id
    return ok(f"{len(d['bugs'])} bug(s), {len(d['static_issues'])} static issue(s)", {"markdown": inline, "artifact_id": aid})
