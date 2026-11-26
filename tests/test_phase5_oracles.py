"""Phase 5 acceptance: finds the planted bugs in sample_lib and sample_api; detects the planted regression."""
import pytest

from conftest import lib_charter
from helpers import Host
from bugscout.store import assets, tree

pytestmark = [pytest.mark.docker, pytest.mark.integration]

API_CH = lambda repo: {
    "target": {"kind": "rest_api", "repo_path": repo, "openapi": "openapi.json", "base_url": "http://sut:8000",
               "start_cmd": "uvicorn app:app --host 0.0.0.0"},
    "scope": {"include": ["/items/*", "/orders/*", "/health"], "exclude": [], "allowed_hosts": ["sut"]},
    "oracles": ["crash", "schema"], "budget": {"max_steps": 400, "max_requests": 5000, "max_minutes": 60}}


async def test_sample_lib_bugs_and_regression(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        try:
            await h.call("scan_python_code", run_id=rid)
            mean = assets.get_by_key(rid, "samplelib.stats:mean")

            # (1) edge-case crash found by Hypothesis, shrunk to the empty list
            r = await h.call("run_hypothesis", run_id=rid, target_asset_id=str(mean["id"]))
            assert r["status"] == "ok" and "ZeroDivisionError" in r["summary"], r
            assert r["data"]["example"] == {"values": "[]"}
            nid = r["data"]["expl_node_id"]
            c = await h.call("check_crash", run_id=rid, expl_node_id=nid)
            assert c["data"]["candidate"] and c["data"]["oracle"] == "crash" and c["data"]["exception"] == "ZeroDivisionError"
            assert c["data"]["frames"][-1]["func"] == "mean"

            # (2) rule violation: withdraw can make the balance negative
            r = await h.call("check_rule", run_id=rid, rule_name="balance_non_negative")
            assert "VIOLATED" in r["summary"] and r["data"]["oracle"] == "rule", r
            ex = tree.get_node(r["data"]["expl_node_id"])["result"]["repro"]["kwargs"]
            assert ex["amount"] > ex["balance"] >= 0

            # (3) planted regression between the two commits: apply_discount truncates cents in HEAD
            d = await h.call("compare_with_git_version", run_id=rid, test_ref={
                "target": "samplelib.rates:apply_discount", "inputs": [{"price": 10.0, "pct": 50}, {"price": 19.99, "pct": 10}]})
            assert "REGRESSION" in d["summary"] and len(d["data"]["diffs"]) == 1, d
            assert d["data"]["diffs"][0]["old"]["result"] == 17.99 and d["data"]["diffs"][0]["new"]["result"] == 17
            same = await h.call("compare_with_git_version", run_id=rid, test_ref={"target": "samplelib.stats:clamp",
                                                                                  "kwargs": {"x": 5, "lo": 0, "hi": 3}})
            assert "identical" in same["summary"]
            # a failing node's repro can be replayed on the old version
            fm = await h.call("compare_with_git_version", run_id=rid, test_ref={"from_node": nid})
            assert fm["status"] == "ok"

            # generated test + pytest
            wt = await h.call("write_test", run_id=rid, target_asset_id=str(mean["id"]), kind="unit",
                              code="from samplelib.stats import mean\n\ndef test_mean_empty():\n    assert mean([]) == 0\n")
            assert wt["status"] == "ok", wt
            p = await h.call("run_pytest", run_id=rid, selector=wt["data"]["selector"], expl_node_id=wt["data"]["expl_node_id"])
            assert p["data"]["summary"]["failed"] == 1 and p["data"]["failures"][0]["message"].startswith("ZeroDivisionError") or "ZeroDivision" in str(p)
            assert tree.get_node(wt["data"]["expl_node_id"])["result"]["verdict"] == "fail"
            base = await h.call("run_pytest", run_id=rid)
            assert base["data"]["summary"]["passed"] >= 9
            # a function with no hints and no strategy asks for one instead of guessing
            bad = await h.call("write_test", run_id=rid, target_asset_id=str(mean["id"]), code="def helper(): pass")
            assert bad["status"] == "error"
        finally:
            await h.call("end_run", run_id=rid)


async def test_sample_api_bugs_and_guards(fx_api):
    async with Host() as h:
        rid = await h.start(API_CH(fx_api))
        try:
            await h.call("import_openapi", run_id=rid)
            # (1) http_request: negative id -> 500
            r = await h.call("http_request", run_id=rid, method="GET", path="/items/-1")
            assert r["data"]["status_code"] == 500, r
            c = await h.call("check_crash", run_id=rid, expl_node_id=r["data"]["expl_node_id"])
            assert c["data"]["oracle"] == "http_5xx"
            ok_ = await h.call("http_request", run_id=rid, method="GET", path="/items/1")
            assert ok_["data"]["status_code"] == 200 and (await h.call("check_schema", run_id=rid, expl_node_id=ok_["data"]["expl_node_id"]))["data"]["validated"]

            # (2) schema mismatch: /orders response misses the required `total`
            o = await h.call("http_request", run_id=rid, method="GET", path="/orders/7")
            s = await h.call("check_schema", run_id=rid, expl_node_id=o["data"]["expl_node_id"])
            assert s["data"]["candidate"] and "total" in s["data"]["problems"][0]["message"]

            # (3) DELETE escalates, GET with a different id does not; host cannot reach another host or absolute URL
            dl = await h.call("http_request", run_id=rid, method="DELETE", path="/items/1")
            assert dl["status"] == "escalation_required" and dl["reason"] == "destructive"
            assert (await h.call("http_request", run_id=rid, method="GET", path="http://evil.example/x"))["status"] in ("error", "escalation_required")
            assert (await h.call("http_request", run_id=rid, method="GET", path="/admin/x"))["status"] == "escalation_required"   # out of scope
            still = await h.call("http_request", run_id=rid, method="GET", path="/items/1")
            assert still["data"]["status_code"] == 200                    # item 1 still exists: DELETE never ran

            # (4) schemathesis finds both, skips DELETE (and raises an escalation for it)
            st = await h.call("run_schemathesis", run_id=rid, max_examples=150, seed=7)
            assert st["status"] == "ok", st
            fails = {(f["endpoint"], f["check"]) for f in st["data"]["failures"]}
            assert ("GET /orders/{order_id}", "response_schema_conformance") in fails, fails
            assert ("GET /items/{item_id}", "not_a_server_error") in fails, fails
            assert "DELETE /items/{item_id}" in st["data"]["skipped_destructive"]
            still = await h.call("http_request", run_id=rid, method="GET", path="/items/1")
            assert still["data"]["status_code"] == 200
        finally:
            await h.call("end_run", run_id=rid)
