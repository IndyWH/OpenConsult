"""The one database module and its versioned tables (spec 6.5, 15.6)."""

import sqlite3

import pytest

from openconsult import schema
from openconsult.db import NewerDatabase, open_database


def test_6_5_a_fresh_database_has_every_table_at_the_current_version(tmp_path):
    db = open_database(tmp_path / "data" / "openconsult.db")
    assert db.version() == schema.VERSION
    assert {"app_user", "audit_log", "first_run", "schema_version"} <= set(db.tables())
    db.close()


def test_6_5_opening_the_database_again_changes_nothing(tmp_path):
    path = tmp_path / "openconsult.db"
    first = open_database(path)
    first.execute("INSERT INTO first_run (step, done_at) VALUES (?, ?)", ("statement", "t"))
    first.close()
    second = open_database(path)
    assert second.version() == schema.VERSION
    assert second.query_one("SELECT step FROM first_run")["step"] == "statement"
    second.close()


def test_6_5_a_database_from_a_newer_version_is_refused(tmp_path):
    # Pins V1_LESSONS 6.2: tables change by version number, never by
    # guesswork against whatever file is there.
    path = tmp_path / "openconsult.db"
    open_database(path).close()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE schema_version SET version = ?", (schema.VERSION + 1,))
    raw.commit()
    raw.close()
    with pytest.raises(NewerDatabase):
        open_database(path)


def test_15_6_an_audit_line_can_never_be_changed_or_removed(tmp_path):
    db = open_database(tmp_path / "openconsult.db")
    db.execute("INSERT INTO audit_log (at, event) VALUES (?, ?)", ("t", "login"))
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE audit_log SET event = 'logout'")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("DELETE FROM audit_log")
    assert db.query_one("SELECT event FROM audit_log")["event"] == "login"
    db.close()


def test_6_5_a_version_2_database_with_its_user_comes_forward_to_3(tmp_path, monkeypatch):
    # The owner's real database is at version 2 with his user in it (stage 5a).
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 2)
    old = open_database(path)
    assert old.version() == 2 and "speech_self_test" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() >= 3 and "speech_self_test" in new.tables()
    users = Users(new, Audit(new))
    assert users.exists() and users.verify("example-password") and users.get().name == "Example"
    new.close()


def test_6_5_a_version_3_database_with_its_user_and_self_tests_comes_forward_to_4(tmp_path, monkeypatch):
    # The owner's real database is at version 3 with his user and his
    # self-tests in it (stage 5b to 5d). Stage 6a's tables arrive, model_call
    # gains its tie, and nothing of his is lost (spec 15.10, The record).
    from openconsult.llm.record import CallRow, ModelCalls
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 3)
    old = open_database(path)
    assert old.version() == 3 and "consultation" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.execute("INSERT INTO speech_self_test (at, choice, passed, detail) VALUES ('t', 'nemotron', 1, '{}')")
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() >= 4          # 6b's version 5 comes with it, as the version 2 test allows for 3
    assert {"patient", "consultation", "live_line", "transcript_line", "cds_pass", "warning"} <= set(new.tables())
    assert Users(new, Audit(new)).verify("example-password")
    assert new.query_one("SELECT choice FROM speech_self_test")["choice"] == "nemotron"
    # The old rows of the record have no consultation; a new row may carry one.
    row = CallRow("alarm", "made-up", None, "tag", None, "0" * 64, "{}", None, None, None, 1, None, None, None, None,
                  "ok", None)
    calls = ModelCalls(new)
    assert calls.get(calls.add(row))["consultation_id"] is None
    new.close()


def test_6_5_a_version_4_database_with_its_consultations_comes_forward_to_5(tmp_path, monkeypatch):
    # The owner's real database and stage6a-data are at version 4 with their
    # consultations in them (stage 6a). Stage 6b's note tables arrive,
    # transcript_line gains set_by_doctor, and nothing of theirs is lost.
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 4)
    old = open_database(path)
    assert old.version() == 4 and "note_draft" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    old.execute("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, "
                "speakers_given, state) VALUES (1, 't', 15, 'nemotron', 'vllm', 'tag', 2, 'final')")
    old.execute("INSERT INTO transcript_line (consultation_id, n, start_s, end_s, text, label, changed_by_check, "
                "revised_by_service, unsure, refused) VALUES (1, 1, 0.0, 1.0, 'made up', 'doctor', 1, 0, 0, 0)")
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() >= 5
    assert {"note_draft", "note_entry", "note_edit", "transcript_edit", "note_approval", "note_refusal"} <= set(new.tables())
    assert Users(new, Audit(new)).verify("example-password")
    line = new.query_one("SELECT * FROM transcript_line")
    assert (line["text"], line["changed_by_check"], line["set_by_doctor"]) == ("made up", 1, 0)
    assert new.query_one("SELECT state FROM consultation")["state"] == "final"
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO note_draft (consultation_id, n, at, asked_by, engine, model_tag, prompt_sha256, transcript, "
                    "entries_total, entries_cited, refused, wall_ms) VALUES (1, 1, 't', 'nobody', 'e', 't', 'h', 'x', 0, 0, 0, 1)")
    new.close()


def test_6_5_a_version_5_database_with_its_consultations_comes_forward_to_6(tmp_path, monkeypatch):
    # The owner's real database and stage6b-data are at version 5 (stage 6b).
    # Stage 7a's tables arrive, the consultation keeps the details it ran
    # with, filled from the patient as it stands, its format is wav where a
    # file is named, and the user and every row stay (15.11, The record).
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 5)
    old = open_database(path)
    assert old.version() == 5 and "patient_change" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    old.execute("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, "
                "speakers_given, state, recording_file) VALUES (1, 't', 15, 'nemotron', 'vllm', 'tag', 2, 'final', 'consultation_1.wav')")
    old.execute("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, "
                "speakers_given, state) VALUES (1, 'u', 15, 'nemotron', 'vllm', 'tag', 2, 'final')")
    old.execute("INSERT INTO note_draft (consultation_id, n, at, asked_by, engine, model_tag, prompt_sha256, transcript, "
                "entries_total, entries_cited, refused, wall_ms) VALUES (1, 1, 't', 'stop', 'e', 't', 'h', 'x', 1, 1, 0, 1)")
    old.execute("INSERT INTO note_approval (consultation_id, draft_id, at, text) VALUES (1, 1, 't', 'made up')")
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() == 6
    assert {"patient_change", "audio_deletion", "setting"} <= set(new.tables())
    assert Users(new, Audit(new)).verify("example-password")
    rows = new.query("SELECT * FROM consultation ORDER BY id")
    assert [(r["patient_name"], r["patient_date_of_birth"], r["patient_sex"], r["recording_format"]) for r in rows] == [
        ("Made-up", "1990-01-01", "F", "wav"), ("Made-up", "1990-01-01", "F", None)]
    assert all(r["earlier_notes_shown"] is None and r["audio_deleted_at"] is None for r in rows)
    assert new.query_one("SELECT text FROM note_approval")["text"] == "made up"
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO patient_change (patient_id, field, before, after, at, by_whom) VALUES (1, 'age', 'a', 'b', 't', 'w')")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("UPDATE consultation SET recording_format = 'mp3'")
    new.close()


def test_ruling_8_a_transaction_lands_whole_or_not_at_all(tmp_path):
    db = open_database(tmp_path / "openconsult.db")
    with pytest.raises(sqlite3.DatabaseError):
        with db.transaction() as con:
            con.execute("INSERT INTO first_run (step, done_at) VALUES ('statement', 't')")
            con.execute("INSERT INTO no_such_table (x) VALUES (1)")
    assert db.query("SELECT * FROM first_run") == []
    with db.transaction() as con:
        con.execute("INSERT INTO first_run (step, done_at) VALUES ('statement', 't')")
        con.execute("INSERT INTO first_run (step, done_at) VALUES ('machine', 't')")
    assert [r["step"] for r in db.query("SELECT step FROM first_run ORDER BY step")] == ["machine", "statement"]
    db.close()
