CREATE TABLE run (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  charter       jsonb NOT NULL,
  status        text NOT NULL DEFAULT 'active',   -- active | paused | done | aborted
  budget_used   jsonb NOT NULL DEFAULT '{}',      -- steps, requests, seconds
  created_at    timestamptz DEFAULT now()
);

-- ASSET GRAPH: what exists in the system under test
CREATE TABLE asset_node (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id        uuid REFERENCES run(id) ON DELETE CASCADE,
  type          text NOT NULL,   -- module | class | function | endpoint | param | schema | datastore
  key           text NOT NULL,   -- stable id, e.g. "pkg.mod:func" or "GET /v1/orders/{id}"
  name          text,
  props         jsonb NOT NULL DEFAULT '{}',
    -- complexity, maintainability, coverage_line, coverage_branch, is_dead, dup_group,
    -- static_issues_count, mutation_score, tested (bool),
    -- big_o (e.g. "O(n^2)"), big_o_fit_residual, runtime_ms_p50, runtime_ms_p95,
    -- profile_self_pct, peak_memory_mb
  discovered_by text,
  updated_at    timestamptz DEFAULT now(),
  UNIQUE (run_id, key)
);

CREATE TABLE asset_edge (
  id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id  uuid REFERENCES run(id) ON DELETE CASCADE,
  src_id  uuid REFERENCES asset_node(id) ON DELETE CASCADE,
  dst_id  uuid REFERENCES asset_node(id) ON DELETE CASCADE,
  type    text NOT NULL,   -- calls | imports | contains | has_param | duplicate_of | routes_to
  props   jsonb NOT NULL DEFAULT '{}',
  UNIQUE (run_id, src_id, dst_id, type)
);

-- EXPLORATION TREE: what the agent tried and learned
CREATE TABLE expl_node (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id          uuid REFERENCES run(id) ON DELETE CASCADE,
  parent_id       uuid REFERENCES expl_node(id),
  kind            text NOT NULL,    -- goal | subgoal | idea | test | observation
  status          text NOT NULL DEFAULT 'frontier',
                  -- frontier | in_progress | done | dead_end | escalated | duplicate | flaky | confirmed_bug
  title           text NOT NULL,
  hypothesis      text,
  target_asset_id uuid REFERENCES asset_node(id),
  action          jsonb,            -- tool + args used
  result          jsonb,            -- verdict, oracle outputs, artifacts
  input_signature text,             -- normalized target+input shape, for idea dedup
  priority        real DEFAULT 0,
  flaky_score     real,             -- failure rate across reruns
  created_at      timestamptz DEFAULT now()
);
CREATE INDEX ON expl_node (run_id, status);
CREATE INDEX ON expl_node (run_id, input_signature);

CREATE TABLE finding (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id        uuid REFERENCES run(id) ON DELETE CASCADE,
  expl_node_id  uuid REFERENCES expl_node(id),
  asset_id      uuid REFERENCES asset_node(id),
  kind          text NOT NULL,   -- bug | static_issue | warning | cleanup
  oracle        text,            -- crash | http_5xx | schema | diff_git | rule | ruff | mypy | bandit | radon | duplication | vulture | mutation | complexity | perf_regression | hotspot | memory
  severity      text NOT NULL,   -- low | medium | high | critical
  title         text NOT NULL,
  fingerprint   text,            -- for bug dedup
  duplicate_of  uuid REFERENCES finding(id),
  occurrences   int DEFAULT 1,
  repro         jsonb,           -- minimal input + command to replay
  status        text DEFAULT 'open',  -- open | needs_confirmation | confirmed | rejected
  created_at    timestamptz DEFAULT now()
);
CREATE INDEX ON finding (run_id, fingerprint);

CREATE TABLE escalation (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id      uuid REFERENCES run(id) ON DELETE CASCADE,
  expl_node_id uuid REFERENCES expl_node(id),
  reason      text NOT NULL,   -- destructive | stuck | serious_bug | out_of_scope | budget
  question    text NOT NULL,
  context     jsonb,
  status      text DEFAULT 'pending',  -- pending | approved | denied | answered
  answer      text,
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE event_log (       -- append-only audit trail of every tool call
  id        bigserial PRIMARY KEY,
  run_id    uuid REFERENCES run(id) ON DELETE CASCADE,
  tool      text, args jsonb, outcome text, duration_ms int,
  created_at timestamptz DEFAULT now()
);
