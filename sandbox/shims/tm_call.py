"""Call one function with JSON kwargs, capture result or exception. usage: tm_call.py --target pkg.mod:f --kwargs '{"a":1}' --out F"""
import argparse
import json
import sys

from tm_common import dump, exc_info, resolve

ap = argparse.ArgumentParser()
ap.add_argument("--target", required=True)
ap.add_argument("--kwargs", default="{}")
ap.add_argument("--out", required=True)
ap.add_argument("--property")
a = ap.parse_args()
try:
    fn = resolve(a.target)
    kw = json.loads(a.kwargs)
    res = fn(**kw)
    prop_ok = None
    if a.property:
        prop_ok = bool(eval(a.property, {"__builtins__": __builtins__}, {**kw, "result": res, "args": kw}))
    try:
        json.dumps(res)
        val = res
    except TypeError:
        val = repr(res)
    dump(a.out, {"ok": True, "result": val, "result_repr": repr(res)[:1000], "property_ok": prop_ok})
except BaseException as e:   # noqa: BLE001  (we want SystemExit etc. too)
    dump(a.out, {"ok": False, "exception": exc_info(e)})
