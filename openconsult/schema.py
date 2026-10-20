"""The tables, as versioned SQL. One file lists them (spec 6.5).

A change to the tables is a new version here, never an edit of an old
one, so an existing data folder is brought forward step by step.
Each stage makes only the tables it uses (spec 15.6).
"""

VERSION = 4

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
    # Stage 6a (spec 15.10, The record; 6.3): the patient, the consultation,
    # the live lines as shown, the lines at Stop as the choice gave them and
    # as they stand after the label check, each pass as settled, and every
    # warning the gate raised. model_call rows are tied to their
    # consultation. Every row holds what the patient said, so the tables
    # live in the data folder only.
    4: """
CREATE TABLE patient (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    sex TEXT NOT NULL CHECK (sex IN ('F', 'M')),
    created_at TEXT NOT NULL
);

CREATE TABLE consultation (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patient(id),
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    final_at TEXT,
    intended_minutes INTEGER NOT NULL,
    speech_choice TEXT NOT NULL,
    speech_stamp TEXT,
    engine TEXT NOT NULL,
    engine_version TEXT,
    model_tag TEXT NOT NULL,
    model_digest TEXT,
    echo_cancellation INTEGER,
    noise_suppression INTEGER,
    auto_gain INTEGER,
    sample_rate INTEGER,
    speakers_given INTEGER NOT NULL,
    doctor_speaker TEXT,
    recording_file TEXT,
    loudness TEXT,
    stop_raw TEXT,
    state TEXT NOT NULL CHECK (state IN ('live', 'stopping', 'final')),
    stop_stage TEXT,
    speech_failure TEXT
);

CREATE TABLE live_line (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    n INTEGER NOT NULL,
    line_id INTEGER,
    speaker TEXT,
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    refused INTEGER NOT NULL,
    shown_at_s REAL NOT NULL
);

CREATE TABLE transcript_line (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    n INTEGER,
    line_id INTEGER,
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    text TEXT NOT NULL,
    confidence REAL,
    raw_speaker TEXT,
    label TEXT NOT NULL CHECK (label IN ('doctor', 'patient', 'unsure')),
    changed_by_check INTEGER NOT NULL,
    revised_by_service INTEGER NOT NULL,
    unsure INTEGER NOT NULL,
    refused INTEGER NOT NULL
);

CREATE TABLE cds_pass (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    n INTEGER NOT NULL,
    at TEXT NOT NULL,
    transcript TEXT NOT NULL,
    alarm_call_id INTEGER REFERENCES model_call(id),
    assessment_call_id INTEGER REFERENCES model_call(id),
    result TEXT NOT NULL,
    shown INTEGER NOT NULL
);

CREATE TABLE warning (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    kind TEXT NOT NULL,
    start_s REAL,
    end_s REAL,
    line_n INTEGER,
    detail TEXT
);

ALTER TABLE model_call ADD COLUMN consultation_id INTEGER REFERENCES consultation(id);
""",
}
