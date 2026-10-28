"""Deleting (spec 15.11 ruling 8; D44; R15; V1_LESSONS 10.3, 10.4, 10.5):
one function, the rows in one transaction, then the file, one audit
line with counts and no words; the question asked once; a patient
deleted only when no consultation is left. Made-up everything."""

import sqlite3

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.consult import deletion
from openconsult.consult.background import block_for
from openconsult.consult.earlier import approved_notes
from openconsult.settings import store
from tests.conftest import PORT, refusal_on, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_review_page import LINES, engine_with, nemotron_doors, run_through
from tests.test_start import PATIENT, TICKS, app_with

TABLES = ("letter_edit", "letter_approval", "letter", "referral_item", "referral_list", "note_edit", "note_entry", "note_approval", "note_refusal", "note_draft", "transcript_edit", "transcript_line",
          "live_line", "warning", "cds_pass", "model_call", "consultation")


def rows_of(db, cid):
    found = {}
    for table in TABLES:
        if table == "consultation":
            found[table] = db.query_one("SELECT COUNT(*) AS n FROM consultation WHERE id = ?", (cid,))["n"]
        elif table in ("letter_edit", "letter_approval"):
            found[table] = db.query_one(f"SELECT COUNT(*) AS n FROM {table} WHERE letter_id IN (SELECT id FROM letter WHERE consultation_id = ?)", (cid,))["n"]
        elif table == "note_entry":
            found[table] = db.query_one("SELECT COUNT(*) AS n FROM note_entry WHERE draft_id IN (SELECT id FROM note_draft WHERE consultation_id = ?)", (cid,))["n"]
        elif table == "note_edit":
            found[table] = db.query_one("SELECT COUNT(*) AS n FROM note_edit WHERE entry_id IN (SELECT e.id FROM note_entry e JOIN note_draft d ON d.id = e.draft_id WHERE d.consultation_id = ?)", (cid,))["n"]
        else:
            found[table] = db.query_one(f"SELECT COUNT(*) AS n FROM {table} WHERE consultation_id = ?", (cid,))["n"]
    return found


def letters_rows(p, cid):
    """8a: a list, two items, two letters, one edit and one approval under
    the consultation, so the delete of ruling 8 is proven to take them too."""
    from openconsult.consult.letter_rows import ItemRow, LetterRow, ListRow
    letters = p.letters
    list_id = letters.add_list(ListRow(cid, p.notes.approval(cid)["id"], None, "[1] made", None, None, 1))
    stated = letters.add_item(ItemRow(cid, list_id, "stated", "Made-up specialty", "Physician", "made", "routine", [9], None, 0))
    named = letters.add_item(ItemRow(cid, None, "named", "Other specialty", "Surgeon", None, None, [], None, 0))
    row = LetterRow(cid, stated, None, "made-up", "0", "tag", "d", "h" * 64, "[1] made", None, [], "made body.", {}, 1, 1, 0, 0, False, None, 1)
    one = letters.add_letter(row)
    letters.add_letter(LetterRow(**{**row.__dict__, "item_id": named}))
    letters.set_paragraph(one, 0, "edited body.")
    letters.approve(one, "Dear Consultant Physician,\n\nedited body.")


def test_ruling_8_D44_10_5_delete_removes_every_row_in_one_transaction_then_the_file_and_leaves_the_audit_line_with_counts_and_no_words(tmp_path, clock, machine):
    app, client, c = run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=LINES)), engine_with())
    p = app.state.parts
    entry = p.notes.entries(p.notes.current_draft(1)["id"])[0]
    client.post(f"/consultations/1/entries/{entry['id']}", data={"text": "edited words"})
    client.post("/consultations/1/note/approve")
    letters_rows(p, 1)
    before = rows_of(p.db, 1)
    assert before["letter"] == 2 and before["letter_edit"] == 1 and before["letter_approval"] == 1 and before["referral_item"] == 2
    assert before["transcript_line"] == 2 and before["cds_pass"] >= 1 and before["note_approval"] == 1 and before["note_edit"] == 1
    recording = tmp_path / "recordings" / "consultation_1.wav"
    assert recording.is_file() and approved_notes(p.notes, 1) and 1 in p.running
    size = recording.stat().st_size
    page = client.get("/consultations/1").text
    assert 'id="delete" aria-describedby="delete-refusal"' in page
    asked = client.post("/consultations/1/delete")
    assert asked.status_code == 200 and words.DELETE_CONSULTATION_QUESTION.format(name="Made-up Patient", date="4 Oct 2026") in text_of(asked)
    assert rows_of(p.db, 1) == before and recording.is_file()                            # the question alone deletes nothing
    done = client.post("/consultations/1/delete", data={"confirm": "yes"})
    assert done.status_code == 303 and done.headers["location"] == "/patients/1"
    assert all(n == 0 for n in rows_of(p.db, 1).values()) and not recording.is_file() and 1 not in p.running
    line = p.audit.lines()[0]
    assert line.event == "consultation.deleted"
    assert line.detail == (f"patient 1, consultation 1 of 2026-10-04: 1 letter edits, 1 letter approvals, 2 letters, 2 referral items, "
                           f"1 referral lists, {before['note_edit']} edits, {before['note_entry']} entries, "
                           f"1 approvals, 0 refusals, 1 drafts, 0 transcript edits, 2 lines, 2 live lines, {before['warning']} warnings, "
                           f"{before['cds_pass']} passes, {before['model_call']} model calls, 1 recording file, {size} bytes")
    for word in ("word", "Yes", "made up", "edited"):
        assert word not in line.detail                                                       # no word of the note or a line
    # Gone from the patient's page, the earlier notes and the block (8.3); the Patients page still lists the patient.
    assert 'data-consultation="1"' not in client.get("/patients/1").text and words.NO_CONSULTATIONS in text_of(client.get("/patients/1"))
    assert approved_notes(p.notes, 1) == [] and block_for(p.notes, 1, clock(), 2) is None
    assert client.get("/consultations/1").headers["location"] == "/" and 'data-patient="1"' in client.get("/").text
    assert client.get("/consultations/1/recording").headers["location"] == "/"


def test_ruling_8_10_3_a_failed_transaction_leaves_every_row_and_the_file_and_the_start_up_sweep_reports_an_orphan(tmp_path, clock, machine, monkeypatch):
    app, client, c = run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=LINES)), engine_with())
    p = app.state.parts
    before = rows_of(p.db, 1)
    recording = tmp_path / "recordings" / "consultation_1.wav"
    monkeypatch.setattr(deletion, "ROW_DELETIONS", deletion.ROW_DELETIONS + (("made_up", "DELETE FROM no_such_table WHERE x = ?"),))
    with pytest.raises(sqlite3.DatabaseError):
        deletion.delete_consultation(p, 1)
    assert rows_of(p.db, 1) == before and recording.is_file()                             # rolled back whole; the file untouched
    assert not any(l.event == "consultation.deleted" for l in p.audit.lines())
    monkeypatch.undo()
    # The rows first, then the file: a crash between the two leaves a file with no row, which the start-up sweep reports.
    with p.db.transaction() as con:
        deletion.delete_rows(con, 1)
    assert all(n == 0 for n in rows_of(p.db, 1).values()) and recording.is_file()
    again = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                      engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    assert any(l.event == "recording.orphan" and l.detail == "consultation_1.wav" for l in again.state.parts.audit.lines())
    assert recording.is_file()                                                              # reported, never deleted


def test_ruling_8_R15_10_4_a_live_or_stopping_consultation_is_refused_the_page_asks_once_and_a_second_delete_is_refused(tmp_path, clock, machine):
    app, client = app_with(tmp_path, clock, machine)
    p = app.state.parts
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    assert 'id="delete"' not in client.get("/consultations/1").text                         # the live page has no control
    with pytest.raises(deletion.NotFinal):
        deletion.delete_consultation(p, 1)
    refused = client.post("/consultations/1/delete", data={"confirm": "yes"})
    assert refused.status_code == 303 and refused.headers["location"] == "/consultations/1" and p.consultations.get(1)
    p.running[1].on_stop = None
    client.post("/consultations/1/stop")
    with pytest.raises(deletion.NotFinal):
        deletion.delete_consultation(p, 1)                                                  # stopping: Stop first
    p.consultations.set(1, state="final", stop_stage=None)
    del p.running[1]
    deletion.delete_consultation(p, 1)
    with pytest.raises(deletion.NoSuchConsultation):
        deletion.delete_consultation(p, 1)                                                  # a second delete is refused (10.4)
    assert client.post("/consultations/1/delete", data={"confirm": "yes"}).headers["location"] == "/"
    assert len([l for l in p.audit.lines() if l.event == "consultation.deleted"]) == 1


def test_ruling_8_R15_delete_patient_is_disabled_with_its_reason_while_a_consultation_remains_and_asks_once_when_none_is_left(tmp_path, clock, machine):
    app, client, c = run_through(tmp_path, clock, machine, nemotron_doors(MadeUpWorker(live=LINES)), engine_with())
    p = app.state.parts
    client.post("/patients/1/name", data={"value": "Corrected Patient"})
    raw = client.get("/patients/1").text
    assert 'id="delete-patient" aria-describedby="delete-patient-refusal" disabled' in raw
    assert words.DELETE_PATIENT_BLOCKED in text_of(client.get("/patients/1"))
    refused = client.post("/patients/1/delete", data={"confirm": "yes"})
    assert refused.status_code == 400 and refusal_on(refused.text, "delete-patient") == words.DELETE_PATIENT_BLOCKED
    with pytest.raises(deletion.ConsultationsRemain):
        deletion.delete_patient(p, 1)
    assert p.patients.get(1) is not None
    deletion.delete_consultation(p, 1)
    raw = client.get("/patients/1").text
    assert 'id="delete-patient"' in raw and 'aria-describedby="delete-patient-refusal" disabled' not in raw   # enabled
    asked = client.post("/patients/1/delete")
    assert asked.status_code == 200 and words.DELETE_PATIENT_QUESTION.format(name="Corrected Patient", id=1) in text_of(asked)
    assert p.patients.get(1) is not None                                                          # the question alone deletes nothing
    done = client.post("/patients/1/delete", data={"confirm": "yes"})
    assert done.status_code == 303 and done.headers["location"] == "/?deleted=1"
    assert p.patients.get(1) is None and p.patients.changes(1) == []
    assert (p.audit.lines()[0].event, p.audit.lines()[0].detail) == ("patient.deleted", "patient 1")
    assert words.PATIENT_DELETED.format(id=1) in text_of(client.get("/?deleted=1"))
    assert client.get("/patients/1").headers["location"] == "/" and client.post("/patients/1/delete").headers["location"] == "/"
