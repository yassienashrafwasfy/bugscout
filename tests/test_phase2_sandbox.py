import json
from pathlib import Path

import pytest

from bugscout.models import Charter
from bugscout.runners import sandbox

from conftest import lib_charter

pytestmark = [pytest.mark.docker, pytest.mark.integration]


@pytest.fixture(scope="module")
def bench(fx_lib):
    import uuid
    rid = str(uuid.uuid4())
    info = sandbox.provision(rid, Charter.model_validate(lib_charter(fx_lib)))
    yield rid, info
    sandbox.destroy_run(rid)


def test_pytest_json_inside_container(bench):
    rid, _ = bench
    r = sandbox.run(rid, "python -m pytest tests/test_basic.py -p no:randomly -p no:cacheprovider --benchmark-disable "
                         "-q --json-report --json-report-file=/work/out/pytest.json", timeout=120)
    raw = sandbox.read_file(sandbox.get(rid), "/work/out/pytest.json")
    assert raw, r.stderr
    rep = json.loads(raw)
    assert rep["summary"]["passed"] >= 8 and rep["summary"]["total"] == len(rep["tests"])


def test_no_network_and_limits(bench):
    rid, _ = bench
    r = sandbox.run(rid, ["python", "-c", "import socket; socket.create_connection(('1.1.1.1', 53), 2)"])
    assert r.code != 0                                    # network_mode=none
    c = sandbox.get(rid)
    c.reload()
    assert c.attrs["HostConfig"]["Memory"] > 0 and c.attrs["HostConfig"]["NanoCpus"] > 0
    assert c.attrs["HostConfig"]["NetworkMode"] == "none"


def test_timeout_enforced(bench):
    rid, _ = bench
    r = sandbox.run(rid, ["sleep", "30"], timeout=2)
    assert r.timed_out and r.seconds < 10


def test_reset_restores_repo(bench, fx_lib):
    rid, _ = bench
    sandbox.run(rid, "echo junk > samplelib/junk.py")
    sandbox.reset(rid, fx_lib)
    assert sandbox.run(rid, "ls samplelib/junk.py").code != 0
    assert sandbox.run(rid, "ls samplelib/stats.py").code == 0


def test_runs_as_non_root(bench):
    rid, _ = bench
    assert sandbox.run(rid, "id -u").stdout.strip() == "1000"
