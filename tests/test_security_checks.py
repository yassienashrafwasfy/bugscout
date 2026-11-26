"""Security tools without Docker: detectors on canned responses, the secrets scan, the OSV lookup (mocked, never the network)."""
import httpx
import pytest

from helpers import Host
from conftest import vuln_charter
from bugscout import security_checks as sc
from bugscout.store import findings


def resp(text="", status=200, **headers):
    return {"status_code": status, "text": text, "headers": {k.replace("_", "-"): v for k, v in headers.items()}}


# ---------------------------------------------------------------- detectors need positive evidence
def test_sqli_error_and_boolean_detected_but_plain_500_is_not():
    ctl = resp("[]")
    err = sc.analyse_injection({"control": ctl, "sqli_quote": resp("sqlite3.OperationalError: unrecognized token", 500)})
    assert [e["class"] for e in err] == ["sqli"]
    boolean = sc.analyse_injection({"control": ctl, "sqli_true": resp('[{"id":1},{"id":2}]'), "sqli_false": resp("[]")})
    assert boolean[0]["class"] == "sqli" and boolean[0]["expect"]["min_body_len"] == 3
    # a bare 500 or an error the control also shows is not evidence
    assert not sc.analyse_injection({"control": ctl, "sqli_quote": resp("Internal Server Error", 500)})
    assert not sc.analyse_injection({"control": resp("sqlite3.OperationalError"), "sqli_quote": resp("sqlite3.OperationalError", 500)})
    # true == false is not boolean injection
    assert not sc.analyse_injection({"control": ctl, "sqli_true": resp("[]"), "sqli_false": resp("[]")})


def test_traversal_cmd_xss_and_trace_detectors():
    ctl = resp("hello")
    out = sc.analyse_injection({"control": ctl, "traversal_0": resp("root:x:0:0:root:/root:/bin/bash\n"),
                                "cmd_1": resp("pinging \n9359\n"),
                                "xss": resp("<h1><bscout7f3a></h1>", content_type="text/html; charset=utf-8")})
    assert {e["class"] for e in out} == {"path_traversal", "cmd_injection", "xss"}
    # the payload echoed back (no execution) and JSON reflection are not findings
    echo = sc.analyse_injection({"control": ctl, "cmd_0": resp(";echo $((1337*7))"),
                                 "xss": resp('{"text":"<bscout7f3a>"}', content_type="application/json")})
    assert echo == []
    leak = sc.analyse_injection({"control": ctl, "sqli_quote": resp("Traceback (most recent call last):\n  File", 500)})
    assert [e["class"] for e in leak] == ["info_leak"]


def test_headers_and_cors_analysis():
    assert sc.analyse_headers(resp("{}", content_type="application/json"))["expect"] == {"header_absent": ["x-content-type-options"]}
    assert sc.analyse_headers(resp("{}", content_type="application/json", x_content_type_options="nosniff")) is None
    html = sc.analyse_headers(resp("<p>", content_type="text/html", x_content_type_options="nosniff"))
    assert "content-security-policy" in html["evidence"]
    assert sc.analyse_cors(resp(access_control_allow_origin=sc.EVIL_ORIGIN))["class"] == "cors"
    assert sc.analyse_cors(resp(access_control_allow_origin="*", access_control_allow_credentials="true"))
    assert sc.analyse_cors(resp(access_control_allow_origin="*")) is None      # public wildcard without credentials is fine
    assert sc.analyse_cors(resp()) is None


def test_eval_expect_requires_every_condition():
    r = resp("root:x:0:0:", 200, content_type="text/html")
    assert sc.eval_expect(r, {"body_regex": sc.PASSWD, "status_in": [200]})[0]
    assert not sc.eval_expect(r, {"body_regex": sc.PASSWD, "status_in": [404]})[0]
    assert not sc.eval_expect(r, {})[0]                                      # an empty expectation proves nothing
    assert sc.eval_expect(r, {"header_absent": ["x-frame-options"]})[0]


def test_payload_corpus_is_fixed():
    assert sc.CORPUS_VERSION == "1" and len(sc.PAYLOADS) == 9
    assert sc.CALC_RESULT == str(1337 * 7)


# ---------------------------------------------------------------- secrets
def test_secret_patterns_and_placeholders():
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    gh = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    text = "\n".join([f'aws = "{key}"', f"GITHUB = '{gh}'", 'DB_PASSWORD = "Sup3r-S3cret-Pass-2024"',
                      "url = 'postgres://admin:hunter22pass@db.internal/app'", "-----BEGIN RSA PRIVATE KEY-----",
                      'password = "changeme"', 'api_key = "xxxxxxxxxx"', 'token = os.environ["TOKEN"]', 'TOKENS = {"alice-token": 1}',
                      'password = ""', '# password = "short"'])
    names = {h["name"] for h in sc.scan_text(text)}
    assert names == {"AWS access key id", "GitHub token", "hardcoded secret", "credentials in URL", "private key"}, names
    assert all(key not in h["snippet"] and gh not in h["snippet"] for h in sc.scan_text(text))      # redacted


async def test_run_secrets_scan_finds_planted_secret_and_history(fx_vuln, tmp_path):
    async with Host() as h:
        rid = await h.start(vuln_charter(fx_vuln))
        r = await h.call("run_secrets_scan", run_id=rid)
        assert r["status"] == "ok" and r["data"]["working_tree"] == 1, r
        f = [x for x in findings.list_findings(rid) if x["oracle"] == "secrets"]
        assert len(f) == 1 and "DB_PASSWORD" in f[0]["title"] and "Sup3r-S3cret-Pass-2024" not in f[0]["title"]
        again = await h.call("run_secrets_scan", run_id=rid)               # re-running does not pile up rows
        assert again["data"]["new_findings"] == 0


async def test_secret_removed_from_head_is_still_reported_from_history(tmp_path):
    import subprocess
    repo = tmp_path / "r"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x", *a], cwd=repo, check=True, capture_output=True)
    git("init", "-q")
    (repo / "app.py").write_text('SECRET_KEY = "r4nd0m-h1storic-v4lue"\n')
    git("add", "-A"); git("commit", "-qm", "add")
    (repo / "app.py").write_text("import os\nSECRET_KEY = os.environ['SECRET_KEY']\n")
    git("add", "-A"); git("commit", "-qm", "fix")
    async with Host() as h:
        rid = await h.start({"target": {"kind": "rest_api", "repo_path": str(repo), "openapi": "o.json", "start_cmd": "x"}})
        r = await h.call("run_secrets_scan", run_id=rid)
        assert r["data"]["working_tree"] == 0 and r["data"]["history_only"] == 1, r


# ---------------------------------------------------------------- dependencies (OSV is mocked)
def _osv(monkeypatch, handler):
    from bugscout.tools import security
    monkeypatch.setattr(security, "_osv_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


async def test_pip_audit_is_off_unless_the_owner_opts_in(fx_vuln, tmp_path, monkeypatch):
    called = []
    _osv(monkeypatch, lambda req: called.append(req) or httpx.Response(500))
    (tmp_path / "requirements.txt").write_text("pyyaml==5.3\n")
    async with Host() as h:
        rid = await h.start({"target": {"kind": "rest_api", "repo_path": str(tmp_path), "openapi": "o.json", "start_cmd": "x"}})
        r = await h.call("run_pip_audit", run_id=rid)
        assert r["data"] == {"skipped": True} and "osv_lookup" in r["summary"] and not called   # nothing left the machine


async def test_pip_audit_records_advisories(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("pyyaml==5.3  # pinned\nrequests>=2\nflask[async]==2.0.0\n")

    def handler(req: httpx.Request):
        if req.url.path.endswith("/querybatch"):
            qs = [(q["package"]["name"], q["version"]) for q in __import__("json").loads(req.content)["queries"]]
            assert qs == [("flask", "2.0.0"), ("pyyaml", "5.3")]            # only pinned packages, normalised names
            return httpx.Response(200, json={"results": [{}, {"vulns": [{"id": "GHSA-test-1"}]}]})
        assert req.url.path.endswith("/vulns/GHSA-test-1")
        return httpx.Response(200, json={"id": "GHSA-test-1", "summary": "arbitrary code execution", "database_specific": {"severity": "CRITICAL"},
                                         "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "5.4"}]}]}]})
    _osv(monkeypatch, handler)
    async with Host() as h:
        rid = await h.start({"target": {"kind": "rest_api", "repo_path": str(tmp_path), "openapi": "o.json", "start_cmd": "x"},
                             "security": {"osv_lookup": True}})
        r = await h.call("run_pip_audit", run_id=rid)
        assert r["data"]["advisories"] == 1 and r["data"]["new_findings"] == 1 and r["data"]["serious_escalations"], r
        f = [x for x in findings.list_findings(rid) if x["oracle"] == "dependency"][0]
        assert f["severity"] == "critical" and "pyyaml 5.3" in f["title"] and "fixed in 5.4" in f["title"]
        assert f["status"] == "needs_confirmation"                          # critical needs a human


async def test_osv_failure_is_reported_not_raised(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("pyyaml==5.3\n")
    _osv(monkeypatch, lambda req: httpx.Response(503))
    async with Host() as h:
        rid = await h.start({"target": {"kind": "rest_api", "repo_path": str(tmp_path), "openapi": "o.json", "start_cmd": "x"},
                             "security": {"osv_lookup": True}})
        r = await h.call("run_pip_audit", run_id=rid)
        assert r["status"] == "error" and "OSV" in r["summary"]
