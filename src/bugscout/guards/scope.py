"""Scope guard: include/exclude globs for code targets and endpoints; host allow-list."""
from __future__ import annotations

from fnmatch import fnmatchcase
from urllib.parse import urlparse


def python_candidates(key: str | None = None, file: str | None = None) -> list[str]:
    """All the ways a user might write a pattern for a python target."""
    c: list[str] = []
    if key:
        c.append(key)
        mod = key.split(":")[0]
        c += [mod, mod.replace(".", "/"), mod.replace(".", "/") + ".py", key.replace(":", ".")]
        if ":" in key:
            c.append(mod.replace(".", "/") + "/" + key.split(":", 1)[1])
    if file:
        c += [file, file.removesuffix(".py"), file.removesuffix(".py").replace("/", ".")]
    return list(dict.fromkeys(c))


def endpoint_candidates(method: str | None, path: str) -> list[str]:
    c = [path]
    if method:
        c.append(f"{method.upper()} {path}")
    return c


def _match(cands: list[str], patterns: list[str]) -> bool:
    return any(fnmatchcase(c, p) for c in cands for p in patterns)


def in_scope(scope: dict, cands: list[str]) -> bool:
    """Include patterns must match (an empty include list means 'everything'); exclude must not."""
    inc, exc = scope.get("include") or ["*"], scope.get("exclude") or []
    return _match(cands, inc) and not _match(cands, exc)


def host_allowed(scope: dict, host: str | None) -> bool:
    if not host:
        return True
    host = urlparse(host).hostname if "//" in host else host.split(":")[0]
    return host in (scope.get("allowed_hosts") or [])


def check(scope: dict, *, key: str | None = None, file: str | None = None, method: str | None = None,
          path: str | None = None, host: str | None = None) -> tuple[bool, str | None]:
    """(ok, reason). Used by the guard layer before any executing call."""
    if host is not None and not host_allowed(scope, host):
        return False, f"host '{host}' is not in scope.allowed_hosts {scope.get('allowed_hosts')}"
    if path is not None:
        if not in_scope(scope, endpoint_candidates(method, path)):
            return False, f"endpoint {method or ''} {path} is outside scope.include/exclude"
    if key and " " in key and key.split(" ", 1)[1].startswith("/"):
        # an endpoint asset key ("GET /items/{id}"): match it like an endpoint, not like a python target
        m, p = key.split(" ", 1)
        if not in_scope(scope, endpoint_candidates(m, p)):
            return False, f"endpoint {key} is outside scope.include/exclude"
        key = None
    if key or file:
        if not in_scope(scope, python_candidates(key, file)):
            return False, f"target {key or file} is outside scope.include/exclude"
    return True, None
