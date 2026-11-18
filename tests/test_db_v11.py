"""The tables of version 11 (spec 15.13, the details of run 9b: The
record; 6.5): a folder of version 10 comes forward with every row, an
older consultation reads this computer for both, and the new rows of a
consultation are deleted with it."""

from __future__ import annotations

from openconsult import schema
from openconsult.consult.consultations import Consultations
from openconsult.db import open_database
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath

OLDER = ("INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, model_tag, speakers_given, state, "
         "doctor_speaker, patient_name, patient_date_of_birth, patient_sex) "
         "VALUES (1, 't', 15, 'nemotron', 'vllm', 'tag', 2, 'final', 'S1', 'Made-up', '1990-01-01', 'F')")


def test_6_5_a_version_10_database_comes_forward_to_11_with_every_row_and_an_older_consultation_reads_this_computer(tmp_path, monkeypatch, clock):
    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 10)
    old = open_database(path)
    assert old.version() == 10 and "speech_session" not in old.tables()
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    old.execute(OLDER)
    old.execute("INSERT INTO live_line (consultation_id, n, line_id, speaker, start_s, end_s, text, confidence, refused, shown_at_s) "
                "VALUES (1, 1, 1, 'S1', 0.0, 1.0, 'made up words', NULL, 0, 1.5)")
    old.execute("INSERT INTO transcript_line (consultation_id, n, line_id, start_s, end_s, text, raw_speaker, label, changed_by_check, "
                "revised_by_service, unsure, refused) VALUES (1, 1, 1, 0.0, 1.0, 'made up words', 'S1', 'doctor', 0, 0, 0, 0)")
    old.execute("INSERT INTO setting (name, value, changed_at) VALUES ('audio_retention_days', '30', 't')")
    old.execute("INSERT INTO first_run (step, done_at) VALUES ('statement', 't')")
    counts = {t: old.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in old.tables()}
    old.close()
    monkeypatch.setattr(schema, "VERSION", 11)              # the step from 10 to 11 by itself, now that a later version exists (run 9c)
    new = open_database(path)
    assert new.version() == 11
    assert {t: new.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in counts} == counts          # every row came forward
    assert {"speech_session", "recording_upload", "first_run_left"} <= set(new.tables())
    rows = Consultations(new, clock)
    row = rows.get(1)
    assert (row["language_model_path"], row["transcription_path"], row["better_accuracy"], row["statement_sha256"]) == (
        THIS_COMPUTER, THIS_COMPUTER, 0, None)
    assert rows.live_lines(1)[0]["session"] == 1 and rows.transcript_lines(1)[0]["session"] == 1
    assert rows.sessions(1) == [] and rows.upload(1) is None
    assert new.query_one("SELECT value FROM setting WHERE name = 'audio_retention_days'")["value"] == "30"
    new.close()


def test_details_of_9b_a_consultation_keeps_the_path_it_started_with_its_sessions_and_its_recording_sent_and_never_a_key(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    db.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    rows = Consultations(db, clock)
    cid = rows.start(1, 15, "speechmatics", "claude", "made-up version", "claude-haiku-5-5", None, 2,
                     path=ChosenPath(CLAUDE, SPEECHMATICS), statement_sha256="a" * 64)
    row = rows.get(cid)
    assert (row["language_model_path"], row["transcription_path"], row["better_accuracy"], row["statement_sha256"]) == (
        CLAUDE, SPEECHMATICS, 0, "a" * 64)
    # The tick counts only where the transcription runs on this computer (15.9, ruling 36).
    ticked = rows.start(1, 15, "nemotron", "vllm", None, "tag", None, 2, path=ChosenPath(THIS_COMPUTER, THIS_COMPUTER, True))
    assert rows.get(ticked)["better_accuracy"] == 1
    assert rows.get(rows.start(1, 15, "speechmatics", "vllm", None, "tag", None, 2,
                               path=ChosenPath(THIS_COMPUTER, SPEECHMATICS, True)))["better_accuracy"] == 0
    assert rows.get(rows.start(1, 15, "nemotron", "vllm", None, "tag", None, 2))["transcription_path"] == THIS_COMPUTER
    # The sessions: written from the first loss on, each with its seconds, its reason and its own answer.
    rows.add_session(cid, 1, 0.0)
    rows.lose_session(cid, 1, 42.5, "made-up reason")
    rows.add_session(cid, 2, 61.0)
    rows.answer_session(cid, 2, "S2")
    rows.lose_session(cid, 1, 99.0, "a second loss of the same session changes nothing")
    assert [(s["n"], s["opened_at_s"], s["lost_at_s"], s["reason"], s["doctor_speaker"]) for s in rows.sessions(cid)] == [
        (1, 0.0, 42.5, "made-up reason", None), (2, 61.0, None, None, "S2")]
    # The recording sent after Stop: one row, with the job, the delete and its proof.
    rows.add_upload(ticked, "tick", "recording.wav", 1234)
    rows.end_upload(ticked, "made-up-job", 6.3, 290.0, {"model": "enhanced"}, {"status": 200}, [{"what": "the job", "status": 404}],
                    True, "the job: HTTP 404", None, result=True)
    sent = rows.upload(ticked)
    assert (sent["way"], sent["file_name"], sent["bytes"], sent["job_id"], sent["gone"], sent["proof"], sent["failure"]) == (
        "tick", "recording.wav", 1234, "made-up-job", 1, "the job: HTTP 404", None)
    assert sent["applied"] == {"model": "enhanced"} and sent["asked_again"] == [{"what": "the job", "status": 404}] and sent["result_at"]
    assert [r["name"] for r in db.query("PRAGMA table_info(recording_upload)") if "key" in r["name"]] == []      # no column for a key
    # 15.11 ruling 8: the new rows go with their consultation, in the one transaction; the audit line names them
    # where there are any, and reads as it always did where there are none.
    from openconsult.consult import deletion
    with db.transaction() as con:
        with_sessions, with_upload = deletion.delete_rows(con, cid), deletion.delete_rows(con, ticked)
    assert rows.sessions(cid) == [] and rows.upload(ticked) is None and rows.get(cid) is None and rows.get(ticked) is None
    assert (with_sessions["speech_sessions"], with_sessions["recordings_sent"]) == (2, 0)
    line = deletion.Deleted(cid, 1, "2026-10-04", with_sessions, None, 0).line()
    assert ", 2 speech sessions, " in line and "recordings sent" not in line
    line = deletion.Deleted(ticked, 1, "2026-10-04", with_upload, None, 0).line()
    assert ", 1 recordings sent, " in line and "speech sessions" not in line
    db.close()
