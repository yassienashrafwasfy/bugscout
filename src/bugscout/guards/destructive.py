"""Destructive-action guard for HTTP."""
from __future__ import annotations

import re

from ..store import assets

DESTRUCTIVE_METHODS = {"DELETE", "PUT", "PATCH"}
DESTRUCTIVE_WORDS = re.compile(r"delete|remove|pay|charge|send|email|drop|reset", re.I)


def is_destructive(method: str | None, path: str | None = None, operation_id: str | None = None) -> bool:
    m = (method or "GET").upper()
    if m in DESTRUCTIVE_METHODS:
        return True
    if m == "POST":
        return bool(DESTRUCTIVE_WORDS.search(f"{operation_id or ''} {path or ''}"))
    return False


def template_for(run_id: str, method: str, path: str) -> tuple[str, str | None]:
    """Map a concrete path (/items/5) to its OpenAPI template (/items/{item_id}) -> (template, operation_id)."""
    for ep in assets.list_nodes(run_id, "endpoint"):
        p = ep["props"]
        if p.get("method") != method.upper():
            continue
        rx = "^" + re.sub(r"\\\{[^/]+?\\\}", "[^/]+", re.escape(p["path"])) + "/?$"
        if re.match(rx, path.split("?")[0]):
            return p["path"], p.get("operation_id")
    return re.sub(r"/(\d+|[0-9a-f]{8}-[0-9a-f-]{27})(?=/|$)", "/{id}", path.split("?")[0]), None
