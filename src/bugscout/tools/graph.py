"""Graph tools: exploration-tree + asset-graph interface for the host."""
from __future__ import annotations

import hashlib
import json

from .. import priority as prio
from ..guards import escalation
from ..models import NODE_STATUSES, err, ok
from ..runtime import tool
from ..store import assets, tree
from ..store.db import q


def normalize_shape(shape) -> str:
    """Normalized input shape: dict keys sorted, string literals/numbers collapsed to their kind, whitespace dropped."""
    def norm(v):
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, (int, float)):
            return "number"
        if isinstance(v, str):
            return v.strip().lower()
        if isinstance(v, dict):
            return {k: norm(x) for k, x in sorted(v.items())}
        if isinstance(v, (list, tuple)):
            return [norm(x) for x in v]
        return v
    return json.dumps(norm(shape), sort_keys=True, default=str)


def input_signature(target_key: str | None, shape) -> str:
    return hashlib.sha1(f"{target_key}|{normalize_shape(shape)}".encode()).hexdigest()


@tool("add_test_idea", executing=True,
      action=lambda kw: {"key": (assets.get_node(kw["target_asset_id"]) or {}).get("key") if kw.get("target_asset_id") else None,
                         "expl_node_id": kw.get("parent_id")})
def add_test_idea(run_id: str, title: str, hypothesis: str = "", target_asset_id: str | None = None,
                  parent_id: str | None = None, input_shape: dict | list | str | None = None) -> dict:
    """Propose a test idea. The server dedups on hash(target key + normalized input shape): an equal idea returns the existing node."""
    target = assets.get_node(target_asset_id) if target_asset_id else None
    if target_asset_id and not target:
        return err(f"unknown target_asset_id {target_asset_id}")
    sig = input_signature(target["key"] if target else None, input_shape if input_shape is not None else title)
    parent = parent_id or (str(tree.root_goal(run_id)["id"]))
    pr = 0.0
    if target:
        ch = __import__("bugscout.store.runs", fromlist=["runs"]).get_run(run_id)["charter"]
        pr = prio.score_node(target, prio.asset_context(run_id), ch)
    node, created = tree.add_idea_dedup(run_id, parent, title, hypothesis or None, target_asset_id, sig, pr)
    n = {"id": str(node["id"]), "status": node["status"], "title": node["title"], "priority": node["priority"]}
    if not created:
        return ok("duplicate idea: returned the existing node", {"created": False, "node": n},
                  ["pick a different input shape or target"])
    return ok("idea added", {"created": True, "node": n}, ["write_test / run_hypothesis / run_schemathesis / http_request"])


@tool("update_result")
def update_result(run_id: str, expl_node_id: str, status: str, result: dict | None = None) -> dict:
    """Update a node's status/result. (Nothing else on a node may change.)"""
    if status not in NODE_STATUSES:
        return err(f"status must be one of {NODE_STATUSES}")
    node = tree.get_node(expl_node_id)
    if not node or str(node["run_id"]) != run_id:
        return err("unknown node for this run")
    if status == "confirmed_bug":
        from ..store.db import q1
        if not q1("SELECT 1 FROM finding WHERE run_id=%s AND expl_node_id=%s AND status<>'rejected'", (run_id, expl_node_id)):
            return err("confirmed_bug is set by record_bug (reproduced + fingerprinted) or a human confirmation, not by hand")
    n = tree.update(expl_node_id, status=status, result=result)
    return ok("updated", {"id": str(n["id"]), "status": n["status"]})


@tool("get_frontier", count_step=False)
def get_frontier(run_id: str, limit: int = 10) -> dict:
    """Frontier nodes (ideas/subgoals not yet tried) ranked by priority."""
    rows = tree.frontier(run_id, limit)
    return ok(f"{len(rows)} frontier node(s)", {"nodes": [
        {"id": str(r["id"]), "title": r["title"], "hypothesis": r["hypothesis"], "target": r["target_key"], "priority": r["priority"]}
        for r in rows]})


@tool("get_untested", count_step=False)
def get_untested(run_id: str, limit: int = 10) -> dict:
    """In-scope, non-dead asset nodes with no test pointing at them, ranked by priority."""
    from ..store import runs
    ch = runs.get_run(run_id)["charter"]
    ctx = prio.asset_context(run_id)
    tested = tree.tested_asset_ids(run_id)
    cands = [n for n in assets.list_nodes(run_id, types=["function", "endpoint"])
             if n["props"].get("in_scope", True) and not n["props"].get("is_dead") and str(n["id"]) not in tested
             and not n["props"].get("tested")]
    scored = sorted(((prio.score_node(n, ctx, ch), n) for n in cands), key=lambda x: -x[0])[:limit]
    return ok(f"{len(scored)} untested target(s)", {"targets": [
        {"asset_id": str(n["id"]), "key": n["key"], "type": n["type"], "priority": s,
         "complexity": n["props"].get("complexity"), "coverage_branch": n["props"].get("coverage_branch")} for s, n in scored]})


# ---- named, safe queries (no raw SQL)
def _q_neighbors(run_id: str, p: dict):
    n = assets.get_by_key(run_id, p["key"]) if "key" in p else assets.get_node(p["asset_id"])
    if not n:
        return None
    out = [{"dir": "out", "edge": r["edge_type"], "key": r["key"], "type": r["type"]} for r in assets.edges_of(run_id, str(n["id"]))]
    out += [{"dir": "in", "edge": r["edge_type"], "key": r["key"], "type": r["type"]} for r in assets.edges_of(run_id, str(n["id"]), direction="in")]
    return out


def _q_callers(run_id: str, p: dict):
    n = assets.get_by_key(run_id, p["key"])
    return None if not n else [{"key": r["key"]} for r in assets.edges_of(run_id, str(n["id"]), "calls", "in")]


def _q_duplicates_of(run_id: str, p: dict):
    n = assets.get_by_key(run_id, p["key"])
    if not n:
        return None
    sid = str(n["id"])
    return [{"key": r["key"]} for r in assets.edges_of(run_id, sid, "duplicate_of", "out") + assets.edges_of(run_id, sid, "duplicate_of", "in")]


def _q_subtree(run_id: str, p: dict):
    return [{**r, "id": str(r["id"]), "parent_id": str(r["parent_id"]) if r["parent_id"] else None, "target_asset_id": None}
            for r in tree.subtree(p["node_id"])]


NAMED = {"neighbors": _q_neighbors, "callers": _q_callers, "duplicates_of": _q_duplicates_of, "subtree": _q_subtree}


@tool("query_graph", count_step=False)
def query_graph(run_id: str, sql_name: str, params: dict | None = None) -> dict:
    """Safe named queries: neighbors{key}, callers{key}, duplicates_of{key}, subtree{node_id}."""
    fn = NAMED.get(sql_name)
    if not fn:
        return err(f"unknown query '{sql_name}'; choose from {sorted(NAMED)}")
    try:
        rows = fn(run_id, params or {})
    except KeyError as e:
        return err(f"missing param {e}")
    if rows is None:
        return err("target not found")
    return ok(f"{len(rows)} row(s)", {"rows": rows})
