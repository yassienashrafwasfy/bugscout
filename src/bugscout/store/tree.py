"""Exploration tree: what the agent tried and learned. Append-only except status/result/priority/flaky_score."""
from __future__ import annotations

from .db import J, q, q1, tx


def add_node(run_id: str, kind: str, title: str, parent_id: str | None = None, status: str = "frontier",
             hypothesis: str | None = None, target_asset_id: str | None = None, action: dict | None = None,
             result: dict | None = None, input_signature: str | None = None, priority: float = 0.0) -> dict:
    return q1(
        """INSERT INTO expl_node (run_id, parent_id, kind, status, title, hypothesis, target_asset_id, action,
                                  result, input_signature, priority)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (run_id, parent_id, kind, status, title, hypothesis, target_asset_id,
         J(action) if action is not None else None, J(result) if result is not None else None,
         input_signature, priority),
    )


def add_idea_dedup(run_id: str, parent_id: str | None, title: str, hypothesis: str | None,
                   target_asset_id: str | None, input_signature: str, priority: float = 0.0) -> tuple[dict, bool]:
    """Returns (node, created). An equal input_signature in the same run returns the existing node."""
    with tx() as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (run_id + input_signature,))
        row = c.execute("SELECT * FROM expl_node WHERE run_id=%s AND input_signature=%s AND kind='idea' "
                        "ORDER BY created_at LIMIT 1", (run_id, input_signature)).fetchone()
        if row:
            return row, False
        row = c.execute(
            """INSERT INTO expl_node (run_id, parent_id, kind, status, title, hypothesis, target_asset_id,
                                      input_signature, priority)
               VALUES (%s,%s,'idea','frontier',%s,%s,%s,%s,%s) RETURNING *""",
            (run_id, parent_id, title, hypothesis, target_asset_id, input_signature, priority)).fetchone()
        return row, True


def get_node(node_id: str) -> dict | None:
    return q1("SELECT * FROM expl_node WHERE id=%s", (node_id,))


def root_goal(run_id: str) -> dict | None:
    return q1("SELECT * FROM expl_node WHERE run_id=%s AND kind='goal' AND parent_id IS NULL ORDER BY created_at LIMIT 1", (run_id,))


def update(node_id: str, status: str | None = None, result: dict | None = None, priority: float | None = None,
           flaky_score: float | None = None) -> dict | None:
    sets, params = [], []
    if status is not None:
        sets.append("status=%s"); params.append(status)
    if result is not None:
        sets.append("result=%s"); params.append(J(result))
    if priority is not None:
        sets.append("priority=%s"); params.append(priority)
    if flaky_score is not None:
        sets.append("flaky_score=%s"); params.append(flaky_score)
    if not sets:
        return get_node(node_id)
    params.append(node_id)
    return q1(f"UPDATE expl_node SET {', '.join(sets)} WHERE id=%s RETURNING *", params)


def merge_result(node_id: str, extra: dict) -> dict | None:
    return q1("UPDATE expl_node SET result = COALESCE(result,'{}'::jsonb) || %s WHERE id=%s RETURNING *", (J(extra), node_id))


def frontier(run_id: str, limit: int = 10) -> list[dict]:
    return q("""SELECT n.*, a.key AS target_key FROM expl_node n LEFT JOIN asset_node a ON a.id = n.target_asset_id
                WHERE n.run_id=%s AND n.status='frontier' AND n.kind IN ('idea','subgoal')
                ORDER BY n.priority DESC, n.created_at LIMIT %s""", (run_id, limit))


def counts_by_status(run_id: str) -> dict[str, int]:
    return {r["status"]: r["n"] for r in q("SELECT status, count(*) AS n FROM expl_node WHERE run_id=%s GROUP BY status", (run_id,))}


def subtree(node_id: str) -> list[dict]:
    return q("""WITH RECURSIVE t AS (
                  SELECT *, 0 AS depth FROM expl_node WHERE id=%s
                  UNION ALL
                  SELECT c.*, t.depth+1 FROM expl_node c JOIN t ON c.parent_id = t.id)
                SELECT id, parent_id, kind, status, title, depth, target_asset_id, priority FROM t ORDER BY depth, created_at""",
             (node_id,))


def whole_tree(run_id: str) -> list[dict]:
    return q("SELECT id, parent_id, kind, status, title, priority, flaky_score FROM expl_node WHERE run_id=%s ORDER BY created_at", (run_id,))


def tested_asset_ids(run_id: str) -> set[str]:
    rows = q("SELECT DISTINCT target_asset_id FROM expl_node WHERE run_id=%s AND kind='test' AND target_asset_id IS NOT NULL", (run_id,))
    return {str(r["target_asset_id"]) for r in rows}


def tests_per_asset(run_id: str) -> dict[str, int]:
    rows = q("""SELECT target_asset_id, count(*) AS n FROM expl_node WHERE run_id=%s AND kind IN ('test','idea')
                AND target_asset_id IS NOT NULL GROUP BY target_asset_id""", (run_id,))
    return {str(r["target_asset_id"]): r["n"] for r in rows}


def progress_since(run_id: str, since_event_id: int) -> int:
    """New done/confirmed_bug nodes created or findings created since an event id (for the stuck detector)."""
    ts = q1("SELECT created_at FROM event_log WHERE id=%s", (since_event_id,))
    if not ts:
        return 0
    n1 = q1("SELECT count(*) AS n FROM expl_node WHERE run_id=%s AND status IN ('done','confirmed_bug') AND created_at > %s",
            (run_id, ts["created_at"]))["n"]
    return n1
