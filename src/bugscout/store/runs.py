"""runs, charter, budget accounting, event log, artifacts, escalations."""
from __future__ import annotations

import json
from typing import Any

from .db import J, q, q1


def create_run(charter: dict) -> dict:
    return q1("INSERT INTO run (charter) VALUES (%s) RETURNING *", (J(charter),))


def get_run(run_id: str) -> dict | None:
    return q1("SELECT * FROM run WHERE id=%s", (run_id,))


def set_status(run_id: str, status: str) -> None:
    q("UPDATE run SET status=%s WHERE id=%s", (status, run_id))


def bump_budget(run_id: str, steps: int = 0, requests: int = 0, seconds: float = 0.0) -> dict:
    """Atomic increment; returns the new budget_used."""
    row = q1(
        """UPDATE run SET budget_used = jsonb_build_object(
             'steps',    COALESCE((budget_used->>'steps')::int, 0) + %s,
             'requests', COALESCE((budget_used->>'requests')::int, 0) + %s,
             'seconds',  COALESCE((budget_used->>'seconds')::float8, 0) + %s)
           WHERE id=%s RETURNING budget_used""",
        (steps, requests, seconds, run_id),
    )
    return row["budget_used"] if row else {}


def log_event(run_id: str, tool: str, args: Any, outcome: str, duration_ms: int) -> int:
    row = q1(
        "INSERT INTO event_log (run_id, tool, args, outcome, duration_ms) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (run_id, tool, J(json.loads(json.dumps(args, default=str))), outcome, duration_ms),
    )
    return row["id"]


def recent_events(run_id: str, limit: int) -> list[dict]:
    return q("SELECT * FROM event_log WHERE run_id=%s ORDER BY id DESC LIMIT %s", (run_id, limit))


def event_count(run_id: str) -> int:
    return q1("SELECT count(*) AS n FROM event_log WHERE run_id=%s", (run_id,))["n"]


# ---- artifacts (full logs live here; tools return ids) ----
def add_artifact(run_id: str, kind: str, data: Any) -> str:
    return str(q1("INSERT INTO artifact (run_id, kind, data) VALUES (%s,%s,%s) RETURNING id",
                  (run_id, kind, J(json.loads(json.dumps(data, default=str)))))["id"])


def get_artifact(artifact_id: str) -> dict | None:
    return q1("SELECT * FROM artifact WHERE id=%s", (artifact_id,))


def latest_artifact(run_id: str, kind: str) -> dict | None:
    return q1("SELECT * FROM artifact WHERE run_id=%s AND kind=%s ORDER BY created_at DESC LIMIT 1", (run_id, kind))


# ---- escalations ----
def create_escalation(run_id: str, reason: str, question: str, expl_node_id: str | None = None,
                      context: dict | None = None) -> dict:
    return q1(
        "INSERT INTO escalation (run_id, expl_node_id, reason, question, context) VALUES (%s,%s,%s,%s,%s) RETURNING *",
        (run_id, expl_node_id, reason, question, J(context or {})),
    )


def get_escalation(esc_id: str) -> dict | None:
    return q1("SELECT * FROM escalation WHERE id=%s", (esc_id,))


def list_escalations(run_id: str, status: str | None = "pending") -> list[dict]:
    if status:
        return q("SELECT * FROM escalation WHERE run_id=%s AND status=%s ORDER BY created_at", (run_id, status))
    return q("SELECT * FROM escalation WHERE run_id=%s ORDER BY created_at", (run_id,))


def answer_escalation(esc_id: str, answer: str, approve: bool) -> dict | None:
    return q1("UPDATE escalation SET status=%s, answer=%s WHERE id=%s RETURNING *",
              ("approved" if approve else "denied", answer, esc_id))


def find_escalation_by_action(run_id: str, reason: str, action_key: str) -> dict | None:
    """Latest escalation for a normalized action key (method+path template+args hash)."""
    return q1(
        """SELECT * FROM escalation WHERE run_id=%s AND reason=%s AND context->>'action_key'=%s
           ORDER BY created_at DESC LIMIT 1""",
        (run_id, reason, action_key),
    )
