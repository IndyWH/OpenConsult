"""One pass of the clinical decision support (spec 15.7): the alarm
first, then the assessment (R30). Both read the transcript afresh (R9,
R12) and open with the patient line (R11). Code does the bookkeeping:
once the urgent step is arranged it stays arranged. If one call fails
the other still gives its result, and a failed alarm is said to be not
judged, never read as no alarm (plan review, change 4).
"""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.consult.messages import (Patient, alarm_message, assessment_message, names_of,
                                          with_patient)
from openconsult.llm.door import Door, Result
from openconsult.llm.profile import Sampling


@dataclass(frozen=True)
class Carried:
    """What one pass hands the next: the earlier names, and the latch."""
    names: tuple[str, ...] = ()
    arranged: bool = False


@dataclass(frozen=True)
class Alarm:
    judged: bool                      # False when the call failed
    time_critical: bool | None
    arranged: bool                    # latched for the consultation
    actions: list                     # empty when nothing is due, arranged, or not judged
    flag_without_action: bool         # time-critical said, no action named (V1_LESSONS 3.14)
    reason: str | None
    raw_actions: list                 # the reply's own actions, before bookkeeping
    failure: str | None
    detail: str | None
    call_id: int


@dataclass(frozen=True)
class Assessment:
    ok: bool
    differentials: list
    questions: list
    signs: list
    reasoning: str | None
    failure: str | None
    detail: str | None
    call_id: int


@dataclass(frozen=True)
class PassResult:
    alarm: Alarm
    assessment: Assessment
    carried: Carried   # for the next pass


def run_pass(door: Door, transcript: str, patient: Patient, carried: Carried | None = None,
             sampling: Sampling | None = None) -> PassResult:
    carried = carried or Carried()
    alarm_text = with_patient(alarm_message(transcript), patient)
    assessment_text = with_patient(assessment_message(transcript, carried.names), patient)
    alarm = _alarm(door.ask("alarm", alarm_text, sampling), carried.arranged)
    assessment = _assessment(door.ask("assessment", assessment_text, sampling))
    names = names_of(assessment.differentials) if assessment.ok else carried.names
    return PassResult(alarm, assessment, Carried(names, alarm.arranged))


def _alarm(result: Result, arranged_before: bool) -> Alarm:
    if not result.ok:
        return Alarm(False, None, arranged_before, [], False, None, [], result.failure,
                     result.detail, result.call_id)
    reply = result.answer
    time_critical = bool(reply["time_critical_possible"])
    arranged = bool(reply["already_done_or_arranged"]) or arranged_before
    raw = list(reply.get("urgent_actions") or [])
    actions = raw if time_critical and not arranged else []
    return Alarm(True, time_critical, arranged, actions, time_critical and not raw,
                 reply.get("reasoning"), raw, None, None, result.call_id)


def _assessment(result: Result) -> Assessment:
    if not result.ok:
        return Assessment(False, [], [], [], None, result.failure, result.detail, result.call_id)
    reply = result.answer
    return Assessment(True, list(reply.get("differentials") or []),
                      list(reply.get("questions_to_ask") or []),
                      list(reply.get("signs_to_check") or []), reply.get("reasoning"),
                      None, None, result.call_id)
