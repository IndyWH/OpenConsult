"""The table of jobs (spec 15.7; V1_LESSONS 3.11). Each job names its
prompt file, its answer form, the frames around the transcript, its
limit on length, its limit on time, and what happens when it fails.
Stage 3 fills two; the others of spec 10.2 arrive with their stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    name: str
    prompt: str          # the prompt file's name in the prompts folder
    form: str            # the answer form's name
    frames: tuple[str, ...]
    max_tokens: int
    timeout_s: float
    on_failure: str


# The limits are v1's after consultation 486 for the assessment (1,500
# tokens, 60 s) and the alarm's cap (1,000). The alarm's 60 s is a design
# choice: v1 left it at a default nobody chose (spec 15.7).
JOBS = {
    "alarm": Job(
        name="alarm", prompt="alarm", form="alarm", frames=("alarm",),
        max_tokens=1000, timeout_s=60.0,
        on_failure="The pass keeps the earlier alarm state and says this pass's alarm was "
                   "not judged; the assessment still runs.",
    ),
    "assessment": Job(
        name="assessment", prompt="assessment", form="assessment",
        frames=("assessment.frame.first", "assessment.frame.later"),
        max_tokens=1500, timeout_s=60.0,
        on_failure="The alarm's result stands; the earlier differential names stay the stale "
                   "list for the next pass.",
    ),
}


def job(name: str) -> Job:
    try:
        return JOBS[name]
    except KeyError:
        raise KeyError(f"no such job: {name}") from None
