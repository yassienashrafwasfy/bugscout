"""Property-based test of one function (also used for charter rules).
usage: tm_hyp.py --target pkg.mod:f --out F [--max-examples 200] [--strategies '{"x":"st.integers()"}'] [--assume EXPR] [--property EXPR]"""
import argparse
import inspect
import json
import typing

import hypothesis
from hypothesis import HealthCheck, Phase, given, settings
from hypothesis import strategies as st

from tm_common import dump, exc_info, resolve

ap = argparse.ArgumentParser()
ap.add_argument("--target", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--max-examples", type=int, default=200)
ap.add_argument("--strategies", default="{}")
ap.add_argument("--assume")
ap.add_argument("--property")
a = ap.parse_args()


class RuleViolation(AssertionError):
    pass


fn = resolve(a.target)
sig = inspect.signature(fn)
try:
    hints = typing.get_type_hints(fn)
except Exception:
    hints = {}
given_code = json.loads(a.strategies)
strats, skipped = {}, []
for name, p in sig.parameters.items():
    if name in given_code:
        strats[name] = eval(given_code[name], {"st": st, "hypothesis": hypothesis})
    elif name in hints:
        try:
            strats[name] = st.from_type(hints[name])
        except Exception:
            skipped.append(name)
    elif p.default is not inspect.Parameter.empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
        skipped.append(name)
    else:
        dump(a.out, {"status": "no_strategy", "reason": f"parameter '{name}' has no type hint; pass strategies"})
        raise SystemExit(0)
last, count = {}, [0]


@settings(max_examples=a.max_examples, deadline=None, database=None, report_multiple_bugs=False,
          suppress_health_check=list(HealthCheck), phases=[Phase.explicit, Phase.generate, Phase.shrink])
@given(st.fixed_dictionaries(strats))
def prop(kw):
    last.clear(); last.update(kw)
    count[0] += 1
    if a.assume:
        hypothesis.assume(eval(a.assume, {"__builtins__": __builtins__}, dict(kw)))
    result = fn(**kw)
    if a.property:
        if not eval(a.property, {"__builtins__": __builtins__}, {**kw, "result": result, "args": kw}):
            raise RuleViolation(f"property violated: {a.property}")


try:
    prop()
    dump(a.out, {"status": "passed", "examples_run": count[0], "skipped_params": skipped})
except BaseException as e:   # noqa: BLE001
    kind = "rule" if isinstance(e, RuleViolation) else "crash"
    dump(a.out, {"status": "failed", "kind": kind, "examples_run": count[0], "skipped_params": skipped,
                 "failure": exc_info(e), "example": {k: repr(v) for k, v in last.items()},
                 "example_json": json.loads(json.dumps(last, default=repr))})
