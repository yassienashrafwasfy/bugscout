"""FastMCP app: registers tools, resources, prompts."""
from __future__ import annotations

import importlib

from fastmcp import FastMCP

from . import runtime

TOOL_MODULES = ["run_control", "map", "static", "run", "check", "quality", "perf", "graph", "report"]   # extended phase by phase


def build_server() -> FastMCP:
    mcp = FastMCP("bugscout", instructions=(
        "Autonomous testing substrate for Python code and REST APIs. You plan; this server stores the "
        "graphs, runs tools in Docker and enforces guards. Start with the `testing_loop` prompt."))
    for m in TOOL_MODULES:
        importlib.import_module(f"bugscout.tools.{m}")
    for name, fn in runtime.REGISTRY.items():
        mcp.tool(fn, name=name)
    from . import prompts, resources
    resources.register(mcp)
    prompts.register(mcp)
    return mcp


mcp = build_server()


def main() -> None:
    import os
    from .store import db
    db.migrate()
    transport = os.environ.get("BUGSCOUT_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="http", host=os.environ.get("BUGSCOUT_HOST", "127.0.0.1"), port=int(os.environ.get("BUGSCOUT_PORT", "8765")))


if __name__ == "__main__":
    main()
