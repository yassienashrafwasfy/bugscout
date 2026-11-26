"""Phase 8 e2e: a scripted MCP host (real stdio transport, real server process, real Docker sandboxes) follows the testing_loop on
BOTH examples; every planted bug must show up in get_report.

This is a scripted stand-in for Claude Code / Codex: it speaks the same MCP protocol, but the "planner" is a fixed script, not an
LLM. A live Claude Code session was NOT part of this test (see README, "What was and was not verified")."""
import sys

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

import e2e_host
from conftest import TEST_DB, lib_charter
from helpers import Host
from test_phase5_oracles import API_CH

pytestmark = [pytest.mark.docker, pytest.mark.integration]


def stdio_host() -> Host:
    t = StdioTransport(command=sys.executable, args=["-m", "bugscout.server"],
                       env={"DATABASE_URL": TEST_DB, "BUGSCOUT_PROVISION": "1", "PATH": __import__("os").environ["PATH"]})
    return Host(t)


async def test_server_surface_over_stdio():
    async with stdio_host() as h:
        tools = {t.name for t in await h.c.list_tools()}
        plan_tools = {"start_run", "get_status", "end_run", "scan_python_code", "import_openapi", "run_radon", "run_ruff", "run_mypy",
                      "run_bandit", "run_duplication", "run_vulture", "confirm_finding", "add_test_idea", "update_result", "get_frontier",
                      "get_untested", "query_graph", "write_test", "run_pytest", "run_hypothesis", "run_schemathesis", "http_request",
                      "check_crash", "check_schema", "check_rule", "compare_with_git_version", "run_coverage", "run_mutation",
                      "check_flaky", "dedup_tests", "fingerprint_bug", "record_bug", "ask_human", "get_escalations", "answer_escalation",
                      "get_report", "measure_time_complexity", "run_benchmark", "compare_benchmark_with_git_version", "profile_cpu",
                      "profile_memory", "profile_api"}
        assert plan_tools <= tools, plan_tools - tools
        assert {p.name for p in await h.c.list_prompts()} == {"testing_loop", "write_charter", "triage_bug"}
        tmpl = {str(t.uri_template) for t in await h.c.list_resource_templates()}
        assert {f"run://{{run_id}}/{n}" for n in ("charter", "assets", "tree", "frontier", "findings", "escalations")} <= tmpl
        loop = (await h.c.get_prompt("testing_loop")).messages[0].content.text
        for tool_name in ("get_untested", "check_flaky", "record_bug", "compare_benchmark_with_git_version", "escalation_required"):
            assert tool_name in loop
        # every tool the prompt tells the host to call exists
        import re
        mentioned = set(re.findall(r"`([a-z_]+)`", loop)) - {"escalation_required", "flaky"}
        assert mentioned <= tools | {"run_id"}, mentioned - tools


async def test_e2e_sample_lib(fx_lib):
    async with stdio_host() as h:
        out = await e2e_host.lib_loop(h, lib_charter(fx_lib, budget={"max_steps": 300, "max_requests": 1000, "max_minutes": 60},
                                                      perf={"max_big_o": {"default": "O(n log n)"}, "max_memory_mb": 512,
                                                            "max_seconds_per_call": 25, "regression_threshold": 0.2, "hotspot_pct": 30}))
    md = out["report_md"]
    print(md)
    # --- every planted issue is in the report
    checks = {
        "edge-case crash (mean([]))": "samplelib.stats:mean raises ZeroDivisionError",
        "DRY copy with the same bug": "samplelib.invoices:invoice_share_copy raises ZeroDivisionError",
        "original of the copy": "samplelib.billing:invoice_share raises ZeroDivisionError",
        "rule violation": "withdraw() can drive the balance negative",
        "regression in the last commit": "apply_discount() changed behaviour",
        "complexity rank D": "samplelib.rates:region_tax",
        "flaky test": "test_flaky_planted",
        "duplicate tests": "test_mean_basic_again",
        "dead code": "legacy_format",
        "mypy type error": "typed.py",
        "eval / shell (bandit)": "bandit",
        "duplication": "Duplication:",
        "O(n^2)": "O(n^2)",
        "3x slowdown": "slower than HEAD~1",
        "CPU hotspot": "_crunch",
        "memory hog": "build_table",
    }
    missing = {k: v for k, v in checks.items() if v not in md}
    assert not missing, f"not in the report: {missing}\n{md}"
    assert "occurrences" in md and "Coverage: line" in md and "Mutation score: not measured" not in md and "Mutation score:" in md
    # the planted flaky test is not a bug; the bugs section has no test_flaky entry
    bugs_part = md.split("## Flaky")[0]
    assert "test_flaky_planted" not in bugs_part
    # the high-severity rule bug went through human confirmation
    assert any(t.startswith("withdraw()") and r["data"].get("needs_confirmation") for t, r in out["recorded"])


async def test_e2e_sample_api(fx_api):
    async with stdio_host() as h:
        out = await e2e_host.api_loop(h, API_CH(fx_api))
    md = out["report_md"]
    print(md)
    assert "GET /items/{item_id} returns 500 for a negative id" in md
    assert "response misses the required field 'total'" in md
    assert out["delete_escalation"]["reason"] == "destructive"
    # schemathesis rediscovered both and skipped the DELETE
    fails = {(f["endpoint"], f["check"]) for f in out["schemathesis"]["data"]["failures"]}
    assert ("GET /orders/{order_id}", "response_schema_conformance") in fails
    assert ("GET /items/{item_id}", "not_a_server_error") in fails
    assert "DELETE /items/{item_id}" in out["schemathesis"]["data"]["skipped_destructive"]
