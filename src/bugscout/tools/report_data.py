"""Collect everything the final report shows (pure data; rendering in report.py)."""
from __future__ import annotations

from ..store import assets, findings, runs, tree
from ..store.db import q


def collect(run_id: str) -> dict:
    allf = findings.list_findings(run_id, limit=1000)
    uniq = [f for f in allf if not f["duplicate_of"]]
    fn = [n for n in assets.list_nodes(run_id, "function") if n["props"].get("in_scope", True)]
    cov = runs.latest_artifact(run_id, "coverage_summary")
    dup = runs.latest_artifact(run_id, "duplication")
    mut = [n["props"]["mutation_score"] for n in fn if "mutation_score" in n["props"]]
    flaky = q("SELECT test_id FROM test_record WHERE run_id=%s AND status='flaky'", (run_id,))
    dups = q("SELECT test_id FROM test_record WHERE run_id=%s AND status='duplicate'", (run_id,))
    esc = runs.list_escalations(run_id, "pending")
    brief = lambda f: {"id": str(f["id"]), "severity": f["severity"], "oracle": f["oracle"], "title": f["title"],
                       "occurrences": f["occurrences"], "status": f["status"], "target": f.get("asset_key")}
    return {
        "bugs": [brief(f) for f in uniq if f["kind"] == "bug" and f["oracle"] not in ("perf_regression", "memory")],
        "static_issues": [brief(f) for f in uniq if f["kind"] == "static_issue"],
        "warnings": [brief(f) for f in uniq if f["kind"] == "warning"],
        "cleanup": [brief(f) for f in uniq if f["kind"] == "cleanup"],
        "flaky_tests": [r["test_id"] for r in flaky],
        "duplicate_tests": [r["test_id"] for r in dups],
        "coverage": ({"line_pct": round(cov["data"]["line_pct"], 1), "branch_pct": round(cov["data"].get("branch_pct") or 0, 1)} if cov else None),
        "least_covered": [{"key": n["key"], "branch": n["props"]["coverage_branch"]}
                          for n in sorted((n for n in fn if "coverage_branch" in n["props"] and not n["props"].get("is_dead")),
                                          key=lambda n: n["props"]["coverage_branch"])[:5]],
        "mutation_score": (round(sum(mut) / len(mut), 2) if mut else None),
        "complexity_hotspots": [{"key": n["key"], "complexity": n["props"]["complexity"], "rank": n["props"].get("complexity_rank")}
                                for n in sorted((n for n in fn if n["props"].get("complexity", 0) >= 11), key=lambda n: -n["props"]["complexity"])[:8]],
        "duplication_pct": dup["data"]["duplication_pct"] if dup else None,
        "dead_code": [{"key": n["key"], "confidence": n["props"].get("dead_confidence"), "confirmed": bool(n["props"].get("is_dead"))}
                      for n in fn if n["props"].get("dead_candidate") or n["props"].get("is_dead")],
        "time_complexity": [{"key": n["key"], "big_o": n["props"]["big_o"], "allowed": n["props"].get("big_o_allowed"),
                             "uncertain": n["props"].get("big_o_uncertain", False)}
                            for n in fn if n["props"].get("big_o")],
        "cpu_hotspots": [{"key": n["key"], "self_pct": n["props"]["profile_self_pct"]}
                         for n in sorted((n for n in fn if n["props"].get("profile_self_pct")), key=lambda n: -n["props"]["profile_self_pct"])[:5]],
        "memory": [{"key": n["key"], "peak_mb": n["props"]["peak_memory_mb"]} for n in fn if n["props"].get("peak_memory_mb")],
        "perf_regressions": [brief(f) for f in uniq if f["oracle"] == "perf_regression"],
        "perf_findings": [brief(f) for f in uniq if f["oracle"] in ("complexity", "hotspot", "memory")],
        "tree": tree.counts_by_status(run_id),
        "open_escalations": [{"id": str(e["id"]), "reason": e["reason"], "question": e["question"][:160]} for e in esc],
        "budget_used": runs.get_run(run_id)["budget_used"],
    }
