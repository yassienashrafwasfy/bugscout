"""Phase 7 acceptance: O(n^2) detected vs allowed O(n log n); planted slowdown flagged; hotspot on top; memory hog over the limit;
stable across 3 repeated runs."""
import pytest

from conftest import lib_charter
from helpers import Host
from bugscout.store import assets, findings
from bugscout.store.db import q

pytestmark = [pytest.mark.docker, pytest.mark.integration]

PERF = {"max_big_o": {"default": "O(n log n)"}, "max_memory_mb": 512, "max_seconds_per_call": 25, "regression_threshold": 0.2, "hotspot_pct": 30}


async def test_sample_lib_perf(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, perf=PERF))
        try:
            await h.call("scan_python_code", run_id=rid)
            dup = assets.get_by_key(rid, "samplelib.perf:find_duplicates")
            mean = assets.get_by_key(rid, "samplelib.stats:mean")

            # --- time complexity: auto input from the list[int] hint, default sizes, capped by max_seconds_per_call
            r = await h.call("measure_time_complexity", run_id=rid, target_asset_id=str(dup["id"]))
            assert r["status"] == "ok", r
            assert r["data"]["big_o"] == "O(n^2)" and not r["data"]["uncertain"] and r["data"]["finding_id"], r
            # linear function stays within the allowed bound -> no finding
            m = await h.call("measure_time_complexity", run_id=rid, target_asset_id=str(mean["id"]),
                             input_generator="import random\ndef gen(n):\n    return [random.random() for _ in range(n)]\n")
            assert m["data"]["finding_id"] is None, m
            # stable across 3 repeated runs
            seen = {r["data"]["big_o"]}
            for _ in range(2):
                again = await h.call("measure_time_complexity", run_id=rid, target_asset_id=str(dup["id"]), sizes=[200, 400, 800, 1600, 3200, 6400])
                seen.add(again["data"]["big_o"])
            assert seen == {"O(n^2)"}, seen
            assert len([f for f in findings.list_findings(rid) if f["oracle"] == "complexity"]) == 1      # deduped
            assert assets.get_by_key(rid, dup["key"])["props"]["worse_than_allowed_big_o"] is True
            # no generator possible -> a helpful error, not a guess
            bad = await h.call("measure_time_complexity", run_id=rid, target_asset_id=str(assets.get_by_key(rid, "samplelib.accounts:withdraw")["id"]))
            assert bad["status"] == "error"

            # --- benchmark + regression vs HEAD~1
            b = await h.call("run_benchmark", run_id=rid)
            assert b["data"]["results"][0]["target"] == "samplelib.perf:checksum" and b["data"]["results"][0]["median_ms"] > 0
            assert assets.get_by_key(rid, "samplelib.perf:checksum")["props"]["runtime_ms_p95"] > 0
            c = await h.call("compare_benchmark_with_git_version", run_id=rid)
            assert c["status"] == "ok" and "1 perf regression" in c["summary"], c
            row = c["data"]["results"][0]
            assert row["regression"] and row["median_ratio"] > 1.5 and len(row["ratios"]) == 3 and all(x > 1.2 for x in row["ratios"]), row
            pr = [f for f in findings.list_findings(rid) if f["oracle"] == "perf_regression"]
            assert len(pr) == 1 and "checksum" in pr[0]["title"]
            c2 = await h.call("compare_benchmark_with_git_version", run_id=rid)       # re-run: deduped, still one finding
            assert len([f for f in findings.list_findings(rid) if f["oracle"] == "perf_regression"]) == 1

            # --- CPU hotspot (3 runs, same top function)
            tops = []
            for _ in range(3):
                p = await h.call("profile_cpu", run_id=rid, target={"call": "samplelib.perf:run_pipeline"})
                assert p["status"] == "ok", p
                tops.append(p["data"]["top"][0])
            assert {t["function"] for t in tops} == {"_crunch"} and all(t["self_pct"] > 80 for t in tops), tops
            assert assets.get_by_key(rid, "samplelib.perf:_crunch")["props"]["profile_self_pct"] > 80
            assert any(f["oracle"] == "hotspot" for f in findings.list_findings(rid))
            assert any("investigate hotspot samplelib.perf:_crunch" in n["title"] for n in q("SELECT title FROM expl_node WHERE run_id=%s AND kind='idea'", (rid,)))

            # --- memory hog
            mem = await h.call("profile_memory", run_id=rid, target={"call": "samplelib.perf:build_table"})
            assert mem["status"] == "ok", mem
            assert mem["data"]["peak_mb"] > 512 and mem["data"]["finding_id"], mem
            assert assets.get_by_key(rid, "samplelib.perf:build_table")["props"]["peak_memory_mb"] > 512
            small = await h.call("profile_memory", run_id=rid, target={"call": "samplelib.perf:build_table", "kwargs": {"rows": 1000}})
            assert small["data"]["peak_mb"] < 512 and small["data"]["finding_id"] is None

            # --- report mentions all of it
            md = (await h.call("get_report", run_id=rid))["data"]["markdown"]
            assert "O(n^2)" in md and "perf_regression" in md.lower().replace(" ", "_") or "slower" in md
            assert "_crunch" in md and "build_table" in md
        finally:
            await h.call("end_run", run_id=rid)


async def test_no_false_regression_against_same_code(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib, perf=PERF, reference={"git_ref": "HEAD"}))
        try:
            await h.call("scan_python_code", run_id=rid)
            c = await h.call("compare_benchmark_with_git_version", run_id=rid)
            assert c["status"] == "ok" and "no perf regression" in c["summary"], c
            assert not [f for f in findings.list_findings(rid) if f["oracle"] == "perf_regression"]
        finally:
            await h.call("end_run", run_id=rid)


async def test_profile_api(fx_api):
    from test_phase5_oracles import API_CH
    async with Host() as h:
        rid = await h.start(API_CH(fx_api))
        try:
            await h.call("import_openapi", run_id=rid)
            assert (await h.call("profile_api", run_id=rid, endpoint="DELETE /items/1"))["status"] in ("error", "escalation_required")     # GET only (guard fires first)
            assert (await h.call("profile_api", run_id=rid, endpoint="/admin/x"))["status"] == "escalation_required"  # scope guard
            p = await h.call("profile_api", run_id=rid, endpoint="/items/1", n_requests=150)
            assert p["status"] == "ok", p
            assert p["data"]["load"]["errors"] == 0 and p["data"]["load"]["status_codes"] == {"200": 150} or p["data"]["load"]["status_codes"] == {200: 150}
            assert p["data"]["load"]["p95_ms"] >= p["data"]["load"]["p50_ms"] > 0
            assert p["data"]["hot_frames"], p["data"]            # py-spy sampled the server process
            ep = assets.get_by_key(rid, "GET /items/{item_id}")
            assert ep["props"]["latency_p95_ms"] > 0
            assert int((await h.call("get_status", run_id=rid))["data"]["budget"]["requests"].split("/")[0]) >= 150
        finally:
            await h.call("end_run", run_id=rid)
