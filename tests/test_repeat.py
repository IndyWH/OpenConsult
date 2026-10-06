"""The repeat test (spec 15.8, ruling 9): the same call sent ten times,
and a count of the replies that are the same as the first. A made-up
engine stands behind the door; every case and every reply is made up."""

import pytest

from openconsult.bench.cases import case_named, load_cases
from openconsult.bench.repeat import run_repeat, user_text
from openconsult.bench.replay import CHAINS, run_chain
from openconsult.bench.writer import ResultWriter
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.record import ModelCalls
from tests.fakes import ALARM_QUIET, ASSESSMENT, FakeEngine
from tests.test_bench import made_up_folder

POINTS = (("seven", None),)     # the made-up consultation at its last pass
NAMES = "Made-up condition A\nMade-up condition B"


class Wavering(FakeEngine):
    """Answers a call the same way every time, except at the sendings
    named: there one character differs, or the call fails."""

    def __init__(self, differ=(), fail=()):
        super().__init__()
        self.differ, self.fail, self.sent = set(differ), set(fail), {}

    def chat(self, call):
        self.calls.append(call)
        key = (call.job, call.user)
        self.sent[key] = n = self.sent.get(key, 0) + 1
        if (call.job, n) in self.fail:
            raise EngineTimeout("made-up: too slow")
        answer = dict(ALARM_QUIET if call.job == "alarm" else ASSESSMENT)
        if (call.job, n) in self.differ:
            answer["reasoning"] = "made uq"     # one character from "made up"
        return self.chat_item(call, answer)


@pytest.fixture
def bench(tmp_path, clock):
    cases = load_cases(made_up_folder(tmp_path))
    db = open_database(tmp_path / "calls.db")
    record = ModelCalls(db, clock)
    reference = ResultWriter(tmp_path / "reference")
    for case in cases:      # a finished run, whose chain A1 gives the earlier lists
        reference.write(case.name, "A1", run_chain(Door(FakeEngine(), record), case, CHAINS[0], log=lambda line: None))
    yield cases, record, reference, ResultWriter(tmp_path / "repeat")
    db.close()


def repeat(bench, engine, **more):
    cases, record, reference, writer = bench
    return run_repeat(Door(engine, record), record, cases, reference, writer, points=POINTS,
                      between_case="madeup", log=lambda line: None, **more)


def test_ruling_9_the_repeat_test_counts_replies_the_same_as_the_first(bench):
    # The alarm call is sent 20 times in all: 1 to 10 with nothing in between, 11 to 20 with a call in between.
    engine = Wavering(differ=[("alarm", 4), ("alarm", 9), ("alarm", 15)], fail=[("alarm", 17)])
    assert repeat(bench, engine) == {"run": 4, "kept": 0}
    writer = bench[3]
    bare, between = writer.read("seven", "alarm-bare"), writer.read("seven", "alarm-between")
    assert bare["same_as_first"] == 8 and bare["times"] == 10      # two differ by one character
    assert [s["n"] for s in bare["sends"] if not s["same"]] == [4, 9]
    assert between["same_as_first"] == 8                           # one differs, one failed
    failed = next(s for s in between["sends"] if s["role"] == "test" and s["n"] == 7)
    assert failed["outcome"] == "too_slow" and failed["same"] is False and failed["sha256"] is None
    # The twin: a call that always answers the same counts ten of ten, the first included.
    assert writer.read("seven", "assessment-bare")["same_as_first"] == 10
    assert writer.read("seven", "assessment-between")["same_as_first"] == 10
    assert bare["engine_version"] == "0.0-made-up" and bare["kind"] == "repeat" and bare["point"] == 2


def test_ruling_9_a_different_call_goes_in_between_and_is_not_counted(bench):
    cases, record, reference, writer = bench
    engine = Wavering()
    repeat(bench, engine)
    seven, other = case_named(cases, "seven"), case_named(cases, "madeup")
    jobs = [call.job for call in engine.calls]
    # Alarm: ten in a row, then ten with the other job's call before each but the first. Then the assessment.
    assert jobs[:10] == ["alarm"] * 10
    assert jobs[10:29] == ["alarm"] + ["assessment", "alarm"] * 9
    assert jobs[29:39] == ["assessment"] * 10
    assert jobs[39:] == ["assessment"] + ["alarm", "assessment"] * 9
    # The call in between is the other job at the other case's first point, with no earlier list.
    assert {call.user for call in engine.calls[11:29:2]} == {user_text(other, 4, "assessment")}
    assert {call.user for call in engine.calls[40::2]} == {user_text(other, 4, "alarm")}
    # The call under test is the same words every time; the assessment carries the reference's earlier list.
    assert len({call.user for call in engine.calls[29:39]}) == 1 and NAMES in engine.calls[29].user
    assert engine.calls[29].user == user_text(seven, 2, "assessment", NAMES.split("\n"))
    assert all((call.temperature, call.seed) == (0.0, 42) for call in engine.calls)
    between = writer.read("seven", "alarm-between")
    assert sum(1 for s in between["sends"] if s["role"] == "between") == 9
    assert between["same_as_first"] == 10 and all("same" not in s for s in between["sends"] if s["role"] == "between")
    # A test that was stopped carries on: what has a result is not sent again.
    sent = len(engine.calls)
    assert repeat(bench, engine) == {"run": 0, "kept": 4} and len(engine.calls) == sent
