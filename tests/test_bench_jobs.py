"""The three jobs of the speech bench (spec 15.9, rulings 17, 18, 19 and 22;
15.8 ruling 1; R20; R30; R31; spec 10.4; V1_LESSONS 3.10, 3.12, 3.13). A
made-up engine stands behind the door; every reply here is made up."""

import hashlib
import json

import pytest

from openconsult import cli as app_cli
from openconsult.bench.speech import jobs, model_lines
from openconsult.db import open_database
from openconsult.llm import jobs as app_jobs
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.record import ModelCalls
from openconsult.settings import store
from openconsult.speech.choices import CHOICES
from tests.fakes import FakeEngine, reply
from tests.test_model_lines import PAGE, pieces_of


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    yield ModelCalls(db, clock)
    db.close()


def door_with(record, script):
    engine = FakeEngine(script)
    return Door(engine, record), engine


LINES = model_lines.lines_of(pieces_of(PAGE))
USER = model_lines.lines_text(LINES)
GOOD_LABELS = {"lines": [{"line": 1, "label": "doctor"}, {"line": 2, "label": "patient"},
                         {"line": 3, "label": "unsure"}, {"line": 4, "label": "patient"}]}


def test_rulings_17_18_19_the_three_prompt_files_are_the_approved_bytes():
    for name, expected in jobs.PROMPT_SHA256.items():
        assert hashlib.sha256(jobs.prompt_bytes(name)).hexdigest() == expected
        text = jobs.prompt_text(name)
        assert not text.endswith("\n") and text.endswith("Output JSON only.")
    # The twin: one byte changed is caught before any model reads it.
    changed = jobs.prompt_bytes("note")[:-2] + b"!\n"
    assert hashlib.sha256(changed).hexdigest() != jobs.PROMPT_SHA256["note"]
    with pytest.raises(jobs.PromptChanged):
        jobs.PROMPT_SHA256["note"], kept = "0" * 64, jobs.PROMPT_SHA256["note"]
        try:
            jobs.prompt_text("note")
        finally:
            jobs.PROMPT_SHA256["note"] = kept


@pytest.mark.parametrize("bad, reason", [
    ({"lines": [{"line": 1, "label": "nurse"}]}, "not one of"),
    ({"lines": [{"line": 1}]}, "lacks label"),
    ({"doubtful": []}, "lacks lines"),
    ("not json at all", "not JSON"),
])
def test_3_10_a_reply_that_does_not_fit_a_bench_form_is_a_failure(record, bad, reason):
    door, _ = door_with(record, [bad, GOOD_LABELS])
    result = jobs.ask(door, "label_check", USER)
    assert not result["ok"] and result["failure"] == "bad_form" and reason in result["detail"]
    assert jobs.ask(door, "label_check", USER)["ok"]           # the twin: a reply that fits is an answer


def test_R20_R30_a_bench_call_is_recorded_under_its_own_job_with_the_prompts_hash_and_the_named_limits(record):
    door, engine = door_with(record, [GOOD_LABELS, {"doubtful": []}, reply({"reasoning": "cut"}, ended="cut"),
                                      EngineTimeout("no answer")])
    label = jobs.ask(door, "label_check", USER)
    drug = jobs.ask(door, "drug_name", USER)
    note = jobs.ask(door, "note", "TRANSCRIPT:\n[0] Doctor: made up")
    slow = jobs.ask(door, "note", "TRANSCRIPT:\n[0] Doctor: made up")
    rows = {row["id"]: row for row in record.rows()}
    # The record holds the hash of the system text as it was sent (spec 15.7): the file's text less its final line break.
    assert rows[label["call_id"]]["job"] == "bench_label_check"
    assert rows[label["call_id"]]["prompt_sha256"] == hashlib.sha256(jobs.prompt_text("label_check").encode("utf-8")).hexdigest()
    assert label["prompt_file_sha256"] == jobs.PROMPT_SHA256["label_check"]
    assert rows[drug["call_id"]]["job"] == "bench_drug_name" and rows[drug["call_id"]]["outcome"] == "ok"
    assert note["failure"] == "too_long" and "3000" in note["detail"] and rows[note["call_id"]]["outcome"] == "too_long"
    assert slow["failure"] == "too_slow" and rows[slow["call_id"]]["outcome"] == "too_slow"
    assert [(c.max_tokens, c.timeout_s) for c in engine.calls] == [(3000, 120.0), (1500, 90.0), (3000, 120.0), (3000, 120.0)]
    assert label["prompt_tokens"] == 50 and label["output_tokens"] == 20 and label["wall_ms"] >= 0
    for call in engine.calls:
        assert (call.context, call.think, call.temperature, call.seed) == (16384, False, 0.0, 42)   # the app's own settings


def test_R31_the_three_jobs_are_not_in_the_apps_table(record):
    # Stage 6a built the label check in the app's table under its own name
    # (15.10 ruling 7); the bench's three names stay out of it.
    for name in ("bench_label_check", "bench_drug_name", "bench_note", "drug_name", "note"):
        with pytest.raises(KeyError):
            app_jobs.job(name)
    door, engine = door_with(record, [])
    with pytest.raises(KeyError):
        door.ask("bench_note", "words")
    assert sorted(app_jobs.JOBS) == ["alarm", "assessment", "label_check"] and engine.calls == []


def test_R31_nothing_of_the_app_names_part_two():
    assert sorted(CHOICES) == ["assemblyai", "nemotron", "speechmatics", "whisperx_pyannote"]
    for command in ("speech-voice", "speech-drugs", "speech-calls", "speech-score"):
        with pytest.raises(SystemExit) as refused:
            app_cli.main([command])
        assert refused.value.code == 2
    names = [setting.name for setting in store.SETTINGS]
    assert not any("voice" in n or "drug" in n or "call" in n or "label" in n for n in names)


def test_the_exact_text_sent_for_a_small_made_up_page_for_each_of_the_three_jobs(record):
    # The details of part two (what follows each prompt), ruling 22, 15.8 ruling 1: no word of mine.
    door, engine = door_with(record, [GOOD_LABELS, {"doubtful": []}, {"reasoning": "made up.", "subjective": [],
                                                                        "objective": [], "assessment": [], "plan": []}])
    jobs.ask(door, "label_check", model_lines.lines_text(LINES))
    jobs.ask(door, "drug_name", model_lines.lines_text(LINES))
    turns = model_lines.turns_of(LINES)
    jobs.ask(door, "note", model_lines.turns_text(turns, {"S1": "DOCTOR", "S2": "PATIENT"}))
    label, drug, note = engine.calls
    user = "TRANSCRIPT:\n[1] Any chest pain at rest?\n[2] No. Not at rest.\n[3] Only on the stairs.\n[4] Is that bad?"
    assert label.user == user and drug.user == user
    assert note.user == ("TRANSCRIPT:\n[0] Doctor: Any chest pain at rest?\n[1] Patient: No. Not at rest.\n"
                         "[2] Unknown: Only on the stairs.\n[3] Patient: Is that bad?")
    assert label.system == jobs.prompt_bytes("label_check").decode("utf-8")[:-1]
    assert drug.system == jobs.prompt_bytes("drug_name").decode("utf-8")[:-1]
    assert note.system == jobs.prompt_bytes("note").decode("utf-8")[:-1]
    assert note.form == json.loads((jobs.PROMPTS / "note.form.json").read_text(encoding="utf-8"))


def test_ruling_17_a_label_check_that_misses_repeats_or_invents_a_line_is_refused_whole():
    labels, refusal = jobs.check_labels(GOOD_LABELS, 4)
    assert labels == {1: "doctor", 2: "patient", 3: "unsure", 4: "patient"} and refusal is None
    missed = {"lines": GOOD_LABELS["lines"][:3]}
    assert jobs.check_labels(missed, 4) == (None, {"reason": "refused", "missing": [4], "repeated": [], "unknown": []})
    repeated = {"lines": GOOD_LABELS["lines"] + [{"line": 2, "label": "doctor"}]}
    assert jobs.check_labels(repeated, 4)[1]["repeated"] == [2]
    invented = {"lines": GOOD_LABELS["lines"] + [{"line": 5, "label": "doctor"}]}
    assert jobs.check_labels(invented, 4)[1]["unknown"] == [5]
    assert jobs.check_labels(None, 4) == (None, {"reason": "no answer"})
    assert jobs.check_labels({"lines": [{"line": 0, "label": "doctor"}]}, 1)[1]["unknown"] == [0]


def test_ruling_18_a_doubtful_name_whose_heard_words_are_not_on_its_line_is_dropped_and_counted():
    answer = {"doubtful": [{"line": 2, "heard": "Not at rest", "meant": ""},
                           {"line": 2, "heard": "not at rest", "meant": "made up"},       # the case differs: not letter for letter
                           {"line": 1, "heard": "stairs", "meant": ""},                  # on another line
                           {"line": 9, "heard": "Any", "meant": ""},                     # no such line
                           {"line": 1, "heard": "", "meant": "x"}]}
    kept, dropped = jobs.check_doubtful(answer, LINES)
    assert [(k["line"], k["heard"], k["normalised_too"]) for k in kept] == [(2, "Not at rest", True)]
    assert [(d["line"], d["why"]) for d in dropped] == [(2, "not on its line"), (1, "not on its line"), (9, "no such line"), (1, "nothing heard")]
    assert dropped[0]["normalised_only"] is True and dropped[1]["normalised_only"] is False
    assert jobs.check_doubtful(None, LINES) == ([], [])
