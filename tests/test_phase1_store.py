import psycopg
import pytest

from bugscout.store import assets, findings, runs, tree

pytestmark = pytest.mark.integration

CH = {"target": {"kind": "python", "repo_path": "/tmp/x", "package": "p"}}


def _run():
    from bugscout.models import Charter
    return str(runs.create_run(Charter.model_validate(CH).model_dump())["id"])


def test_run_roundtrip_and_budget():
    rid = _run()
    assert runs.get_run(rid)["status"] == "active"
    runs.bump_budget(rid, steps=2, requests=3, seconds=1.5)
    b = runs.bump_budget(rid, steps=1)
    assert b["steps"] == 3 and b["requests"] == 3 and b["seconds"] == 1.5


def test_asset_upsert_merges_props_and_edges():
    rid = _run()
    a = assets.upsert_node(rid, "function", "p.m:f", "f", {"complexity": 3})
    a2 = assets.upsert_node(rid, "function", "p.m:f", None, {"coverage_branch": 0.5})
    assert a["id"] == a2["id"] and a2["props"] == {"complexity": 3, "coverage_branch": 0.5}
    b = assets.upsert_node(rid, "function", "p.m:g")
    assets.add_edge(rid, a["id"], b["id"], "calls")
    assets.add_edge(rid, a["id"], b["id"], "calls")  # idempotent
    assert [n["key"] for n in assets.edges_of(rid, a["id"], "calls")] == ["p.m:g"]


def test_tree_append_only():
    rid = _run()
    n = tree.add_node(rid, "idea", "t")
    tree.update(n["id"], status="done", result={"v": 1}, priority=0.4, flaky_score=0.2)
    with pytest.raises(psycopg.errors.RaiseException):
        from bugscout.store.db import q
        q("UPDATE expl_node SET title='changed' WHERE id=%s", (n["id"],))
    assert tree.get_node(n["id"])["title"] == "t"


def test_subtree_and_frontier():
    rid = _run()
    g = tree.add_node(rid, "goal", "g", status="in_progress")
    i1 = tree.add_node(rid, "idea", "i1", parent_id=g["id"], priority=0.9)
    tree.add_node(rid, "idea", "i2", parent_id=i1["id"], priority=0.1)
    assert [r["title"] for r in tree.subtree(g["id"])] == ["g", "i1", "i2"]
    assert [r["title"] for r in tree.frontier(rid)] == ["i1", "i2"]


def test_findings_fingerprint_dedup():
    rid = _run()
    f, created = findings.add_static_finding_once(rid, "static_issue", "ruff", "low", "x", None, "fp1")
    f2, created2 = findings.add_static_finding_once(rid, "static_issue", "ruff", "low", "x", None, "fp1")
    assert created and not created2 and f2["occurrences"] == 2 and f["id"] == f2["id"]


def test_event_log_append_only():
    rid = _run()
    runs.log_event(rid, "t", {"a": 1}, "ok", 5)
    from bugscout.store.db import q
    with pytest.raises(psycopg.errors.RaiseException):
        q("UPDATE event_log SET tool='x' WHERE run_id=%s", (rid,))
