"""Stuck detector: progress = new done/confirmed nodes + new findings + coverage gain over the last window of steps."""
from __future__ import annotations

from collections import Counter

from ..store import runs, tree
from ..store.db import q, q1
from . import escalation

NON_STEP_TOOLS = {"get_status", "get_report", "get_escalations", "answer_escalation", "start_run", "end_run",
                  "get_frontier", "get_untested", "query_graph", "fingerprint_bug", "ask_human", "confirm_finding"}


def score(run_id: str) -> int:
    n = q1("SELECT count(*) AS n FROM expl_node WHERE run_id=%s AND status IN ('done','confirmed_bug')", (run_id,))["n"]
    f = q1("SELECT count(*) AS n FROM finding WHERE run_id=%s AND duplicate_of IS NULL", (run_id,))["n"]
    return n + f


def latest_coverage(run_id: str) -> float | None:
    a = runs.latest_artifact(run_id, "coverage_summary")
    return float(a["data"]["line_pct"]) if a and a["data"].get("line_pct") is not None else None


def record(run_id: str, step: int) -> None:
    q("""INSERT INTO progress_snapshot (run_id, step, score, coverage) VALUES (%s,%s,%s,%s)
         ON CONFLICT (run_id, step) DO UPDATE SET score=EXCLUDED.score, coverage=EXCLUDED.coverage""",
      (run_id, step, score(run_id), latest_coverage(run_id)))


def check(run_id: str, expl_node_id: str | None = None) -> dict | None:
    run = runs.get_run(run_id)
    cfg = run["charter"]["stuck"]
    step = int(run["budget_used"].get("steps", 0))
    window = cfg["window_steps"]
    if step < window:
        return None
    last = q1("""SELECT (context->>'step')::int AS step FROM escalation WHERE run_id=%s AND reason='stuck'
                 ORDER BY created_at DESC LIMIT 1""", (run_id,))
    if last and last["step"] is not None and step - last["step"] < window:
        return None                      # fired recently; give the host a full window to react
    start = q1("SELECT score, coverage FROM progress_snapshot WHERE run_id=%s AND step<=%s ORDER BY step DESC LIMIT 1",
               (run_id, step - window))
    start_score = start["score"] if start else 0
    start_cov = start["coverage"] if start else None
    now_cov = latest_coverage(run_id)
    progress = score(run_id) - start_score
    if now_cov is not None and start_cov is not None:
        progress += int(now_cov - start_cov)       # each +1 point of line coverage counts as progress
    if progress >= cfg["min_progress"]:
        return None
    events = [e for e in runs.recent_events(run_id, window * 2) if e["tool"] not in NON_STEP_TOOLS][:window]
    tried = Counter(e["tool"] for e in events)
    ideas = [r["title"] for r in tree.frontier(run_id, 5)]
    summary = (f"No progress in the last {window} steps (progress={progress}, need {cfg['min_progress']}). "
               f"Tried: {dict(tried)}. Open frontier: {ideas or 'none'}")
    return escalation.escalate(run_id, "stuck", summary, expl_node_id,
                               key=escalation.action_key("stuck", step), context={"step": step, "tried": dict(tried)})
