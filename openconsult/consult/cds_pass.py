"""One pass of the clinical decision support (spec 15.7): the alarm
first, then the assessment (R30). Both read the transcript afresh (R9,
R12) and open with the patient line (R11). Code does the bookkeeping:
once the urgent step is arranged it stays arranged, and an empty list of
differentials keeps the earlier list (spec 15.8, ruling 5). If one call
fails the other still gives its result, and a failed alarm is said to be
not judged, never read as no alarm (HANDOVER, stage 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.consult.messages import (Patient, alarm_message, assessment_message, names_of,
                                          with_patient)
from openconsult.llm.door import Door, Result
from openconsult.llm.profile import Sampling


@dataclass(frozen=True)
class Carried:
    """What one pass hands the next: the earlier names, the latch, and
    the earlier list whole, so an empty reply cannot make it vanish."""
    names: tuple[str, ...] = ()
    arranged: bool = False
    differentials: tuple = ()


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
    kept: bool = False   # the reply's own list was empty, so this is the earlier pass's list


@dataclass(frozen=True)
class PassResult:
    alarm: Alarm
    assessment: Assessment
    carried: Carried   # for the next pass


def messages(transcript: str, patient: Patient, carried: Carried) -> tuple[str, str]:
    """The two messages of a pass: the alarm's, and the assessment's with
    the earlier names. Both open with the patient line (R11)."""
    return (with_patient(alarm_message(transcript), patient),
            with_patient(assessment_message(transcript, carried.names), patient))


def settle(alarm_result: Result, assessment_result: Result, carried: Carried) -> PassResult:
    """The bookkeeping, once both calls are back: the latch, the kept
    list, and what the next pass is handed."""
    alarm = _alarm(alarm_result, carried.arranged)
    assessment = _assessment(assessment_result, carried.differentials)
    if not assessment.ok:
        return PassResult(alarm, assessment, Carried(carried.names, alarm.arranged, carried.differentials))
    shown = tuple(assessment.differentials)
    return PassResult(alarm, assessment, Carried(names_of(shown), alarm.arranged, shown))


def run_pass(door: Door, transcript: str, patient: Patient, carried: Carried | None = None,
             sampling: Sampling | None = None) -> PassResult:
    """The alarm, then the assessment, one after another (R30)."""
    carried = carried or Carried()
    alarm_text, assessment_text = messages(transcript, patient, carried)
    alarm_result = door.ask("alarm", alarm_text, sampling)
    assessment_result = door.ask("assessment", assessment_text, sampling)
    return settle(alarm_result, assessment_result, carried)


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


def _assessment(result: Result, earlier: tuple) -> Assessment:
    """An empty list in a reply that fits its form keeps the earlier
    list, and says so; the record still holds the model's own reply. At
    the first pass there is no earlier list, so empty stays empty."""
    if not result.ok:
        return Assessment(False, [], [], [], None, result.failure, result.detail, result.call_id)
    reply = result.answer
    own = list(reply.get("differentials") or [])
    kept = not own and bool(earlier)
    return Assessment(True, list(earlier) if kept else own,
                      list(reply.get("questions_to_ask") or []),
                      list(reply.get("signs_to_check") or []), reply.get("reasoning"),
                      None, None, result.call_id, kept)
