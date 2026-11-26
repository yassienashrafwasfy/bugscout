-- full logs / reports live here; tool outputs return only ids
CREATE TABLE artifact (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id     uuid REFERENCES run(id) ON DELETE CASCADE,
  kind       text NOT NULL,
  data       jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX ON artifact (run_id, kind);

-- generated tests + what they cover (coverage contexts) and kill (mutation)
CREATE TABLE test_record (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id        uuid REFERENCES run(id) ON DELETE CASCADE,
  expl_node_id  uuid REFERENCES expl_node(id),
  test_id       text NOT NULL,          -- pytest node id
  file          text,
  covered       jsonb,                  -- {file: [lines]}
  covered_sig   text,
  killed_mutants jsonb,
  status        text NOT NULL DEFAULT 'active',  -- active | duplicate | flaky
  created_at    timestamptz DEFAULT now(),
  UNIQUE (run_id, test_id)
);

-- Exploration tree is append-only: only status/result/priority/flaky_score may change.
CREATE FUNCTION expl_node_append_only() RETURNS trigger AS $$
BEGIN
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.run_id IS DISTINCT FROM OLD.run_id
     OR NEW.parent_id IS DISTINCT FROM OLD.parent_id OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.title IS DISTINCT FROM OLD.title OR NEW.hypothesis IS DISTINCT FROM OLD.hypothesis
     OR NEW.target_asset_id IS DISTINCT FROM OLD.target_asset_id
     OR NEW.action IS DISTINCT FROM OLD.action
     OR NEW.input_signature IS DISTINCT FROM OLD.input_signature
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'expl_node is append-only: only status/result/priority/flaky_score may change';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER expl_node_append_only BEFORE UPDATE ON expl_node
  FOR EACH ROW EXECUTE FUNCTION expl_node_append_only();

CREATE FUNCTION event_log_append_only() RETURNS trigger AS $$
BEGIN
  IF pg_trigger_depth() > 1 THEN RETURN COALESCE(OLD, NEW); END IF;  -- allow FK cascade from run
  RAISE EXCEPTION 'event_log is append-only';
END $$ LANGUAGE plpgsql;
CREATE TRIGGER event_log_no_update BEFORE UPDATE ON event_log
  FOR EACH ROW EXECUTE FUNCTION event_log_append_only();
