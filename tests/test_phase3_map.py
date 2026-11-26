"""Phase 3 (host-side part): ast scan + OpenAPI import. Static tools in test_phase3_static.py (docker)."""
import pytest

from conftest import lib_charter
from helpers import Host

pytestmark = pytest.mark.integration


async def test_scan_python_code_builds_graph(fx_lib):
    async with Host() as h:
        rid = await h.start(lib_charter(fx_lib))
        r = await h.call("scan_python_code", run_id=rid)
        assert r["status"] == "ok", r
        assert r["data"]["function"] >= 15 and r["data"]["module"] >= 10
        from bugscout.store import assets
        mean = assets.get_by_key(rid, "samplelib.stats:mean")
        assert mean["props"]["signature"] == "mean(values: list[float]) -> float"
        assert mean["props"]["has_type_hints"] is True
        # calls edge: run_pipeline -> _crunch
        callees = {n["key"] for n in assets.edges_of(rid, str(assets.get_by_key(rid, "samplelib.perf:run_pipeline")["id"]), "calls")}
        assert {"samplelib.perf:_crunch", "samplelib.perf:_light"} <= callees
        assert assets.edges_of(rid, str(assets.get_by_key(rid, "samplelib.stats")["id"]), "contains")


async def test_import_openapi(fx_api):
    ch = {"target": {"kind": "rest_api", "repo_path": fx_api, "openapi": "openapi.json", "start_cmd": "uvicorn app:app --host 0.0.0.0",
                     "base_url": "http://sut:8000"},
          "scope": {"include": ["/items/*", "/orders/*", "/health"], "exclude": [], "allowed_hosts": ["sut"]}}
    async with Host() as h:
        rid = await h.start(ch)
        r = await h.call("import_openapi", run_id=rid)
        assert r["status"] == "ok", r
        from bugscout.store import assets
        keys = {n["key"] for n in assets.list_nodes(rid, "endpoint")}
        assert {"GET /items/{item_id}", "DELETE /items/{item_id}", "GET /orders/{order_id}", "GET /health"} <= keys
        ep = assets.get_by_key(rid, "GET /items/{item_id}")
        assert ep["props"]["params"][0]["name"] == "item_id"
        assert "200" in ep["props"]["responses"]
        assert assets.get_by_key(rid, "schema:Order")["props"]["schema"]["required"] == ["id", "total", "status"]
