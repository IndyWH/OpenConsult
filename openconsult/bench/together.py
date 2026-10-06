"""The two calls of a pass sent at the same moment (spec 15.8, ruling 8).
A measurement of the bench only: the app still sends the alarm and then
the assessment, and nothing in the app can send together (R31).

Each call goes through the door on its own thread, so each is limited,
checked and recorded as ever. The door never raises for an engine's
failure, so one call failing cannot lose the other. The messages and
the bookkeeping are the pass's own.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from openconsult.consult.cds_pass import Carried, PassResult, messages, settle
from openconsult.consult.messages import Patient
from openconsult.llm.door import Door
from openconsult.llm.profile import Sampling


def run_pass_together(door: Door, transcript: str, patient: Patient, carried: Carried | None = None,
                      sampling: Sampling | None = None) -> PassResult:
    carried = carried or Carried()
    alarm_text, assessment_text = messages(transcript, patient, carried)
    with ThreadPoolExecutor(max_workers=2) as pool:
        alarm = pool.submit(door.ask, "alarm", alarm_text, sampling)
        assessment = pool.submit(door.ask, "assessment", assessment_text, sampling)
    return settle(alarm.result(), assessment.result(), carried)
