import sys

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from bugscout.server import mcp

pytestmark = pytest.mark.integration

CH = {"target": {"kind": "python", "repo_path": "/tmp/x", "package": "p"}, "objective": "o"}


async def test_start_status_end_in_memory():
    async with Client(mcp) as c:
        r = (await c.call_tool("start_run", {"charter": CH})).data
        assert r["status"] == "ok"
        rid = r["data"]["run_id"]
        s = (await c.call_tool("get_status", {"run_id": rid})).data
        assert s["data"]["run_status"] == "active" and s["data"]["tree"] == {"in_progress": 1}
        e = (await c.call_tool("end_run", {"run_id": rid})).data
        assert e["status"] == "ok"
        s = (await c.call_tool("get_status", {"run_id": rid})).data
        assert s["data"]["run_status"] == "done"


async def test_invalid_charter_rejected():
    async with Client(mcp) as c:
        r = (await c.call_tool("start_run", {"charter": {"target": {"kind": "python", "repo_path": "/x"}}})).data
        assert r["status"] == "error" and "invalid charter" in r["summary"]


async def test_event_log_written():
    from bugscout.store import runs
    async with Client(mcp) as c:
        rid = (await c.call_tool("start_run", {"charter": CH})).data["data"]["run_id"]
        await c.call_tool("get_status", {"run_id": rid})
    assert {e["tool"] for e in runs.recent_events(rid, 10)} >= {"start_run", "get_status"}


async def test_server_starts_over_stdio():
    """Spawn the real server process and talk MCP over stdio."""
    from bugscout import config
    t = StdioTransport(command=sys.executable, args=["-m", "bugscout.server"],
                       env={"DATABASE_URL": config.DATABASE_URL, "BUGSCOUT_PROVISION": "0"})
    async with Client(t) as c:
        names = {x.name for x in await c.list_tools()}
        assert {"start_run", "get_status", "end_run"} <= names
        rid = (await c.call_tool("start_run", {"charter": CH})).data["data"]["run_id"]
        assert (await c.call_tool("get_status", {"run_id": rid})).data["status"] == "ok"


def test_stuck_non_step_tools_match_registry():
    """Tools registered with count_step=False must be exactly the ones the stuck detector ignores."""
    from bugscout.guards import stuck
    from bugscout.server import runtime
    uncounted = {n for n, fn in runtime.REGISTRY.items() if getattr(fn, "__bugscout_count_step__", True) is False}
    assert uncounted == stuck.NON_STEP_TOOLS, uncounted ^ stuck.NON_STEP_TOOLS
