"""Read-only MCP resources: run://{id}/charter|assets|tree|frontier|findings|escalations|report."""
from __future__ import annotations

import json

from fastmcp import FastMCP

from .store import assets, findings, runs, tree

MAX_ROWS = 500


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, default=str)


def _run(run_id: str) -> dict:
    r = runs.get_run(run_id)
    if not r:
        raise ValueError(f"unknown run {run_id}")
    return r


def charter(run_id: str) -> str:
    r = _run(run_id)
    return _dump({"run_id": run_id, "status": r["status"], "charter": r["charter"], "budget_used": r["budget_used"]})


def assets_(run_id: str) -> str:
    _run(run_id)
    nodes = assets.list_nodes(run_id)
    keep = ("file", "lineno", "complexity", "complexity_rank", "coverage_branch", "tested", "is_dead", "dead_candidate", "big_o",
            "runtime_ms_p50", "peak_memory_mb", "profile_self_pct", "static_issues_count", "mutation_score", "duplicate_group")
    rows = [{"id": str(n["id"]), "type": n["type"], "key": n["key"], **{k: n["props"][k] for k in keep if k in n["props"]}}
            for n in nodes[:MAX_ROWS]]
    return _dump({"counts": assets.count_nodes(run_id), "shown": len(rows), "total": len(nodes), "nodes": rows})


def tree_(run_id: str) -> str:
    _run(run_id)
    rows = tree.whole_tree(run_id)
    return _dump({"counts": tree.counts_by_status(run_id), "shown": min(len(rows), MAX_ROWS), "total": len(rows),
                  "nodes": [{**r, "id": str(r["id"]), "parent_id": str(r["parent_id"]) if r["parent_id"] else None} for r in rows[:MAX_ROWS]]})


def frontier(run_id: str) -> str:
    _run(run_id)
    return _dump([{"id": str(n["id"]), "title": n["title"], "kind": n["kind"], "priority": n["priority"], "target": n.get("target_key")}
                  for n in tree.frontier(run_id, 50)])


def findings_(run_id: str) -> str:
    _run(run_id)
    rows = findings.list_findings(run_id, limit=MAX_ROWS)
    return _dump([{"id": str(f["id"]), "kind": f["kind"], "oracle": f["oracle"], "severity": f["severity"], "status": f["status"],
                   "title": f["title"], "occurrences": f["occurrences"], "fingerprint": f["fingerprint"],
                   "duplicate_of": str(f["duplicate_of"]) if f["duplicate_of"] else None, "repro": f["repro"]} for f in rows])


def escalations(run_id: str) -> str:
    _run(run_id)
    return _dump([{"id": str(e["id"]), "reason": e["reason"], "status": e["status"], "question": e["question"], "answer": e["answer"],
                   "expl_node_id": str(e["expl_node_id"]) if e["expl_node_id"] else None} for e in runs.list_escalations(run_id, None)])


def report(run_id: str) -> str:
    _run(run_id)
    from .tools.report import build_report, render_md
    return render_md(build_report(run_id), run_id)


def register(mcp: FastMCP) -> None:
    for name, fn, mime in (("charter", charter, "application/json"), ("assets", assets_, "application/json"),
                           ("tree", tree_, "application/json"), ("frontier", frontier, "application/json"),
                           ("findings", findings_, "application/json"), ("escalations", escalations, "application/json"),
                           ("report", report, "text/markdown")):
        mcp.resource(f"run://{{run_id}}/{name}", name=f"run_{name}", mime_type=mime,
                     description=f"Read-only view: the {name} of a run")(fn)
