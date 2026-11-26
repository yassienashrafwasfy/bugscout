"""Shared helpers for the in-container shims. Every shim writes its result as JSON to --out; stdout/stderr are just logs."""
import importlib
import json
import os
import sys
import traceback

REPO = os.environ.get("BUGSCOUT_REPO", "/work/repo")


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, default=repr)


def resolve(target):
    """'pkg.mod:func' or 'pkg.mod:Class.method' -> callable"""
    mod, _, attr = target.partition(":")
    obj = importlib.import_module(mod)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def project_frames(tb, limit=6):
    """In-project stack frames (innermost last), as 'file:func'."""
    out = []
    for fs in traceback.extract_tb(tb):
        fn = os.path.abspath(fs.filename)
        if fn.startswith(REPO) and "/tests" not in fn and "/gen/" not in fn:
            out.append({"file": os.path.relpath(fn, REPO), "func": fs.name, "line": fs.lineno})
    return out[-limit:]


def exc_info(e):
    return {"type": type(e).__name__, "message": str(e)[:500], "frames": project_frames(e.__traceback__),
            "traceback": "".join(traceback.format_exception(type(e), e, e.__traceback__))[-2500:]}
