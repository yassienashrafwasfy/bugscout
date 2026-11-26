"""Environment-driven configuration."""
from __future__ import annotations

import os
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://test:test@localhost:5432/bugscout")
DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE", "bugscout-sandbox:latest")
MIGRATIONS_DIR = Path(os.environ.get("BUGSCOUT_MIGRATIONS_DIR", Path(__file__).resolve().parents[2] / "migrations"))
SANDBOX_DIR = Path(os.environ.get("BUGSCOUT_SANDBOX_DIR", Path(__file__).resolve().parents[2] / "sandbox"))

# Every container gets fixed limits so numbers are comparable across runs (and the host box survives).
CONTAINER_CPUS = float(os.environ.get("BUGSCOUT_CPUS", "2"))
CONTAINER_MEMORY = os.environ.get("BUGSCOUT_MEMORY", "1536m")
DEFAULT_TIMEOUT_S = int(os.environ.get("BUGSCOUT_TIMEOUT", "120"))

# BUGSCOUT_PROVISION=0 skips creating containers in start_run (store-only unit tests).
PROVISION = os.environ.get("BUGSCOUT_PROVISION", "1") == "1"
AUTO_BUILD_IMAGE = os.environ.get("BUGSCOUT_AUTO_BUILD", "1") == "1"

# max_minutes is measured as the SUM of tool-call durations (not wall clock since created_at),
# so a human thinking/answering an escalation does not burn the budget.
BUDGET_WARN_FRACTION = 0.9
