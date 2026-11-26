"""Escalations: create, dedupe, match approvals, resolve. Escalations stop a BRANCH, never the run."""
from __future__ import annotations

import hashlib
from typing import Any

from ..store import findings, runs, tree


def action_key(*parts: Any) -> str:
    """Normalized action key (e.g. method + path template) so an approval covers repeats of the same action."""
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def approved(run_id: str, reason: str, key: str) -> bool:
    e = runs.find_escalation_by_action(run_id, reason, key)
    return bool(e and e["status"] == "approved")


def denied(run_id: str, reason: str, key: str) -> bool:
    e = runs.find_escalation_by_action(run_id, reason, key)
    return bool(e and e["status"] == "denied")


def escalate(run_id: str, reason: str, question: str, expl_node_id: str | None = None, key: str | None = None,
             context: dict | None = None) -> dict:
    ctx = dict(context or {})
    if key:
        ctx["action_key"] = key
        existing = runs.find_escalation_by_action(run_id, reason, key)
        if existing and existing["status"] == "pending":
            esc = existing
        else:
            esc = runs.create_escalation(run_id, reason, question, expl_node_id, ctx)
    else:
        esc = runs.create_escalation(run_id, reason, question, expl_node_id, ctx)
    if expl_node_id:
        node = tree.get_node(expl_node_id)
        if node and node["status"] in ("frontier", "in_progress"):
            tree.update(expl_node_id, status="escalated")
    return {"status": "escalation_required", "reason": reason, "question": question,
            "escalation_id": str(esc["id"]),
            "summary": f"{reason}: {question} (branch paused; work on other frontier nodes, check get_escalations later)"}


def on_serious_finding(run_id: str, finding: dict, expl_node_id: str | None = None) -> dict | None:
    """high|critical findings need a human to confirm before they count as confirmed bugs."""
    if finding["severity"] not in ("high", "critical"):
        return None
    findings.set_status(str(finding["id"]), "needs_confirmation")
    return escalate(run_id, "serious_bug", f"Confirm {finding['severity']} finding: {finding['title']}", expl_node_id,
                    key=action_key("finding", finding["id"]),
                    context={"finding_id": str(finding["id"]), "oracle": finding["oracle"]})


def resolve(esc: dict, approve: bool) -> dict:
    """After a human answers: unblock the branch, settle serious-bug findings."""
    ctx = esc.get("context") or {}
    if esc["reason"] == "serious_bug" and ctx.get("finding_id"):
        findings.set_status(ctx["finding_id"], "confirmed" if approve else "rejected")
    node_id = esc.get("expl_node_id")
    if node_id:
        node = tree.get_node(str(node_id))
        if node and node["status"] == "escalated":
            if esc["reason"] == "serious_bug":
                tree.update(str(node_id), status="confirmed_bug" if approve else "done")
            else:
                tree.update(str(node_id), status="frontier" if approve else "dead_end")
    return esc
