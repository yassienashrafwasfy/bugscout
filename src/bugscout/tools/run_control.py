"""Run control: start_run, get_status, end_run."""
from __future__ import annotations

from pydantic import ValidationError

from .. import config
from ..models import Charter, err, ok
from ..runtime import tool
from ..store import assets, findings, runs, tree


@tool("start_run", count_step=False)
def start_run(charter: dict) -> dict:
    """Validate the charter, create a run, provision the sandbox, create the root goal node."""
    try:
        ch = Charter.model_validate(charter)
    except ValidationError as e:
        return err("invalid charter", {"errors": e.errors(include_url=False, include_context=False)})
    run = runs.create_run(ch.model_dump())
    run_id = str(run["id"])
    goal = tree.add_node(run_id, "goal", ch.objective, status="in_progress")
    data: dict = {"run_id": run_id, "root_node_id": str(goal["id"])}
    if config.PROVISION:
        try:
            from ..runners import sandbox
            data["sandbox"] = sandbox.provision(run_id, ch)
        except Exception as e:
            runs.set_status(run_id, "aborted")
            return err(f"sandbox provisioning failed: {type(e).__name__}: {e}", data)
    runs.log_event(run_id, "start_run", {"objective": ch.objective}, "ok", 0)
    return ok("run created", data, next_suggestions=[
        "scan_python_code / import_openapi to populate the asset graph", "then the static stage (run_radon, run_ruff, ...)"])


def _limits(run: dict) -> dict:
    b, used = run["charter"]["budget"], run["budget_used"]
    return {
        "steps": f'{used.get("steps", 0)}/{b["max_steps"]}',
        "requests": f'{used.get("requests", 0)}/{b["max_requests"]}',
        "minutes": f'{used.get("seconds", 0) / 60:.1f}/{b["max_minutes"]}',
    }


@tool("get_status", count_step=False)
def get_status(run_id: str) -> dict:
    """Budget used, node counts per status, open escalations, top findings."""
    run = runs.get_run(run_id)
    esc = runs.list_escalations(run_id, "pending")
    data = {
        "run_status": run["status"],
        "budget": _limits(run),
        "tree": tree.counts_by_status(run_id),
        "assets": assets.count_nodes(run_id),
        "open_escalations": [{"id": str(e["id"]), "reason": e["reason"], "question": e["question"]} for e in esc],
        "top_findings": [{**f, "id": str(f["id"])} for f in findings.top(run_id, 5)],
        "findings_total": findings.count(run_id),
    }
    return ok(f"run {run['status']}; {len(esc)} pending escalation(s)", data)


@tool("end_run", count_step=False)
def end_run(run_id: str) -> dict:
    """Stop containers, mark done, return the final report."""
    stopped = {}
    if config.PROVISION:
        try:
            from ..runners import sandbox
            stopped = sandbox.destroy_run(run_id)
            from ..runners import git_ref
            git_ref.cleanup(run_id, runs.get_run(run_id)["charter"]["target"]["repo_path"])
        except Exception as e:
            stopped = {"error": f"{type(e).__name__}: {e}"}
    runs.set_status(run_id, "done")
    from .report import build_report
    return ok("run ended", {"containers": stopped, "report": build_report(run_id)})
