"""Security probes against sample_vuln_api (real sut container): every planted issue is found by its tool, the clean endpoints are not
flagged, record_bug replays the evidence, and the guards still apply."""
import pytest

from conftest import vuln_charter
from helpers import Host
from bugscout.store import findings, runs, tree

pytestmark = [pytest.mark.docker, pytest.mark.integration]


def by(cands):
    return {(c["class"], c["endpoint"]) for c in cands}


async def test_probes_find_every_planted_vulnerability_and_nothing_else(fx_vuln):
    async with Host() as h:
        rid = await h.start(vuln_charter(fx_vuln))
        try:
            assert (await h.call("import_openapi", run_id=rid))["status"] == "ok"

            inj = await h.call("probe_injection", run_id=rid)
            assert inj["status"] == "ok", inj
            assert by(inj["data"]["candidates"]) == {("sqli", "GET /search"), ("path_traversal", "GET /files"),
                                                     ("cmd_injection", "GET /ping"), ("xss", "GET /hello")}, inj["data"]
            # /echo reflects JSON only and must stay clean; no candidate may point at it
            assert not [c for c in inj["data"]["candidates"] if "/echo" in c["endpoint"]]
            assert inj["data"]["requests_sent"] == 5 * 10                 # 5 string params (4 planted + the clean /echo) x (control + 9 corpus payloads)

            az = await h.call("probe_authz", run_id=rid)
            assert by(az["data"]["candidates"]) == {("missing_auth", "GET /admin/users"), ("bola", "GET /users/{user_id}/profile")}, az["data"]
            assert not [c for c in az["data"]["candidates"] if c["endpoint"] == "GET /me"]       # /me really checks the token
            bola = [c for c in az["data"]["candidates"] if c["class"] == "bola"]
            assert len(bola) == 2 and {"bob read alice", "alice read bob"} <= {c["evidence"][:14] for c in bola}

            hd = await h.call("probe_http_hardening", run_id=rid)
            assert {c["class"] for c in hd["data"]["candidates"]} == {"headers", "cors"}, hd["data"]

            used = runs.get_run(rid)["budget_used"]["requests"]
            assert used == inj["data"]["requests_sent"] + az["data"]["requests_sent"] + hd["data"]["requests_sent"]   # budget is counted
        finally:
            await h.call("end_run", run_id=rid)


async def test_record_bug_replays_security_evidence_and_escalates_serious(fx_vuln):
    async with Host() as h:
        rid = await h.start(vuln_charter(fx_vuln))
        try:
            await h.call("import_openapi", run_id=rid)
            cands = (await h.call("probe_injection", run_id=rid, endpoints=["GET /search"]))["data"]["candidates"]
            assert [c["class"] for c in cands] == ["sqli"]
            r = await h.call("record_bug", run_id=rid, expl_node_id=cands[0]["expl_node_id"], oracle="security", severity="high",
                             title=cands[0]["title"])
            assert r["status"] == "ok" and r["data"].get("recorded") is not False, r
            f = [x for x in findings.list_findings(rid) if x["oracle"] == "security"]
            assert len(f) == 1 and f[0]["status"] == "needs_confirmation"            # high -> a human must confirm
            esc = await h.call("get_escalations", run_id=rid)
            assert any(e["reason"] == "serious_bug" for e in esc["data"]["escalations"])
            # the same finding again is a duplicate, not a second row
            n = await h.call("probe_injection", run_id=rid, endpoints=["GET /search"])
            dup = await h.call("record_bug", run_id=rid, expl_node_id=n["data"]["candidates"][0]["expl_node_id"], oracle="security",
                               severity="high", title="again")
            assert dup["data"].get("duplicate") is True and len([x for x in findings.list_findings(rid) if x["oracle"] == "security"]) == 1

            # a made-up claim that the server does not support is NOT recorded: it is replayed first
            node = tree.get_node(cands[0]["expl_node_id"])
            fake = {"kind": "http", "method": "GET", "path": "/echo?text=hi", "headers": {}, "check": "security",
                    "expect": {"body_contains": "sqlite3."}}
            bad = await h.call("record_bug", run_id=rid, expl_node_id=str(node["id"]), oracle="security", severity="medium",
                               title="invented", repro=fake)
            assert bad["data"].get("recorded") is False and bad["data"].get("flaky") is True, bad
        finally:
            await h.call("end_run", run_id=rid)


async def test_probes_respect_scope_methods_and_budget(fx_vuln):
    async with Host() as h:
        # scope: only /search and /health are in scope -> nothing else is touched
        rid = await h.start(vuln_charter(fx_vuln, scope={"include": ["/search", "/health"], "exclude": [], "allowed_hosts": ["sut"]}))
        try:
            await h.call("import_openapi", run_id=rid)
            inj = await h.call("probe_injection", run_id=rid)
            assert {c["endpoint"] for c in inj["data"]["candidates"]} == {"GET /search"} and inj["data"]["requests_sent"] == 10
        finally:
            await h.call("end_run", run_id=rid)
        # a host outside allowed_hosts is refused by the guard before any request leaves
        rid = await h.start(vuln_charter(fx_vuln, scope={"include": ["/*"], "exclude": [], "allowed_hosts": ["somewhere-else"]}))
        try:
            await h.call("import_openapi", run_id=rid)
            r = await h.call("probe_injection", run_id=rid)
            assert r["status"] == "escalation_required", r
            assert runs.get_run(rid)["budget_used"].get("requests", 0) == 0
        finally:
            await h.call("end_run", run_id=rid)
        # request cap: max_probe_requests=15 allows only one parameter's ten requests
        rid = await h.start(vuln_charter(fx_vuln, security={"max_probe_requests": 15}))
        try:
            await h.call("import_openapi", run_id=rid)
            r = await h.call("probe_injection", run_id=rid)
            assert r["data"]["requests_sent"] == 10 and any("request cap" in s for s in r["data"]["skipped"]), r["data"]
        finally:
            await h.call("end_run", run_id=rid)
