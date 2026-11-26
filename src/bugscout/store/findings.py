"""Bugs, static issues, fingerprints, dedup."""
from __future__ import annotations

from .db import J, q, q1


def add_finding(run_id: str, kind: str, oracle: str | None, severity: str, title: str, expl_node_id: str | None = None,
                asset_id: str | None = None, fingerprint: str | None = None, repro: dict | None = None,
                status: str = "open", duplicate_of: str | None = None) -> dict:
    return q1(
        """INSERT INTO finding (run_id, expl_node_id, asset_id, kind, oracle, severity, title, fingerprint, repro,
                                status, duplicate_of)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (run_id, expl_node_id, asset_id, kind, oracle, severity, title, fingerprint,
         J(repro) if repro is not None else None, status, duplicate_of),
    )


def add_static_finding_once(run_id: str, kind: str, oracle: str, severity: str, title: str, asset_id: str | None,
                            fingerprint: str) -> tuple[dict, bool]:
    """Static tools get re-run; same fingerprint -> bump occurrences instead of piling up rows."""
    existing = by_fingerprint(run_id, fingerprint)
    if existing:
        return bump_occurrences(existing["id"]), False
    return add_finding(run_id, kind, oracle, severity, title, asset_id=asset_id, fingerprint=fingerprint), True


def by_fingerprint(run_id: str, fingerprint: str) -> dict | None:
    return q1("SELECT * FROM finding WHERE run_id=%s AND fingerprint=%s AND duplicate_of IS NULL ORDER BY created_at LIMIT 1",
              (run_id, fingerprint))


def bump_occurrences(finding_id: str, by: int = 1) -> dict:
    return q1("UPDATE finding SET occurrences = occurrences + %s WHERE id=%s RETURNING *", (by, finding_id))


def get(finding_id: str) -> dict | None:
    return q1("SELECT * FROM finding WHERE id=%s", (finding_id,))


def set_status(finding_id: str, status: str) -> dict | None:
    return q1("UPDATE finding SET status=%s WHERE id=%s RETURNING *", (status, finding_id))


def list_findings(run_id: str, kind: str | None = None, oracle: str | None = None, limit: int = 200) -> list[dict]:
    sql, params = "SELECT f.*, a.key AS asset_key FROM finding f LEFT JOIN asset_node a ON a.id=f.asset_id WHERE f.run_id=%s", [run_id]
    if kind:
        sql += " AND f.kind=%s"; params.append(kind)
    if oracle:
        sql += " AND f.oracle=%s"; params.append(oracle)
    sql += """ ORDER BY CASE f.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
               f.created_at LIMIT %s"""
    params.append(limit)
    return q(sql, params)


def top(run_id: str, limit: int = 5) -> list[dict]:
    return q("""SELECT id, kind, oracle, severity, title, occurrences, status FROM finding
                WHERE run_id=%s AND duplicate_of IS NULL ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium' THEN 2 ELSE 3 END, created_at LIMIT %s""", (run_id, limit))


def count(run_id: str) -> int:
    return q1("SELECT count(*) AS n FROM finding WHERE run_id=%s", (run_id,))["n"]
