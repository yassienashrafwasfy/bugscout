"""MCP prompts: testing_loop, write_charter, triage_bug."""
from __future__ import annotations

from fastmcp import FastMCP

TESTING_LOOP = """\
You are the test planner. This server stores the asset graph and the exploration tree, runs everything that executes target
code inside Docker, and enforces scope / destructive-action / budget / stuck / serious-bug guards. You decide WHAT to test; the
server decides whether you may. Keep going until the budget is spent or `get_untested` / `get_frontier` run dry.

1. `start_run(charter)`, then `scan_python_code` and/or `import_openapi`.
2. Static stage (cheap first): `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture`.
   Security, passive: `run_secrets_scan`; `run_pip_audit` (needs charter security.osv_lookup, it sends dependency names out).
3. `run_pytest` on the existing tests, then `run_coverage` for a baseline.
4. Loop until the budget or the stop condition:
   1. `get_untested` + `get_frontier` -> pick a target.
   2. `add_test_idea` (duplicates are returned, not re-created).
   3. Execute: `write_test` + `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request`.
   4. Oracles: `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version`.
   5. On a failure: `check_flaky` first. Only a stable failure goes on: `fingerprint_bug` -> `record_bug` (it reruns the repro
      itself; a repro that does not reproduce becomes `flaky`, not a bug).
   6. `update_result` on the node you worked on.
   7. Now and then: `run_coverage`, `run_mutation` on well-covered files (1-3 files, never together with perf tools), `dedup_tests`.
   8. Performance pass, once correctness is stable: `profile_cpu` -> `measure_time_complexity` on hotspots and on high-complexity
      functions -> `run_benchmark` + `compare_benchmark_with_git_version` -> `profile_memory` -> `profile_api` (API targets).
   9. Security, active (API targets, once functional testing is stable): `probe_injection`, `probe_authz` (set charter
      security.tokens and security.owned for the object-level check), `probe_http_hardening`. Each hit is a candidate node with
      evidence: judge it, then `record_bug` with oracle `security`. The probes only send a fixed corpus to in-scope GET endpoints.
   10. A tool that answers `escalation_required` has paused ONLY that branch: move to another one and look at `get_escalations`
      later. Never retry the same action to get around a guard. Ask the human with `ask_human` when you need a decision.
5. `get_report`, then `end_run`.

Rules: tool outputs are small on purpose (summaries + ids); read the `run://{run_id}/...` resources for the full picture. High or
critical bugs need a human confirmation (`answer_escalation`). Nothing is a bug until it reproduces.

Subagents (optional, Claude Code): if bugscout-mapper, bugscout-static-auditor, bugscout-security-auditor, bugscout-fuzzer,
bugscout-red-team, bugscout-diff-hunter, bugscout-perf-analyst, bugscout-quality-auditor and bugscout-triager are available, delegate each phase to the matching one and pass
it the run_id. Only bugscout-triager records bugs. Run at most two executing agents at a time, and never mutation testing together
with performance work. You keep start_run, end_run and every human escalation yourself."""

WRITE_CHARTER = """\
Help me write a charter for bugscout's `start_run`. Ask me (one short question at a time, skip what you can infer from the repo):
- target: kind (`python` | `rest_api`), repo_path, package (python) or openapi file + base_url + start_cmd (REST API; the server is
  started inside the sandbox, e.g. `uvicorn app:app --host 0.0.0.0`).
- scope.include / scope.exclude globs, and for APIs scope.allowed_hosts. Anything outside is escalated, so be generous but not reckless.
- objective in one sentence; which oracles apply (crash, schema, diff_git, rule).
- rules: invariants worth checking, each as {name, target, property, assume?} where `property` is a Python expression over
  `result` and the arguments, and `assume` restricts the generated inputs.
- reference.git_ref (default HEAD~1) for differential testing and regression checks.
- perf.max_big_o per function (default O(n log n)), perf.max_memory_mb, perf.regression_threshold.
- budget: max_steps, max_requests, max_minutes.
Then print the charter as JSON, ready to pass to `start_run`.@@CONTEXT@@"""

TRIAGE_BUG = """\
Triage the failure @@SUBJECT@@.
1. Minimize the repro: the smallest input that still fails (shrink lists to [] / one element, strings to a few characters, drop
   optional fields). Replay it with `compare_with_git_version` / `http_request` to be sure it is deterministic.
2. Run `check_flaky` if it came from a test; a failure that does not always fail is flaky, not a bug.
3. Pick the oracle that says why it is wrong: crash / http_5xx (unhandled error), schema (response does not match the contract),
   rule (a user invariant broke), diff_git (behaviour changed since the previous commit and the change is not intended).
4. Severity: critical = data loss / security / money wrong; high = wrong results or crash on a normal input; medium = crash on an
   edge input or contract violation; low = cosmetic or only reachable through unusual use. High and critical are escalated to a human.
5. Search for siblings: `query_graph duplicates_of` (copy-pasted code often carries the same bug) and `add_test_idea` for the neighbours.
6. `fingerprint_bug` then `record_bug` with a one-line title that says what breaks and for which input."""


def register(mcp: FastMCP) -> None:
    @mcp.prompt(name="testing_loop", description="The testing loop the host should follow with this server")
    def testing_loop() -> str:
        return TESTING_LOOP

    @mcp.prompt(name="write_charter", description="Interview the user and produce a charter for start_run")
    def write_charter(project_hint: str = "") -> str:
        return WRITE_CHARTER.replace("@@CONTEXT@@", f"\n\nContext from the user: {project_hint}" if project_hint else "")

    @mcp.prompt(name="triage_bug", description="How to judge severity and minimise a repro")
    def triage_bug(failure: str = "you are looking at") -> str:
        return TRIAGE_BUG.replace("@@SUBJECT@@", failure)
