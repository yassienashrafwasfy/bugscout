"""Empirical time complexity: measure at growing n (median of repeats, warm-up first), then pick the best-fitting growth class.
usage: tm_bigo.py --target pkg.mod:f --out F [--sizes 10,100,1000] [--gen FILE.py (defines gen(n))] [--max-seconds 60]"""
import argparse
import inspect
import math
import random
import statistics
import time
import typing

import big_o.complexities as C
import numpy as np

from tm_common import dump, resolve

ap = argparse.ArgumentParser()
ap.add_argument("--target", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--sizes")
ap.add_argument("--gen")
ap.add_argument("--max-seconds", type=float, default=60)
ap.add_argument("--min-n", type=int, default=10)
ap.add_argument("--max-n", type=int, default=100000)
ap.add_argument("--n-measures", type=int, default=10)
a = ap.parse_args()
fn = resolve(a.target)
LABELS = [(C.Constant, "O(1)"), (C.Logarithmic, "O(log n)"), (C.Linear, "O(n)"), (C.Linearithmic, "O(n log n)"),
          (C.Quadratic, "O(n^2)"), (C.Cubic, "O(n^3)"), (C.Exponential, "O(2^n)")]


def auto_gen():
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = {}
    first = next(iter(sig.parameters))
    h = str(hints.get(first, ""))
    extra = {k: v.default for k, v in list(sig.parameters.items())[1:] if v.default is not inspect.Parameter.empty}
    if "list" in h or "Sequence" in h or "Iterable" in h:
        make = lambda n: random.sample(range(10 * n + 10), n) if "int" in h else [random.random() for _ in range(n)]
    elif "str" in h:
        make = lambda n: "".join(random.choice("abcdefgh") for _ in range(n))
    elif "dict" in h:
        make = lambda n: {i: i for i in range(n)}
    elif "int" in h:
        make = lambda n: n
    else:
        raise SystemExit(dump(a.out, {"status": "no_generator", "reason": f"cannot build input for parameter '{first}' ({h or 'no hint'}); pass input_generator"}))
    return lambda n: ((make(n),), extra)


if a.gen:
    ns_ = {}
    exec(open(a.gen).read(), ns_)
    g = ns_["gen"]
    gen = lambda n: ((g(n),), {})
else:
    gen = auto_gen()

sizes = ([int(x) for x in a.sizes.split(",")] if a.sizes else
         sorted({int(round(math.exp(math.log(a.min_n) + i * (math.log(a.max_n) - math.log(a.min_n)) / (a.n_measures - 1)))) for i in range(a.n_measures)}))
args0, kw0 = gen(sizes[0])
fn(*args0, **kw0)  # warm-up
t_start, points, truncated = time.perf_counter(), [], False
for n in sizes:
    args, kw = gen(n)
    times = []
    t_n = time.perf_counter()
    while True:
        t0 = time.perf_counter()
        fn(*args, **kw)
        times.append(time.perf_counter() - t0)
        if len(times) >= 7 or sum(times) > 0.2 and len(times) >= 3 or times[-1] > 1.0:
            break
    points.append({"n": n, "seconds": statistics.median(times), "repeats": len(times)})
    spent = time.perf_counter() - t_start
    # stop growing when the next size (x~3) would blow the per-call cap
    if spent + 3.5 * (time.perf_counter() - t_n) > a.max_seconds * 0.9 and n != sizes[-1]:
        truncated = True
        break

# Points near the timer floor are mostly call overhead and say nothing about growth: fit on the points above the highest
# floor that still leaves >= 5 of them (then >= 4), falling back to everything.
fit_pts = points
for need in (5, 4):
    chosen = None
    for floor in (1e-3, 2e-4, 2e-5):
        sel = [p for p in points if p["seconds"] >= floor]
        if len(sel) >= need:
            chosen = sel
            break
    if chosen:
        fit_pts = chosen
        break

ns = np.array([p["n"] for p in fit_pts], dtype=float)
ts = np.array([p["seconds"] for p in fit_pts], dtype=float)
MODEL = {"O(1)": lambda n: np.ones_like(n), "O(log n)": np.log, "O(n)": lambda n: n, "O(n log n)": lambda n: n * np.log(n),
         "O(n^2)": lambda n: n ** 2, "O(n^3)": lambda n: n ** 3, "O(2^n)": lambda n: np.exp2(np.minimum(n, 1000.0))}
fits = []
if len(fit_pts) >= 4:
    for cls, label in LABELS:
        # selection: scale-free fit t = c * f(n), c chosen in log space (no intercept) -> RMS log error. Robust against the constant
        # call overhead and against the largest points dominating, which a plain least-squares fit is not.
        lf = np.log(np.maximum(MODEL[label](ns), 1e-300))
        c = float(np.mean(np.log(ts) - lf))
        log_rms = float(np.sqrt(np.mean((np.log(ts) - lf - c) ** 2)))
        row = {"class": label, "log_rms": log_rms}
        try:   # big_O's own least-squares residual, kept as a cross-check
            row["residual"] = float(cls().fit(ns, ts))
        except Exception as e:  # noqa: BLE001
            row["residual_error"] = str(e)[:80]
        fits.append(row)
good = sorted(fits, key=lambda f: f["log_rms"])
best = good[0] if good else None
plausible = [f["class"] for f in good if f["log_rms"] <= best["log_rms"] * 1.15 + 0.02] if best else []
poor_fit = best is None or best["log_rms"] > 0.35
dump(a.out, {"status": "ok" if best else "too_few_points", "points": points, "fits": fits, "best": best["class"] if best else None,
             "residual": best["log_rms"] if best else None, "plausible": plausible, "poor_fit": bool(poor_fit),
             "fit_points": len(fit_pts), "truncated": truncated, "seconds_total": time.perf_counter() - t_start})
