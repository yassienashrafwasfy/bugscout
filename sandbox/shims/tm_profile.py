"""CPU / memory profiling of a pytest selector, a function call or a script.
usage: tm_profile.py cpu|mem --out F (--pytest SEL | --call pkg.mod:f [--kwargs JSON] | --script FILE)"""
import argparse
import json
import os
import runpy
import sys

from tm_common import REPO, dump, resolve

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["cpu", "mem"])
ap.add_argument("--out", required=True)
ap.add_argument("--pytest")
ap.add_argument("--call")
ap.add_argument("--kwargs", default="{}")
ap.add_argument("--script")
a = ap.parse_args()


def workload():
    if a.pytest:
        import pytest
        pytest.main([*a.pytest.split(), "-p", "no:randomly", "-p", "no:cacheprovider", "--benchmark-disable", "-q", "-x"])
    elif a.call:
        resolve(a.call)(**json.loads(a.kwargs))
    elif a.script:
        runpy.run_path(a.script, run_name="__main__")


def in_project(path):
    p = os.path.abspath(path) if path else ""
    return p.startswith(REPO) or p.startswith("/work/gen")


if a.mode == "cpu":
    from pyinstrument import Profiler
    from pyinstrument.renderers import JSONRenderer
    prof = Profiler(interval=0.0005)
    prof.start()
    workload()
    prof.stop()
    root = json.loads(prof.output(JSONRenderer()))["root_frame"]
    total = root["time"] or 1e-9
    agg = {}

    def walk(fr):
        child = sum(c["time"] for c in fr.get("children", []))
        self_t = max(fr["time"] - child, 0.0)
        key = (fr["function"], fr.get("file_path_short") or fr.get("file_path"), fr.get("line_no"))
        e = agg.setdefault(key, {"function": fr["function"], "file": fr.get("file_path_short"), "path": fr.get("file_path"), "line": fr.get("line_no"),
                                 "self_seconds": 0.0, "project": in_project(fr.get("file_path"))})
        e["self_seconds"] += self_t
        for c in fr.get("children", []):
            walk(c)
    walk(root)
    rows = sorted(agg.values(), key=lambda r: -r["self_seconds"])
    for r in rows:
        r["self_pct"] = round(100 * r["self_seconds"] / total, 2)
    dump(a.out, {"status": "ok", "total_seconds": total, "top": rows[:10], "top_project": [r for r in rows if r["project"]][:10]})
else:
    import memray
    path = "/tmp/tm_mem.bin"
    if os.path.exists(path):
        os.remove(path)
    with memray.Tracker(path):
        workload()
    rd = memray.FileReader(path)
    peak = rd.metadata.peak_memory
    top = {}
    for rec in rd.get_high_watermark_allocation_records(merge_threads=True):
        fr = None
        for f in rec.stack_trace():
            if in_project(f[1]):
                fr = f
                break
        key = (fr[0], os.path.relpath(fr[1], REPO), fr[2]) if fr else ("<non-project>", "", 0)
        top[key] = top.get(key, 0) + rec.size
    rows = [{"function": k[0], "file": k[1], "line": k[2], "bytes": v} for k, v in sorted(top.items(), key=lambda kv: -kv[1])[:10]]
    dump(a.out, {"status": "ok", "engine": "memray", "peak_mb": round(peak / 2**20, 2), "top_allocators": rows})
