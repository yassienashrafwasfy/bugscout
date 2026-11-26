"""Build a throwaway git repo with TWO commits for differential / perf-regression tests.

    commit 1 (HEAD~1): current/ with v1_overrides/ laid over it  -> previous, clean version
    commit 2 (HEAD)  : current/                                   -> latest, contains the planted regressions

Usage:  python examples/build_fixture.py sample_lib /tmp/some_dir      (also importable: build())
For sample_api an openapi.json is generated (needs fastapi installed) and committed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=f@x", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)


def _write_openapi(dest: Path) -> None:
    code = ("import json,sys; sys.path.insert(0,'.'); from app import app; print(json.dumps(app.openapi(), indent=1))")
    out = subprocess.run([sys.executable, "-c", code], cwd=dest, check=True, capture_output=True, text=True).stdout
    (dest / "openapi.json").write_text(out)


def build(name: str, dest: str | Path | None = None) -> Path:
    src = HERE / name
    dest = Path(dest) if dest else Path(tempfile.mkdtemp(prefix=f"fixture_{name}_"))
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _git(dest, "init", "-q", "-b", "main")
    shutil.copytree(src / "current", dest, dirs_exist_ok=True)
    shutil.copytree(src / "v1_overrides", dest, dirs_exist_ok=True)   # previous version
    if name == "sample_api":
        _write_openapi(dest)
    _git(dest, "add", "-A"); _git(dest, "commit", "-qm", "v1: previous version")
    shutil.copytree(src / "current", dest, dirs_exist_ok=True)         # latest version
    if name == "sample_api":
        _write_openapi(dest)
    (dest / "CHANGELOG.md").write_text("v2: latest changes (contains planted regressions)\n")
    _git(dest, "add", "-A"); _git(dest, "commit", "-qm", "v2: latest version")
    return dest


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
