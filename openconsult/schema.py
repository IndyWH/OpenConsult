"""The tables, as versioned SQL. One file lists them (spec 6.5).

A change to the tables is a new version here, never an edit of an old
one, so an existing data folder is brought forward step by step.
Stage 2 makes only the tables it uses (spec 15.6).
"""

VERSION = 1

MIGRATIONS = {
    1: """
CREATE TABLE schema_version (
    version INTEGER NOT NULL
);
INSERT INTO schema_version (version) VALUES (1);

-- The one user. The CHECK keeps it to one row (spec 7.1).
-- password_generation goes up at every change or reset, so a login made
-- under an older password ends even when the reset ran in another process.
CREATE TABLE app_user (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    title TEXT NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_generation INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- The audit log only ever grows. The triggers make that true by
-- construction, not by discipline (spec 15.6).
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT
);
CREATE TRIGGER audit_log_never_changed BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'an audit line is never changed');
END;
CREATE TRIGGER audit_log_never_removed BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'an audit line is never removed');
END;

-- The first-run steps done so far, so the app resumes at the first step
-- not done (spec 15.6). The user step is done when app_user has its row.
CREATE TABLE first_run (
    step TEXT PRIMARY KEY,
    done_at TEXT NOT NULL
);
""",
}
