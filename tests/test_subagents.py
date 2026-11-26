"""The shipped Claude Code subagents must stay consistent with the real tool registry (no docker)."""
import pathlib
import re

import asyncio

from fastmcp import Client

import bugscout.server as server

AGENTS = pathlib.Path(__file__).resolve().parent.parent / ".claude" / "agents"
HOST_ONLY = {"start_run", "end_run", "answer_escalation", "ask_human"}  # lifecycle and human-in-the-loop stay with the host


def _registry() -> set[str]:
    """The tools the server really exposes (the runtime registry can also hold test-only dummies)."""
    async def go():
        async with Client(server.mcp) as c:
            return {t.name for t in await c.list_tools()}
    return asyncio.run(go())


def _load():
    out = {}
    for f in sorted(AGENTS.glob("bugscout-*.md")):
        head = re.match(r"---\n(.*?)\n---\n", f.read_text(), re.S).group(1)
        meta = dict(line.split(": ", 1) for line in head.splitlines())
        out[meta["name"]] = [t.strip().removeprefix("mcp__bugscout__") for t in meta["tools"].split(",")]
    return out


def test_seven_agents_and_every_tool_exists():
    agents = _load()
    assert len(agents) == 7
    for name, tools in agents.items():
        assert name.startswith("bugscout-")
        unknown = set(tools) - _registry()
        assert not unknown, f"{name} lists unknown tools {unknown}"


def test_every_non_lifecycle_tool_is_owned_by_some_agent():
    owned = {t for tools in _load().values() for t in tools}
    assert _registry() - HOST_ONLY - owned == set()


def test_only_the_triager_records_bugs_and_nobody_answers_escalations():
    agents = _load()
    assert [n for n, t in agents.items() if "record_bug" in t] == ["bugscout-triager"]
    for name, tools in agents.items():
        assert not HOST_ONLY & set(tools), f"{name} may not use lifecycle/human tools"


def test_readmes_list_every_tool_and_every_subagent():
    import sys
    root = AGENTS.parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from agents_data import AGENTS as DOC_AGENTS, GROUPS
    assert {t for _, ts in GROUPS for t in ts} == _registry()           # the doc table is the registry
    assert [n for n, _ in DOC_AGENTS] == sorted(_load(), key=[n for n, _ in DOC_AGENTS].index)  # and the agent files
    readmes = [root / "README.md", *sorted((root / "docs" / "i18n").glob("README.*.md"))]
    assert len(readmes) == 16
    for f in readmes:
        text = f.read_text(encoding="utf-8")
        for tool in _registry():
            assert f"`{tool}`" in text, f"{f.name} misses tool {tool}"
        for name, _ in DOC_AGENTS:
            assert name in text, f"{f.name} misses agent {name}"
