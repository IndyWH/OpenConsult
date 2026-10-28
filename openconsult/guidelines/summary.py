"""The summary call and its outcome by code (spec 15.12, rulings 6 and 7;
the detail The passages and the search; R3, R4, R11, R20, R30; D24): the
message from the frame, the passages sent as numbered blocks, the patient
line first and no slot for the background block; the call through the
door; then the outcome sorted by code, never trusted: covered false is a
refusal with the model's one sentence, a covered reply citing no number
it was given is a refusal too, and a covered reply's marks are checked
against the numbers sent, the invalid ones counted and left as plain
text. Nothing here asserts that a summary is right."""

from __future__ import annotations

import re
from dataclasses import dataclass

from openconsult.consult.messages import Patient, with_patient
from openconsult.guidelines.texts import source_line
from openconsult.llm.door import Door, Result
from openconsult.llm.profile import Sampling
from openconsult.prompts import loader

COVERED, NOT_COVERED, NO_CITATION, FAILED = "covered", "not_covered", "no_citation", "failed"
MARK = re.compile(r"\[(\d+)\]")
PASSAGE_GAP = "\n\n"


def passages_text(sent: list[dict]) -> str:
    """Each passage as the layout file gives it, one blank line between."""
    layout = loader.file_text("guideline.passage")
    return PASSAGE_GAP.join(loader.fill(layout, n=str(p["n"]), source=source_line(p["title"], p["trail"]), text=p["text"])
                            for p in sent)


def message(query: str, sent: list[dict], patient: Patient) -> str:
    """The user text: the patient line (R11), a blank line, the filled
    frame; no slot for the background block (D24)."""
    return with_patient(loader.fill(loader.frame("guideline"), query=query, passages=passages_text(sent)), patient)


def marks_in(text: str) -> list[int]:
    return [int(n) for n in MARK.findall(text or "")]


@dataclass(frozen=True)
class Outcome:
    outcome: str                 # covered, not_covered, no_citation or failed
    covered: bool | None
    summary: str | None          # the model's summary, or its one sentence when not covered
    cited: list                  # the valid numbers, sorted, once each
    invalid: int                 # marks and listed numbers outside those sent
    call_id: int
    wall_ms: int
    failure: str | None


def judge(result: Result, sent_count: int) -> Outcome:
    """The outcome by code from the door's result."""
    if not result.ok:
        return Outcome(FAILED, None, None, [], 0, result.call_id, result.wall_ms, f"{result.failure}: {result.detail}")
    answer = result.answer
    summary = str(answer.get("summary") or "")
    listed = [n for n in (answer.get("passages_cited") or []) if isinstance(n, int) and not isinstance(n, bool)]
    numbers = marks_in(summary) + listed
    valid = sorted({n for n in numbers if 1 <= n <= sent_count})
    invalid = sum(1 for n in numbers if not 1 <= n <= sent_count)
    if not answer.get("covered"):
        return Outcome(NOT_COVERED, False, summary, [], invalid, result.call_id, result.wall_ms, None)
    if not valid:
        return Outcome(NO_CITATION, True, summary, [], invalid, result.call_id, result.wall_ms, None)
    return Outcome(COVERED, True, summary, valid, invalid, result.call_id, result.wall_ms, None)


def summarise(door: Door, query: str, sent: list[dict], patient: Patient, sampling: Sampling | None = None,
              consultation_id: int | None = None) -> Outcome:
    """The one call, through the door (limited, checked, recorded, R30), and its outcome."""
    result = door.ask("guideline", message(query, sent, patient), sampling, consultation_id)
    return judge(result, len(sent))
