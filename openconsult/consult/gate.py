"""The checks at Stop and the gate (spec 15.10 ruling 8; 11.4; 11.5 rules
2 and 5; R3; V1_LESSONS 1.9, 1.10, 3.6). The two checks for missing
speech are the two functions of 5c, unchanged: their results become
warnings at their place. The gate has three rules in code. One: it
refuses when the transcript is empty or too short to hold a
consultation, and no note is drafted. Two: it flags, never refuses, a
missing passage and a line with no speaker. Three: where the speech
choice gives a confidence score, a low-confidence line is flagged as v1
flagged it; where it gives none, the page says confidence was not
measured, and no score is made up."""

from __future__ import annotations

from dataclasses import dataclass, field

from openconsult.speech.lines import Declares, Line
from openconsult.speech.loudness import WINDOW_S
from openconsult.speech.matching import normalise
from openconsult.speech.missing import missing_from_final, uncovered_speech

# Too short: a design choice, not a measurement, a tenth of the shortest
# script of the bank (script 01, 667 words by the bench's parser; the
# shortest of the sixteen cases is 07 at 619). The room may move it.
TOO_SHORT_WORDS = 60
# The low-confidence line: v1's 0.60, for a choice that gives a score
# (V1_LESSONS 1.10: 468, a news broadcast, was refused at 0.549).
LOW_CONFIDENCE = 0.60


@dataclass
class Verdict:
    refused: bool
    warnings: list[dict] = field(default_factory=list)


def word_count(rows: list[dict]) -> int:
    """Words as the bench's matching counts them: a number said in words is
    one word (V1_LESSONS 3.6)."""
    return sum(len(normalise(row["text"])) for row in rows)


def missing_speech(live: list[Line], final: list[Line], windows: list, second_transcript: bool) -> list[dict]:
    """The two checks of 5c on the stored lines and the stored loudness
    (11.5 rule 2; D45), each result a warning at its place."""
    found = []
    if second_transcript:
        for gap in missing_from_final(live, final):
            found.append({"kind": "missing_passage", "start_s": gap.start_s, "end_s": gap.end_s,
                          "detail": " ".join(gap.words)})
    for stretch in uncovered_speech(windows, WINDOW_S, final):
        found.append({"kind": "uncovered_speech", "start_s": stretch.start_s, "end_s": stretch.end_s})
    return found


def judge(rows: list[dict], declares: Declares, choice_title: str) -> Verdict:
    """The three rules over the numbered lines as they stand after the
    label check."""
    words = word_count(rows)
    if not rows or words == 0:
        return Verdict(True, [{"kind": "empty"}])
    warnings = []
    refused = words < TOO_SHORT_WORDS
    if refused:
        from openconsult import words as sentences
        warnings.append({"kind": "too_short", "detail": sentences.WARN_TOO_SHORT.format(words=words, least=TOO_SHORT_WORDS)})
    for row in rows:
        if row.get("unsure") or row.get("label") == "unsure":
            warnings.append({"kind": "no_speaker", "line_n": row["n"]})
    if declares.confidence == "none":
        warnings.append({"kind": "confidence_not_measured", "detail": choice_title})
    else:
        for row in rows:
            score = row.get("confidence")
            if score is not None and score < LOW_CONFIDENCE:
                warnings.append({"kind": "low_confidence", "line_n": row["n"], "detail": f"{score:.2f}"})
    return Verdict(refused, warnings)
