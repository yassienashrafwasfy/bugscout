-- per-step progress snapshots for the stuck detector
CREATE TABLE progress_snapshot (
  run_id   uuid REFERENCES run(id) ON DELETE CASCADE,
  step     int  NOT NULL,
  score    int  NOT NULL,       -- done/confirmed_bug nodes + non-duplicate findings
  coverage real,                -- latest overall line coverage % (nullable)
  PRIMARY KEY (run_id, step)
);
