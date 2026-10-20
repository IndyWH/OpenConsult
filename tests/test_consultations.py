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
