"""Server-side guards. `check_action` runs before every executing tool; hosts cannot bypass it."""
from __future__ import annotations

from ..store import runs
from . import budget, destructive, escalation, scope, stuck


def check_action(run_id: str, tool_name: str, act: dict) -> dict | None:
    """Return None to allow, or a result dict (escalation_required / budget_exhausted / denied) to return instead of running.

    act keys: key|file (python target), method+path (+operation_id) / host (http), requests (int), expl_node_id.
    """
    run = runs.get_run(run_id)
    ch = run["charter"]
    node_id = act.get("expl_node_id")

    # 1. budget (hard stop first, then 90% escalation)
    r = budget.check(run_id, tool_name, int(act.get("requests", 0) or 0), node_id)
    if r:
        return r

    # 2. scope
    path = act.get("path")
    if path is not None and act.get("method"):
        path, _ = destructive.template_for(run_id, act["method"], path)
    ok, reason = scope.check(ch["scope"], key=act.get("key"), file=act.get("file"), method=act.get("method"),
                             path=path, host=act.get("host"))
    if not ok:
        k = escalation.action_key("scope", tool_name, act.get("key") or act.get("file"), act.get("method"), path, act.get("host"))
        if escalation.denied(run_id, "out_of_scope", k):
            return {"status": "denied", "reason": "out_of_scope", "summary": f"human denied: {reason}"}
        if not escalation.approved(run_id, "out_of_scope", k):
            return escalation.escalate(run_id, "out_of_scope", reason, node_id, key=k)

    # 3. destructive
    if act.get("method"):
        tmpl, opid = destructive.template_for(run_id, act["method"], act.get("path") or "")
        if destructive.is_destructive(act["method"], tmpl, act.get("operation_id") or opid) and not ch["scope"].get("allow_destructive"):
            k = escalation.action_key("destructive", act["method"].upper(), tmpl)
            if escalation.denied(run_id, "destructive", k):
                return {"status": "denied", "reason": "destructive", "summary": f"human denied {act['method'].upper()} {tmpl}"}
            if not escalation.approved(run_id, "destructive", k):
                return escalation.escalate(
                    run_id, "destructive", f"{act['method'].upper()} {tmpl} may be destructive/irreversible. Allow it?",
                    node_id, key=k, context={"method": act["method"].upper(), "path_template": tmpl})

    # 4. stuck
    return stuck.check(run_id, node_id)
