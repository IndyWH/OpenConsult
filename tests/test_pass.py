"""One pass: the alarm, then the assessment, with the bookkeeping in code
(spec 15.7; R9, R11, R12, R30; V1_LESSONS 3.1, 3.2, 3.14; plan review,
change 4). Every transcript here is made up."""

import pytest

from openconsult.consult.cds_pass import Carried, run_pass
from openconsult.consult.messages import NoPatient, Patient, patient_line
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineUnreachable
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import ALARM_FIRES, ALARM_QUIET, ASSESSMENT, FakeEngine, reply

TRANSCRIPT = "Made-up line one.\nMade-up line two."
WOMAN = Patient(31, "F")
LINE = "The patient is a 31-year-old woman."


@pytest.fixture
def door_of(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    record = ModelCalls(db, clock)

    def make(script=None):
        engine = FakeEngine(script)
        return Door(engine, record), engine

    yield make
    db.close()


def test_R11_both_calls_open_with_the_patient_line(door_of):
    door, engine = door_of()
    run_pass(door, TRANSCRIPT, WOMAN)
    assert [c.job for c in engine.calls] == ["alarm", "assessment"]
    for call in engine.calls:
        assert call.user.startswith(f"{LINE}\n\n") and call.user.count("The patient is") == 1


@pytest.mark.parametrize("age, sex, line", [
    (31, "F", "The patient is a 31-year-old woman."),
    (52, "M", "The patient is a 52-year-old man."),
    (15, "M", "The patient is a 15-year-old boy."),
    (17, "F", "The patient is a 17-year-old girl."),
    (18, "M", "The patient is a 18-year-old man."),
    (0, "F", "The patient is a baby girl, under 1 year old."),
    (0, "M", "The patient is a baby boy, under 1 year old."),
    (121, "F", None), (-1, "M", None), (True, "F", None), (30, "female", None), (None, "F", None),
])
def test_R11_the_patient_line_for_each_age_and_sex(age, sex, line):
    assert patient_line(age, sex) == line


def test_R11_a_pass_without_a_patient_is_refused_before_any_call(door_of):
    door, engine = door_of()
    with pytest.raises(NoPatient):
        run_pass(door, TRANSCRIPT, None)
    with pytest.raises(NoPatient):
        run_pass(door, TRANSCRIPT, Patient(200, "F"))
    assert engine.calls == []


def test_R12_the_assessment_gets_earlier_names_only_and_the_alarm_gets_none(door_of):
    door, engine = door_of()
    first = run_pass(door, TRANSCRIPT, WOMAN)
    assert first.carried.names == ("Made-up condition A", "Made-up condition B")
    run_pass(door, TRANSCRIPT, WOMAN, first.carried)
    first_alarm, first_assessment, later_alarm, later_assessment = (c.user for c in engine.calls)
    assert first_assessment == f"{LINE}\n\n" + loader.fill(loader.frame("assessment.first"), transcript=TRANSCRIPT)
    assert later_assessment == f"{LINE}\n\n" + loader.fill(
        loader.frame("assessment.later"), stale="Made-up condition A\nMade-up condition B",
        transcript=TRANSCRIPT)
    for absent in ("high", "low", "rationale", "made-up question", "made-up sign", "likelihood"):
        assert absent not in later_assessment
    assert later_assessment.index("Made-up condition A") < later_assessment.index(TRANSCRIPT)
    assert first_alarm == later_alarm == f"{LINE}\n\n" + loader.fill(loader.frame("alarm"), transcript=TRANSCRIPT)
    # An empty earlier list means the first-pass frame again.
    run_pass(door, TRANSCRIPT, WOMAN, Carried(names=()))
    assert engine.calls[-1].user == first_assessment


def test_R9_R30_the_alarm_goes_first_and_survives_a_failed_assessment(door_of):
    door, engine = door_of([ALARM_FIRES, reply(ASSESSMENT, ended="cut")])
    result = run_pass(door, TRANSCRIPT, WOMAN, Carried(names=("Earlier made-up",)))
    assert [c.job for c in engine.calls] == ["alarm", "assessment"]
    assert result.alarm.judged and result.alarm.actions == ALARM_FIRES["urgent_actions"]
    assert not result.assessment.ok and result.assessment.failure == "too_long"
    assert result.carried.names == ("Earlier made-up",)  # the stale list is kept


def test_R30_a_failed_alarm_leaves_the_assessment_and_the_earlier_alarm_state(door_of):
    door, engine = door_of([EngineUnreachable("gone"), ASSESSMENT])
    result = run_pass(door, TRANSCRIPT, WOMAN, Carried(arranged=True))
    assert result.assessment.ok and result.carried.names == ("Made-up condition A", "Made-up condition B")
    # The third state: not judged, with the reason. Never read as no alarm.
    assert result.alarm.judged is False and result.alarm.failure == "unreachable"
    assert result.alarm.time_critical is None and result.alarm.actions == []
    assert result.alarm.arranged is True and result.carried.arranged is True
    assert "gone" in result.alarm.detail
    judged_quiet = run_pass(door_of([ALARM_QUIET, ASSESSMENT])[0], TRANSCRIPT, WOMAN).alarm
    assert judged_quiet.judged is True and judged_quiet.time_critical is False and judged_quiet.actions == []


def test_3_1_once_arranged_stays_arranged(door_of):
    arranged = {**ALARM_FIRES, "already_done_or_arranged": True}
    door, _ = door_of([arranged, ASSESSMENT, ALARM_FIRES, ASSESSMENT])
    first = run_pass(door, TRANSCRIPT, WOMAN)
    assert first.alarm.arranged and first.alarm.actions == [] and first.alarm.raw_actions
    second = run_pass(door, TRANSCRIPT, WOMAN, first.carried)
    assert second.alarm.time_critical and second.alarm.arranged and second.alarm.actions == []
    assert second.carried.arranged is True
    # Without the latch, the same reply fires.
    fresh = run_pass(door_of([ALARM_FIRES, ASSESSMENT])[0], TRANSCRIPT, WOMAN)
    assert fresh.alarm.actions == ALARM_FIRES["urgent_actions"] and not fresh.alarm.arranged


def test_3_14_time_critical_with_no_action_is_kept_as_such(door_of):
    flagged = {**ALARM_FIRES, "urgent_actions": []}
    door, _ = door_of([flagged, ASSESSMENT])
    alarm = run_pass(door, TRANSCRIPT, WOMAN).alarm
    assert alarm.judged and alarm.time_critical and alarm.flag_without_action and alarm.actions == []
    quiet = run_pass(door_of([ALARM_QUIET, ASSESSMENT])[0], TRANSCRIPT, WOMAN).alarm
    assert not quiet.flag_without_action
