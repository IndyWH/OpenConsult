"""The tables, as versioned SQL. One file lists them (spec 6.5).

A change to the tables is a new version here, never an edit of an old
one, so an existing data folder is brought forward step by step.
Each stage makes only the tables it uses (spec 15.6).
"""

VERSION = 3

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
    # The record of every model call (spec 15.7; 6.5; V1_LESSONS 3.12,
    # 3.13). Written by the door itself, so no call can skip it. It holds
    # what the patient said, so it lives in the data folder only. Stage 6
    # ties each row to its consultation.
    2: """
CREATE TABLE model_call (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    job TEXT NOT NULL,
    engine TEXT NOT NULL,
    engine_version TEXT,
    model_tag TEXT NOT NULL,
    model_digest TEXT,
    prompt_sha256 TEXT NOT NULL,
    request TEXT NOT NULL,
    reply TEXT,
    prompt_tokens INTEGER,
    output_tokens INTEGER,
    wall_ms INTEGER NOT NULL,
    total_ms INTEGER,
    load_ms INTEGER,
    read_ms INTEGER,
    write_ms INTEGER,
    outcome TEXT NOT NULL,
    detail TEXT
);
""",
    # The stored results of the speech self-test (spec 15.9; D46), one row
    # per run; This machine reads the last. detail is JSON: the words heard
    # live and at Stop, the delays, the seconds, what the rule refused, the
    # raw segments and the stamp.
    3: """
CREATE TABLE speech_self_test (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    choice TEXT NOT NULL,
    passed INTEGER NOT NULL,
    detail TEXT NOT NULL
);
""",
}
