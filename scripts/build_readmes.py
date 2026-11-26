"""Generate docs/i18n/README.<lang>.md from i18n_strings.py. English lives in README.md (hand-written)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from i18n_strings import LANGS, RTL, S, CHARTER

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "i18n"
GH = "yassienashrafwasfy/bugscout"
BADGES = f"""[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/{GH}/actions/workflows/ci.yml/badge.svg)](https://github.com/{GH}/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/{GH}?style=social)](https://github.com/{GH}/stargazers)"""
JSON_CLAUDE = '''{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }'''
TOML = '''[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }'''
QUICK = '''git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout'''
DIAGRAM = '''host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref'''


def langbar(cur):
    parts = []
    for code, label, f in LANGS:
        if code == cur:
            parts.append(f"**{label}**")
        elif code == "en":
            parts.append(f"[{label}](../../README.md)")
        else:
            parts.append(f"[{label}]({f})")
    return " · ".join(parts)


def build(code):
    d = S[code]; t = d["t"]
    rtl = code in RTL
    live = d["live_ok"].split("؛")[0].split("; التفاصيل")[0]
    live += " ([docs/LIVE_RUN.md](../LIVE_RUN.md))"
    auto = d["status_auto"].replace("38", "39")
    why_rows = "\n".join(f"| {a} | {b} |" for a, b in d["why"])
    guards_rows = "\n".join(f"| {a} | {b} |" for a, b in d["guards"])
    what = "\n".join(f"* {x}" for x in d["what"])
    steps = "\n".join(f"{i}. {x}" for i, x in enumerate(d["how_steps"], 1))
    head = f'<div align="center">\n\n# 🐞 BugScout\n\n**{d["tagline"]}**\n\n{BADGES}\n\n{langbar(code)}\n\n</div>\n'
    body = f"""
---

## {t['why']}

{d['why_intro']}

| {d['why_h'][0]} | {d['why_h'][1]} |
|---|---|
{why_rows}

> [!NOTE]
> {d['note']}

## {t['what']}

{what}

{d['what_tools']}

## {t['how']}

```
{DIAGRAM}
```

{steps}

## {t['quick']}

```bash
{QUICK}
```

## {t['usage']}

{d['usage_claude']}

```json
{JSON_CLAUDE}
```

{d['usage_codex']}

```toml
{TOML}
```

{d['usage_prompt']}

{d['usage_charter']}

```json
{CHARTER}
```

{d['usage_try']}

## {t['guards']}

| {d['guards_h'][0]} | {d['guards_h'][1]} |
|---|---|
{guards_rows}

## {t['status']}

> [!WARNING]
> {d['status_warn']}

* {auto}
* {live}

## {t['docs']}

{d['docs_text']}

## {t['contrib']}

{d['contrib_text']}

## {t['license']}

{d['license_text']}

## {t['star']}

<a href="https://star-history.com/#{GH}&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos={GH}&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos={GH}&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos={GH}&type=Date" />
  </picture>
</a>
"""
    if rtl:
        # GitHub renders dir="rtl" on block HTML; markdown must sit in a div with blank lines around it
        body = '\n<div dir="rtl" align="right">\n' + body.replace("\n---\n", "\n", 1) + "\n</div>\n"
    return head + body


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for code, _, fname in LANGS:
        if code == "en":
            continue
        (OUT / fname).write_text(build(code), encoding="utf-8")
        print("wrote", fname)


if __name__ == "__main__":
    main()
