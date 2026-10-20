"""When a pass runs and what the screen keeps between passes (spec 15.10,
rulings 1 and 2, When a pass runs; 15.8 ruling 5; R9, R29; V1_LESSONS
3.14). The pass results here are made up by code; no model speaks."""

from openconsult.consult.cds_pass import Alarm, Assessment, Carried, PassResult
from openconsult.consult.passes import FIRED, NEW_CHARS_FOR_PASS, NO_ACTION, NOT_JUDGED, QUIET, Passes, alarm_key
from openconsult.consult.transcript import Transcript
from openconsult.speech.lines import Line, Live


def alarm(actions=(), judged=True, flag=False, arranged=False, detail=None, reasoning="made up"):
    return Alarm(judged, True if (actions or flag) else (False if judged else None), arranged, list(actions), flag,
                 reasoning, list(actions), None if judged else "unreachable", detail, 1)


def assessment(differentials=("Made-up A",), ok=True, kept=False, failure=None, detail=None):
    diffs = [{"condition": d, "likelihood": "high", "rationale": "made up"} for d in differentials]
    return Assessment(ok, diffs if ok else [], ["a question?"] if ok else [], ["a sign"] if ok else [], "made up",
                      failure, detail, 2, kept)


def result(alarm_=None, assessment_=None, names=()):
    return PassResult(alarm_ or alarm(), assessment_ or assessment(), Carried(names, False, ()))


ACTION_A = {"action": "Send to the emergency department now", "reason": "made up"}
ACTION_A_REWORDED = {"action": "send to the Emergency Department now.", "reason": "made up"}
ACTION_B = {"action": "Give aspirin", "reason": "made up"}


def fed(text, fed_s=1.0):
    return Live(True, fed_s, None, lines=(Line("S1", 0.0, 0.5, text, None, 1),))


def test_when_a_pass_runs_v1s_figure_in_characters_never_two_at_once():
    passes, transcript = Passes(), Transcript()
    assert not passes.due(transcript)                         # nothing heard
    transcript.add(fed("a"))
    assert passes.due(transcript)                             # the first pass on the first line
    passes.begin()
    transcript.mark_sent()
    transcript.add(fed("x" * 200))
    assert not passes.due(transcript)                         # one is running
    passes.settle(1, result(), shown=True, wall_ms=5)
    assert passes.due(transcript)                             # 200 new characters, new lines
    transcript.mark_sent()
    passes.begin()
    passes.settle(2, result(), True, 5)
    transcript.add(fed("y" * (NEW_CHARS_FOR_PASS - 2)))      # the line break counts: 149 new characters
    assert not passes.due(transcript)
    transcript.add(fed("z"))                                  # 151
    assert passes.due(transcript)
    assert NEW_CHARS_FOR_PASS == 150


def test_R9_an_alarm_that_drops_out_stays_as_an_earlier_alarm_and_each_pass_is_judged_fresh():
    passes = Passes()
    passes.begin()
    passes.settle(1, result(alarm([ACTION_A])), True, 5)
    assert passes.state()["alarm"]["state"] == FIRED and passes.state()["earlier_alarms"] == []
    passes.begin()
    passes.settle(2, result(alarm()), True, 5)
    state = passes.state()
    assert state["alarm"]["state"] == QUIET
    assert [(a["n"], a["state"], a["actions"]) for a in state["earlier_alarms"]] == [(1, FIRED, [ACTION_A])]
    passes.begin()
    passes.settle(3, result(alarm([ACTION_A])), True, 5)
    assert passes.state()["alarm"]["state"] == FIRED and passes.state()["earlier_alarms"] == []


def test_R29_an_acknowledged_alarm_stays_acknowledged_and_a_new_alarm_is_not():
    passes = Passes()
    passes.begin()
    passes.settle(1, result(alarm([ACTION_A])), True, 5)
    key = passes.state()["alarm"]["key"]
    assert not passes.acknowledge("not-a-key") and passes.acknowledge(key)
    assert passes.state()["alarm"]["acknowledged"]
    # The same alarm, reworded: still acknowledged (review point 4).
    passes.begin()
    passes.settle(2, result(alarm([ACTION_A_REWORDED])), True, 5)
    assert passes.state()["alarm"]["acknowledged"] and passes.state()["earlier_alarms"] == []
    # A new alarm, with different actions: not acknowledged; the old one is an earlier alarm, still acknowledged.
    passes.begin()
    passes.settle(3, result(alarm([ACTION_A, ACTION_B])), True, 5)
    state = passes.state()
    assert not state["alarm"]["acknowledged"] and state["earlier_alarms"][0]["acknowledged"]
    assert alarm_key(FIRED, [ACTION_A]) == alarm_key(FIRED, [ACTION_A_REWORDED]) != alarm_key(FIRED, [ACTION_A, ACTION_B])
    assert alarm_key(QUIET, []) is None and alarm_key(NOT_JUDGED, []) is None


def test_ruling_1_an_alarm_with_no_action_is_its_own_state_with_the_reasoning_and_stays_as_an_earlier_alarm():
    passes = Passes()
    passes.begin()
    passes.settle(1, result(alarm(flag=True, reasoning="made-up worry")), True, 5)
    shown = passes.state()["alarm"]
    assert (shown["state"], shown["actions"], shown["reasoning"]) == (NO_ACTION, [], "made-up worry")
    assert passes.results[0]["alarm"]["state"] == NO_ACTION       # recorded as its own state
    passes.begin()
    passes.settle(2, result(alarm()), True, 5)
    assert passes.state()["earlier_alarms"][0]["state"] == NO_ACTION
    # Not judged is the third state, with the reason, never read as quiet.
    passes.begin()
    passes.settle(3, result(alarm(judged=False, detail="gone")), True, 5)
    assert passes.state()["alarm"]["state"] == NOT_JUDGED and passes.state()["alarm"]["reason"] == "gone"


def test_ruling_2_a_failed_assessment_keeps_the_earlier_lists_marked_with_the_reason():
    passes = Passes()
    passes.begin()
    passes.settle(1, result(assessment_=assessment(ok=False, failure="too_slow", detail="no answer")), True, 5)
    panel = passes.state()["assessment"]
    assert panel["differentials"] == [] and panel["from_earlier"] is False     # the first pass: the line alone
    assert panel["failure"] == "too_slow: no answer"
    passes.begin()
    passes.settle(2, result(assessment_=assessment(("Made-up A", "Made-up B")), names=("Made-up A", "Made-up B")), True, 5)
    assert passes.state()["assessment"]["failure"] is None and not passes.state()["assessment"]["from_earlier"]
    passes.begin()
    passes.settle(3, result(assessment_=assessment(ok=False, failure="unreachable", detail="gone"),
                            names=("Made-up A", "Made-up B")), True, 5)
    panel = passes.state()["assessment"]
    assert [d["condition"] for d in panel["differentials"]] == ["Made-up A", "Made-up B"]
    assert panel["from_earlier"] and panel["failure"] == "unreachable: gone" and panel["questions"] == ["a question?"]
    assert passes.carried.names == ("Made-up A", "Made-up B")        # the next pass gets the same stale names
    assert passes.results[-1]["assessment"]["failure"] == "unreachable"


def test_ruling_5_a_kept_list_is_marked_from_the_earlier_pass():
    passes = Passes()
    passes.begin()
    passes.settle(1, result(assessment_=assessment(kept=True)), True, 5)
    assert passes.state()["assessment"]["from_earlier"] and passes.state()["assessment"]["failure"] is None


def test_a_result_that_arrives_after_stop_is_recorded_and_not_shown():
    passes = Passes()
    passes.begin()
    passes.settle(1, result(alarm([ACTION_A])), True, 5)
    passes.begin()
    stored = passes.settle(2, result(alarm([ACTION_B]), assessment(("Made-up C",))), shown=False, wall_ms=9)
    assert stored["shown"] is False and stored["wall_ms"] == 9
    state = passes.state()
    assert state["alarm"]["n"] == 1 and state["alarm"]["actions"] == [ACTION_A]
    assert state["assessment"]["n"] == 1 and not passes.running
