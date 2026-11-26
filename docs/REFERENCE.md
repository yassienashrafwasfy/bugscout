# BugScout reference

The short, translated READMEs are in the repository root and `docs/i18n/`. This page is the full reference.

An MCP server that lets Claude Code or Codex act as a **testing agent** for Python code and REST APIs.

The host (the LLM) does the planning. The server holds the memory (an asset graph and an append-only exploration tree in
Postgres), runs anything that executes target code **inside Docker**, and enforces the rules **server-side**: scope, destructive
actions, budget, stuck detection and confirmation of serious bugs. Nothing is a bug until it reproduces.

```
host (Claude Code / Codex) ──MCP──▶ bugscout (FastMCP)
                                      ├─ Postgres: runs, asset graph, exploration tree, findings, events, artifacts
                                      ├─ guards:   scope · destructive · budget · stuck · serious-bug
                                      └─ Docker:   bench container (tools + tests) · sut container (the API) · ref container (previous commit)
```

## Quick start

```bash
docker compose up -d postgres                        # Postgres 16, user/password: test/test
docker build -t bugscout-sandbox:latest sandbox   # one-off; the server also rebuilds a stale image on start_run
uv sync
uv run bugscout                                   # stdio; migrations run on start
```

`BUGSCOUT_TRANSPORT=http uv run bugscout` serves streamable HTTP on `127.0.0.1:8765` instead.

### Connect a host

Claude Code, `.mcp.json` (the one in this repo works when Claude Code is opened in the repo root):

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

From any other directory add `"--directory", "/ABSOLUTE/PATH/TO/bugscout"` before `"bugscout"` in `args`.

Codex, `~/.codex/config.toml` (also in `docs/codex-config.toml`):

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/ABSOLUTE/PATH/TO/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

Then ask the host to use the `testing_loop` prompt (and `write_charter` to build the charter with you).

## The charter

`start_run(charter)` takes one JSON document; the server validates it. Minimal Python example:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*", "mypkg.*"], "exclude": ["mypkg/migrations/*"]},
  "objective": "find bugs in mypkg",
  "oracles": ["crash", "diff_git", "rule"],
  "rules": [{"name": "balance_non_negative", "target": "mypkg.accounts:withdraw",
             "property": "result['balance'] >= 0", "assume": "balance >= 0 and 0 < amount < 1e9"}],
  "reference": {"git_ref": "HEAD~1"},
  "perf": {"max_big_o": {"default": "O(n log n)"}, "max_memory_mb": 512, "regression_threshold": 0.2},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

REST API targets use `{"kind": "rest_api", "repo_path": ..., "openapi": "openapi.json", "base_url": "http://sut:8000",
"start_cmd": "uvicorn app:app --host 0.0.0.0"}` and `scope.allowed_hosts: ["sut"]`. The API runs in its own container on an
internal network; the tester reaches it as `sut`. Nothing else has network access.

## Tools (42) by stage

| Stage | Tools |
|---|---|
| Run | `start_run` `get_status` `end_run` `get_report` |
| Map | `scan_python_code` `import_openapi` |
| Static | `run_radon` `run_ruff` `run_mypy` `run_bandit` `run_duplication` `run_vulture` `confirm_finding` |
| Tree | `add_test_idea` (deduped) `update_result` `get_frontier` `get_untested` `query_graph` |
| Run tests | `write_test` `run_pytest` `run_hypothesis` `run_schemathesis` `http_request` |
| Oracles | `check_crash` `check_schema` `check_rule` `compare_with_git_version` |
| Quality | `run_coverage` `run_mutation` `check_flaky` `dedup_tests` |
| Bugs | `fingerprint_bug` `record_bug` |
| Performance | `measure_time_complexity` `run_benchmark` `compare_benchmark_with_git_version` `profile_cpu` `profile_memory` `profile_api` |
| Humans | `ask_human` `get_escalations` `answer_escalation` |

Resources (read-only): `run://{id}/charter|assets|tree|frontier|findings|escalations|report`.
Prompts: `testing_loop`, `write_charter`, `triage_bug`.

Every tool answers `{status, summary, data, next_suggestions}`; big payloads are stored as artifacts and replaced by a stub, so
outputs stay small. Everything is parsed from JSON reports, never scraped from text.

## Subagents (Claude Code)

`.claude/agents/bugscout-*.md` defines seven specialised subagents: `mapper`, `static-auditor`, `fuzzer`, `diff-hunter`, `perf-analyst`,
`quality-auditor`, `triager`. Each lists only its own `mcp__bugscout__*` tools in its frontmatter. The rules, enforced by
`tests/test_subagents.py`:

* every tool name in an agent file exists on the server, and every tool except `start_run`, `end_run`, `answer_escalation`, `ask_human` is owned by some agent;
* only `bugscout-triager` has `record_bug`; no agent can start or end a run or answer an escalation (the host and the human keep those);
* the README tool and subagent tables are generated from `scripts/agents_data.py` (`python scripts/build_readmes.py`), and the test checks all 16 READMEs list every tool and agent.

The `testing_loop` prompt tells the host to delegate when the agents exist and to run at most two executing agents at a time.
Codex does not read `.claude/agents/`, so for Codex the main session does all phases itself.

## How the guards behave

* **Scope**: a target outside `scope.include/exclude` (or a host outside `allowed_hosts`) returns `escalation_required`.
* **Destructive**: `DELETE/PUT/PATCH`, and `POST` to paths like delete/remove/pay/charge/send/email/drop/reset, escalate before
  anything is sent. Approving covers the same method + path template afterwards. `run_schemathesis` skips them and says so.
* **Budget**: steps, requests, and minutes (sum of tool durations, so a human answering does not burn it). Warn at 90 %, hard stop at 100 %.
* **Stuck**: no new done nodes/findings/coverage over `stuck.window_steps` steps raises one escalation.
* **Serious bugs**: `high`/`critical` findings need a human (`answer_escalation`) before they count as confirmed.
* An escalation pauses **only its branch**; the host moves on and checks `get_escalations` later.

## Sandbox

One image (`sandbox/Dockerfile`) with pytest + plugins, hypothesis, schemathesis, coverage, mutmut, ruff, mypy, bandit, radon,
vulture, pylint, big_O, pytest-benchmark, pyinstrument, memray, py-spy, jscpd. Containers run as uid 1000 with all capabilities
dropped, `no-new-privileges`, 2 CPUs / 1.5 GB (`BUGSCOUT_CPUS`, `BUGSCOUT_MEMORY`), a pids limit, **no network** except the per-run
internal network of an API target, and an in-container `timeout` on every command. The exception is py-spy, which runs as root in
the `sut` container only (it needs `CAP_SYS_PTRACE`). The target repo is copied in; your working tree is never mounted writable.

## Layout

```
src/bugscout/   server.py runtime.py (tool decorator, guards, event log) priority.py resources.py prompts.py
  guards/ store/ runners/ (sandbox, git worktrees, parsers) tools/
sandbox/           Dockerfile + shims/ (the in-container entry points; each writes one JSON file)
migrations/        plain SQL, tracked in schema_migration
examples/          sample_lib + sample_api with planted bugs (build_fixture.py makes a 2-commit git repo from each)
tests/             one file per phase + e2e (test_phase8_e2e.py, e2e_host.py = a scripted host)
```

## Tests

```bash
docker compose up -d postgres
uv run pytest -m "not docker"          # Postgres only
uv run pytest -m docker                # needs Docker + the image; the perf tests are timing-based, run them on an idle machine
```

Tests use a throwaway `bugscout_test` database (its public schema is dropped per session). CI is in `.github/workflows/ci.yml`
(Postgres service container; Docker tests in a second job).

## Planted bugs in `examples/`

`sample_lib`: `stats.mean([])` crashes; `accounts.withdraw` can go negative (rule); `rates.region_tax` has complexity rank D;
`billing.invoice_share` and its copy `invoices.invoice_share_copy` share a divide-by-zero; `legacy.legacy_format` is unused; a mypy error
in `typed.py`; `eval`/`shell=True` in `dangerous.py`; a flaky test; two identical tests; `rates.apply_discount` regressed in the
last commit; `perf.find_duplicates` is O(n²); `perf.checksum` is 3x slower in the last commit; `perf.run_pipeline` spends its time in
`_crunch`; `perf.build_table` allocates ~600 MB.
`sample_api` (FastAPI): `GET /items/{id}` returns 500 for negative ids; `GET /orders/{id}` omits the required `total`;
`DELETE /items/{id}` must escalate.

## What was and was not verified

Verified by automated tests (all passing, `uv run pytest tests`, run on one machine against Postgres 16 and real Docker containers):

| Phase | What the tests prove |
|---|---|
| 1 | server starts over stdio; runs are created and read back; append-only tree and event-log triggers; migrations |
| 2 | pytest runs inside a locked-down container on `sample_lib` and returns JSON; no network; limits and timeouts |
| 3 | function nodes with complexity; ruff/mypy/bandit findings; a duplicate group; a dead-code candidate; OpenAPI import |
| 4 | duplicate idea returns the existing node; DELETE escalates; out-of-scope escalates; the stuck detector fires with no progress; budget stops |
| 5 | Hypothesis finds `mean([])`; the rule violation in `withdraw`; the 500 and the schema mismatch in `sample_api` (by hand and with schemathesis); the `apply_discount` regression between two commits |
| 6 | flaky test is marked flaky, not a bug; 20 fuzz failures collapse to 1 finding (`occurrences=20`); identical tests are marked duplicates; coverage per function and per test; mutation score; a failure that does not reproduce is never recorded; a `pytest_diff` bug is replayed before it is recorded |
| 7 | O(n²) detected vs an allowed O(n log n) and stable across 3 runs; the 3x `checksum` slowdown is a `perf_regression` (and identical code is not); `_crunch` tops the CPU profile; `build_table` exceeds 512 MB; `profile_api` with py-spy |
| 8 | the server surface over stdio (all tools, resources, prompts); the end-to-end run below |

**The end-to-end test is scripted, not a live agent.** `tests/test_phase8_e2e.py` starts the real server as a stdio process, with
real Docker sandboxes, and drives it with `tests/e2e_host.py`, a fixed script that follows the `testing_loop` prompt against
both examples. Every planted bug has to appear in the report that the server produces. The script makes the judgement calls an LLM
would make (what to fuzz, which severity, what to record), so some of what it records is not a real bug. For example, the
`sample_lib` report lists `deposit` / `withdraw` raising `ValueError` at `amount=0.0`, which is probably intended input validation.
The server reports what the host records.

**A live Claude Code session has been run once against `sample_api`** (see [`LIVE_RUN.md`](LIVE_RUN.md)): it found both planted bugs and
exposed a scope-guard bug that is now fixed. It has not been run against `sample_lib`, and Codex has not been driven at all, so the Codex
config and the other prompts are untested with a real model.

## Design notes and known deviations from the plan

* `max_minutes` counts the sum of tool-call durations, not wall-clock time since the run was created.
* `check_flaky` runs N **separate** pytest processes with different `--randomly-seed` values: pytest-randomly reseeds `random` per
  process, so `pytest-repeat` with `--count` would repeat the same outcome.
* mutmut 3 exposes no per-test kill sets, so `dedup_tests` uses identical coverage contexts (pytest-cov `--cov-context=test`).
  Two tests that cover exactly the same lines are duplicates; a benchmark and a unit test of the same function can therefore be
  flagged. It reports, the host decides.
* Time complexity picks the class by a scale-free log-space fit on the measurements above the timer floor, and reports `big_O`'s own
  residual alongside. A fit that is poor, or whose plausible classes straddle the allowed bound, is `uncertain` and never a finding.
* Memory profiling needs the target to fit the container limit (`BUGSCOUT_MEMORY`); a function that exceeds it is killed and reported as an error, not a measurement.
