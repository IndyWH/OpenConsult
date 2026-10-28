"""The table of jobs (spec 15.7; V1_LESSONS 3.11). Each job names its
prompt file, its answer form, the frames around the transcript, its
limit on length, its limit on time, and what happens when it fails.
Stage 3 filled two; stage 6a added the label check (15.9 ruling 17;
15.10 ruling 7); stage 6b adds the note (15.10 rulings 3, 5 and 8); the
others of spec 10.2 arrive with their stages."""

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


# The note's limits are the bench's figures, which the bench reads from
# here (spec 5.1): the longest note of the rehearsal of 11 Oct was 1,284
# tokens, so 3,000 is more than twice it; the longest call was 8.2 s.
NOTE_MAX_TOKENS, NOTE_TIMEOUT_S = 3000, 120.0

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
        frames=("assessment.first", "assessment.later"),
        max_tokens=1500, timeout_s=60.0,
        on_failure="The alarm's result stands; the earlier differential names stay the stale "
                   "list for the next pass.",
    ),
    # The limits are the bench's named figures (15.9, the details of part
    # two): the longest page of the rehearsal had 124 lines and a line of
    # the reply is about 13 tokens.
    "label_check": Job(
        name="label_check", prompt="label_check", form="label_check", frames=("label_check",),
        max_tokens=3000, timeout_s=120.0,
        on_failure="The labels stand as the who-spoke answer set them; the final page says the check "
                   "did not run and why. Nothing is asked a second time.",
    ),
    # The two calls of 8a (15.12, rulings 2, 3 and 8; R30). Design choices
    # until the bench measures them: the list's reply is a reasoning under
    # 60 words and a few items, so 1,500 tokens and the assessment's 60 s;
    # the letter's a reasoning under 80 words and four paragraphs, about
    # 700 tokens, so 2,500 and the note's 120 s.
    "referrals": Job(
        name="referrals", prompt="referrals", form="referrals", frames=("referrals",),
        max_tokens=1500, timeout_s=60.0,
        on_failure="The review page says the referral list could not be made and why, and offers to make it again; "
                   "name a specialty still drafts a letter.",
    ),
    "letter": Job(
        name="letter", prompt="letter", form="letter", frames=("letter",),
        max_tokens=2500, timeout_s=120.0,
        on_failure="The letter's page says the letter could not be drafted and why; Draft again is offered. "
                   "Nothing is asked a second time by itself.",
    ),
    # The note (15.10, The note): the transcript alone, no patient line (D3).
    "note": Job(
        name="note", prompt="note", form="note", frames=("note",),
        max_tokens=NOTE_MAX_TOKENS, timeout_s=NOTE_TIMEOUT_S,
        on_failure="The review page says the note could not be drafted and why; Draft the note is "
                   "offered. Nothing is asked a second time by itself.",
    ),
}


def job(name: str) -> Job:
    try:
        return JOBS[name]
    except KeyError:
        raise KeyError(f"no such job: {name}") from None
