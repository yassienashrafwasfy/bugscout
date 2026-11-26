import os
import psycopg
import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://test:test@localhost:5432/bugscout_test")
os.environ["DATABASE_URL"] = TEST_DB
os.environ.setdefault("BUGSCOUT_PROVISION", "0")

from bugscout import config  # noqa: E402
from bugscout.store import db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Fresh schema in the throwaway bugscout_test database."""
    try:
        with psycopg.connect(TEST_DB, autocommit=True, connect_timeout=3) as c:
            c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    except Exception as e:  # no Postgres -> integration tests skip
        pytest.skip(f"postgres unavailable: {e}", allow_module_level=False)
    config.DATABASE_URL = TEST_DB
    db.migrate(TEST_DB)
    db.init_pool(TEST_DB)
    yield
    db.close_pool()


# ---- fixtures: throwaway git repos with two commits (previous clean version + latest with planted regressions)
import importlib.util  # noqa: E402
import pathlib  # noqa: E402

_spec = importlib.util.spec_from_file_location("build_fixture", pathlib.Path(__file__).resolve().parents[1] / "examples" / "build_fixture.py")
build_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_fixture)


@pytest.fixture(scope="session")
def fx_lib(tmp_path_factory):
    return str(build_fixture.build("sample_lib", tmp_path_factory.mktemp("fx") / "sample_lib"))


@pytest.fixture(scope="session")
def fx_api(tmp_path_factory):
    return str(build_fixture.build("sample_api", tmp_path_factory.mktemp("fx") / "sample_api"))


LIB_CHARTER = {
    "target": {"kind": "python", "repo_path": "", "package": "samplelib"},
    "scope": {"include": ["samplelib/*", "samplelib.*"], "exclude": []},
    "objective": "find bugs in samplelib",
    "oracles": ["crash", "diff_git", "rule"],
    "rules": [{"name": "balance_non_negative", "target": "samplelib.accounts:withdraw",
               "property": "result['balance'] >= 0", "assume": "balance >= 0 and 0 < amount < 1e9"}],
    "reference": {"git_ref": "HEAD~1"},
    "perf": {"max_big_o": {"default": "O(n log n)", "samplelib.perf:find_duplicates": "O(n log n)"}, "max_memory_mb": 512},
}


def lib_charter(repo, **over):
    import copy
    c = copy.deepcopy(LIB_CHARTER)
    c["target"]["repo_path"] = repo
    c.update(over)
    return c


@pytest.fixture(autouse=True)
def _provision_for_docker_tests(request, monkeypatch):
    """Store-only tests skip container creation; tests marked `docker` provision real sandboxes."""
    monkeypatch.setattr(config, "PROVISION", request.node.get_closest_marker("docker") is not None)


@pytest.fixture(scope="session")
def fx_vuln(tmp_path_factory):
    return str(build_fixture.build("sample_vuln_api", tmp_path_factory.mktemp("fx") / "sample_vuln_api"))


def vuln_charter(repo, **over):
    c = {"target": {"kind": "rest_api", "repo_path": repo, "openapi": "openapi.json", "base_url": "http://sut:8000",
                    "start_cmd": "uvicorn app:app --host 0.0.0.0"},
         "scope": {"include": ["/*"], "exclude": [], "allowed_hosts": ["sut"]}, "oracles": ["crash", "schema"],
         "budget": {"max_steps": 400, "max_requests": 2000, "max_minutes": 60},
         "security": {"tokens": {"alice": "Bearer alice-token", "bob": "Bearer bob-token"},
                      "owned": {"alice": {"/users/{user_id}/profile": [1]}, "bob": {"/users/{user_id}/profile": [2]}}}}
    c.update(over)
    return c
