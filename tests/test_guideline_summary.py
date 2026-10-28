"""The summary call and its outcome by code (spec 15.12, rulings 6 and 7;
R3, R11, R20, R30; D24). Made-up passages and made-up replies; no reply
is asserted right, only sorted."""

from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.guidelines import summary
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import FakeEngine

SENT = [{"n": 1, "passage_id": 7, "source_id": 1, "title": "Title A", "publisher": "P", "trail": "Heading › Sub", "text": "first made text", "similarity": 0.7, "rerank_score": None, "cited": False},
        {"n": 2, "passage_id": 9, "source_id": 2, "title": "Title B", "publisher": "P", "trail": "", "text": "second made text", "similarity": 0.6, "rerank_score": None, "cited": False},
        {"n": 3, "passage_id": 3, "source_id": 1, "title": "Title A", "publisher": "P", "trail": "Other", "text": "third {brace} text", "similarity": 0.5, "rerank_score": None, "cited": False}]


def test_R11_D24_the_summary_message_opens_with_the_patient_line_and_has_no_slot_for_the_background():
    text = summary.message("Made-up A; Made-up B", SENT, Patient(50, "F"))
    assert text == ("The patient is a 50-year-old woman.\n\nQUERY: Made-up A; Made-up B\n\nPASSAGES:\n"
                    "[1] Title A: Heading › Sub\nfirst made text\n\n"
                    "[2] Title B\nsecond made text\n\n"
                    "[3] Title A: Other\nthird {brace} text")
    assert "{passages}" not in text and "{query}" not in text and "BACKGROUND" not in text
    assert "{notes}" not in loader.frame("guideline") and "{background}" not in loader.frame("guideline")


def door_with(tmp_path, clock, script):
    db = open_database(tmp_path / "openconsult.db")
    engine = FakeEngine({"guideline": script})
    return Door(engine, ModelCalls(db, clock)), engine, db


def test_ruling_6_R3_the_outcome_by_code_covered_not_covered_no_citation_and_invalid_marks(tmp_path, clock):
    door, engine, db = door_with(tmp_path, clock, [
        {"covered": True, "summary": "made [1] and made [3].", "passages_cited": [1, 3]},
        {"covered": True, "summary": "made [7] alone.", "passages_cited": [7]},
        {"covered": True, "summary": "made [2] and [9].", "passages_cited": [2, 9]},
        {"covered": False, "summary": "the corpus lacks a made thing.", "passages_cited": []},
        EngineTimeout("no answer"),
        {"covered": True, "summary": "made [1][2][2].", "passages_cited": [2, 2]}])
    patient = Patient(50, "F")
    covered = summary.summarise(door, "Made-up A", SENT, patient)
    assert (covered.outcome, covered.covered, covered.cited, covered.invalid, covered.failure) == ("covered", True, [1, 3], 0, None)
    assert covered.summary == "made [1] and made [3]." and covered.call_id and covered.wall_ms >= 0
    none = summary.summarise(door, "Made-up A", SENT, patient)
    assert (none.outcome, none.covered, none.cited, none.invalid) == ("no_citation", True, [], 2)      # [7] in the text and in the list
    some = summary.summarise(door, "Made-up A", SENT, patient)
    assert (some.outcome, some.cited, some.invalid) == ("covered", [2], 2)
    refused = summary.summarise(door, "Made-up A", SENT, patient)
    assert (refused.outcome, refused.covered, refused.summary, refused.cited) == ("not_covered", False, "the corpus lacks a made thing.", [])
    failed = summary.summarise(door, "Made-up A", SENT, patient)
    assert failed.outcome == "failed" and failed.covered is None and failed.failure.startswith("too_slow") and failed.call_id
    odd = summary.summarise(door, "Made-up A", SENT, patient)
    assert (odd.outcome, odd.cited, odd.invalid) == ("covered", [1, 2], 0)       # a mark twice counts once
    assert summary.marks_in("a [1] b [12] c [x]") == [1, 12]
    # The judge alone, on a result the door let through: a listed value that is not a number is not a citation.
    from openconsult.llm.door import Result
    made = Result("guideline", True, {"covered": True, "summary": "x [1]", "passages_cited": [1, "x", True]}, None, None, 1, 1, None, None)
    assert (summary.judge(made, 3).cited, summary.judge(made, 3).invalid) == ([1], 0)
    db.close()


def test_R20_the_summary_call_is_recorded_with_the_request_as_sent_and_the_prompts_hash(tmp_path, clock):
    import hashlib
    import json
    door, engine, db = door_with(tmp_path, clock, [{"covered": True, "summary": "made [1].", "passages_cited": [1]}])
    patient = Patient(34, "M")
    found = summary.summarise(door, "Made-up A", SENT, patient, consultation_id=None)
    row = ModelCalls(db, clock).get(found.call_id)
    assert (row["job"], row["engine"], row["engine_version"], row["model_tag"], row["model_digest"]) == \
        ("guideline", "made-up", "0.0-made-up", "gemma4:26b-a4b-it-qat", "made-up-digest")
    assert row["prompt_sha256"] == loader.sha256(loader.prompt("guideline"))
    assert hashlib.sha256(loader.prompt_bytes("guideline")).hexdigest() == loader.APPROVED_BYTES["guideline"]
    assert json.loads(row["request"])["user"] == summary.message("Made-up A", SENT, patient)
    call = engine.calls_for("guideline")[0]
    assert (call.max_tokens, call.timeout_s, call.temperature, call.seed, call.context, call.think) == (1000, 60.0, 0.0, 42, 16384, False)
    assert call.system == loader.prompt("guideline") and call.form == loader.form("guideline")
    db.close()
