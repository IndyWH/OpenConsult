"""The note (spec 15.10, rulings 3, 5, 6 and 8; The note; R4, R20, R30;
D3; 10.4; V1_LESSONS 3.6, 6.2). Made-up replies through a made-up
engine; no model's words are asserted."""

import pytest

from openconsult.bench.speech import model_lines
from openconsult.consult import note
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.jobs import job
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import FakeEngine, reply

ROWS = [{"n": 1, "label": "doctor", "text": "What brings you in?"},
        {"n": 2, "label": "patient", "text": "A pain in my chest."},
        {"n": 3, "label": "patient", "text": "Since Monday."},
        {"n": 4, "label": "unsure", "text": "Yes."},
        {"n": None, "label": "unsure", "text": "refused line"},
        {"n": 5, "label": "doctor", "text": "Tell me more."}]
NOTE = {"reasoning": "made up.", "subjective": [{"text": "made up", "turns": [1]}], "objective": [],
        "assessment": [], "plan": []}


@pytest.fixture
def door(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    engine = FakeEngine({"note": [NOTE, reply({"reasoning": "cut"}, ended="cut"), EngineTimeout("no answer")]})
    yield Door(engine, ModelCalls(db, clock)), engine
    db.close()


def test_ruling_5_D3_the_note_frame_sends_the_benchs_words_and_no_patient_line():
    turns = note.turns_of(ROWS)
    # The bench's rule: neighbouring lines of one label join, numbered from 0, with their lines kept; a refused line is not there.
    assert [(t["n"], t["label"], t["text"], t["lines"]) for t in turns] == [
        (0, "doctor", "What brings you in?", [1]), (1, "patient", "A pain in my chest. Since Monday.", [2, 3]),
        (2, "unsure", "Yes.", [4]), (3, "doctor", "Tell me more.", [5])]
    text = note.turns_text(turns)
    assert text == ("TRANSCRIPT:\n[0] Doctor: What brings you in?\n[1] Patient: A pain in my chest. Since Monday.\n"
                    "[2] Unknown: Yes.\n[3] Doctor: Tell me more.")
    # Word for word what the bench sends for the same turns, through its own builder.
    bench_turns = [{"n": t["n"], "speaker": {"doctor": "D", "patient": "P", "unsure": None}[t["label"]], "text": t["text"]}
                   for t in turns]
    assert text == model_lines.turns_text(bench_turns, {"D": "DOCTOR", "P": "PATIENT"})
    assert (model_lines.DOCTOR, model_lines.PATIENT, model_lines.UNKNOWN) == (note.DOCTOR, note.PATIENT, note.UNKNOWN)
    assert "The patient is" not in text and text.startswith(loader.frame("note").split("\n")[0])


def test_10_4_D3_the_note_call_has_the_named_limits_temperature_0_seed_42_and_no_patient_line(door):
    door, engine = door
    text = note.turns_text(note.turns_of(ROWS))
    answered = door.ask("note", text, consultation_id=None)
    assert answered.ok and answered.answer == NOTE
    call = engine.calls_for("note")[0]
    assert call.system == loader.prompt("note") and call.form == loader.form("note")
    assert (call.max_tokens, call.timeout_s) == (job("note").max_tokens, job("note").timeout_s) == (3000, 120.0)
    assert (call.temperature, call.seed, call.context, call.think) == (0.0, 42, 16384, False)
    assert call.user == text and "The patient is" not in call.user           # D3: no patient line
    # A cut reply is too_long and a late one too_slow, each plainly, with no second call by itself (R30).
    cut = door.ask("note", text)
    assert cut.failure == "too_long" and "3000" in cut.detail
    slow = door.ask("note", text)
    assert slow.failure == "too_slow" and len(engine.calls_for("note")) == 3
