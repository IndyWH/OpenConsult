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
    assert new.version() >= 6          # 8a's version 7 comes with it, as the version 4 test allows for 5
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


def test_6_5_a_version_6_database_with_its_approved_notes_comes_forward_to_7(tmp_path, monkeypatch):
    # The owner's real database and stage7b-data are at version 6 (stage 7).
    # Stage 8a's five tables arrive empty, every row stays, and the CHECKs
    # and the UNIQUEs hold (15.12, The record; R2).
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 6)
    old = open_database(path)
    assert old.version() == 6 and "letter" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    old.execute("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, "
                "speakers_given, state, patient_name, patient_date_of_birth, patient_sex) "
                "VALUES (1, 't', 15, 'nemotron', 'vllm', 'tag', 2, 'final', 'Made-up', '1990-01-01', 'F')")
    old.execute("INSERT INTO note_draft (consultation_id, n, at, asked_by, engine, model_tag, prompt_sha256, transcript, "
                "entries_total, entries_cited, refused, wall_ms) VALUES (1, 1, 't', 'stop', 'e', 't', 'h', 'x', 1, 1, 0, 1)")
    old.execute("INSERT INTO note_approval (consultation_id, draft_id, at, text) VALUES (1, 1, 't', 'made up')")
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() >= 7          # 8b's version 8 comes with it, as the version 6 test allows for 7
    assert {"referral_list", "referral_item", "letter", "letter_edit", "letter_approval"} <= set(new.tables())
    assert Users(new, Audit(new)).verify("example-password")
    assert new.query_one("SELECT text FROM note_approval")["text"] == "made up"
    assert new.query_one("SELECT patient_name FROM consultation")["patient_name"] == "Made-up"
    assert new.query("SELECT * FROM letter") == [] and new.query("SELECT * FROM referral_item") == []
    new.execute("INSERT INTO referral_list (consultation_id, approval_id, at, note_lines, wall_ms) VALUES (1, 1, 't', 'x', 1)")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO referral_list (consultation_id, approval_id, at, note_lines, wall_ms) VALUES (1, 1, 't', 'x', 1)")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO referral_item (consultation_id, kind, specialty, title, note_lines, position, created_at) "
                    "VALUES (1, 'guessed', 's', 't', '[]', 0, 't')")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO referral_item (consultation_id, kind, specialty, title, urgency, note_lines, position, created_at) "
                    "VALUES (1, 'stated', 's', 't', 'soon', '[]', 0, 't')")
    new.execute("INSERT INTO referral_item (consultation_id, kind, specialty, title, note_lines, position, created_at) "
                "VALUES (1, 'named', 's', 't', '[]', 0, 't')")
    new.execute("INSERT INTO letter (consultation_id, item_id, n, at, engine, model_tag, prompt_sha256, note_lines, sentences_total, "
                "sentences_grounded, placeholders, expectations_dropped, refused, wall_ms) VALUES (1, 1, 1, 't', 'e', 't', 'h', 'x', 0, 0, 0, 0, 0, 1)")
    new.execute("INSERT INTO letter_approval (letter_id, at, text) VALUES (1, 't', 'x')")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO letter_approval (letter_id, at, text) VALUES (1, 't', 'y')")
    new.close()


def test_6_5_a_version_7_database_with_its_letters_comes_forward_to_8(tmp_path, monkeypatch):
    # The owner's real database and stage8a-data are at version 7 (stage 8a).
    # Stage 8b's three tables arrive empty (the corpus ships empty, ruling
    # 5), every row stays, and the CHECKs hold (15.12, The passages and the search).
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 7)
    old = open_database(path)
    assert old.version() == 7 and "guideline_source" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    old.execute("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, "
                "speakers_given, state, patient_name, patient_date_of_birth, patient_sex) "
                "VALUES (1, 't', 15, 'nemotron', 'vllm', 'tag', 2, 'final', 'Made-up', '1990-01-01', 'F')")
    old.execute("INSERT INTO note_draft (consultation_id, n, at, asked_by, engine, model_tag, prompt_sha256, transcript, "
                "entries_total, entries_cited, refused, wall_ms) VALUES (1, 1, 't', 'stop', 'e', 't', 'h', 'x', 1, 1, 0, 1)")
    old.execute("INSERT INTO note_approval (consultation_id, draft_id, at, text) VALUES (1, 1, 't', 'made up')")
    old.execute("INSERT INTO referral_item (consultation_id, kind, specialty, title, note_lines, position, created_at) "
                "VALUES (1, 'named', 's', 't', '[]', 0, 't')")
    old.execute("INSERT INTO letter (consultation_id, item_id, n, at, engine, model_tag, prompt_sha256, note_lines, sentences_total, "
                "sentences_grounded, placeholders, expectations_dropped, refused, wall_ms) VALUES (1, 1, 1, 't', 'e', 't', 'h', 'x', 0, 0, 0, 0, 0, 1)")
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() >= 8          # 6c's version 9 comes with it, as the version 6 test allows for 7
    assert {"guideline_source", "guideline_passage", "guideline_answer"} <= set(new.tables())
    assert Users(new, Audit(new)).verify("example-password")
    assert new.query_one("SELECT text FROM note_approval")["text"] == "made up"
    assert new.query_one("SELECT n FROM letter")["n"] == 1
    assert new.query("SELECT * FROM guideline_source") == [] and new.query("SELECT * FROM guideline_passage") == []
    assert new.query("SELECT * FROM guideline_answer") == []
    source = ("INSERT INTO guideline_source (title, publisher, file_name, kind, sha256, bytes, added_at, added_by, "
              "statement_accepted, passage_count, model) VALUES ('t', 'p', 'f', ?, 'h', 1, 't', ?, ?, 1, 'm')")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute(source, ("docx", "page", 1))            # not a kind
    with pytest.raises(sqlite3.DatabaseError):
        new.execute(source, ("html", "page", 0))            # the statement not accepted
    with pytest.raises(sqlite3.DatabaseError):
        new.execute(source, ("html", "model", 1))           # not a way of adding
    new.execute(source, ("html", "page", 1))
    answer = ("INSERT INTO guideline_answer (consultation_id, pass_n, at, names, query, passages, candidates, floor, reranker_ran, "
              "outcome, search_ms, wall_ms, shown) VALUES (1, 1, 't', '[]', 'q', '[]', 0, 0.45, 0, ?, 1, 1, 1)")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute(answer, ("guessed",))
    new.execute(answer, ("below_floor",))
    new.close()


def test_6_5_a_version_8_database_with_its_checked_labels_comes_forward_to_9(tmp_path, monkeypatch):
    # The owner's real database is at version 8 (stage 8b), with consultations whose check of who spoke ran at Stop.
    # Step 6c (15.10, the details: The record; ruling 24): the edits keep their ids and the kind check is allowed;
    # a check that answered at Stop is a run that counts as run, each line still marked with the answer's label before;
    # a refused or failed one is a run that did not answer; the two counts are 0 for a reply the old rule took.
    from openconsult.patients.audit import Audit
    from openconsult.patients.users import Users

    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 8)
    old = open_database(path)
    assert old.version() == 8 and "speaker_check" not in old.tables()
    Users(old, Audit(old)).set_up("Dr", "Example", "example-password")
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    for cid, doctor in ((1, "S1"), (2, "S1"), (3, "none"), (4, "S2")):
        old.execute("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, "
                    "speakers_given, state, doctor_speaker, patient_name, patient_date_of_birth, patient_sex) "
                    "VALUES (1, 't', 15, 'nemotron', 'vllm', 'tag', 2, 'final', ?, 'Made-up', '1990-01-01', 'F')", (doctor,))
    line = ("INSERT INTO transcript_line (consultation_id, n, start_s, end_s, text, raw_speaker, label, changed_by_check, "
            "revised_by_service, unsure, refused, set_by_doctor) VALUES (?, ?, 0.0, 1.0, 'made up', ?, ?, ?, 0, 0, ?, 0)")
    # Consultation 1: the check answered and changed lines 1 (S1, the doctor by the answer) and 3 (S2); line 2 stands; one line refused.
    for n, speaker, label, changed, refused in ((1, "S1", "patient", 1, 0), (2, "S2", "patient", 0, 0), (3, "S2", "doctor", 1, 0), (None, "S1", "unsure", 0, 1)):
        old.execute(line, (1, n, speaker, label, changed, refused))
    old.execute(line, (2, 1, "S1", "doctor", 0, 0))          # consultation 2: the reply was refused
    old.execute(line, (3, 1, "S1", "doctor", 1, 0))          # consultation 3: I cannot tell, then the check named the doctor
    old.execute(line, (4, 1, "S1", "patient", 0, 0))         # consultation 4: the call failed; consultation 5 has no check at all
    call = ("INSERT INTO model_call (at, job, engine, model_tag, prompt_sha256, request, wall_ms, outcome, consultation_id) "
            "VALUES (?, ?, 'vllm', 'tag', 'h', '{}', 1, ?, ?)")
    old.execute(call, ("t1", "note", "ok", 1))
    for at, outcome, cid in (("t2", "ok", 1), ("t3", "ok", 2), ("t4", "ok", 3), ("t5", "too_slow", 4)):
        old.execute(call, (at, "label_check", outcome, cid))
    old.execute("INSERT INTO warning (consultation_id, kind, detail) VALUES (2, 'label_check_refused', 'repeated 2')")
    old.execute("INSERT INTO warning (consultation_id, kind, detail) VALUES (4, 'label_check_failed', 'too_slow')")
    old.execute("INSERT INTO transcript_edit (consultation_id, at, kind, line_n, before, after) VALUES (1, 't', 'words', 2, 'made', 'made up')")
    old.execute("INSERT INTO transcript_edit (consultation_id, at, kind, line_n, before, after) VALUES (1, 't', 'swap', NULL, NULL, NULL)")
    old.execute("DELETE FROM transcript_edit WHERE id = 1")                      # so that an id kept is not an id made again
    old.close()
    monkeypatch.undo()
    new = open_database(path)
    assert new.version() == 9
    assert {"speaker_check", "speaker_check_change", "drug_name_call", "drug_mark", "transcript_edit"} <= set(new.tables())
    assert "transcript_edit_9" not in new.tables() and Users(new, Audit(new)).verify("example-password")
    assert [(r["id"], r["kind"]) for r in new.query("SELECT * FROM transcript_edit")] == [(2, "swap")]
    new.execute("INSERT INTO transcript_edit (consultation_id, at, kind, line_n, before, after) VALUES (1, 't', 'check', NULL, NULL, '2')")
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO transcript_edit (consultation_id, at, kind, line_n, before, after) VALUES (1, 't', 'other', NULL, NULL, NULL)")
    runs = {r["consultation_id"]: dict(r) for r in new.query("SELECT * FROM speaker_check")}
    assert sorted(runs) == [1, 2, 3, 4]
    assert [(runs[c]["outcome"], runs[c]["reason"], runs[c]["named_twice"], runs[c]["dropped"], runs[c]["at_stop"]) for c in (1, 2, 3, 4)] == [
        ("answered", None, 0, 0, 1), ("refused", "repeated 2", None, None, 1), ("answered", None, 0, 0, 1), ("failed", "too_slow", None, None, 1)]
    assert (runs[1]["parts"], runs[1]["joined_lines"], runs[1]["call_ids"], runs[1]["changed"], runs[1]["asked_at"]) == (1, 3, "[2]", 2, "t2")
    changes = [(r["check_id"], r["line_n"], r["label_before"], r["label_after"], r["undone_at"]) for r in new.query("SELECT * FROM speaker_check_change ORDER BY id")]
    assert changes == [(runs[1]["id"], 1, "doctor", "patient", None), (runs[1]["id"], 3, "patient", "doctor", None),
                       (runs[3]["id"], 1, "unsure", "doctor", None)]
    assert new.query("SELECT * FROM drug_name_call") == [] and new.query("SELECT * FROM drug_mark") == []
    assert new.query_one("SELECT COUNT(*) AS n FROM transcript_line")["n"] == 7 and new.query_one("SELECT COUNT(*) AS n FROM model_call")["n"] == 5
    with pytest.raises(sqlite3.DatabaseError):
        new.execute("INSERT INTO speaker_check (consultation_id, asked_at, outcome, parts, joined_lines) VALUES (1, 't', 'half', 1, 1)")
    new.close()
