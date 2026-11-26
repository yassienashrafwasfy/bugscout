"""Phase 3 acceptance: sample_lib yields complexity, a ruff/mypy finding, a duplicate group, a dead-code node."""
import pytest

from conftest import lib_charter
from helpers import Host
from bugscout.store import assets, findings, runs

pytestmark = [pytest.mark.docker, pytest.mark.integration]


async def test_static_stage_on_sample_lib(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        try:
            await h.call("scan_python_code", run_id=rid)
            for t in ("run_radon", "run_ruff", "run_mypy", "run_bandit", "run_duplication", "run_vulture"):
                r = await h.call(t, run_id=rid)
                assert r["status"] == "ok", (t, r)

            # complexity on function nodes; region_tax is rank D
            tax = assets.get_by_key(rid, "samplelib.rates:region_tax")
            assert tax["props"]["complexity"] >= 21 and tax["props"]["complexity_rank"] == "D"
            assert assets.get_by_key(rid, "samplelib.stats:mean")["props"]["complexity"] == 1
            assert "maintainability" in assets.get_by_key(rid, "samplelib.perf")["props"]

            fs = findings.list_findings(rid)
            by = lambda o: [f for f in fs if f["oracle"] == o]
            assert by("radon") and any("region_tax" in f["title"] for f in by("radon"))
            assert by("ruff"), "expected at least one ruff finding"
            mypy = by("mypy")
            assert mypy and mypy[0]["asset_key"] == "samplelib.typed:total_label"      # attached to enclosing function
            bandit = by("bandit")
            assert any(f["severity"] == "high" for f in bandit)                       # shell=True (B602) high/high
            assert any("eval" in f["title"] or "B307" in f["title"] for f in bandit)

            # duplicate group: invoice_share <-> invoice_share_copy
            a = assets.get_by_key(rid, "samplelib.billing:invoice_share")
            b = assets.get_by_key(rid, "samplelib.invoices:invoice_share_copy")
            assert a["props"].get("dup_group") and a["props"]["dup_group"] == b["props"]["dup_group"]
            assert b["key"] in [n["key"] for n in assets.edges_of(rid, str(a["id"]), "duplicate_of") + assets.edges_of(rid, str(a["id"]), "duplicate_of", "in")]
            assert runs.latest_artifact(rid, "duplication")["data"]["duplication_pct"] > 0

            # dead code: low confidence -> candidate (still tested) + needs_confirmation finding; confirm -> is_dead
            dead = assets.get_by_key(rid, "samplelib.legacy:legacy_format")
            assert dead["props"]["dead_candidate"] is True and not dead["props"].get("is_dead")
            cf = [f for f in by("vulture") if f["asset_key"] == dead["key"]][0]
            assert cf["kind"] == "cleanup" and cf["status"] == "needs_confirmation"
            await h.call("confirm_finding", run_id=rid, finding_id=str(cf["id"]), confirmed=True)
            assert assets.get_by_key(rid, dead["key"])["props"]["is_dead"] is True

            # re-running a static tool is idempotent (fingerprints bump occurrences, no pile-up)
            n_before = findings.count(rid)
            await h.call("run_ruff", run_id=rid)
            assert findings.count(rid) == n_before
            # bandit high finding escalated for human confirmation (guard 5)
            assert any(e["reason"] == "serious_bug" for e in runs.list_escalations(rid))
        finally:
            await h.call("end_run", run_id=rid)
