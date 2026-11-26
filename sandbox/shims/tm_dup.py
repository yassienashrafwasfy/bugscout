"""Duplicate-code detection with pylint's symilar API (the engine behind `pylint --enable=duplicate-code`).
Optionally also runs jscpd (--jscpd). usage: tm_dup.py --out F --min-lines 5 PATH..."""
import argparse
import glob
import json
import os
import subprocess
import tempfile

from pylint.checkers.symilar import Symilar

from tm_common import dump

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--min-lines", type=int, default=5)
ap.add_argument("--jscpd", action="store_true")
ap.add_argument("paths", nargs="+")
a = ap.parse_args()
files = []
for p in a.paths:
    files += sorted(glob.glob(os.path.join(p, "**/*.py"), recursive=True)) if os.path.isdir(p) else [p]
s = Symilar(min_lines=a.min_lines, ignore_comments=True, ignore_docstrings=True, ignore_imports=True, ignore_signatures=True)
for f in files:
    with open(f, encoding="utf-8", errors="replace") as fh:
        s.append_stream(f, fh)
clones, dup_lines = [], 0
for n, locs in s._compute_sims():
    clones.append({"lines": n, "locations": sorted(({"file": ls.name, "start": st, "end": en} for ls, st, en in locs),
                                                     key=lambda d: d["file"])})
    dup_lines += n * len(locs)
total = sum(len(ls.stripped_lines) for ls in s.linesets) or 1
out = {"engine": "symilar", "clones": clones, "total_lines": total, "duplicated_lines": dup_lines,
       "duplication_pct": round(100.0 * dup_lines / total, 2)}
if a.jscpd:
    d = tempfile.mkdtemp()
    subprocess.run(["jscpd", *a.paths, "--min-lines", str(a.min_lines), "--min-tokens", "20", "--mode", "weak",
                    "--reporters", "json", "--output", d, "--silent"], capture_output=True)
    rp = os.path.join(d, "jscpd-report.json")
    if os.path.exists(rp):
        j = json.load(open(rp))
        out["jscpd"] = {"statistics": j.get("statistics", {}).get("total"),
                        "clones": [{"first": c["firstFile"]["name"], "second": c["secondFile"]["name"], "lines": c["lines"]}
                                   for c in j.get("duplicates", [])]}
dump(a.out, out)
