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

[Why you need this](#why-you-need-this) · [What it does](#what-it-does) · [Subagents](#specialized-subagents) · [Tools](#tools) · [How it works](#how-it-works) · [Quick start](#quick-start) · [Usage](#usage) · [Guards](#guards) · [What was verified](#what-was-and-was-not-verified) · [Docs](#docs) · [Contributing](#contributing) · [License](#license)

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
* **Security:** bandit, hard-coded secrets (code and git history), vulnerable dependencies, and active probes for injection, broken authorization and CORS/headers, within scope and budget.
* **Performance:** empirical time complexity (O(n²) vs the allowed O(n log n)), benchmark regressions between commits, CPU hotspots, memory hogs, API profiling.
* **Reports** the deduplicated result: bugs, static issues, coverage, hotspots, regressions.

47 tools, 7 read-only resources (`run://{id}/…`) and 3 prompts (`testing_loop`, `write_charter`, `triage_bug`).

<!-- AGENTS:START -->

## Specialized subagents

BugScout ships nine Claude Code subagents in [`.claude/agents/`](.claude/agents). Each owns one phase of the `testing_loop` and only the tools that phase needs. Your main session coordinates them and keeps `start_run`, `end_run` and every human escalation.

| Subagent | Role | Main tools |
|---|---|---|
| [`bugscout-mapper`](.claude/agents/bugscout-mapper.md) | Maps the target and ranks what to test | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](.claude/agents/bugscout-static-auditor.md) | Runs the static analysers and keeps the real findings | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis and HTTP probes; reproduces failures | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](.claude/agents/bugscout-diff-hunter.md) | Behaviour and speed changes against an older git ref | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](.claude/agents/bugscout-perf-analyst.md) | Time complexity, CPU, memory, API latency | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](.claude/agents/bugscout-quality-auditor.md) | Coverage, mutation score, flaky and duplicate tests | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-security-auditor`](.claude/agents/bugscout-security-auditor.md) | Defensive and passive: bandit, secrets in code and git history, vulnerable dependencies | `run_bandit`, `run_secrets_scan`, `run_pip_audit` |
| [`bugscout-red-team`](.claude/agents/bugscout-red-team.md) | Adversarial: injection, broken authorization and hardening probes against the running API | `probe_injection`, `probe_authz`, `probe_http_hardening`, `http_request` |
| [`bugscout-triager`](.claude/agents/bugscout-triager.md) | Judges candidates and is the only one that records bugs | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> Only the triager can call `record_bug`; no subagent can start or end a run or answer an escalation. Run at most two executing agents at a time and never mutation with performance. Subagents are a Claude Code feature (Codex ignores `.claude/agents/`).

## Tools

| Group | Tools |
|---|---|
| Run control & graph | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| Mapping | `scan_python_code`, `import_openapi` |
| Static analysis | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| Dynamic testing | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| Oracles & diffs | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| Test quality | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| Performance | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| Bug reports | `fingerprint_bug`, `record_bug`, `confirm_finding` |
| Security | `run_secrets_scan`, `run_pip_audit`, `probe_injection`, `probe_authz`, `probe_http_hardening` |

<!-- AGENTS:END -->

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
