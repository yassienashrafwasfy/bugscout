"""Pydantic models: charter, node/status enums, tool result envelope."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ORACLES = ["crash", "http_5xx", "schema", "diff_git", "rule", "ruff", "mypy", "bandit", "radon",
           "duplication", "vulture", "mutation", "complexity", "perf_regression", "hotspot", "memory",
           "security", "secrets", "dependency"]
NODE_STATUSES = ["frontier", "in_progress", "done", "dead_end", "escalated", "duplicate", "flaky", "confirmed_bug"]
SEVERITIES = ["low", "medium", "high", "critical"]


class Target(BaseModel):
    kind: Literal["python", "rest_api", "both"]
    repo_path: str
    package: str | None = None
    openapi: str | None = None
    base_url: str | None = None
    start_cmd: str | None = None
    port: int = 8000

    @model_validator(mode="after")
    def _check(self):
        if self.kind in ("python", "both") and not self.package:
            raise ValueError("target.package is required for kind python/both")
        if self.kind in ("rest_api", "both") and not (self.openapi and self.start_cmd):
            raise ValueError("target.openapi and target.start_cmd are required for kind rest_api/both")
        return self


class Scope(BaseModel):
    include: list[str] = Field(default_factory=lambda: ["*"])
    exclude: list[str] = Field(default_factory=list)
    allow_destructive: bool = False
    allowed_hosts: list[str] = Field(default_factory=lambda: ["sut"])


class Rule(BaseModel):
    name: str
    target: str                # "pkg.mod:func"
    property: str              # python expr over `result` and the call args, e.g. "result >= 0"
    assume: str | None = None    # python expr over the args, e.g. "balance >= 0 and amount > 0"
    strategy: str | None = None  # optional hypothesis strategies: python dict literal {arg: "st.floats(0, 1e6)"}


class Reference(BaseModel):
    git_ref: str = "HEAD~1"


class Budget(BaseModel):
    max_steps: int = 400
    max_requests: int = 5000
    max_minutes: float = 60


class Perf(BaseModel):
    max_big_o: dict[str, str] = Field(default_factory=lambda: {"default": "O(n log n)"})
    regression_threshold: float = 0.20
    hotspot_pct: float = 30
    max_memory_mb: float = 512
    max_seconds_per_call: float = 60


class Stuck(BaseModel):
    window_steps: int = 15
    min_progress: int = 1


class Security(BaseModel):
    """Inputs for the security tools. Everything is optional; probes that need credentials are skipped without them."""
    auth_header: str = "Authorization"
    tokens: dict[str, str] = Field(default_factory=dict)      # user name -> full header value, e.g. {"alice": "Bearer alice-token"}
    owned: dict[str, dict[str, list]] = Field(default_factory=dict)   # user -> {"/users/{user_id}/profile": [1]}: resources that user owns
    public_paths: list[str] = Field(default_factory=lambda: ["/health", "/docs", "/redoc", "/openapi.json"])
    osv_lookup: bool = False    # run_pip_audit sends package names+versions to api.osv.dev; off unless the owner opts in
    max_probe_requests: int = 300


class Charter(BaseModel):
    target: Target
    scope: Scope = Field(default_factory=Scope)
    objective: str = "find bugs"
    oracles: list[str] = Field(default_factory=lambda: ["crash", "schema", "diff_git", "rule"])
    rules: list[Rule] = Field(default_factory=list)
    reference: Reference = Field(default_factory=Reference)
    budget: Budget = Field(default_factory=Budget)
    perf: Perf = Field(default_factory=Perf)
    stuck: Stuck = Field(default_factory=Stuck)
    security: Security = Field(default_factory=Security)


def ok(summary: str, data: Any = None, next_suggestions: list[str] | None = None, status: str = "ok") -> dict:
    out: dict[str, Any] = {"status": status, "summary": summary, "data": data if data is not None else {}}
    if next_suggestions:
        out["next_suggestions"] = next_suggestions
    return out


def err(summary: str, data: Any = None) -> dict:
    return ok(summary, data, status="error")
