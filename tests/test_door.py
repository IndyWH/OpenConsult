"""The one door (spec 15.7; R19, R20, R30; spec 10.4; V1_LESSONS 3.3,
3.10, 3.11, 3.12, 3.13). A made-up engine stands behind the joint."""

import json

import pytest

from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout, EngineUnreachable
from openconsult.llm.profile import Sampling
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import ALARM_QUIET, ASSESSMENT, FakeEngine, reply


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    yield ModelCalls(db, clock)
    db.close()


def door_with(record, script=None, **engine_args):
    engine = FakeEngine(script, **engine_args)
    return Door(engine, record), engine


def test_R20_every_call_is_recorded_with_what_was_sent_and_what_came_back(record):
    door, engine = door_with(record)
    result = door.ask("alarm", "made-up words")
    assert result.ok and result.answer == ALARM_QUIET and result.failure is None
    rows = record.rows()
    assert len(rows) == 1 and rows[0]["id"] == result.call_id
    row = rows[0]
    assert row["job"] == "alarm" and row["engine"] == "made-up"
    assert row["engine_version"] == "0.0-made-up" and row["model_digest"] == "made-up-digest"
    assert row["model_tag"] == door.profile.tag
    assert row["prompt_sha256"] == loader.sha256(loader.prompt("alarm"))
    assert json.loads(row["request"])["user"] == "made-up words"
    assert json.loads(row["reply"])["message"]["content"] == json.dumps(ALARM_QUIET)
    assert (row["prompt_tokens"], row["output_tokens"]) == (50, 20)
    assert (row["total_ms"], row["read_ms"], row["write_ms"]) == (4, 1, 3)
    assert row["outcome"] == "ok" and row["wall_ms"] >= 0


FAILURES = [
    ("too_slow", EngineTimeout("timed out", request='{"tried": true}')),
    ("unreachable", EngineUnreachable("connection refused")),
    ("too_long", reply('{"reasoning": "cut off', ended="cut")),
    ("bad_form", reply("not json at all")),
    ("did_not_fit", reply(None, ended="did_not_fit", status=400,
                          error='{"error":{"type":"exceed_context_size_error","n_prompt_tokens":77585,"n_ctx":16384}}')),
]


@pytest.mark.parametrize("outcome, item", FAILURES)
def test_3_13_a_failed_call_is_recorded_with_its_outcome(record, outcome, item):
    door, engine = door_with(record, [item])
    result = door.ask("assessment", "made-up words")
    assert not result.ok and result.answer is None and result.failure == outcome
    row = record.get(result.call_id)
    assert row["outcome"] == outcome and row["detail"]
    assert row["request"]  # the request as tried, or the parts, is always kept
    if outcome == "too_slow":
        assert row["request"] == '{"tried": true}'
    assert len(engine.calls) == 1


def test_R30_a_reply_cut_at_its_length_limit_is_a_failure_not_an_answer(record):
    door, engine = door_with(record, [reply(ASSESSMENT, ended="cut")])
    result = door.ask("assessment", "words")
    assert not result.ok and result.failure == "too_long" and result.answer is None
    assert "1500" in result.detail
    assert engine.calls[0].max_tokens == 1500


def test_R30_a_call_over_its_time_limit_is_a_failure(record):
    ticks = iter([0.0, 61.0, 100.0, 100.5])
    door = Door(FakeEngine([ASSESSMENT, ASSESSMENT]), record, timer=lambda: next(ticks))
    late = door.ask("assessment", "words")
    assert not late.ok and late.failure == "too_slow" and "61000 ms" in late.detail
    in_time = door.ask("assessment", "words")
    assert in_time.ok
    door2, engine = door_with(record, [EngineTimeout("no answer")])
    assert door2.ask("alarm", "words").failure == "too_slow"
    assert engine.calls[0].timeout_s == 60.0


def test_10_4_an_absent_engine_or_model_fails_and_nothing_else_is_tried(record):
    door, engine = door_with(record, [EngineUnreachable("connection refused"),
                                      reply(None, ended="error", status=404, error="model not found")])
    gone = door.ask("alarm", "words")
    assert gone.failure == "unreachable" and "refused" in gone.detail
    absent = door.ask("alarm", "words")
    assert absent.failure == "unreachable" and "404" in absent.detail
    assert len(engine.calls) == 2  # one attempt each; no retry, no other engine


def test_3_3_an_input_that_does_not_fit_is_a_failure_marked_as_such(record):
    door, engine = door_with(record, [FAILURES[4][1]])
    result = door.ask("alarm", "a very long made-up transcript")
    assert result.failure == "did_not_fit" and "16384" in result.detail
    assert record.get(result.call_id)["outcome"] == "did_not_fit"


def test_R19_one_context_size_and_the_steady_settings_on_every_call(record):
    door, engine = door_with(record)
    door.ask("alarm", "words")
    door.ask("assessment", "words")
    for call in engine.calls:
        assert (call.context, call.think, call.temperature, call.seed) == (16384, False, 0.0, 42)
    assert engine.calls[0].context == engine.calls[1].context
    # The bench's override changes the sampling and nothing else.
    door.ask("alarm", "words", Sampling(0.5, 7))
    assert (engine.calls[2].temperature, engine.calls[2].seed, engine.calls[2].context) == (0.5, 7, 16384)


def test_3_11_each_job_sends_its_own_prompt_form_cap_and_time_limit(record):
    door, engine = door_with(record)
    door.ask("alarm", "words")
    door.ask("assessment", "words")
    alarm, assessment = engine.calls
    assert alarm.system == loader.prompt("alarm") and alarm.form == loader.form("alarm")
    assert assessment.system == loader.prompt("assessment") and assessment.form == loader.form("assessment")
    assert (alarm.max_tokens, alarm.timeout_s) == (1000, 60.0)
    assert (assessment.max_tokens, assessment.timeout_s) == (1500, 60.0)
    assert alarm.user == assessment.user == "words"
    with pytest.raises(KeyError):
        door.ask("note", "words")


@pytest.mark.parametrize("bad, reason", [
    ({"reasoning": "x", "time_critical_possible": True, "urgent_actions": []}, "lacks already_done_or_arranged"),
    ({**ALARM_QUIET, "time_critical_possible": "yes"}, "not a boolean"),
    ({**ALARM_QUIET, "urgent_actions": [{"action": "x"}]}, "lacks reason"),
    ({**ALARM_QUIET, "urgent_actions": [{"action": "a", "reason": "b"}] * 4}, "more than 3"),
])
def test_3_10_a_reply_that_does_not_fit_its_form_is_a_failure(record, bad, reason):
    door, _ = door_with(record, [bad, ALARM_QUIET])
    result = door.ask("alarm", "words")
    assert result.failure == "bad_form" and reason in result.detail
    assert door.ask("alarm", "words").ok  # the twin: a reply that fits is an answer
    bad_grade = {**ASSESSMENT, "differentials": [{"condition": "x", "likelihood": "certain", "rationale": "y"}]}
    door2, _ = door_with(record, [bad_grade])
    assert "not one of" in door2.ask("assessment", "words").detail
