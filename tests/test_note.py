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
from openconsult.speech.lines import Line
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
    made = Door(engine, ModelCalls(db, clock))
    made.tmp_path = tmp_path
    yield made, engine
    db.close()


def tmp_path_of(door):
    return door[0].tmp_path


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


TURNS = [{"n": 0, "label": "doctor", "text": "a", "lines": [1]}, {"n": 1, "label": "patient", "text": "b", "lines": [2, 3]},
         {"n": 2, "label": "doctor", "text": "c", "lines": [4]}]


def entry(text, turns=None, section="subjective"):
    return {"text": text, "turns": turns or []}


def test_R4_ruling_8_every_entry_cites_lines_that_exist_and_one_whose_lines_do_not_is_kept_uncited():
    made = {"reasoning": "made up.", "subjective": [entry("one", [1]), entry("two", [9]), entry("three", [0, 2])],
            "objective": [], "assessment": [entry("four", [True])], "plan": [entry("five", [2, 2])]}
    checked = note.check_citations(made, TURNS)
    assert [(e["section"], e["text"], e["turns"], e["lines"], e["uncited"]) for e in checked.entries] == [
        ("subjective", "one", [1], [2, 3], False), ("subjective", "two", [9], [], True),
        ("subjective", "three", [0, 2], [1, 4], False), ("assessment", "four", [], [], True),   # a boolean is not a number
        ("plan", "five", [2, 2], [4], False)]
    assert (checked.total, checked.cited, checked.refused) == (5, 3, False)


def test_ruling_8_consultation_78_fewer_than_half_cited_is_refused_with_the_count_and_the_draft_discarded(door):
    assert note.CITATION_HALF == 0.5
    half = {"reasoning": "x", "subjective": [entry("a", [0]), entry("b", [7])], "objective": [], "assessment": [], "plan": []}
    assert not note.check_citations(half, TURNS).refused                       # exactly half passes
    under = {**half, "plan": [entry("c", [8])]}
    checked = note.check_citations(under, TURNS)
    assert checked.refused and (checked.total, checked.cited) == (3, 1)
    none = {"reasoning": "x", "subjective": [], "objective": [], "assessment": [], "plan": []}
    assert note.check_citations(none, TURNS).refused
    # Through the draft: the row keeps the count and no entry; nothing is asked a second time.
    from openconsult.consult.consultations import Consultations, line_as_row
    from openconsult.consult.note_rows import Notes
    from openconsult.db import open_database
    from openconsult.patients.audit import Audit
    from openconsult.patients.patients import Patients
    from datetime import date
    db = open_database(tmp_path_of(door) / "rows.db")
    engine = FakeEngine({"note": [under]})
    door_ = Door(engine, ModelCalls(db))
    cons, notes, audit = Consultations(db), Notes(db), Audit(db)
    patient = Patients(db, audit).add("Made-up", date(1990, 1, 1), "F")
    cid = cons.start(patient.id, 15, "nemotron", "vllm", "0", "tag", "d", 2)
    cons.add_transcript_lines(cid, [line_as_row(Line("S1", 0.0, 1.0, "made up", None, 1), 1, "doctor")])
    drafted = note.draft(door_, cons, notes, audit, cid, "stop")
    assert (drafted["refused"], drafted["entries_total"], drafted["entries_cited"], drafted["failure"]) == (1, 3, 1, None)
    assert notes.entries(drafted["id"]) == [] and len(engine.calls_for("note")) == 1
    assert audit.lines()[0].event == "note.refused_by_check" and "1 of 3" in audit.lines()[0].detail


def test_3_6_a_citation_written_in_words_is_read_and_a_cited_line_proves_only_that_it_exists():
    assert note.cited_turns(entry("pain [twelve]")) == [12]
    assert note.cited_turns(entry("pain [12] and [1, 2]")) == [12, 1, 2]
    assert note.cited_turns(entry("pain [twenty one]")) == [21]
    assert note.cited_turns(entry("pain [left side]")) == [] and note.cited_turns(entry("pain [12 mg]")) == []
    assert note.cited_turns(entry("pain [12]", [1])) == [1]                       # the turns field first
    # The check judges existence, not truth: an entry whose words contradict its line is still cited.
    made = {"reasoning": "x", "subjective": [entry("no chest pain at all", [1])], "objective": [], "assessment": [], "plan": []}
    checked = note.check_citations(made, [{"n": 1, "label": "patient", "text": "the chest pain is bad", "lines": [2]}])
    assert checked.entries[0]["lines"] == [2] and not checked.entries[0]["uncited"]


def test_ruling_6_the_note_form_has_no_field_for_a_guessed_name_and_an_entrys_words_are_kept_letter_for_letter():
    form = loader.form("note")
    for section in ("subjective", "objective", "assessment", "plan"):
        assert sorted(form["properties"][section]["items"]["properties"]) == ["text", "turns"]
    garbled = "Takes levithirixin (unclear) 50 mcg."          # a made-up garbled word, written as heard
    made = {"reasoning": "x", "subjective": [entry(garbled, [0])], "objective": [], "assessment": [], "plan": []}
    checked = note.check_citations(made, TURNS)
    assert checked.entries[0]["text"] == garbled                 # letter for letter; no replacement anywhere in the app
    assert not hasattr(note, "DRUGS") and "meant" not in str(form)


def test_the_turns_are_the_benchs_rule_over_the_lines_as_they_stand_after_the_check_and_any_edit():
    rows = [{"n": 1, "label": "doctor", "text": "a"}, {"n": 2, "label": "doctor", "text": "b"},
            {"n": 3, "label": "patient", "text": "c"}, {"n": 4, "label": "unsure", "text": "d"},
            {"n": 5, "label": "unsure", "text": "e"}, {"n": 6, "label": "patient", "text": "f"}]
    turns = note.turns_of(rows)
    assert [(t["n"], t["label"], t["text"], t["lines"]) for t in turns] == [
        (0, "doctor", "a b", [1, 2]), (1, "patient", "c", [3]), (2, "unsure", "d e", [4, 5]), (3, "patient", "f", [6])]
    bench = model_lines.turns_of([{"n": r["n"], "speaker": r["label"], "text": r["text"]} for r in rows])
    assert [(t["n"], t["text"], t["lines"]) for t in bench] == [(t["n"], t["text"], t["lines"]) for t in turns]
    # An edited word and an undone label are what the next draft reads.
    rows[1]["text"], rows[2]["label"] = "B", "doctor"
    assert note.turns_text(note.turns_of(rows)).startswith("TRANSCRIPT:\n[0] Doctor: a B c\n[1] Unknown: d e\n[2] Patient: f")


def test_ruling_4_the_copy_text_holds_the_note_alone_in_the_four_sections_and_strips_a_bracketed_citation():
    entries = [{"section": "plan", "text": "Start aspirin [31]"}, {"section": "subjective", "text": "Pain [twelve] since Monday"},
               {"section": "subjective", "text": "BP [left arm] 150/95 [12, 13]"}, {"section": "assessment", "text": "ACS?  [7]"}]
    text = note.plain_text(entries)
    assert text == ("Subjective\nPain since Monday\nBP [left arm] 150/95\n\nObjective\n\nAssessment\nACS?\n\nPlan\nStart aspirin\n")
    assert "Made-up condition" not in text and "arning" not in text
    assert note.strip_citations("as it stands") == "as it stands"


def test_ruling_4_the_differentials_beside_the_assessment_are_the_last_shown_pass():
    diffs = [{"condition": "Made-up condition A", "likelihood": "high", "rationale": "made up"}]
    passes = [{"n": 1, "shown": 1, "result": {"assessment": {"ok": True, "differentials": diffs}}},
              {"n": 2, "shown": 1, "result": {"assessment": {"ok": False, "differentials": [], "failure": "too_slow"}}},
              {"n": 3, "shown": 0, "result": {"assessment": {"ok": True, "differentials": []}}}]
    assert note.last_shown_differentials(passes) == diffs           # a failed last pass keeps the earlier; shown 0 ignored
    assert note.last_shown_differentials([]) == []
