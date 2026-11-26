<div align="center">

# 🐞 BugScout

**Let your AI hunt bugs — safely, in Docker, with receipts.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

**English** · [العربية](docs/i18n/README.ar.md) · [مصري](docs/i18n/README.ar-EG.md) · [خليجي](docs/i18n/README.ar-GULF.md) · [شامي](docs/i18n/README.ar-LEV.md) · [الدارجة](docs/i18n/README.ar-MAG.md) · [Español](docs/i18n/README.es.md) · [Français](docs/i18n/README.fr.md) · [Deutsch](docs/i18n/README.de.md) · [Português](docs/i18n/README.pt.md) · [中文](docs/i18n/README.zh.md) · [日本語](docs/i18n/README.ja.md) · [Русский](docs/i18n/README.ru.md) · [हिन्दी](docs/i18n/README.hi.md) · [Türkçe](docs/i18n/README.tr.md) · [한국어](docs/i18n/README.ko.md)

</div>

---

## Table of contents

[Why you need this](#why-you-need-this) · [What it does](#what-it-does) · [How it works](#how-it-works) · [Quick start](#quick-start) · [Usage](#usage) · [Guards](#guards) · [What was verified](#what-was-and-was-not-verified) · [Docs](#docs) · [Contributing](#contributing) · [License](#license)

## Why you need this

Letting an AI agent "go test my code" usually ends one of three ways: it runs untrusted code on your machine, it forgets what it
already tried and loops, or it reports a "bug" that was a flaky test. BugScout is the missing substrate:

| Problem with a bare agent | What BugScout does about it |
|---|---|
| It executes target code on your laptop | Everything that runs target code runs in a locked-down **Docker** sandbox (no network, dropped capabilities, CPU/memory limits) |
| It has no memory and repeats itself | An **asset graph** and an append-only **exploration tree** in Postgres; duplicate test ideas return the existing node |
| It hits `DELETE /users` "to see what happens" | **Server-side guards**: scope, destructive actions, budget, stuck detection, human confirmation for serious bugs |
| It reports flaky or one-off failures as bugs | A failure is **re-run before it counts**; one that does not reproduce becomes `flaky`, and the same bug found 20 times is one finding |

> [!NOTE]
> You (or rather the LLM host: Claude Code, Codex) do the planning. BugScout stores, executes, checks and enforces.

## What it does

* **Maps** a Python package or an OpenAPI spec into a graph of functions, classes, endpoints and their relations.
* **Static stage:** complexity (radon), lint (ruff), types (mypy), security (bandit), copy-paste (duplication), dead code (vulture).
* **Dynamic stage:** pytest, Hypothesis property tests, schemathesis, hand-made HTTP requests, user-written rules.
* **Oracles:** crash / HTTP 5xx, response schema, behaviour diff against the previous git commit, your own invariants.
* **Quality:** coverage per function and per test, mutation score, flaky-test detection, duplicate-test detection.
* **Performance:** empirical time complexity (O(n²) vs the allowed O(n log n)), benchmark regressions between commits, CPU hotspots, memory hogs, API profiling.
* **Reports** the deduplicated result: bugs, static issues, coverage, hotspots, regressions.

42 tools, 7 read-only resources (`run://{id}/…`) and 3 prompts (`testing_loop`, `write_charter`, `triage_bug`).

## How it works

```
 host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP server)
                                         ├─ Postgres  runs · asset graph · exploration tree · findings · events
                                         ├─ guards    scope · destructive · budget · stuck · serious-bug
                                         └─ Docker    bench (tools + tests) · sut (your API) · ref (previous commit)
```

1. The host sends a **charter**: target, scope, oracles, rules, budget.
2. It works the loop in the `testing_loop` prompt: map → static stage → run tests → check oracles → record bugs → performance pass → report.
3. Every executing call passes the guards first. An **escalation** pauses only its own branch; the host moves on.
4. `record_bug` re-runs the repro, fingerprints it and deduplicates. High and critical bugs wait for a human.

## Quick start

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres            # Postgres 16 (user/password: test/test)
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout                          # stdio; migrations run on start
```

## Usage

**Claude Code** — `.mcp.json` in the repo root (already included):

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** — `~/.codex/config.toml`:

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

Then tell your agent: *"Use the `testing_loop` prompt from bugscout and test `./my_project`."* (Use `write_charter` to build the charter together.)

A minimal charter:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

Try it on the planted-bug examples in [`examples/`](examples) (`sample_lib`, `sample_api`).

## Guards

| Guard | Behaviour |
|---|---|
| Scope | A target outside `scope.include/exclude`, or a host outside `allowed_hosts`, returns `escalation_required` |
| Destructive | `DELETE/PUT/PATCH` and risky `POST`s escalate before anything is sent; schemathesis skips them and says so |
| Budget | Steps, requests, minutes; warning at 90 %, hard stop at 100 % |
| Stuck | No new findings / progress over a window of steps raises one escalation |
| Serious bug | `high` / `critical` need `answer_escalation` before they count as confirmed |

## What was and was not verified

> [!WARNING]
> See [`docs/REFERENCE.md`](docs/REFERENCE.md#what-was-and-was-not-verified) for the per-phase table.

* Automated: 39 tests against real Postgres and real Docker containers, including a **scripted-host e2e** over a stdio server that finds every planted bug in both examples.
* **Live:** one real Claude Code session (`claude -p` following `testing_loop`) found both planted bugs in `sample_api` for about $0.22; see [`docs/LIVE_RUN.md`](docs/LIVE_RUN.md). Not yet run live: `sample_lib`, Codex.

## Docs

[`docs/REFERENCE.md`](docs/REFERENCE.md): all tools, charter fields, sandbox details, design notes · [`examples/`](examples): planted bugs · [`.github/workflows/ci.yml`](.github/workflows/ci.yml): CI.

## Contributing

Issues and PRs are welcome. Run `uv run pytest -m "not docker"` for the quick suite and `uv run pytest -m docker` (one file at a time, on an idle machine) for the sandbox, oracle and performance tests.

## License

[Apache License 2.0](LICENSE).

## Star history

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
