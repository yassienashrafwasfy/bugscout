"""Phase 6 acceptance: flaky != bug; 20 fuzz failures -> 1 finding; identical tests -> duplicate; report renders."""
import pytest

from conftest import lib_charter
from helpers import Host
from bugscout.store import assets, findings, runs, tree
from bugscout.store.db import q

pytestmark = [pytest.mark.docker, pytest.mark.integration]


async def test_quality_stage(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, stuck={'window_steps': 99, 'min_progress': 1}))
        try:
            await h.call("scan_python_code", run_id=rid)
            for t in ("run_radon", "run_duplication", "run_vulture"):
                await h.call(t, run_id=rid)
            mean = assets.get_by_key(rid, "samplelib.stats:mean")

            # ---- flaky: marked flaky, never a bug
            FLAKY = "tests/test_basic.py::test_flaky_planted"
            f = await h.call("check_flaky", run_id=rid, test_ids=[FLAKY], n=10)
            res = f["data"]["results"][0]
            assert res["verdict"] == "flaky" and 0 < res["flaky_score"] < 1, res
            assert q("SELECT status FROM test_record WHERE run_id=%s AND test_id=%s", (rid, FLAKY))[0]["status"] == "flaky"
            stable = await h.call("check_flaky", run_id=rid, test_ids=["tests/test_basic.py::test_mean_basic"], n=3)
            assert stable["data"]["results"][0]["verdict"] == "stable_pass"
            # a failure that does not reproduce on rerun becomes flaky instead of a bug
            ghost = tree.add_node(rid, "test", "ghost", status="in_progress", target_asset_id=str(mean["id"]), result={
                "verdict": "fail", "repro": {"kind": "call", "target": "samplelib.stats:mean", "kwargs": {"values": [1, 2]},
                                             "expect_exception": "ZeroDivisionError"}})
            rb = await h.call("record_bug", run_id=rid, expl_node_id=str(ghost["id"]), oracle="crash", severity="medium", title="ghost")
            assert rb["data"]["recorded"] is False and rb["data"]["flaky"] is True
            assert tree.get_node(ghost["id"])["status"] == "flaky" and findings.count(rid) == _static_count(rid)

            # ---- 20 fuzz failures of the same bug collapse into 1 finding with occurrences=20
            hy = await h.call("run_hypothesis", run_id=rid, target_asset_id=str(mean["id"]))
            base = tree.get_node(hy["data"]["expl_node_id"])
            nodes = [str(base["id"])]
            for i in range(19):
                n = tree.add_node(rid, "test", f"fuzz failure {i}", status="in_progress", target_asset_id=str(mean["id"]), result=base["result"])
                nodes.append(str(n["id"]))
            outs = [await h.call("record_bug", run_id=rid, expl_node_id=nid, oracle="crash", severity="medium", title="mean([]) crashes")
                    for nid in nodes]
            assert outs[0]["data"]["recorded"] is True and all(o["data"].get("duplicate") for o in outs[1:])
            bugs = [x for x in findings.list_findings(rid, kind="bug")]
            assert len(bugs) == 1 and bugs[0]["occurrences"] == 20 and bugs[0]["fingerprint"]
            assert tree.get_node(nodes[0])["status"] == "confirmed_bug" and tree.get_node(nodes[5])["status"] == "duplicate"
            # the DRY copy of buggy code is prioritised: record the invoice_share bug, its copy gains priority
            share = assets.get_by_key(rid, "samplelib.billing:invoice_share")
            hy2 = await h.call("run_hypothesis", run_id=rid, target_asset_id=str(share["id"]))
            assert "ZeroDivisionError" in hy2["summary"], hy2
            rb2 = await h.call("record_bug", run_id=rid, expl_node_id=hy2["data"]["expl_node_id"], oracle="crash", severity="low", title="parts=0")
            assert rb2["data"]["recorded"]
            from bugscout import priority
            ctx = priority.asset_context(rid)
            copy = assets.get_by_key(rid, "samplelib.invoices:invoice_share_copy")
            assert str(copy["id"]) in ctx["dup_with_bug"]

            # ---- high severity needs a human
            hi = tree.add_node(rid, "test", "serious", status="in_progress", target_asset_id=str(mean["id"]), result=base["result"])
            r = await h.call("record_bug", run_id=rid, expl_node_id=str(hi["id"]), oracle="rule", severity="high", title="serious one",
                             repro={"kind": "call", "target": "samplelib.stats:mean", "kwargs": {"values": []}, "expect_exception": "ZeroDivisionError"})
            assert r["data"]["needs_confirmation"] is True
            assert findings.get(r["data"]["finding_id"])["status"] == "needs_confirmation"

            # ---- coverage with contexts + dedup of identical tests
            cv = await h.call("run_coverage", run_id=rid)
            assert cv["status"] == "ok" and cv["data"]["tests_with_contexts"] >= 8, cv
            assert assets.get_by_key(rid, "samplelib.stats:mean")["props"]["coverage_branch"] == 1.0
            assert assets.get_by_key(rid, "samplelib.rates:region_tax")["props"]["coverage_branch"] < 0.2
            assert assets.get_by_key(rid, "samplelib.legacy:legacy_format")["props"]["coverage_line"] == 0
            assert runs.latest_artifact(rid, "coverage_summary")["data"]["line_pct"] > 0
            dd = await h.call("dedup_tests", run_id=rid)
            kept = [g for g in dd["data"]["groups"] if "tests/test_basic.py::test_mean_basic" in [g["keep"], *g["duplicates"]]]
            assert kept and set([kept[0]["keep"], *kept[0]["duplicates"]]) >= {"tests/test_basic.py::test_mean_basic",
                                                                                "tests/test_basic.py::test_mean_basic_again"}
            assert q("SELECT status FROM test_record WHERE run_id=%s AND test_id=%s", (rid, "tests/test_basic.py::test_mean_basic_again"))[0]["status"] == "duplicate"
            # priority now uses coverage
            top = (await h.call("get_untested", run_id=rid, limit=30))["data"]["targets"]
            keys = [t["key"] for t in top]
            assert "samplelib.legacy:legacy_format" in keys and "samplelib.stats:mean" not in keys   # uncovered listed, covered not
        finally:
            pass
        # (the finally above intentionally leaves the run for the report/mutation checks below)
        rep = await h.call("get_report", run_id=rid)
        md = rep["data"]["markdown"]
        assert "mean([]) crashes" in md and "occurrences: 20" in md and "test_flaky_planted" in md
        assert "region_tax" in md and "Duplication" in md and "test_mean_basic_again" in md
        # mutation on one small file (flaky + known-failing tests are deselected automatically)
        mu = await h.call("run_mutation", run_id=rid, paths=["samplelib/stats.py"])
        assert mu["status"] == "ok", mu
        assert 0 < mu["data"]["score"] <= 1
        assert "mutation_score" in assets.get_by_key(rid, "samplelib.stats:clamp")["props"]
        end = await h.call("end_run", run_id=rid)
        assert end["status"] == "ok"


def _static_count(rid):
    return len([f for f in findings.list_findings(rid) if f["kind"] != "bug"])


async def test_record_bug_reruns_pytest_diff(fx_lib):
    """A diff_git bug from a pytest comparison is replayed on old+new code before it is recorded."""
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        try:
            await h.call("scan_python_code", run_id=rid)
            disc = assets.get_by_key(rid, "samplelib.rates:apply_discount")
            wt = await h.call("write_test", run_id=rid, target_asset_id=str(disc["id"]),
                              code="from samplelib.rates import apply_discount\n\ndef test_discount_keeps_cents():\n"
                                   "    assert apply_discount(19.99, 10) == 17.99\n")
            d = await h.call("compare_with_git_version", run_id=rid, test_ref={"pytest": wt["data"]["selector"]})
            assert "REGRESSION" in d["summary"], d
            nid = d["data"]["expl_node_id"]
            assert tree.get_node(nid)["result"]["repro"]["kind"] == "pytest_diff"
            rb = await h.call("record_bug", run_id=rid, expl_node_id=nid, oracle="diff_git", severity="medium", title="discount truncates cents")
            assert rb["data"]["recorded"] is True, rb

            # a comparison that shows no difference cannot be recorded: the rerun does not reproduce
            ok_t = await h.call("write_test", run_id=rid, target_asset_id=str(disc["id"]),
                                code="from samplelib.rates import apply_discount\n\ndef test_discount_zero():\n    assert apply_discount(10.0, 0) == 10.0\n")
            fake = tree.add_node(rid, "test", "fake diff", status="in_progress", target_asset_id=str(disc["id"]),
                                 result={"verdict": "fail", "repro": {"kind": "pytest_diff", "selector": ok_t["data"]["selector"]}})
            rb2 = await h.call("record_bug", run_id=rid, expl_node_id=str(fake["id"]), oracle="diff_git", severity="medium", title="not a diff")
            assert rb2["data"]["recorded"] is False and rb2["data"]["flaky"] is True, rb2
        finally:
            await h.call("end_run", run_id=rid)
