"""Tiny HTTP load generator. usage: tm_load.py --url U --n 200 [--concurrency 4] --out F  (GET only)"""
import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from tm_common import dump

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--n", type=int, default=200)
ap.add_argument("--concurrency", type=int, default=4)
ap.add_argument("--out", required=True)
a = ap.parse_args()
lat, codes, errors = [], {}, 0


def one(_):
    global errors
    t0 = time.perf_counter()
    try:
        r = httpx.get(a.url, timeout=10)
        codes[r.status_code] = codes.get(r.status_code, 0) + 1
    except Exception:  # noqa: BLE001
        errors += 1
        return
    lat.append((time.perf_counter() - t0) * 1000)


t = time.perf_counter()
with ThreadPoolExecutor(a.concurrency) as ex:
    list(ex.map(one, range(a.n)))
dt = time.perf_counter() - t
lat.sort()
pct = lambda p: lat[min(len(lat) - 1, int(p * len(lat)))] if lat else None
dump(a.out, {"requests": a.n, "errors": errors, "status_codes": codes, "seconds": dt, "rps": a.n / dt if dt else None,
             "p50_ms": pct(0.5), "p95_ms": pct(0.95), "max_ms": lat[-1] if lat else None,
             "mean_ms": statistics.mean(lat) if lat else None})
