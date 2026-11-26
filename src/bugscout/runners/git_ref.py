"""Reference version of the target (previous git commit) as a cached git worktree + a container holding it."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import git

from ..store import assets
from . import sandbox


def _repo(repo_path: str) -> tuple[git.Repo, Path]:
    repo = git.Repo(repo_path, search_parent_directories=True)
    root = Path(repo.working_tree_dir)
    return repo, Path(repo_path).resolve().relative_to(root.resolve())


def worktree_path(run_id: str) -> Path:
    return Path(tempfile.gettempdir()) / "bugscout-worktrees" / sandbox.short(run_id)


def ensure_worktree(run_id: str, repo_path: str, ref: str) -> tuple[Path, str]:
    """Create (once per run) a detached worktree at `ref`. Returns (path of the target dir inside it, sha)."""
    repo, sub = _repo(repo_path)
    try:
        sha = repo.git.rev_parse(ref)
    except git.GitCommandError as e:
        raise RuntimeError(f"git ref '{ref}' not found in {repo_path} (needs at least 2 commits): {e.stderr.strip()[:120]}")
    wt = worktree_path(run_id)
    if not wt.exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        repo.git.worktree("add", "--detach", str(wt), sha)
    return wt / sub, sha


def ensure_ref_container(run_id: str, repo_path: str, ref: str):
    """Container with the OLD code. Cached per run: created once, reused."""
    src, sha = ensure_worktree(run_id, repo_path, ref)
    if sandbox.has(run_id, "ref"):
        return sandbox.get(run_id, "ref"), sha
    return sandbox.new_ref_container(run_id, src, "old"), sha


def cleanup(run_id: str, repo_path: str) -> None:
    wt = worktree_path(run_id)
    if wt.exists():
        try:
            repo, _ = _repo(repo_path)
            repo.git.worktree("remove", "--force", str(wt))
            repo.git.worktree("prune")
        except Exception:
            import shutil
            shutil.rmtree(wt, ignore_errors=True)


def changed_function_keys(run_id: str, repo_path: str, ref: str) -> list[str]:
    """Function asset keys whose lines were touched since `ref` (working tree vs ref)."""
    repo, sub = _repo(repo_path)
    sha = repo.git.rev_parse(ref)
    diff = repo.git.diff("-U0", sha, "--", str(sub) if str(sub) != "." else ".")
    ranges: dict[str, list[tuple[int, int]]] = {}
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            if str(sub) != ".":
                cur = str(Path(cur).relative_to(sub))
        elif line.startswith("@@") and cur:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, n = int(m.group(1)), int(m.group(2) or 1)
            ranges.setdefault(cur, []).append((start, start + max(n, 1) - 1))
    keys = []
    for f in assets.list_nodes(run_id, "function"):
        for lo, hi in ranges.get(f["props"].get("file", ""), []):
            if f["props"]["lineno"] <= hi and f["props"]["end_lineno"] >= lo:
                keys.append(f["key"])
                break
    return keys
