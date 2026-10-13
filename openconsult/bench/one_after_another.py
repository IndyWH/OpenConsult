"""The two calls of a pass one after another: the alarm, then the
assessment, as the app sent them before 3c (spec 15.8, ruling 31). The
app's one way is together, in consult/cds_pass; the bench keeps this way
for its arms, so the engine bench can still be read against them.
"""

from __future__ import annotations

from openconsult.consult.cds_pass import Carried, PassResult, messages, settle
from openconsult.consult.messages import Patient
from openconsult.llm.door import Door
from openconsult.llm.profile import Sampling


def run_pass_one_after_another(door: Door, transcript: str, patient: Patient, carried: Carried | None = None,
                               sampling: Sampling | None = None) -> PassResult:
    carried = carried or Carried()
    alarm_text, assessment_text = messages(transcript, patient, carried)
    alarm_result = door.ask("alarm", alarm_text, sampling)
    assessment_result = door.ask("assessment", assessment_text, sampling)
    return settle(alarm_result, assessment_result, carried)
