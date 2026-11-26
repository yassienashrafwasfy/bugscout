"""Send a batch of HTTP requests from inside the sandbox network. usage: tm_batch.py BATCH.json --out F
BATCH.json: {"requests": [{"id","method","url","headers","body"}], "timeout": 15}
out: {"results": {id: {"status_code","headers","text","elapsed_ms"} | {"error","message"}}}"""
import argparse
import json
import time

import httpx

from tm_common import dump

ap = argparse.ArgumentParser()
ap.add_argument("batch")
ap.add_argument("--out", required=True)
a = ap.parse_args()
spec = json.load(open(a.batch))
results = {}
with httpx.Client(timeout=spec.get("timeout", 15), follow_redirects=False) as c:
    for r in spec["requests"]:
        t0 = time.perf_counter()
        try:
            resp = c.request(r["method"], r["url"], headers=r.get("headers") or {}, content=r.get("body"))
            results[r["id"]] = {"status_code": resp.status_code, "headers": {k.lower(): v for k, v in resp.headers.items()},
                                "text": resp.text[:8000], "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
        except Exception as e:  # noqa: BLE001
            results[r["id"]] = {"error": type(e).__name__, "message": str(e)[:200], "timeout": "Timeout" in type(e).__name__}
dump(a.out, {"results": results})
