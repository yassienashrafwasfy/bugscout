"""Quality tools: coverage (with per-test contexts), mutation, flaky detection, test dedup."""
from __future__ import annotations

import hashlib
import re
import shlex
from collections import defaultdict

from ..guards import scope as scope_guard
from ..models import err, ok
from ..runners import parsers, sandbox
from ..runtime import tool
from ..store import assets, runs, tree
from ..store.db import J, q
from . import _exec as X
from .run import _safe_selector

COVERAGERC = "[run]\nbranch = True\n[json]\nshow_contexts = True\n"


def _clean_ctx(c: str) -> str:
    c = re.sub(r"\|(run|setup|teardown)$", "", c)
    return c[len("repo/"):] if c.startswith("repo/") else c      # rootdir is /work when /work/gen is collected too


def _func_cov(f: dict, cov_file: dict) -> dict:
    lo, hi = f["props"]["lineno"], f["props"]["end_lineno"]
    ex = [l for l in cov_file["executed"] if lo <= l <= hi]
    mi = [l for l in cov_file["missing"] if lo <= l <= hi]
    stmts = len(ex) + len(mi)
    line = (len(ex) / stmts) if stmts else 1.0
    eb = [b for b in cov_file["executed_branches"] if lo <= b[0] <= hi]
    mb = [b for b in cov_file["missing_branches"] if lo <= b[0] <= hi]
    nb = len(eb) + len(mb)
    branch = (len(eb) / nb) if nb else line
    return {"coverage_line": round(line, 3), "coverage_branch": round(branch, 3), "tested": len(ex) > 0}


@tool("run_coverage", executing=True)
def run_coverage(run_id: str, selector: str | None = None) -> dict:
    """pytest-cov with --cov-branch --cov-context=test. Stores line/branch coverage per function node and which tests cover which
    lines (needed for dedup_tests). Returns the least-covered in-scope functions."""
    ch = X.charter(run_id)
    pkg = X.pkg_rel(ch)
    sel = _safe_selector(selector)
    sandbox.put_files(sandbox.get(run_id), {f"{sandbox.OUT}/coveragerc": COVERAGERC})
    cmd = (f"python -m pytest {sel or '$(ls -d tests test 2>/dev/null) /work/gen'} -p no:randomly -p no:cacheprovider --benchmark-disable "
           f"--timeout=60 -q --cov={pkg} --cov-branch --cov-context=test --cov-config={sandbox.OUT}/coveragerc "
           f"--cov-report=json:$OUT")
    res, text = X.run_to_json(run_id, cmd, timeout=170)
    cov = parsers.parse_coverage(text)
    if not cov["files"]:
        return err("coverage report missing", {"stderr": X.tail(res.stderr), "stdout": X.tail(res.stdout)})
    n = 0
    for f in assets.list_nodes(run_id, "function"):
        cf = cov["files"].get(f["props"].get("file"))
        if cf:
            assets.set_props(str(f["id"]), _func_cov(f, cf))
            n += 1
    # which tests cover which lines
    sigs = 0
    for ctx, files in cov["contexts"].items():
        tid = _clean_ctx(ctx)
        norm = {f: sorted(set(ls)) for f, ls in sorted(files.items())}
        sig = hashlib.sha1(repr(norm).encode()).hexdigest()[:16]
        q("""INSERT INTO test_record (run_id, test_id, file, covered, covered_sig) VALUES (%s,%s,%s,%s,%s)
             ON CONFLICT (run_id, test_id) DO UPDATE SET covered=EXCLUDED.covered, covered_sig=EXCLUDED.covered_sig""",
          (run_id, tid, tid.split("::")[0], J(norm), sig))
        sigs += 1
    totals = cov["totals"]
    runs.add_artifact(run_id, "coverage_summary", {"line_pct": totals["line_pct"], "branch_pct": totals["branch_pct"],
                                                   "tests_with_contexts": sigs})
    low = sorted((x for x in assets.list_nodes(run_id, "function") if x["props"].get("in_scope", True)
                  and "coverage_branch" in x["props"] and not x["props"].get("is_dead")),
                 key=lambda x: (x["props"]["coverage_branch"], x["key"]))[:8]
    return ok(f"line coverage {totals['line_pct']:.1f}%, branch {totals['branch_pct'] or 0:.1f}%",
              {"line_pct": round(totals["line_pct"], 2), "branch_pct": round(totals["branch_pct"] or 0, 2),
               "functions_updated": n, "tests_with_contexts": sigs,
               "least_covered": [{"asset_id": str(x["id"]), "key": x["key"], "branch": x["props"]["coverage_branch"]} for x in low]},
              ["get_untested", "write_test for the least-covered functions", "dedup_tests"])


# ------------------------------------------------------------------ mutation
def _mutant_function(key: str) -> tuple[str, str] | None:
    """samplelib.stats.x_mean__mutmut_1 -> ('samplelib.stats', 'mean'); methods: xǁClassǁm__mutmut_1 -> Class.m"""
    m = re.match(r"^(?P<mod>.+)\.x(?P<fn>[^.]+?)__mutmut_\d+$", key)
    if not m:
        return None
    fn = m["fn"]
    fn = fn[1:] if fn.startswith("_") and not fn.startswith("__") else fn      # x_name -> name (mutmut inserts "_")
    return m["mod"], fn.replace("ǁ", ".")


def _non_passing(run_id: str) -> list[str]:
    """Tests mutmut must not run: flaky ones and ones failing on the unmutated code (its baseline run must be green)."""
    rows = q("SELECT test_id FROM test_record WHERE run_id=%s AND status='flaky'", (run_id,))
    bad = {r["test_id"] for r in rows}
    a = runs.latest_artifact(run_id, "pytest_report")
    if a:
        bad |= {t["nodeid"] for t in a["data"]["tests"] if t["outcome"] in ("failed", "error")}
    return sorted(bad)


@tool("run_mutation", executing=True, action=lambda kw: {"file": (kw.get("paths") or [None])[0]})
def run_mutation(run_id: str, paths: list[str]) -> dict:
    """mutmut on a few changed / well-covered files (slow: keep it to 1-3 small files; never run it together with perf jobs).
    Stores `mutation_score` on function nodes; every surviving mutant becomes an `idea` node 'add test to kill mutant X'."""
    ch = X.charter(run_id)
    if not paths or len(paths) > 3:
        return err("pass 1-3 python files (relative to the repo root), mutation testing is slow")
    for p in paths:
        if not re.fullmatch(r"[\w./\-]+\.py", p) or ".." in p:
            return err(f"bad path {p}")
        if not scope_guard.in_scope(ch["scope"], scope_guard.python_candidates(None, p)):
            return err(f"{p} is outside scope")
    bad = _non_passing(run_id)
    deselect = ("--deselect " + " ".join(shlex.quote(t) for t in bad)) if bad else ""
    res, text = X.run_to_json(run_id, f"python /opt/bugscout/tm_mutation.py --out $OUT --paths {' '.join(map(shlex.quote, paths))} "
                                      f"--tests tests {deselect} --max-seconds 150",
                              timeout=175)
    d = parsers.jloads(text)
    if not d or d["status"] != "ok":
        return err("mutation run produced no result (baseline tests must pass: deselect/fix failing or flaky tests)",
                   {"detail": (d or {}).get("log_tail") or X.tail(res.stderr), "timed_out": res.timed_out})
    by_fn: dict[str, list[dict]] = defaultdict(list)
    for m in d["mutants"]:
        k = _mutant_function(m["key"])
        if k and m["status"] != "not_checked":
            by_fn[f"{k[0]}:{k[1]}"].append(m)
    survivors = 0
    from ..guards import escalation  # noqa: F401
    for key, ms in by_fn.items():
        killed = sum(m["status"] in ("killed", "timeout") for m in ms)
        node = assets.set_props_by_key(run_id, key, {"mutation_score": round(killed / len(ms), 3), "mutants": len(ms)})
        if not node:
            continue
        for m in ms:
            if m["status"] != "survived":
                continue
            survivors += 1
            sig = hashlib.sha1(f"mutant|{m['key']}".encode()).hexdigest()
            tree.add_idea_dedup(run_id, str(tree.root_goal(run_id)["id"]), f"add test to kill mutant {m['key']}",
                                (m.get("diff") or "")[-400:], str(node["id"]), sig, 0.5)
    runs.add_artifact(run_id, "mutation", d)
    return ok(f"mutation score {d['score']:.0%} ({d['killed']}/{d['checked']} killed); {survivors} survivor(s)",
              {"score": d["score"], "checked": d["checked"], "survivors": survivors,
               "per_function": {k: round(sum(m['status'] in ('killed', 'timeout') for m in v) / len(v), 2) for k, v in by_fn.items()}},
              ["get_frontier for 'kill mutant' ideas"] if survivors else None)


# ------------------------------------------------------------------ flaky
@tool("check_flaky", executing=True)
def check_flaky(run_id: str, test_ids: list[str], n: int = 10) -> dict:
    """Run tests N times in separate pytest processes with random order/seeds (pytest-randomly). flaky_score = failure rate.
    0 < score < 1 -> status `flaky` (excluded from bugs); score 1 -> consistently failing (a real failure)."""
    if not test_ids or len(test_ids) > 10:
        return err("pass 1-10 pytest node ids")
    n = max(2, min(int(n), 30))
    ids = " ".join(_safe_selector(t) or "" for t in test_ids)
    loop = (f"for i in $(seq 1 {n}); do python -m pytest {ids} -p randomly --randomly-seed=$i -p no:cacheprovider --benchmark-disable "
            f"--timeout=60 -q --json-report --json-report-file={sandbox.OUT}/flaky_$i.json --json-report-omit=collectors >/dev/null 2>&1; done")
    sandbox.run(run_id, loop, timeout=170)
    c = sandbox.get(run_id)
    fails: dict[str, int] = defaultdict(int)
    runs_seen: dict[str, int] = defaultdict(int)
    for i in range(1, n + 1):
        rep = parsers.parse_pytest_report(sandbox.read_file(c, f"{sandbox.OUT}/flaky_{i}.json"))
        for t in rep["tests"]:
            runs_seen[t["nodeid"]] += 1
            fails[t["nodeid"]] += t["outcome"] in ("failed", "error")
    out = []
    for tid, seen in runs_seen.items():
        score = fails[tid] / seen
        verdict = "flaky" if 0 < score < 1 else ("always_fails" if score == 1 else "stable_pass")
        out.append({"test": tid, "runs": seen, "failures": fails[tid], "flaky_score": round(score, 2), "verdict": verdict})
        if verdict == "flaky":
            q("""INSERT INTO test_record (run_id, test_id, file, status) VALUES (%s,%s,%s,'flaky')
                 ON CONFLICT (run_id, test_id) DO UPDATE SET status='flaky'""", (run_id, tid, tid.split("::")[0]))
        for node in q("SELECT id FROM expl_node WHERE run_id=%s AND kind='test' AND action->>'nodeid'=%s", (run_id, tid)):
            tree.update(str(node["id"]), status="flaky" if verdict == "flaky" else None, flaky_score=score)
    if not out:
        return err("no results; check the test ids", {"ids": test_ids})
    flaky = [o for o in out if o["verdict"] == "flaky"]
    return ok(f"{len(flaky)} flaky of {len(out)} test(s)", {"results": out},
              ["flaky tests are excluded from bugs; real failures -> record_bug"] if out else None)


# ------------------------------------------------------------------ dedup
@tool("dedup_tests", count_step=True)
def dedup_tests(run_id: str) -> dict:
    """Tests with identical covered lines (coverage contexts) are duplicates: the first is kept, extras are marked `duplicate`.
    Needs run_coverage first. (mutmut 3 exposes no per-test kill sets, so identical-coverage is the signal.)"""
    rows = q("SELECT test_id, covered_sig FROM test_record WHERE run_id=%s AND covered_sig IS NOT NULL AND status='active' "
             "ORDER BY test_id", (run_id,))
    if not rows:
        return err("no coverage contexts yet; run run_coverage first")
    groups: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        groups[r["covered_sig"]].append(r["test_id"])
    dups = []
    for sig, tests in groups.items():
        if len(tests) < 2:
            continue
        keep, extras = tests[0], tests[1:]
        for t in extras:
            q("UPDATE test_record SET status='duplicate' WHERE run_id=%s AND test_id=%s", (run_id, t))
            for node in q("SELECT id FROM expl_node WHERE run_id=%s AND kind='test' AND action->>'nodeid'=%s", (run_id, t)):
                tree.update(str(node["id"]), status="duplicate")
        dups.append({"keep": keep, "duplicates": extras})
    return ok(f"{sum(len(d['duplicates']) for d in dups)} duplicate test(s) in {len(dups)} group(s)", {"groups": dups})
