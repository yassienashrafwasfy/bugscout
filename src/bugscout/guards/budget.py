"""Budget guard: warn/escalate at 90%, hard stop at 100%. max_minutes = SUM of tool-call durations."""
from __future__ import annotations

from .. import config
from ..store import runs
from . import escalation


def usage(run: dict) -> dict[str, tuple[float, float]]:
    b, u = run["charter"]["budget"], run["budget_used"]
    return {"steps": (u.get("steps", 0), b["max_steps"]),
            "requests": (u.get("requests", 0), b["max_requests"]),
            "minutes": (u.get("seconds", 0) / 60.0, b["max_minutes"])}


def check(run_id: str, tool_name: str, extra_requests: int = 0, expl_node_id: str | None = None) -> dict | None:
    run = runs.get_run(run_id)
    for metric, (used, limit) in usage(run).items():
        if metric == "requests":
            used += extra_requests
        frac = used / limit if limit else 0
        if frac >= 1.0:
            esc = escalation.escalate(run_id, "budget", f"{metric} budget exhausted ({used:.0f}/{limit}); hard stop",
                                      None, key=escalation.action_key("budget100", metric))
            return {"status": "budget_exhausted", "reason": "budget", "escalation_id": esc["escalation_id"],
                    "summary": f"hard stop: {metric} budget {used:.0f}/{limit} exhausted. Call get_report then end_run."}
        if frac >= config.BUDGET_WARN_FRACTION:
            key = escalation.action_key("budget90", metric)
            if not escalation.approved(run_id, "budget", key):
                return escalation.escalate(run_id, "budget", f"{metric} budget at {frac:.0%} ({used:.0f}/{limit}); continue?",
                                           expl_node_id, key=key, context={"metric": metric})
    return None
