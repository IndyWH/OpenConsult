"""The repeat test (spec 15.8, ruling 9): does an engine give the same
answer twice? At temperature 0 with seed 42 it should. One alarm call and
one assessment call from each of three cases are each sent ten times,
first with nothing in between, then with a different call in between
each time. The count is how many of the ten replies are the same as the
first, character for character; the first counts as one.

Every call goes through the door. An assessment call at a later point
needs an earlier list: it is taken from chain A1 of a finished run, the
reference, so the words are the same on every engine.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Callable

from openconsult.bench.cases import Case, case_named
from openconsult.bench.replay import STEADY, answer_text, stamp
from openconsult.bench.writer import ResultWriter
from openconsult.consult.messages import alarm_message, assessment_message, with_patient
from openconsult.llm.door import Door
from openconsult.llm.record import ModelCalls

# 495 at its last pass, the malaria case at turn 16, script 15 at its last update.
POINTS = (("495", None), ("T2", 16), ("15", None))
# The call in between comes from a case that is none of the three, and is the other job,
# so it shares as little as it can with the call under test.
BETWEEN_CASE = "01"
TIMES = 10
WAYS = ("bare", "between")
JOBS = ("alarm", "assessment")


def stale_names(reference: ResultWriter, case: str, point: int) -> tuple[str, ...]:
    """The list the reference's chain A1 held after the point before."""
    earlier = [p for p in reference.read(case, "A1")["passes"] if p["point"] < point]
    return tuple(earlier[-1]["names"]) if earlier else ()


def user_text(case: Case, point: int, job: str, names=()) -> str:
    transcript = dict(case.points())[point]
    plain = alarm_message(transcript) if job == "alarm" else assessment_message(transcript, names)
    return with_patient(plain, case.patient)


def send_ten(door: Door, record: ModelCalls, job: str, user: str, between: tuple[str, str] | None,
             times: int = TIMES) -> list[dict]:
    """The call sent `times` times, with the other call before each
    sending after the first when one is given. A failed call is not the
    same as anything."""
    sends, first = [], None
    for n in range(1, times + 1):
        if between and n > 1:
            other = door.ask(between[0], between[1], STEADY)
            sends.append({"n": n, "role": "between", "job": between[0], "call_id": other.call_id,
                          "outcome": other.failure or "ok"})
        result = door.ask(job, user, STEADY)
        text = answer_text(record.get(result.call_id)["reply"])[0]
        if n == 1 and result.ok:
            first = text
        sends.append({"n": n, "role": "test", "job": job, "call_id": result.call_id,
                      "outcome": result.failure or "ok",
                      "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None,
                      "same": bool(result.ok and first is not None and text == first)})
    return sends


def run_repeat(door: Door, record: ModelCalls, cases: list[Case], reference: ResultWriter,
               writer: ResultWriter, points=POINTS, between_case: str = BETWEEN_CASE,
               times: int = TIMES, log: Callable = print) -> dict:
    """Every call of the test that has no result yet. One result for each
    case, job and way, written when its ten are done."""
    other_case = case_named(cases, between_case)
    other_point = other_case.points()[0][0]
    done, kept = 0, 0
    for name, point in points:
        case = case_named(cases, name)
        point = case.points()[-1][0] if point is None else point
        names = stale_names(reference, name, point)
        for job in JOBS:
            user = user_text(case, point, job, names)
            other_job = "assessment" if job == "alarm" else "alarm"
            between = (other_job, user_text(other_case, other_point, other_job))
            for way in WAYS:
                label = f"{job}-{way}"
                if writer.exists(name, label):
                    kept += 1
                    continue
                sends = send_ten(door, record, job, user, between if way == "between" else None, times)
                same = sum(1 for s in sends if s.get("same"))
                writer.write(name, label, {
                    "kind": "repeat", "case": name, "group": case.group, "chain": label, "point": point,
                    "job": job, "way": way, "times": times, "same_as_first": same,
                    "stale": list(names) if job == "assessment" else [], "sends": sends,
                    "patient": asdict(case.patient), "case_sha256": case.sha256,
                    "together": False, **stamp(door)})
                done += 1
                log(f"repeat {name} {job} {way}: {same} of {times} the same as the first")
    return {"run": done, "kept": kept}
