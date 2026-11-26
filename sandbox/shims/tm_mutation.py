"""mutmut 3 wrapper: writes [mutmut] config, runs it, reads mutants/**/*.meta (JSON) -> JSON.
usage: tm_mutation.py --out F --paths samplelib/stats.py [--tests tests/test_basic.py] [--deselect ID ...] [--max-seconds 150]"""
import argparse
import glob
import json
import os
import subprocess
import sys

from tm_common import dump

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--paths", nargs="+", required=True)
ap.add_argument("--tests", nargs="*", default=["tests"])
ap.add_argument("--deselect", nargs="*", default=[])
ap.add_argument("--max-seconds", type=int, default=150)
a = ap.parse_args()
top = sorted({p.split("/")[0] for p in a.paths})
args = ["-p", "no:randomly", "-p", "no:cacheprovider", "--benchmark-disable"]
for d in a.deselect:
    args += ["--deselect", d]
def ml(items):          # configparser continuation lines must be indented
    return "".join("\n    " + i for i in items)


lines = ["[mutmut]", f"source_paths={ml(top)}", f"only_mutate={ml(a.paths)}",
         f"pytest_add_cli_args_test_selection={ml(a.tests)}", f"pytest_add_cli_args={ml(args)}"]
open("setup.cfg", "a").write("\n" + "\n".join(lines) + "\n")
subprocess.run(["rm", "-rf", "mutants"])
try:
    p = subprocess.run(["mutmut", "run"], capture_output=True, text=True, timeout=a.max_seconds)
    log = (p.stdout + p.stderr)[-1500:]
    timed_out = False
except subprocess.TimeoutExpired as e:
    log, timed_out = "mutmut timed out", True
mutants = []
for meta in glob.glob("mutants/**/*.meta", recursive=True):
    data = json.load(open(meta))
    src = os.path.relpath(meta[: -len(".meta")], "mutants")
    for key, code in data.get("exit_code_by_key", {}).items():
        status = "not_checked" if code is None else "survived" if code == 0 else "timeout" if code == 36 else "killed"
        mutants.append({"key": key, "file": src, "exit_code": code, "status": status})
for m in mutants:
    if m["status"] == "survived":
        d = subprocess.run(["mutmut", "show", m["key"]], capture_output=True, text=True)
        m["diff"] = d.stdout[-600:]
checked = [m for m in mutants if m["status"] != "not_checked"]
killed = sum(m["status"] in ("killed", "timeout") for m in checked)
dump(a.out, {"status": "ok" if checked else "no_result", "timed_out": timed_out, "mutants": mutants,
             "total": len(mutants), "checked": len(checked), "killed": killed,
             "score": (killed / len(checked)) if checked else None, "log_tail": log if not checked else ""})
