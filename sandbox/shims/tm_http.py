"""One HTTP request from inside the sandbox network. usage: tm_http.py REQUEST.json --out F
REQUEST.json: {"method","url","headers","body"(json or str),"timeout"}"""
import argparse
import json
import time

import httpx

from tm_common import dump

ap = argparse.ArgumentParser()
ap.add_argument("req")
ap.add_argument("--out", required=True)
a = ap.parse_args()
r = json.load(open(a.req))
t0 = time.perf_counter()
try:
    kw = {}
    if r.get("body") is not None:
        kw["json" if not isinstance(r["body"], str) else "content"] = r["body"]
    resp = httpx.request(r["method"], r["url"], headers=r.get("headers") or {}, timeout=r.get("timeout", 20), **kw)
    try:
        js = resp.json()
    except Exception:
        js = None
    dump(a.out, {"status_code": resp.status_code, "headers": dict(resp.headers), "text": resp.text[:8000], "json": js,
                 "elapsed_ms": int((time.perf_counter() - t0) * 1000)})
except Exception as e:  # noqa: BLE001
    dump(a.out, {"error": type(e).__name__, "message": str(e)[:300], "timeout": "Timeout" in type(e).__name__,
                 "elapsed_ms": int((time.perf_counter() - t0) * 1000)})
