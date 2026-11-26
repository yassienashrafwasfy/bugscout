"""Asset graph: what exists in the system under test."""
from __future__ import annotations

from typing import Any

from .db import J, q, q1


def upsert_node(run_id: str, type: str, key: str, name: str | None = None, props: dict | None = None,
                discovered_by: str | None = None) -> dict:
    """Insert, or merge props into the existing node (props are merged with ||)."""
    return q1(
        """INSERT INTO asset_node (run_id, type, key, name, props, discovered_by)
           VALUES (%s,%s,%s,%s,%s,%s)
           ON CONFLICT (run_id, key) DO UPDATE SET
             props = asset_node.props || EXCLUDED.props,
             name = COALESCE(EXCLUDED.name, asset_node.name),
             updated_at = now()
           RETURNING *""",
        (run_id, type, key, name, J(props or {}), discovered_by),
    )


def set_props(node_id: str, props: dict) -> dict | None:
    return q1("UPDATE asset_node SET props = props || %s, updated_at = now() WHERE id=%s RETURNING *", (J(props), node_id))


def set_props_by_key(run_id: str, key: str, props: dict) -> dict | None:
    return q1("UPDATE asset_node SET props = props || %s, updated_at = now() WHERE run_id=%s AND key=%s RETURNING *",
              (J(props), run_id, key))


def get_node(node_id: str) -> dict | None:
    return q1("SELECT * FROM asset_node WHERE id=%s", (node_id,))


def get_by_key(run_id: str, key: str) -> dict | None:
    return q1("SELECT * FROM asset_node WHERE run_id=%s AND key=%s", (run_id, key))


def list_nodes(run_id: str, type: str | None = None, types: list[str] | None = None) -> list[dict]:
    if types:
        return q("SELECT * FROM asset_node WHERE run_id=%s AND type = ANY(%s) ORDER BY key", (run_id, types))
    if type:
        return q("SELECT * FROM asset_node WHERE run_id=%s AND type=%s ORDER BY key", (run_id, type))
    return q("SELECT * FROM asset_node WHERE run_id=%s ORDER BY key", (run_id,))


def add_edge(run_id: str, src_id: str, dst_id: str, type: str, props: dict | None = None) -> None:
    q("""INSERT INTO asset_edge (run_id, src_id, dst_id, type, props) VALUES (%s,%s,%s,%s,%s)
         ON CONFLICT (run_id, src_id, dst_id, type) DO UPDATE SET props = asset_edge.props || EXCLUDED.props""",
      (run_id, src_id, dst_id, type, J(props or {})))


def edges_of(run_id: str, node_id: str, type: str | None = None, direction: str = "out") -> list[dict]:
    col, other = ("src_id", "dst_id") if direction == "out" else ("dst_id", "src_id")
    sql = f"""SELECT e.type AS edge_type, e.props AS edge_props, n.* FROM asset_edge e
              JOIN asset_node n ON n.id = e.{other} WHERE e.run_id=%s AND e.{col}=%s"""
    params: list[Any] = [run_id, node_id]
    if type:
        sql += " AND e.type=%s"
        params.append(type)
    return q(sql, params)


def count_nodes(run_id: str) -> dict[str, int]:
    return {r["type"]: r["n"] for r in q("SELECT type, count(*) AS n FROM asset_node WHERE run_id=%s GROUP BY type", (run_id,))}


def enclosing_function(run_id: str, file: str, line: int) -> dict | None:
    """Function node whose [lineno, end_lineno] range contains `line` in `file`."""
    return q1(
        """SELECT * FROM asset_node WHERE run_id=%s AND type='function' AND props->>'file'=%s
             AND (props->>'lineno')::int <= %s AND (props->>'end_lineno')::int >= %s
           ORDER BY (props->>'end_lineno')::int - (props->>'lineno')::int LIMIT 1""",
        (run_id, file, line, line),
    )
