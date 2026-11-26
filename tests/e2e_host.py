"""A scripted host: follows the `testing_loop` prompt (plan §10) against a running bugscout over MCP, the way Claude Code / Codex
would. It makes the judgement calls an LLM host makes (which targets to fuzz, severity, what to record); every fact it records
comes from tool output. Used by the e2e test; also a worked example of the tool protocol."""
from __future__ import annotations

import json

SKIP_FUZZ_MODULES = ("samplelib.perf:", "samplelib.dangerous:")      # perf functions are unbounded by design; eval/shell are not fuzzed


def data(r: dict) -> dict:
    return r.get("data") or {}


async def resource(h, uri: str):
    res = await h.c.read_resource(uri)
    return res[0].text


async def lib_loop(h, charter: dict) -> dict:
    """Returns the run id and the list of bugs the host recorded."""
    rid = await h.start(charter)
    call = lambda name, **kw: h.call(name, run_id=rid, **kw)   # noqa: E731
    await call("scan_python_code")
    for t in ("run_radon", "run_ruff", "run_mypy", "run_bandit", "run_duplication", "run_vulture"):
        r = await call(t)
        assert r["status"] == "ok", (t, r)
    # existing tests + baseline coverage
    await call("run_pytest")
    await call("run_coverage")

    recorded = []

    async def record(node_id: str, oracle: str, severity: str, title: str, repro: dict | None = None) -> dict:
        kw = {"expl_node_id": node_id, "oracle": oracle, "severity": severity, "title": title}
        if repro:
            kw["repro"] = repro
        r = await call("record_bug", **kw)
        assert r["status"] == "ok", r
        recorded.append((title, r))
        return r

    # fuzz what get_untested ranks highest first, then the functions that existing tests touch (covered != correct)
    untested = data(await call("get_untested", limit=40))["targets"]
    seen = {t["key"] for t in untested}
    nodes = json.loads(await resource(h, f"run://{rid}/assets"))["nodes"]
    covered = [{"asset_id": n["id"], "key": n["key"], "type": n["type"]} for n in nodes
               if n["type"] == "function" and n["key"] not in seen and not n.get("is_dead")]
    for t in untested + covered:
        if t["type"] != "function" or t["key"].startswith(SKIP_FUZZ_MODULES):
            continue
        idea = await call("add_test_idea", title=f"hypothesis on {t['key']}", target_asset_id=t["asset_id"], input_shape={"fuzz": "types"})
        r = await call("run_hypothesis", target_asset_id=t["asset_id"], expl_node_id=data(idea).get("expl_node_id"))
        if r["status"] != "ok" or "FAILED" not in r["summary"]:
            continue
        nid = data(r)["expl_node_id"]
        c = await call("check_crash", expl_node_id=nid)
        if data(c).get("candidate"):
            await record(nid, "crash", "medium", f"{t['key']} raises {data(r)['exception']} for {data(r)['example']}")

    # user rule
    r = await call("check_rule", rule_name="balance_non_negative")
    if "VIOLATED" in r["summary"]:
        rb = await record(data(r)["expl_node_id"], "rule", "high", "withdraw() can drive the balance negative")
        if data(rb).get("needs_confirmation"):                    # high severity: a human confirms
            await call("answer_escalation", escalation_id=data(rb)["escalation_id"], answer="confirmed, real bug", approve=True)

    # regression between the last two commits
    d = await call("compare_with_git_version", test_ref={"target": "samplelib.rates:apply_discount",
                                                         "inputs": [{"price": 10.0, "pct": 50}, {"price": 19.99, "pct": 10}]})
    if "REGRESSION" in d["summary"]:
        await record(data(d)["expl_node_id"], "diff_git", "medium", "apply_discount() changed behaviour in the last commit (cents truncated)")

    # a generated test, a flaky test, duplicates
    mean = next(n for n in nodes if n["key"] == "samplelib.stats:mean")
    wt = await call("write_test", target_asset_id=mean["id"],
                    code="from samplelib.stats import mean\n\ndef test_mean_empty_list():\n    assert mean([]) == 0\n")
    await call("run_pytest", selector=data(wt)["selector"], expl_node_id=data(wt)["expl_node_id"])
    await call("check_flaky", test_ids=["tests/test_basic.py::test_flaky_planted", "tests/test_basic.py::test_mean_basic"], n=10)
    await call("run_coverage")
    await call("dedup_tests")
    mu = await call("run_mutation", paths=["samplelib/stats.py"])
    assert mu["status"] == "ok", mu

    # dead code needs a human-style confirmation
    fs = json.loads(await resource(h, f"run://{rid}/findings"))
    for f in fs:
        if f["oracle"] == "vulture" and "legacy_format" in f["title"]:
            await call("confirm_finding", finding_id=f["id"], confirmed=True)

    # performance pass
    p = await call("profile_cpu", target={"call": "samplelib.perf:run_pipeline"})
    assert p["status"] == "ok", p
    find_dup = next(n for n in nodes if n["key"] == "samplelib.perf:find_duplicates")
    await call("measure_time_complexity", target_asset_id=find_dup["id"], sizes=[200, 400, 800, 1600, 3200, 6400])
    await call("run_benchmark")
    await call("compare_benchmark_with_git_version")
    await call("profile_memory", target={"call": "samplelib.perf:build_table"})

    # drain the escalations (static high-severity findings etc.): a human approves them
    for e in data(await call("get_escalations"))["escalations"]:
        await call("answer_escalation", escalation_id=e["id"], answer="reviewed", approve=True)
    report = await call("get_report")
    full = await resource(h, f"run://{rid}/report")
    status = await call("get_status")
    await call("end_run")
    return {"run_id": rid, "recorded": recorded, "report_md": full, "report_head": data(report)["markdown"], "status": status}


async def api_loop(h, charter: dict) -> dict:
    rid = await h.start(charter)
    call = lambda name, **kw: h.call(name, run_id=rid, **kw)   # noqa: E731
    await call("import_openapi")
    recorded = []
    # explore by hand: the failing and the healthy path
    r = await call("http_request", method="GET", path="/items/-1")
    nid = data(r)["expl_node_id"]
    if data(await call("check_crash", expl_node_id=nid)).get("candidate"):
        rb = await call("record_bug", expl_node_id=nid, oracle="http_5xx", severity="medium", title="GET /items/{item_id} returns 500 for a negative id")
        recorded.append(rb)
    o = await call("http_request", method="GET", path="/orders/7")
    if data(await call("check_schema", expl_node_id=data(o)["expl_node_id"])).get("candidate"):
        rb = await call("record_bug", expl_node_id=data(o)["expl_node_id"], oracle="schema", severity="medium",
                        title="GET /orders/{order_id} response misses the required field 'total'")
        recorded.append(rb)
    # destructive call: must escalate, then a human answers (denied: we never want the data deleted)
    dl = await call("http_request", method="DELETE", path="/items/1")
    assert dl["status"] == "escalation_required", dl
    await call("answer_escalation", escalation_id=dl["escalation_id"], answer="no, keep the data", approve=False)
    # contract fuzzing finds both again, and reports the DELETE it skipped
    st = await call("run_schemathesis", max_examples=150, seed=7)
    assert st["status"] == "ok", st
    await call("profile_api", endpoint="/items/1", n_requests=100)
    for e in data(await call("get_escalations"))["escalations"]:
        await call("answer_escalation", escalation_id=e["id"], answer="reviewed", approve=False)
    report = await call("get_report")
    full = await resource(h, f"run://{rid}/report")
    await call("end_run")
    return {"run_id": rid, "recorded": recorded, "delete_escalation": dl, "schemathesis": st, "report_md": full, "report_head": data(report)["markdown"]}
