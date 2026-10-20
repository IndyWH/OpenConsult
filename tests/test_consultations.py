"""The rows of a consultation (spec 15.10, The record; R20): the
consultation with its stamps, the live lines, the lines at Stop, the
passes and the warnings, and the tie of model_call rows. Every line here
is made up."""

from datetime import date

import pytest

from openconsult.consult.cds_pass import run_pass
from openconsult.consult.consultations import Consultations, line_as_row, row_as_line
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.record import ModelCalls
from openconsult.patients.audit import Audit
from openconsult.patients.patients import Patients
from openconsult.speech.lines import Line
from tests.fakes import FakeEngine


@pytest.fixture
def rows(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    patient = Patients(db, Audit(db, clock), clock).add("Made-up", date(1990, 1, 1), "F")
    yield db, Consultations(db, clock), patient
    db.close()


def test_R20_the_consultation_row_carries_the_engine_the_model_and_the_speech_stamp(rows):
    db, table, patient = rows
    cid = table.start(patient.id, 30, "nemotron", "vllm", "0.31-made-up", "made-up/tag", "made-up-digest", 2)
    row = table.get(cid)
    assert (row["engine"], row["engine_version"], row["model_tag"], row["model_digest"]) == (
        "vllm", "0.31-made-up", "made-up/tag", "made-up-digest")
    assert row["state"] == "live" and row["intended_minutes"] == 30 and row["speakers_given"] == 2
    table.set(cid, speech_stamp='{"choice": "nemotron"}', state="stopping", stop_stage="who_spoke")
    assert table.get(cid)["speech_stamp"] == '{"choice": "nemotron"}' and table.in_state("stopping")[0]["id"] == cid
    with pytest.raises(KeyError):
        table.set(cid, engine="other")          # a stamp is never changed after Start
    with pytest.raises(ValueError):
        table.set(cid, state="approved")
    assert table.last_intended() == 30 and table.get(cid + 1) is None


def test_15_10_the_lines_the_passes_and_the_warnings_are_tied_to_their_consultation(rows, clock):
    db, table, patient = rows
    cid = table.start(patient.id, 15, "nemotron", "ollama", "9.9", "tag", None, 2)
    line = Line("S1", 0.0, 1.5, "made up words", None, 7)
    table.add_live_line(cid, 1, line, refused=False, shown_at_s=2.25)
    table.add_live_line(cid, 2, Line(None, 1.5, 2.0, "Thank you.", None, 8), refused=True, shown_at_s=2.5)
    live = table.live_lines(cid)
    assert [(r["n"], r["text"], r["refused"], r["shown_at_s"]) for r in live] == [
        (1, "made up words", 0, 2.25), (2, "Thank you.", 1, 2.5)]
    table.add_transcript_lines(cid, [line_as_row(line, 1, "patient"), line_as_row(Line(None, 2.0, 2.5, "yes", None, 9), 2, "unsure", unsure=True)])
    table.set_labels(cid, {1: {"label": "doctor", "changed_by_check": True, "unsure": False}})
    stored = table.transcript_lines(cid)
    assert [(r["n"], r["raw_speaker"], r["label"], r["changed_by_check"], r["unsure"]) for r in stored] == [
        (1, "S1", "doctor", 1, 0), (2, None, "unsure", 0, 1)]
    assert row_as_line(stored[0]) == line
    with pytest.raises(ValueError):
        table.add_transcript_lines(cid, [line_as_row(line, 3, "nurse")])
    # A pass tied to its consultation, with both calls of the record tied too.
    door = Door(FakeEngine(), ModelCalls(db, clock))
    result = run_pass(door, "made up words", Patient(36, "F"), consultation_id=cid)
    table.add_pass(cid, 1, "made up words", result.alarm.call_id, result.assessment.call_id,
                   {"kept": False, "failure": None}, shown=True)
    assert table.passes(cid)[0]["result"] == {"kept": False, "failure": None}
    assert sorted(r["job"] for r in table.model_calls(cid)) == ["alarm", "assessment"]
    assert all(r["consultation_id"] == cid for r in ModelCalls(db).rows())
    # A call with no consultation leaves the tie empty (the bench's calls).
    door.ask("alarm", "made up")
    assert ModelCalls(db).rows()[0]["consultation_id"] is None
    table.add_warning(cid, "uncovered_speech", 3.0, 5.5)
    table.add_warning(cid, "no_speaker", line_n=2)
    assert [(w["kind"], w["start_s"], w["end_s"], w["line_n"]) for w in table.warnings(cid)] == [
        ("uncovered_speech", 3.0, 5.5, None), ("no_speaker", None, None, 2)]


def test_R20_a_draft_carries_its_stamp_its_prompt_hash_and_its_call_and_the_earlier_draft_is_kept(rows, clock):
    from openconsult.consult.note_rows import DraftRow, Notes
    db, table, patient = rows
    cid = table.start(patient.id, 15, "nemotron", "vllm", "0.31-made-up", "made-up/tag", "made-up-digest", 2)
    door = Door(FakeEngine(), ModelCalls(db, clock))
    call_id = door.ask("alarm", "made up", consultation_id=cid).call_id
    notes = Notes(db, clock)
    entries = [{"section": "plan", "text": "made-up plan", "turns": [2], "lines": [3, 4], "uncited": False},
               {"section": "subjective", "text": "made-up history", "turns": [9], "lines": [], "uncited": True}]
    first = notes.add_draft(DraftRow(cid, "stop", call_id, "vllm", "0.31-made-up", "made-up/tag", "made-up-digest", "a" * 64,
                                     "TRANSCRIPT:\nmade up", None, "made up.", 2, 1, False, None, 4000, entries))
    draft = notes.current_draft(cid)
    assert (draft["n"], draft["asked_by"], draft["call_id"], draft["engine"], draft["model_tag"], draft["model_digest"],
            draft["prompt_sha256"], draft["entries_total"], draft["entries_cited"], draft["refused"]) == (
        1, "stop", call_id, "vllm", "made-up/tag", "made-up-digest", "a" * 64, 2, 1, 0)
    stored = notes.entries(first)
    assert [(e["section"], e["position"], e["text"], e["turns"], e["lines"], e["uncited"]) for e in stored] == [
        ("subjective", 0, "made-up history", [9], [], 1), ("plan", 0, "made-up plan", [2], [3, 4], 0)]
    # The doctor's edit: the words before are kept, the model's words stay.
    notes.set_entry_text(stored[1]["id"], "the doctor's words")
    edited = notes.entry(stored[1]["id"])
    assert (edited["text"], edited["model_text"]) == ("the doctor's words", "made-up plan")
    assert [(e["text_before"], e["text_after"]) for e in notes.edits(stored[1]["id"])] == [("made-up plan", "the doctor's words")]
    # Draft again keeps the earlier draft and its entries; the latest is the page's.
    second = notes.add_draft(DraftRow(cid, "again", None, "vllm", None, "made-up/tag", None, "a" * 64, "x", 1, None, 0, 0,
                                      True, None, 10, []))
    assert [d["n"] for d in notes.drafts(cid)] == [1, 2] and notes.current_draft(cid)["id"] == second
    assert notes.entries(first)[1]["text"] == "the doctor's words" and notes.entries(second) == []
    with pytest.raises(ValueError):
        notes.add_draft(DraftRow(cid, "nobody", None, "vllm", None, "t", None, "h", "x", None, None, 0, 0, False, None, 1))
    # One approval at most (R2); a refusal is recorded; the list waiting for review drops the approved one.
    assert table.waiting_for_review() == []           # not final yet
    table.set(cid, state="final")
    assert table.waiting_for_review()[0]["id"] == cid
    notes.refuse(cid, first)
    assert [r["draft_id"] for r in notes.refusals(cid)] == [first] and notes.approval(cid) is None
    notes.approve(cid, second, "Subjective\n")
    assert notes.approval(cid)["text"] == "Subjective\n" and table.waiting_for_review() == []
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        notes.approve(cid, second, "again")


def test_rulings_7_11_the_doctors_edits_to_words_and_labels_keep_what_stood_before(rows):
    db, table, patient = rows
    cid = table.start(patient.id, 15, "nemotron", "vllm", "0", "tag", None, 2)
    table.add_transcript_lines(cid, [line_as_row(Line("S1", 0.0, 1.0, "made up one", None, 1), 1, "doctor"),
                                     line_as_row(Line("S2", 1.0, 2.0, "made up two", None, 2), 2, "patient"),
                                     line_as_row(Line(None, 2.0, 3.0, "yes", None, 3), 3, "unsure", unsure=True)])
    table.set_labels(cid, {1: {"label": "patient", "changed_by_check": True, "unsure": False}})
    assert table.last_edit_id(cid) is None
    words = table.set_line_words(cid, 2, "made up too")
    undo = table.set_line_label(cid, 1, "doctor", kind="undo")
    label = table.set_line_label(cid, 3, "patient")
    lines = table.transcript_lines(cid)
    assert [(r["n"], r["text"], r["label"], r["changed_by_check"], r["unsure"], r["set_by_doctor"]) for r in lines] == [
        (1, "made up one", "doctor", 0, 0, 1), (2, "made up too", "patient", 0, 0, 0), (3, "yes", "patient", 0, 0, 1)]
    swap = table.swap_labels(cid)
    assert [r["label"] for r in table.transcript_lines(cid)] == ["patient", "doctor", "doctor"]
    table.set_line_label(cid, 3, "unsure")
    assert table.transcript_lines(cid)[2]["unsure"] == 1
    edits = table.transcript_edits(cid)
    assert [(e["id"], e["kind"], e["line_n"], e["before"], e["after"]) for e in edits] == [
        (words, "words", 2, "made up two", "made up too"), (undo, "undo", 1, "patient", "doctor"),
        (label, "label", 3, "unsure", "patient"), (swap, "swap", None, None, None), (swap + 1, "label", 3, "doctor", "unsure")]
    assert table.last_edit_id(cid) == swap + 1
    with pytest.raises(ValueError):
        table.set_line_label(cid, 1, "nurse")
    with pytest.raises(ValueError):
        table.add_transcript_edit(cid, "made-up", None, None, None)
