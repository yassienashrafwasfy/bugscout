"""One wrapper for every tool: guards -> budget -> event_log -> compact output.

`@tool(executing=True, action=...)` is the ONLY way tools reach the sandbox, so guards cannot be bypassed
by the host. A guard trip returns {"status": "escalation_required", ...} and never runs the tool body.
"""
from __future__ import annotations

import functools
import json
import time
import traceback
from typing import Any, Callable

from .models import err
from .store import runs, tree

MAX_INLINE_CHARS = 6000
REGISTRY: dict[str, Callable] = {}


def compact(run_id: str, tool_name: str, out: dict) -> dict:
    """Keep outputs small: oversized `data` is stored as an artifact and replaced by a stub + id."""
    try:
        blob = json.dumps(out, default=str)
    except Exception:
        return out
    if len(blob) <= MAX_INLINE_CHARS:
        return json.loads(blob)
    aid = runs.add_artifact(run_id, f"{tool_name}_output", out.get("data"))
    data = out.get("data")
    stub: dict[str, Any] = {"artifact_id": aid, "truncated": True}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) < 200):
                stub[k] = v
            elif isinstance(v, list):
                stub[f"{k}_count"] = len(v)
                stub[f"{k}_head"] = json.loads(json.dumps(v[:5], default=str))[:5] if len(json.dumps(v[:5], default=str)) < 1500 else "…"
    return {**{k: v for k, v in out.items() if k != "data"}, "data": stub}


def tool(name: str | None = None, *, executing: bool = False, count_step: bool = True,
         action: Callable[[dict], dict] | None = None):
    """Register + wrap a tool. `action(kwargs)` describes what the call would touch, for the guards.

    action keys (all optional): kind(target|http|run), target_key, path, method, host, endpoint, operation_id,
    requests (int, counted against max_requests), expl_node_id.
    """
    def deco(fn: Callable) -> Callable:
        tname = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            bound = dict(kwargs)
            run_id = bound.get("run_id")
            t0 = time.time()
            outcome, result, steps_now = "ok", None, None
            try:
                if run_id:
                    run = runs.get_run(run_id)
                    if run is None:
                        return err(f"unknown run_id {run_id}")
                    if run["status"] not in ("active",) and tname not in ("end_run", "get_status", "get_report"):
                        return err(f"run is {run['status']}; start a new run")
                    if executing:
                        from .guards import check_action
                        act = action(bound) if action else {}
                        decision = check_action(run_id, tname, act)
                        if decision is not None:       # Escalate or hard stop
                            outcome = decision.get("status", "escalation_required")
                            result = decision
                            return decision
                    if count_step:
                        steps_now = runs.bump_budget(run_id, steps=1).get("steps", 0)
                result = fn(*args, **kwargs)
                outcome = result.get("status", "ok") if isinstance(result, dict) else "ok"
                if run_id and isinstance(result, dict):
                    result = compact(run_id, tname, result)
                return result
            except Exception as e:  # tools must never crash the server
                outcome = "exception"
                result = err(f"{type(e).__name__}: {e}", {"trace": traceback.format_exc()[-1500:]})
                return result
            finally:
                if run_id:
                    dur = int((time.time() - t0) * 1000)
                    try:
                        runs.bump_budget(run_id, seconds=dur / 1000.0)
                        if steps_now is not None:
                            from .guards import stuck
                            stuck.record(run_id, steps_now)
                        runs.log_event(run_id, tname, {k: v for k, v in bound.items() if k != "run_id"}, outcome, dur)
                    except Exception:
                        pass

        REGISTRY[tname] = wrapper
        wrapper.__tool_name__ = tname
        wrapper.__bugscout_count_step__ = count_step
        return wrapper
    return deco


def mark_escalated(expl_node_id: str | None) -> None:
    if expl_node_id:
        node = tree.get_node(expl_node_id)
        if node and node["status"] in ("frontier", "in_progress"):
            tree.update(expl_node_id, status="escalated")
