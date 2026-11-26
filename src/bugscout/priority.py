"""Deterministic priority scoring (§9) with a small UCB exploration bonus."""
from __future__ import annotations

import math

from .store import assets, runs, tree


def _norm(v, cap: float) -> float:
    return 0.0 if v is None else max(0.0, min(1.0, float(v) / cap))


def asset_priority(props: dict, *, dup_with_bug: bool = False, changed: bool = False, worse_big_o: bool = False,
                   n_tests: int = 0, total_tests: int = 0) -> float:
    cov = props.get("coverage_branch")
    cov = 0.0 if cov is None else float(cov)
    mut = props.get("mutation_score")
    p = (0.30 * _norm(props.get("complexity"), 20)
         + 0.25 * (1 - cov)
         + 0.15 * _norm(props.get("static_issues_count"), 5)
         + (0.15 * (1 - float(mut)) if mut is not None else 0.0)
         + 0.10 * (1.0 if dup_with_bug else 0.0)
         + 0.05 * (1.0 if changed else 0.0)
         + 0.10 * _norm(props.get("profile_self_pct"), 100)
         + 0.10 * (1.0 if worse_big_o else 0.0)
         - 1.00 * (1.0 if props.get("is_dead") else 0.0))
    # UCB-style bonus: targets with few tests get a nudge so the agent does not fixate on one function
    p += 0.15 * math.sqrt(math.log(total_tests + 2) / (n_tests + 1))
    return round(p, 4)


def asset_context(run_id: str) -> dict:
    """Per-run lookups used when scoring: which assets are copies of buggy code, changed since reference, too slow."""
    from .store.db import q
    buggy = {str(r["asset_id"]) for r in q(
        "SELECT DISTINCT asset_id FROM finding WHERE run_id=%s AND kind='bug' AND duplicate_of IS NULL AND asset_id IS NOT NULL", (run_id,))}
    dup_with_bug: set[str] = set()
    for e in q("SELECT src_id, dst_id FROM asset_edge WHERE run_id=%s AND type='duplicate_of'", (run_id,)):
        a, b = str(e["src_id"]), str(e["dst_id"])
        if a in buggy:
            dup_with_bug.add(b)
        if b in buggy:
            dup_with_bug.add(a)
    changed = set()
    a = runs.latest_artifact(run_id, "changed_since_reference")
    if a:
        changed = set(a["data"].get("keys", []))
    return {"dup_with_bug": dup_with_bug, "changed": changed, "tests": tree.tests_per_asset(run_id)}


def score_node(node: dict, ctx: dict, charter: dict) -> float:
    props = node["props"]
    nid = str(node["id"])
    allowed = charter["perf"]["max_big_o"].get(node["key"], charter["perf"]["max_big_o"].get("default"))
    from .tools.perf_util import big_o_rank
    worse = bool(props.get("big_o")) and bool(allowed) and big_o_rank(props["big_o"]) > big_o_rank(allowed)
    total = sum(ctx["tests"].values())
    return asset_priority(props, dup_with_bug=nid in ctx["dup_with_bug"], changed=node["key"] in ctx["changed"],
                          worse_big_o=worse, n_tests=ctx["tests"].get(nid, 0), total_tests=total)
