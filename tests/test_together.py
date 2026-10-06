"""The two calls of a pass sent at the same moment (spec 15.8, ruling 8;
R30). A made-up engine stands behind the door; every transcript is made up."""

import threading
from dataclasses import asdict

import pytest

from openconsult.bench.cases import case_named, load_cases
from openconsult.bench.replay import CHAINS, run_chain
from openconsult.bench.together import run_pass_together
from openconsult.consult.cds_pass import run_pass
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineUnreachable
from openconsult.llm.record import ModelCalls
from tests.fakes import ALARM_FIRES, ALARM_QUIET, ASSESSMENT, FakeEngine
from tests.test_bench import made_up_folder

TRANSCRIPT = "Made-up line one.\nMade-up line two."
WOMAN = Patient(31, "F")


class ByJob(FakeEngine):
    """Answers each job from its own list, whichever call arrives first.
    An exception in a list is raised. With a barrier, neither call may
    return until both have arrived."""

    def __init__(self, alarm=None, assessment=None, meet=False):
        super().__init__()
        self.answers = {"alarm": list(alarm or []), "assessment": list(assessment or [])}
        self.barrier = threading.Barrier(2, timeout=5) if meet else None

    def chat(self, call):
        self.calls.append(call)
        if self.barrier:
            self.barrier.wait()
        waiting = self.answers[call.job]
        item = waiting.pop(0) if waiting else (ALARM_QUIET if call.job == "alarm" else ASSESSMENT)
        if isinstance(item, BaseException):
            raise item
        return self.chat_item(call, item)


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    yield ModelCalls(db, clock)
    db.close()


def test_ruling_8_the_two_calls_of_a_pass_are_in_flight_at_the_same_moment(record):
    # One after another, the first call would wait at the barrier for a second that never comes.
    engine = ByJob(meet=True)
    result = run_pass_together(Door(engine, record), TRANSCRIPT, WOMAN)
    assert sorted(call.job for call in engine.calls) == ["alarm", "assessment"]
    assert result.alarm.judged and result.assessment.ok
    rows = record.rows()
    assert sorted(row["job"] for row in rows) == ["alarm", "assessment"]
    assert {result.alarm.call_id, result.assessment.call_id} == {row["id"] for row in rows}
    assert all(row["outcome"] == "ok" for row in rows)


@pytest.mark.parametrize("failing", ["alarm", "assessment"])
def test_ruling_8_one_failing_call_does_not_lose_the_other(record, failing):
    engine = ByJob(**{failing: [EngineUnreachable("gone")]}, meet=True)
    result = run_pass_together(Door(engine, record), TRANSCRIPT, WOMAN)
    outcomes = {row["job"]: row["outcome"] for row in record.rows()}
    other = "assessment" if failing == "alarm" else "alarm"
    assert outcomes == {failing: "unreachable", other: "ok"}       # both are recorded
    if failing == "alarm":
        assert result.alarm.judged is False and result.alarm.failure == "unreachable"   # never read as no alarm
        assert result.assessment.ok and result.assessment.differentials == ASSESSMENT["differentials"]
    else:
        assert result.alarm.judged is True and not result.assessment.ok
        assert result.assessment.failure == "unreachable"


def test_ruling_8_sending_together_changes_only_the_sending(tmp_path, record):
    arranged = {**ALARM_FIRES, "already_done_or_arranged": True}
    empty = {**ASSESSMENT, "differentials": []}
    answers = dict(alarm=[ALARM_FIRES, arranged, ALARM_FIRES], assessment=[ASSESSMENT, empty, ASSESSMENT])

    def three_passes(a_pass):
        door, carried, seen = Door(ByJob(**answers), record), None, []
        for _ in range(3):
            result = a_pass(door, TRANSCRIPT, WOMAN, carried)
            carried = result.carried
            shown = asdict(result)
            shown["alarm"].pop("call_id"), shown["assessment"].pop("call_id")
            seen.append(shown)
        return seen

    together, one_after_another = three_passes(run_pass_together), three_passes(run_pass)
    assert together == one_after_another
    assert together[1]["assessment"]["kept"] is True and together[2]["alarm"]["arranged"] is True
    # In the bench, a chain sent together says so, and its passes are timed as before.
    case = case_named(load_cases(made_up_folder(tmp_path)), "seven")
    sent = run_chain(Door(ByJob(meet=True), record), case, CHAINS[0], log=lambda line: None, together=True)
    plain = run_chain(Door(ByJob(), record), case, CHAINS[0], log=lambda line: None)
    assert sent["together"] is True and plain["together"] is False
    assert [p["point"] for p in sent["passes"]] == [1, 2] and all(p["wall_ms"] >= 0 for p in sent["passes"])
