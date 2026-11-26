"""Static analysis tools: radon, ruff, mypy, bandit, duplication (DRY), vulture (YAGNI)."""
from __future__ import annotations

import hashlib

from ..guards import escalation
from ..models import err, ok
from ..runners import parsers
from ..runtime import tool
from ..store import assets, findings, runs
from . import _exec as X


def _fp(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:20]


def _record(run_id: str, ch: dict, issues: list[dict], oracle: str, kind: str, sev_fn, title_fn) -> dict:
    """Store issues as findings attached to their enclosing function; high+ severity trips the serious-bug guard."""
    created = skipped_scope = 0
    escalations = []
    for i in issues:
        if not X.file_in_scope(ch, i["file"]):
            skipped_scope += 1
            continue
        node = X.attach_asset(run_id, i["file"], i["line"])
        sev = sev_fn(i)
        f, new = findings.add_static_finding_once(run_id, kind, oracle, sev, title_fn(i),
                                                  str(node["id"]) if node else None,
                                                  _fp(oracle, i["code"], i["file"], i["line"]))
        created += new
        if new:
            esc = escalation.on_serious_finding(run_id, f)
            if esc:
                escalations.append(esc["escalation_id"])
    X.refresh_issue_counts(run_id)
    return {"found": len(issues), "new_findings": created, "out_of_scope_skipped": skipped_scope,
            "serious_escalations": escalations}


@tool("run_radon", executing=True)
def run_radon(run_id: str) -> dict:
    """Cyclomatic complexity (A-F) on function nodes, maintainability index on modules. Rank D-F -> warning finding."""
    ch = X.charter(run_id)
    pkg = X.pkg_rel(ch)
    cc = X.run_cmd(run_id, f"radon cc -j {pkg}")
    mi = X.run_cmd(run_id, f"radon mi -j {pkg}")
    funcs = parsers.parse_radon_cc(cc.stdout)
    n = bad = 0
    for f in funcs:
        mod = f["file"].removesuffix(".py").removeprefix("src/").replace("/", ".").removesuffix(".__init__")
        node = assets.set_props_by_key(run_id, f"{mod}:{f['name']}", {"complexity": f["complexity"], "complexity_rank": f["rank"]})
        if not node:
            continue
        n += 1
        if f["rank"] in ("D", "E", "F"):
            bad += 1
            findings.add_static_finding_once(run_id, "warning", "radon", "medium",
                                             f"{f['name']} has cyclomatic complexity {f['complexity']} (rank {f['rank']})",
                                             str(node["id"]), _fp("radon", node["key"]))
    for file, v in parsers.parse_radon_mi(mi.stdout).items():
        mod = file.removesuffix(".py").removeprefix("src/").replace("/", ".").removesuffix(".__init__")
        assets.set_props_by_key(run_id, mod, {"maintainability": round(v["mi"], 2), "maintainability_rank": v["rank"]})
    X.refresh_issue_counts(run_id)
    return ok(f"complexity stored on {n} functions; {bad} rank D-F", {"functions": n, "rank_d_or_worse": bad},
              ["run_ruff", "run_mypy", "run_bandit"])


@tool("run_ruff", executing=True)
def run_ruff(run_id: str) -> dict:
    ch = X.charter(run_id)
    r = X.run_cmd(run_id, f"ruff check {X.pkg_rel(ch)} --output-format json --no-cache --exit-zero")
    issues = parsers.parse_ruff(r.stdout)
    s = _record(run_id, ch, issues, "ruff", "static_issue", lambda i: parsers.severity_for_ruff(i["code"]),
                lambda i: f"ruff {i['code']}: {i['message']} ({i['file']}:{i['line']})")
    return ok(f"ruff: {s['found']} issue(s), {s['new_findings']} new", s)


@tool("run_mypy", executing=True)
def run_mypy(run_id: str) -> dict:
    ch = X.charter(run_id)
    r = X.run_cmd(run_id, f"mypy {X.pkg_rel(ch)} -O json --no-incremental --cache-dir=/dev/null --ignore-missing-imports --show-error-codes",
                  timeout=170)
    issues = parsers.parse_mypy(r.stdout)
    s = _record(run_id, ch, issues, "mypy", "static_issue", lambda i: "medium" if i["severity"] == "error" else "low",
                lambda i: f"mypy [{i['code']}]: {i['message']} ({i['file']}:{i['line']})")
    return ok(f"mypy: {s['found']} issue(s), {s['new_findings']} new", s)


@tool("run_bandit", executing=True)
def run_bandit(run_id: str) -> dict:
    """Security issues. high severity AND high confidence -> `high` finding (needs human confirmation)."""
    ch = X.charter(run_id)
    r = X.run_cmd(run_id, f"bandit -r {X.pkg_rel(ch)} -f json -q --exit-zero")
    issues = parsers.parse_bandit(r.stdout)

    def sev(i):
        if i["severity"] == "high" and i["confidence"] == "high":
            return "high"
        return {"high": "medium", "medium": "medium"}.get(i["severity"], "low")
    s = _record(run_id, ch, issues, "bandit", "static_issue", sev,
                lambda i: f"bandit {i['code']} {i['name']}: {i['message']} ({i['file']}:{i['line']})")
    return ok(f"bandit: {s['found']} issue(s), {s['new_findings']} new", s)


@tool("run_duplication", executing=True)
def run_duplication(run_id: str, min_lines: int = 5, use_jscpd: bool = False) -> dict:
    """DRY: pylint/symilar duplicate-code detection -> duplicate_of edges, dup_group prop, duplication %."""
    ch = X.charter(run_id)
    pkg = X.pkg_rel(ch)
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_dup.py --out $OUT --min-lines {min_lines} "
                                      f"{'--jscpd ' if use_jscpd else ''}{pkg}")
    d = parsers.jloads(text)
    if not d:
        return err("duplication shim failed", {"stderr": X.tail(res.stderr)})
    groups = 0
    for clone in d["clones"]:
        nodes = []
        for loc in clone["locations"]:
            if not X.file_in_scope(ch, loc["file"]):
                continue
            n = assets.enclosing_function(run_id, loc["file"], loc["start"]) or assets.enclosing_function(run_id, loc["file"], loc["end"])
            if n and n["id"] not in [x["id"] for x in nodes]:
                nodes.append(n)
        if len(nodes) < 2:
            continue
        groups += 1
        gid = f"dup{groups}"
        for n in nodes:
            assets.set_props(str(n["id"]), {"dup_group": gid})
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                assets.add_edge(run_id, a["id"], b["id"], "duplicate_of", {"lines": clone["lines"]})
        findings.add_static_finding_once(
            run_id, "warning", "duplication", "low",
            f"{clone['lines']} duplicated lines in " + ", ".join(n["key"] for n in nodes), str(nodes[0]["id"]),
            _fp("dup", *[n["key"] for n in sorted(nodes, key=lambda x: x["key"])]))
    runs.add_artifact(run_id, "duplication", d)
    return ok(f"duplication {d['duplication_pct']}%: {groups} duplicate group(s)",
              {"duplication_pct": d["duplication_pct"], "groups": groups, "clones": len(d["clones"]),
               **({"jscpd": d["jscpd"]["statistics"]} if d.get("jscpd") else {})})


@tool("run_vulture", executing=True)
def run_vulture(run_id: str, min_confidence: int = 60) -> dict:
    """YAGNI: unused code. Findings are `cleanup` + needs_confirmation; a node only becomes `is_dead` (and drops out of
    testing priority) at confidence 100 or once confirm_finding confirms it. Lower confidence -> `dead_candidate` only."""
    ch = X.charter(run_id)
    pkg = X.pkg_rel(ch)
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_vulture.py --out $OUT --min-confidence {min_confidence} {pkg} "
                                      f"$(ls -d tests 2>/dev/null)")
    items = parsers.jloads(text)
    if items is None:
        return err("vulture shim failed", {"stderr": X.tail(res.stderr)})
    n = 0
    for i in items:
        if i["type"] not in ("function", "method", "class") or not X.file_in_scope(ch, i["file"]):
            continue
        node = assets.enclosing_function(run_id, i["file"], i["line"])
        if not node or node["name"] != i["name"]:
            continue
        props = {"dead_candidate": True, "dead_confidence": i["confidence"]}
        if i["confidence"] >= 100:
            props["is_dead"] = True
        assets.set_props(str(node["id"]), props)
        f, new = findings.add_static_finding_once(
            run_id, "cleanup", "vulture", "low", f"unused {i['type']} {node['key']} ({i['confidence']}% confidence)",
            str(node["id"]), _fp("vulture", node["key"]))
        if new and i["confidence"] < 100:
            findings.set_status(str(f["id"]), "needs_confirmation")
        n += 1
    return ok(f"vulture: {n} unused definition(s)", {"unused": n})


@tool("confirm_finding", count_step=False)
def confirm_finding(run_id: str, finding_id: str, confirmed: bool) -> dict:
    """Confirm/reject a non-escalated finding (e.g. a vulture cleanup). Confirming dead code marks the node is_dead."""
    f = findings.get(finding_id)
    if not f or str(f["run_id"]) != run_id:
        return err("unknown finding for this run")
    findings.set_status(finding_id, "confirmed" if confirmed else "rejected")
    if f["oracle"] == "vulture" and f["asset_id"]:
        assets.set_props(str(f["asset_id"]), {"is_dead": bool(confirmed), "dead_candidate": bool(confirmed)})
    return ok("confirmed" if confirmed else "rejected", {"finding_id": finding_id})
