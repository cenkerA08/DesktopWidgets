-- One row per installation. Country comes from Cloudflare; no IP is stored.
CREATE TABLE IF NOT EXISTS installs (
  install_id  TEXT PRIMARY KEY,
  country     TEXT NOT NULL DEFAULT 'XX',
  version     TEXT NOT NULL DEFAULT '',
  os          TEXT NOT NULL DEFAULT '',
  first_seen  TEXT NOT NULL,             -- YYYY-MM-DD
  last_seen   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_installs_country   ON installs(country);
CREATE INDEX IF NOT EXISTS idx_installs_last_seen ON installs(last_seen);

CREATE TABLE IF NOT EXISTS feedback (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  install_id  TEXT NOT NULL,
  version     TEXT NOT NULL DEFAULT '',
  country     TEXT NOT NULL DEFAULT 'XX',
  rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  text        TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL              -- ISO timestamp
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at);
