"""Parse the machine-readable output of each CLI tool / shim. Never scrape human-readable text."""
from __future__ import annotations

import json
import os
import re
from typing import Any


def jloads(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def rel(path: str, root: str = "/work/repo") -> str:
    p = path.replace("\\", "/")
    return os.path.relpath(p, root) if p.startswith(root) else p.lstrip("./") if p.startswith("./") else p


def parse_ruff(text: str) -> list[dict]:
    out = []
    for d in jloads(text, []) or []:
        out.append({"file": rel(d["filename"]), "line": d["location"]["row"], "code": d["code"] or "E999",
                    "message": d["message"], "url": d.get("url")})
    return out


def parse_mypy(text: str) -> list[dict]:
    """`mypy -O json` prints one JSON object per line."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        d = jloads(line)
        if d and d.get("severity") in ("error", "warning"):
            out.append({"file": rel(d["file"]), "line": d["line"], "code": d.get("code") or "mypy", "message": d["message"],
                        "severity": d["severity"]})
    return out


def parse_bandit(text: str) -> list[dict]:
    d = jloads(text, {}) or {}
    return [{"file": rel(r["filename"]), "line": r["line_number"], "code": r["test_id"], "message": r["issue_text"],
             "severity": r["issue_severity"].lower(), "confidence": r["issue_confidence"].lower(), "name": r["test_name"]}
            for r in d.get("results", [])]


def parse_radon_cc(text: str) -> list[dict]:
    out = []
    for file, items in (jloads(text, {}) or {}).items():
        if isinstance(items, dict):   # radon error entry
            continue
        for it in items:
            name = f"{it['classname']}.{it['name']}" if it.get("classname") else it["name"]
            out.append({"file": rel(file), "name": name, "type": it["type"], "complexity": it["complexity"], "rank": it["rank"],
                        "lineno": it["lineno"], "endline": it.get("endline")})
            for c in it.get("closures", []) or []:
                out.append({"file": rel(file), "name": f"{name}.{c['name']}", "type": "closure", "complexity": c["complexity"],
                            "rank": c["rank"], "lineno": c["lineno"], "endline": c.get("endline")})
    return out


def parse_radon_mi(text: str) -> dict[str, dict]:
    return {rel(f): v for f, v in (jloads(text, {}) or {}).items() if isinstance(v, dict)}


def parse_pytest_report(text: str | None) -> dict:
    """pytest-json-report -> compact per-test outcomes."""
    d = jloads(text, None)
    if not d:
        return {"summary": {}, "tests": []}
    tests = []
    for t in d.get("tests", []):
        crash = (t.get("call") or t.get("setup") or {}).get("crash") or {}
        longrepr = (t.get("call") or t.get("setup") or {}).get("longrepr", "")
        tests.append({"nodeid": t["nodeid"], "outcome": t["outcome"], "duration": (t.get("call") or {}).get("duration"),
                      "crash_path": crash.get("path"), "crash_line": crash.get("lineno"), "message": crash.get("message"),
                      "longrepr": (longrepr or "")[-1200:]})
    return {"summary": d.get("summary", {}), "tests": tests, "duration": d.get("duration"), "exitcode": d.get("exitcode")}


def parse_benchmark(text: str | None) -> list[dict]:
    d = jloads(text, {}) or {}
    out = []
    for b in d.get("benchmarks", []):
        s = b["stats"]
        out.append({"name": b["name"], "fullname": b["fullname"], "min": s["min"], "median": s["median"], "mean": s["mean"],
                    "max": s["max"], "stddev": s["stddev"], "rounds": s["rounds"], "iqr": s.get("iqr")})
    return out


def parse_coverage(text: str | None) -> dict:
    """coverage json (with show_contexts) -> per-file executed/missing lines + per-test line contexts."""
    d = jloads(text, {}) or {}
    files, contexts = {}, {}
    for f, v in (d.get("files") or {}).items():
        s = v.get("summary", {})
        files[f] = {"executed": v.get("executed_lines", []), "missing": v.get("missing_lines", []),
                    "executed_branches": v.get("executed_branches", []), "missing_branches": v.get("missing_branches", []),
                    "line_pct": s.get("percent_covered"), "num_statements": s.get("num_statements"),
                    "num_branches": s.get("num_branches"), "covered_branches": s.get("covered_branches")}
        for line, ctxs in (v.get("contexts") or {}).items():
            for c in ctxs:
                if c:
                    contexts.setdefault(c, {}).setdefault(f, []).append(int(line))
    totals = d.get("totals", {})
    return {"files": files, "contexts": contexts, "totals": {"line_pct": totals.get("percent_covered"),
            "branch_pct": ((totals["covered_branches"] / totals["num_branches"] * 100) if totals.get("num_branches") else None)}}


_CODE = re.compile(r"\s+")


def severity_for_ruff(code: str) -> str:
    return "medium" if code.startswith(("F8", "E9", "S", "B0")) else "low"
