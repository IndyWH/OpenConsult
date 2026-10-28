"""The tables, as versioned SQL. One file lists them (spec 6.5).

A change to the tables is a new version here, never an edit of an old
one, so an existing data folder is brought forward step by step.
Each stage makes only the tables it uses (spec 15.6).
"""

VERSION = 7

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
    # Stage 6b (spec 15.10, The record; rulings 8 and 11; R2, R20): the note
    # drafts, each with its stamp, its prompt hash, its entries with their
    # line numbers, its citation count and whether it was refused; the
    # doctor's edits to entries, words and labels; the approval and the
    # refusal; the earlier draft kept at draft again (the latest n is the
    # page's). A line's label set by the doctor is marked.
    5: """
CREATE TABLE note_draft (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    n INTEGER NOT NULL,
    at TEXT NOT NULL,
    asked_by TEXT NOT NULL CHECK (asked_by IN ('stop', 'draft', 'again')),
    call_id INTEGER REFERENCES model_call(id),
    engine TEXT NOT NULL,
    engine_version TEXT,
    model_tag TEXT NOT NULL,
    model_digest TEXT,
    prompt_sha256 TEXT NOT NULL,
    transcript TEXT NOT NULL,
    last_edit_id INTEGER,
    reasoning TEXT,
    entries_total INTEGER NOT NULL,
    entries_cited INTEGER NOT NULL,
    refused INTEGER NOT NULL,
    failure TEXT,
    wall_ms INTEGER NOT NULL
);

CREATE TABLE note_entry (
    id INTEGER PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES note_draft(id),
    section TEXT NOT NULL CHECK (section IN ('subjective', 'objective', 'assessment', 'plan')),
    position INTEGER NOT NULL,
    model_text TEXT NOT NULL,
    text TEXT NOT NULL,
    turns TEXT NOT NULL,
    lines TEXT NOT NULL,
    uncited INTEGER NOT NULL
);

CREATE TABLE note_edit (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES note_entry(id),
    at TEXT NOT NULL,
    text_before TEXT NOT NULL,
    text_after TEXT NOT NULL
);

CREATE TABLE transcript_edit (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    at TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('words', 'label', 'undo', 'swap')),
    line_n INTEGER,
    before TEXT,
    after TEXT
);

CREATE TABLE note_approval (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL UNIQUE REFERENCES consultation(id),
    draft_id INTEGER NOT NULL REFERENCES note_draft(id),
    at TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE note_refusal (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    draft_id INTEGER NOT NULL REFERENCES note_draft(id),
    at TEXT NOT NULL
);

ALTER TABLE transcript_line ADD COLUMN set_by_doctor INTEGER NOT NULL DEFAULT 0;
""",
    # Stage 7a (spec 15.11, The record; rulings 2, 3, 7 and 8; 7.3 rule 4):
    # every change to a patient's details with what stood before; on the
    # consultation the three details it ran with (copied at Start, so an
    # earlier consultation is never rewritten), the switch's setting, the
    # numbers of the earlier notes shown at Start, the recording's format,
    # a failed conversion's reason and the date the audio went; the sweep's
    # deletions; and the first setting a page can change. A version 5
    # folder comes forward with every row, the details filled from the
    # patient as it stands.
    6: """
CREATE TABLE patient_change (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patient(id),
    field TEXT NOT NULL CHECK (field IN ('name', 'date_of_birth', 'sex')),
    before TEXT NOT NULL,
    after TEXT NOT NULL,
    at TEXT NOT NULL,
    by_whom TEXT NOT NULL
);

ALTER TABLE consultation ADD COLUMN patient_name TEXT;
ALTER TABLE consultation ADD COLUMN patient_date_of_birth TEXT;
ALTER TABLE consultation ADD COLUMN patient_sex TEXT;
ALTER TABLE consultation ADD COLUMN earlier_notes_shown INTEGER;
ALTER TABLE consultation ADD COLUMN earlier_notes TEXT;
ALTER TABLE consultation ADD COLUMN recording_format TEXT CHECK (recording_format IN ('wav', 'opus'));
ALTER TABLE consultation ADD COLUMN conversion_failure TEXT;
ALTER TABLE consultation ADD COLUMN audio_deleted_at TEXT;
UPDATE consultation SET
    patient_name = (SELECT name FROM patient WHERE patient.id = consultation.patient_id),
    patient_date_of_birth = (SELECT date_of_birth FROM patient WHERE patient.id = consultation.patient_id),
    patient_sex = (SELECT sex FROM patient WHERE patient.id = consultation.patient_id);
UPDATE consultation SET recording_format = 'wav' WHERE recording_file IS NOT NULL;

CREATE TABLE audio_deletion (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    consultation_ids TEXT NOT NULL,
    files INTEGER NOT NULL,
    bytes INTEGER NOT NULL
);

CREATE TABLE setting (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    changed_at TEXT NOT NULL
);
""",

    # Stage 8a (spec 15.12, The record; rulings 1, 2, 4 and 11; R2, R5,
    # R20): the referral list made from an approved note, once; its items
    # in three kinds; each letter with its stamp, the note lines it was
    # sent, the body as the model gave it and as the check left it, the
    # four counts and whether it was refused; the doctor's paragraph
    # edits; the approval, once per letter. A version 6 folder comes
    # forward with every row; these tables start empty.
    7: """
CREATE TABLE referral_list (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    approval_id INTEGER NOT NULL UNIQUE REFERENCES note_approval(id),
    at TEXT NOT NULL,
    call_id INTEGER REFERENCES model_call(id),
    note_lines TEXT NOT NULL,
    reasoning TEXT,
    failure TEXT,
    wall_ms INTEGER NOT NULL
);

CREATE TABLE referral_item (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    list_id INTEGER REFERENCES referral_list(id),
    kind TEXT NOT NULL CHECK (kind IN ('stated', 'suggested', 'named')),
    specialty TEXT NOT NULL,
    title TEXT NOT NULL,
    reason TEXT,
    urgency TEXT CHECK (urgency IN ('urgent', 'routine')),
    note_lines TEXT NOT NULL,
    call_id INTEGER REFERENCES model_call(id),
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE letter (
    id INTEGER PRIMARY KEY,
    consultation_id INTEGER NOT NULL REFERENCES consultation(id),
    item_id INTEGER NOT NULL REFERENCES referral_item(id),
    n INTEGER NOT NULL,
    at TEXT NOT NULL,
    call_id INTEGER REFERENCES model_call(id),
    engine TEXT NOT NULL,
    engine_version TEXT,
    model_tag TEXT NOT NULL,
    model_digest TEXT,
    prompt_sha256 TEXT NOT NULL,
    note_lines TEXT NOT NULL,
    reasoning TEXT,
    model_body TEXT,
    body TEXT,
    check_detail TEXT,
    sentences_total INTEGER NOT NULL,
    sentences_grounded INTEGER NOT NULL,
    placeholders INTEGER NOT NULL,
    expectations_dropped INTEGER NOT NULL,
    refused INTEGER NOT NULL,
    failure TEXT,
    wall_ms INTEGER NOT NULL,
    doctor_refused_at TEXT
);

CREATE TABLE letter_edit (
    id INTEGER PRIMARY KEY,
    letter_id INTEGER NOT NULL REFERENCES letter(id),
    paragraph INTEGER NOT NULL,
    at TEXT NOT NULL,
    text_before TEXT NOT NULL,
    text_after TEXT NOT NULL
);

CREATE TABLE letter_approval (
    id INTEGER PRIMARY KEY,
    letter_id INTEGER NOT NULL UNIQUE REFERENCES letter(id),
    at TEXT NOT NULL,
    text TEXT NOT NULL
);
""",
}
