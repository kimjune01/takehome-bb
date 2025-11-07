-- Associations Pipeline Database Schema
-- Run this to create the associations and embedding tables

-- Associations table: Links signals to issues with scores
CREATE TABLE IF NOT EXISTS associations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL,
    issue_id TEXT NOT NULL,
    score REAL NOT NULL,
    reason TEXT,
    method TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id),
    FOREIGN KEY (issue_id) REFERENCES issues(identifier),
    UNIQUE(signal_id, issue_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_associations_signal ON associations(signal_id);
CREATE INDEX IF NOT EXISTS idx_associations_issue ON associations(issue_id);
CREATE INDEX IF NOT EXISTS idx_associations_score ON associations(score DESC);

-- Signal embeddings table: Cached embeddings for reuse
CREATE TABLE IF NOT EXISTS signal_embeddings (
    signal_id INTEGER PRIMARY KEY,
    embedding TEXT NOT NULL,  -- JSON array of floats
    model TEXT DEFAULT 'text-embedding-3-small',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

-- Issue embeddings table: Cached embeddings for reuse
CREATE TABLE IF NOT EXISTS issue_embeddings (
    issue_id TEXT PRIMARY KEY,
    embedding TEXT NOT NULL,  -- JSON array of floats
    model TEXT DEFAULT 'text-embedding-3-small',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES issues(identifier)
);
