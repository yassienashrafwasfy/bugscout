import pytest

from conftest import lib_charter
from helpers import Host
from bugscout.guards import check_action
from bugscout.models import ok
from bugscout.runtime import tool
from bugscout.store import assets, findings, runs, tree

pytestmark = pytest.mark.integration


@tool("dummy_exec", executing=True, action=lambda kw: {"key": kw.get("key")})
def dummy_exec(run_id: str, key: str | None = None) -> dict:   # an executing tool that makes no progress
    return ok("ran")


API_CH = {"target": {"kind": "rest_api", "repo_path": "/tmp", "openapi": "o.json", "start_cmd": "uvicorn app:app --host 0.0.0.0"},
          "scope": {"include": ["/items/*", "/health"], "exclude": ["/items/secret/*"], "allowed_hosts": ["sut"]}}


async def test_duplicate_idea_returns_existing_node(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        await h.call("scan_python_code", run_id=rid)
        a = assets.get_by_key(rid, "samplelib.stats:mean")
        r1 = await h.call("add_test_idea", run_id=rid, title="empty list", target_asset_id=str(a["id"]), input_shape={"values": []})
        r2 = await h.call("add_test_idea", run_id=rid, title="same thing, other words", target_asset_id=str(a["id"]),
                          input_shape={"values": []})
        assert r1["data"]["created"] is True and r2["data"]["created"] is False
        assert r1["data"]["node"]["id"] == r2["data"]["node"]["id"]
        r3 = await h.call("add_test_idea", run_id=rid, title="x", target_asset_id=str(a["id"]), input_shape={"values": [1]})
        assert r3["data"]["created"] is True
        assert len(tree.frontier(rid)) == 2


async def test_delete_request_escalates_and_approval_unblocks(fx_api):
    ch = dict(API_CH, target={**API_CH["target"], "repo_path": fx_api, "openapi": "openapi.json"})
    ch["scope"] = {**ch["scope"], "include": ["/items/*", "/orders/*", "/health"]}
    async with Host() as h:
        rid = await h.start(ch)
        await h.call("import_openapi", run_id=rid)
        d = check_action(rid, "http_request", {"method": "DELETE", "path": "/items/5", "host": "sut"})
        assert d["status"] == "escalation_required" and d["reason"] == "destructive"
        assert check_action(rid, "http_request", {"method": "GET", "path": "/items/5", "host": "sut"}) is None
        # approving the template covers the same action with a different concrete id
        esc = await h.call("get_escalations", run_id=rid)
        assert esc["data"]["escalations"][0]["reason"] == "destructive"
        await h.call("answer_escalation", run_id=rid, escalation_id=d["escalation_id"], answer="ok, test env", approve=True)
        assert check_action(rid, "http_request", {"method": "DELETE", "path": "/items/77", "host": "sut"}) is None


async def test_out_of_scope_escalates_and_branch_only(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, scope={"include": ["samplelib/*"], "exclude": ["samplelib/vendor/*"]}))
        node = tree.add_node(rid, "idea", "poke vendor")
        r = check_action(rid, "run_hypothesis", {"key": "samplelib.vendor.x:f", "expl_node_id": str(node["id"])})
        assert r["status"] == "escalation_required" and r["reason"] == "out_of_scope"
        assert tree.get_node(node["id"])["status"] == "escalated"                 # only the branch
        assert runs.get_run(rid)["status"] == "active"                            # run keeps going
        assert check_action(rid, "run_hypothesis", {"key": "samplelib.stats:mean"}) is None
        # host not on the allow-list
        r = check_action(rid, "http_request", {"method": "GET", "path": "/x", "host": "evil.example.com"})
        assert r["reason"] == "out_of_scope"


async def test_host_cannot_bypass_guard_through_the_tool_layer(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, scope={"include": ["samplelib/*"], "exclude": []}))
        ran = []
        from bugscout import runtime
        r = runtime.REGISTRY["dummy_exec"](run_id=rid, key="other_pkg:f")
        assert r["status"] == "escalation_required" and not ran


async def test_stuck_detector_fires_without_progress(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, stuck={"window_steps": 4, "min_progress": 1}))
        outs = [dummy_exec(run_id=rid) for _ in range(6)]
        assert [o["status"] for o in outs[:4]] == ["ok"] * 4
        stuck = [o for o in outs if o["status"] == "escalation_required"]
        assert stuck and stuck[0]["reason"] == "stuck" and "Tried" in stuck[0]["question"]


async def test_stuck_detector_quiet_when_progressing(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, stuck={"window_steps": 4, "min_progress": 1}))
        for i in range(8):
            tree.add_node(rid, "test", f"t{i}", status="done")           # progress each step
            assert dummy_exec(run_id=rid)["status"] == "ok"


async def test_budget_90_percent_escalates_and_100_hard_stops(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, budget={"max_steps": 10, "max_requests": 100, "max_minutes": 60},
                                        stuck={"window_steps": 99, "min_progress": 1}))
        res = [dummy_exec(run_id=rid)["status"] for _ in range(10)]
        assert res[:9] == ["ok"] * 9 and res[9] == "escalation_required"     # 9/10 used = 90%
        esc = runs.list_escalations(rid)[0]
        assert esc["reason"] == "budget"
        await h.call("answer_escalation", run_id=rid, escalation_id=str(esc["id"]), answer="continue", approve=True)
        assert dummy_exec(run_id=rid)["status"] == "ok"                       # the 10th step runs after approval
        assert dummy_exec(run_id=rid)["status"] == "budget_exhausted"         # hard stop at 100%


async def test_serious_bug_needs_human_confirmation(fx_lib):
    from bugscout.guards import escalation
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        node = tree.add_node(rid, "test", "t", status="in_progress")
        f = findings.add_finding(rid, "bug", "crash", "high", "boom", expl_node_id=str(node["id"]))
        out = escalation.on_serious_finding(rid, f, str(node["id"]))
        assert out["reason"] == "serious_bug"
        assert findings.get(f["id"])["status"] == "needs_confirmation"
        await h.call("answer_escalation", run_id=rid, escalation_id=out["escalation_id"], answer="yes real", approve=True)
        assert findings.get(f["id"])["status"] == "confirmed"
        assert tree.get_node(node["id"])["status"] == "confirmed_bug"


async def test_query_graph_and_untested_ranking(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        await h.call("scan_python_code", run_id=rid)
        assets.set_props_by_key(rid, "samplelib.rates:region_tax", {"complexity": 26, "coverage_branch": 0.1})
        assets.set_props_by_key(rid, "samplelib.legacy:legacy_format", {"is_dead": True, "complexity": 30})
        top = (await h.call("get_untested", run_id=rid, limit=3))["data"]["targets"]
        assert top[0]["key"] == "samplelib.rates:region_tax"
        assert "samplelib.legacy:legacy_format" not in [t["key"] for t in (await h.call("get_untested", run_id=rid, limit=50))["data"]["targets"]]
        q = await h.call("query_graph", run_id=rid, sql_name="callers", params={"key": "samplelib.perf:_crunch"})
        assert [r["key"] for r in q["data"]["rows"]] == ["samplelib.perf:run_pipeline"]
        bad = await h.call("query_graph", run_id=rid, sql_name="DROP TABLE run")
        assert bad["status"] == "error"


def test_scope_matches_endpoint_asset_keys_as_endpoints():
    """Live run found: add_test_idea on 'GET /items/{item_id}' was 'out of scope' for include ['/items/*']."""
    from bugscout.guards import scope as sc
    s = {"include": ["/items/*"], "exclude": []}
    assert sc.check(s, key="GET /items/{item_id}")[0]
    assert not sc.check(s, key="GET /orders/{order_id}")[0]
    assert sc.check({"include": ["GET /items/*"], "exclude": []}, key="GET /items/{item_id}")[0]
    assert not sc.check({"include": ["/items/*"], "exclude": ["/items/{item_id}"]}, key="GET /items/{item_id}")[0]
