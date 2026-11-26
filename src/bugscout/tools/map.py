"""Map tools: populate the asset graph (python ast, OpenAPI) and attach radon metrics."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import yaml

from ..guards import scope as scope_guard
from ..models import err, ok
from ..runtime import tool
from ..store import assets, findings, runs


def _charter(run_id: str) -> dict:
    return runs.get_run(run_id)["charter"]


# ------------------------------------------------------------------ python ast scan
def package_dir(repo: Path, package: str) -> Path | None:
    rel = package.replace(".", "/")
    for base in (repo, repo / "src"):
        if (base / rel).is_dir():
            return base / rel
    return None


def _sig(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    a = fn.args
    params = []
    pos = a.posonlyargs + a.args
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for arg, d in zip(pos, defaults):
        params.append({"name": arg.arg, "type": ast.unparse(arg.annotation) if arg.annotation else None,
                       "default": ast.unparse(d) if d is not None else None})
    if a.vararg:
        params.append({"name": "*" + a.vararg.arg, "type": ast.unparse(a.vararg.annotation) if a.vararg.annotation else None, "default": None})
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        params.append({"name": arg.arg, "type": ast.unparse(arg.annotation) if arg.annotation else None,
                       "default": ast.unparse(d) if d is not None else None, "kwonly": True})
    if a.kwarg:
        params.append({"name": "**" + a.kwarg.arg, "type": None, "default": None})
    ret = ast.unparse(fn.returns) if fn.returns else None
    hinted = ret is not None or any(p["type"] for p in params)
    return {"params": params, "returns": ret, "has_type_hints": hinted,
            "signature": f"{fn.name}({', '.join(p['name'] + (': ' + p['type'] if p['type'] else '') for p in params)})" + (f" -> {ret}" if ret else "")}


def scan_file(path: Path, root: Path) -> dict:
    """Pure function: parse a file into modules/classes/functions + raw import/call info."""
    rel = path.relative_to(root).as_posix()
    mod = rel.removesuffix(".py").removeprefix("src/").replace("/", ".").removesuffix(".__init__")
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
    out: dict[str, Any] = {"module": mod, "file": rel, "doc": ast.get_docstring(tree), "classes": [], "functions": [],
                           "imports": [], "aliases": {}}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out["imports"].append(a.name)
                out["aliases"][(a.asname or a.name).split(".")[0] if not a.asname else a.asname] = a.name
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                parts = mod.split(".")
                if path.name != "__init__.py":
                    parts = parts[:-1]
                base = ".".join(parts[: len(parts) - (n.level - 1)] + ([n.module] if n.module else []))
            out["imports"].append(base)
            for a in n.names:
                out["aliases"][a.asname or a.name] = f"{base}:{a.name}"

    def calls_in(fn) -> list[str]:
        names = []
        for c in ast.walk(fn):
            if isinstance(c, ast.Call):
                f = c.func
                if isinstance(f, ast.Name):
                    names.append(f.id)
                elif isinstance(f, ast.Attribute):
                    names.append(ast.unparse(f))
        return names

    def add_fn(fn, cls: str | None):
        key = f"{mod}:{cls + '.' if cls else ''}{fn.name}"
        out["functions"].append({"key": key, "name": fn.name, "cls": cls, "lineno": fn.lineno,
                                 "end_lineno": fn.end_lineno, "doc": ast.get_docstring(fn), "calls": calls_in(fn),
                                 "decorators": [ast.unparse(d) for d in fn.decorator_list], **_sig(fn)})

    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_fn(n, None)
        elif isinstance(n, ast.ClassDef):
            out["classes"].append({"key": f"{mod}:{n.name}", "name": n.name, "lineno": n.lineno, "end_lineno": n.end_lineno,
                                   "doc": ast.get_docstring(n), "bases": [ast.unparse(b) for b in n.bases]})
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_fn(m, n.name)
    return out


@tool("scan_python_code")
def scan_python_code(run_id: str) -> dict:
    """Parse the target package with `ast`: modules, classes, functions (signature, hints, docstring),
    plus `imports` and best-effort `calls` edges. Reads source only; nothing is executed."""
    ch = _charter(run_id)
    t, scope = ch["target"], ch["scope"]
    if t["kind"] == "rest_api" and not t.get("package"):
        return err("charter has no python package to scan")
    repo = Path(t["repo_path"])
    pkg = package_dir(repo, t["package"])
    if pkg is None:
        return err(f"package {t['package']} not found under {repo}")
    files = sorted(p for p in pkg.rglob("*.py") if not ({".git", "__pycache__", ".venv"} & set(p.parts)))
    scanned = [scan_file(p, repo) for p in files]
    mods = {s["module"] for s in scanned}
    counts = {"module": 0, "class": 0, "function": 0, "out_of_scope": 0}
    keys: dict[str, str] = {}

    for s in scanned:
        ins = scope_guard.in_scope(scope, scope_guard.python_candidates(s["module"], s["file"]))
        m = assets.upsert_node(run_id, "module", s["module"], s["module"].split(".")[-1],
                               {"file": s["file"], "doc": s["doc"], "in_scope": ins}, "scan_python_code")
        keys[s["module"]] = str(m["id"])
        counts["module"] += 1
        counts["out_of_scope"] += (not ins)
        for c in s["classes"]:
            cn = assets.upsert_node(run_id, "class", c["key"], c["name"], {"file": s["file"], "lineno": c["lineno"],
                                    "end_lineno": c["end_lineno"], "doc": c["doc"], "bases": c["bases"], "in_scope": ins}, "scan_python_code")
            keys[c["key"]] = str(cn["id"]); counts["class"] += 1
            assets.add_edge(run_id, m["id"], cn["id"], "contains")
        for f in s["functions"]:
            fn = assets.upsert_node(run_id, "function", f["key"], f["name"], {
                "file": s["file"], "lineno": f["lineno"], "end_lineno": f["end_lineno"], "doc": f["doc"],
                "signature": f["signature"], "params": f["params"], "returns": f["returns"],
                "has_type_hints": f["has_type_hints"], "decorators": f["decorators"], "class": f["cls"], "in_scope": ins,
                "module": s["module"]}, "scan_python_code")
            keys[f["key"]] = str(fn["id"]); counts["function"] += 1
            parent = keys.get(f"{s['module']}:{f['cls']}") if f["cls"] else str(m["id"])
            assets.add_edge(run_id, parent, fn["id"], "contains")

    edges = {"imports": 0, "calls": 0}
    for s in scanned:
        for imp in set(s["imports"]):
            tgt = imp if imp in mods else next((m for m in mods if imp.startswith(m + ".") or m.startswith(imp + ".")), None)
            if tgt and tgt != s["module"] and tgt in keys:
                assets.add_edge(run_id, keys[s["module"]], keys[tgt], "imports"); edges["imports"] += 1
        local = {f["name"]: f["key"] for f in s["functions"] if not f["cls"]}
        for f in s["functions"]:
            seen = set()
            for call in f["calls"]:
                tgt = None
                if call in local:
                    tgt = local[call]
                elif call in s["aliases"] and ":" in s["aliases"][call]:
                    tgt = s["aliases"][call]
                elif call.startswith("self.") and f["cls"]:
                    tgt = f"{s['module']}:{f['cls']}.{call[5:]}"
                elif "." in call:
                    head, attr = call.split(".", 1)
                    mod = s["aliases"].get(head)
                    if mod and ":" not in mod and "." not in attr:
                        tgt = f"{mod}:{attr}"
                if tgt and tgt in keys and tgt not in seen and tgt != f["key"]:
                    seen.add(tgt)
                    assets.add_edge(run_id, keys[f["key"]], keys[tgt], "calls"); edges["calls"] += 1
    try:
        from ..runners import git_ref
        keys_changed = git_ref.changed_function_keys(run_id, t["repo_path"], ch["reference"]["git_ref"])
        runs.add_artifact(run_id, "changed_since_reference", {"keys": keys_changed, "ref": ch["reference"]["git_ref"]})
        counts["changed_since_reference"] = len(keys_changed)
    except Exception:
        pass
    return ok(f"scanned {len(files)} files: {counts['function']} functions, {counts['class']} classes",
              {**counts, "edges": edges},
              ["run_radon", "run_ruff", "run_mypy", "run_bandit", "run_duplication", "run_vulture"])


# ------------------------------------------------------------------ openapi
def _deref(node: Any, root: dict, depth: int = 0, seen: tuple = ()) -> Any:
    if depth > 12:
        return {}
    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/"):
            if node["$ref"] in seen:
                return {"type": "object", "x-recursive": node["$ref"]}
            cur: Any = root
            for part in node["$ref"][2:].split("/"):
                cur = cur[part.replace("~1", "/").replace("~0", "~")]
            return _deref(cur, root, depth + 1, seen + (node["$ref"],))
        return {k: _deref(v, root, depth + 1, seen) for k, v in node.items()}
    if isinstance(node, list):
        return [_deref(v, root, depth + 1, seen) for v in node]
    return node


def load_openapi(repo: Path, rel: str) -> dict:
    p = Path(rel) if Path(rel).is_absolute() else repo / rel
    text = p.read_text()
    return json.loads(text) if p.suffix == ".json" else yaml.safe_load(text)


def _refs(node: Any, acc: set[str]) -> None:
    if isinstance(node, dict):
        r = node.get("$ref")
        if isinstance(r, str) and r.startswith("#/components/schemas/"):
            acc.add(r.rsplit("/", 1)[1])
        for v in node.values():
            _refs(v, acc)
    elif isinstance(node, list):
        for v in node:
            _refs(v, acc)


@tool("import_openapi")
def import_openapi(run_id: str) -> dict:
    """Endpoints, params, request/response schemas as asset nodes + edges."""
    from openapi_spec_validator import validate

    ch = _charter(run_id)
    t, scope = ch["target"], ch["scope"]
    if not t.get("openapi"):
        return err("charter has no target.openapi")
    spec = load_openapi(Path(t["repo_path"]), t["openapi"])
    try:
        validate(spec)
    except Exception as e:
        return err(f"invalid OpenAPI document: {str(e)[:300]}")
    schema_ids: dict[str, str] = {}
    for name, sch in (spec.get("components", {}).get("schemas", {}) or {}).items():
        n = assets.upsert_node(run_id, "schema", f"schema:{name}", name, {"schema": _deref(sch, spec)}, "import_openapi")
        schema_ids[name] = str(n["id"])
    counts = {"endpoint": 0, "param": 0, "schema": len(schema_ids), "out_of_scope": 0}
    functions = assets.list_nodes(run_id, "function")
    for path, item in spec.get("paths", {}).items():
        common = item.get("parameters", [])
        for method, op in item.items():
            if method not in ("get", "put", "post", "delete", "patch", "head", "options"):
                continue
            M = method.upper()
            ins = scope_guard.in_scope(scope, scope_guard.endpoint_candidates(M, path))
            params = [_deref(p, spec) for p in common + op.get("parameters", [])]
            body = _deref(op.get("requestBody", {}), spec)
            responses = {code: _deref(r, spec) for code, r in (op.get("responses") or {}).items()}
            node = assets.upsert_node(run_id, "endpoint", f"{M} {path}", op.get("summary") or op.get("operationId"), {
                "method": M, "path": path, "operation_id": op.get("operationId"), "summary": op.get("summary"),
                "tags": op.get("tags", []), "params": params, "request_body": body, "responses": responses, "in_scope": ins,
            }, "import_openapi")
            counts["endpoint"] += 1; counts["out_of_scope"] += (not ins)
            for p in params:
                pn = assets.upsert_node(run_id, "param", f"{M} {path}#{p.get('name')}", p.get("name"),
                                        {"in": p.get("in"), "required": p.get("required", False), "schema": p.get("schema")}, "import_openapi")
                assets.add_edge(run_id, node["id"], pn["id"], "has_param"); counts["param"] += 1
            refs: set[str] = set()
            _refs(op, refs)
            for r in refs & set(schema_ids):
                assets.add_edge(run_id, node["id"], schema_ids[r], "contains")
            opid = op.get("operationId") or ""
            best = max((f for f in functions if f["props"].get("in_scope", True) and opid.startswith(f["name"] + "_")),
                       key=lambda f: len(f["name"]), default=None)
            if best:    # FastAPI: operationId = <handler name>_<path>_<method>
                assets.add_edge(run_id, node["id"], best["id"], "routes_to")
    return ok(f"imported {counts['endpoint']} endpoints, {counts['schema']} schemas", counts,
              ["run_schemathesis", "http_request"])
