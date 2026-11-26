"""Helpers shared by the tools that run things in the sandbox."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from ..guards import scope as scope_guard
from ..runners import sandbox
from ..store import assets, runs


def charter(run_id: str) -> dict:
    return runs.get_run(run_id)["charter"]


def pkg_rel(ch: dict) -> str:
    """Package directory relative to the repo root (handles src/ layout)."""
    from .map import package_dir
    t = ch["target"]
    repo = Path(t["repo_path"])
    pkg = package_dir(repo, t["package"]) if t.get("package") else None
    return pkg.relative_to(repo).as_posix() if pkg else "."


def run_cmd(run_id: str, cmd, timeout: int | None = None, role: str = "bench", env: dict | None = None):
    return sandbox.run(run_id, cmd, timeout=timeout, role=role, env=env)


def run_to_json(run_id: str, cmd: str, timeout: int | None = None, role: str = "bench", env: dict | None = None,
                out: str | None = None):
    """Run `cmd` which writes JSON to $OUT. Returns (ExecResult, json_text|None)."""
    out = out or f"/work/out/{uuid.uuid4().hex[:8]}.json"
    res = sandbox.run(run_id, cmd.replace("$OUT", out), timeout=timeout, role=role, env=env)
    return res, sandbox.read_file(sandbox.get(run_id, role), out)


def attach_asset(run_id: str, file: str, line: int) -> dict | None:
    fn = assets.enclosing_function(run_id, file, line)
    if fn:
        return fn
    from ..store.db import q1
    return q1("SELECT * FROM asset_node WHERE run_id=%s AND type='module' AND props->>'file'=%s", (run_id, file))


def file_in_scope(ch: dict, file: str) -> bool:
    return scope_guard.in_scope(ch["scope"], scope_guard.python_candidates(None, file))


def refresh_issue_counts(run_id: str) -> None:
    from ..store.db import q
    q("""UPDATE asset_node a SET props = props || jsonb_build_object('static_issues_count', c.n)
         FROM (SELECT asset_id, count(*) AS n FROM finding WHERE run_id=%s AND kind='static_issue'
               AND duplicate_of IS NULL AND asset_id IS NOT NULL GROUP BY asset_id) c WHERE a.id=c.asset_id""", (run_id,))


def tail(s: str, n: int = 600) -> str:
    return s[-n:] if s else ""
