-- Storage schema — compatible with MySQL and SQLite.
--
-- MySQL:  INTEGER PRIMARY KEY AUTO_INCREMENT
-- SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
--
-- This file uses SQLite syntax. For MySQL, the init code
-- replaces AUTOINCREMENT with AUTO_INCREMENT before executing.

CREATE TABLE IF NOT EXISTS repos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL,
    description     TEXT,
    raw_content     TEXT NOT NULL,
    source_metadata TEXT NOT NULL,
    discovered_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_featured_at TIMESTAMP,
    last_featured_at  TIMESTAMP,
    feature_count   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repos(id),
    summary_type    TEXT NOT NULL,
    content         TEXT NOT NULL,
    model_used      TEXT NOT NULL,
    generated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repos(id),
    feature_type    TEXT NOT NULL,
    featured_date   DATE NOT NULL,
    ranking_criteria TEXT NOT NULL
);
