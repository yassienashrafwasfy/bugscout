"""Shared helpers: call tools through the real FastMCP in-memory client."""
from __future__ import annotations

from fastmcp import Client

from bugscout.server import mcp


class Host:
    """Tiny host: wraps Client so tests read like a tool-call transcript."""
    def __init__(self, transport=None):
        self.c = Client(transport if transport is not None else mcp)

    async def __aenter__(self):
        await self.c.__aenter__()
        return self

    async def __aexit__(self, *a):
        await self.c.__aexit__(*a)

    async def call(self, name: str, **args):
        r = await self.c.call_tool(name, args, raise_on_error=False)
        return r.data if r.data is not None else r.structured_content

    async def start(self, charter: dict) -> str:
        r = await self.call("start_run", charter=charter)
        assert r["status"] == "ok", r
        return r["data"]["run_id"]
