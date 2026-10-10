"""The check for missing speech (spec 11.5 rule 2; D45; 15.9 ruling 13).
Hard mark 1 turns on whether the page shows the doctor a sign, so the
check is written here, as plain functions, for the app and the bench to
measure with one function (V1_LESSONS 1.10). Stage 6 puts the signs on
the page and changes nothing here.

Two checks. For a choice with two transcripts: a run of five or more
words heard live that the transcript at Stop does not have. For every
choice: a stretch of two seconds or more of sound that is like speech and
that no line covers. Both lean towards the patient: where the times are
in doubt they show a sign. The check on the sound cannot see words
dropped inside a stretch a line covers, speech quieter than its figure,
or tell speech from a cough or a door."""

from __future__ import annotations

import math
from dataclasses import dataclass

from openconsult.speech.lines import Line
from openconsult.speech.matching import align, normalise

# Ruling 13: a passage is five or more words in a row.
LEAST_WORDS = 5
# Ruling 13: a stretch of speech counts from two seconds.
LEAST_SPEECH_S = 2.0
# The details of 5c: quiet gaps shorter than this inside speech are joined.
JOIN_GAP_S = 0.5
# Sound is like speech above this. Between the quiet band v1 measured
# under invented words (-42 to -40 dBFS) and real speech (-16 dBFS), from
# V1_LESSONS 1.6, on sound the browser had tidied: NOT YET MEASURED ON RAW
# SOUND. Measured in 5e, like the rule's own threshold.
SPEECH_DBFS = -30.0


@dataclass(frozen=True)
class Gap:
    """Words heard live that the transcript at Stop does not have, with
    the times of the live lines that held them."""
    words: tuple[str, ...]
    start_s: float
    end_s: float
    first_live_word: int       # the index of the first word in the live words, for the bench


@dataclass(frozen=True)
class Stretch:
    """Sound like speech that no line covers."""
    start_s: float
    end_s: float


def live_words(lines: list[Line]) -> list[tuple[str, Line]]:
    return [(word, line) for line in lines for word in normalise(line.text)]


def missing_from_final(live: list[Line], final: list[Line], least_words: int = LEAST_WORDS) -> list[Gap]:
    """Runs of least_words or more live words that no word of the final
    transcript stands for. A word garbled at Stop still stands for its
    live word, so five garbled words are no gap."""
    heard = live_words(live)
    pairs = align([w for w, _ in heard], [w for line in final for w in normalise(line.text)])
    missing = {p.spoken for p in pairs if p.kind == "missing"}
    gaps, run = [], []
    for index in range(len(heard) + 1):
        if index < len(heard) and index in missing:
            run.append(index)
            continue
        if len(run) >= least_words:
            gaps.append(Gap(tuple(heard[i][0] for i in run), heard[run[0]][1].start, heard[run[-1]][1].end, run[0]))
        run = []
    return gaps


def speech_stretches(windows: list[float | None], window_s: float, threshold: float = SPEECH_DBFS,
                     join_gap_s: float = JOIN_GAP_S) -> list[tuple[float, float]]:
    """Runs of windows above the threshold, with quiet gaps shorter than
    join_gap_s between them joined. A window of None is silence."""
    found: list[list[float]] = []
    for index, level in enumerate(windows):
        if level is None or level == -math.inf or level <= threshold:
            continue
        start, end = index * window_s, (index + 1) * window_s
        if found and start - found[-1][1] < join_gap_s:
            found[-1][1] = end
        else:
            found.append([start, end])
    return [(round(s, 3), round(e, 3)) for s, e in found]


def uncovered_speech(windows: list[float | None], window_s: float, lines: list[Line],
                     threshold: float = SPEECH_DBFS, least_s: float = LEAST_SPEECH_S,
                     join_gap_s: float = JOIN_GAP_S) -> list[Stretch]:
    """Speech that no line covers, lasting least_s or more. A line covers
    exactly its own span: the check does not look wider than the line's
    times, so where the times are in doubt it shows the sign."""
    covered = sorted((min(line.start, line.end), max(line.start, line.end)) for line in lines)
    stretches = []
    for start, end in speech_stretches(windows, window_s, threshold, join_gap_s):
        open_from = start
        for c_start, c_end in covered:
            if c_end <= open_from or c_start >= end:
                continue
            if c_start > open_from and c_start - open_from >= least_s:
                stretches.append(Stretch(round(open_from, 3), round(c_start, 3)))
            open_from = max(open_from, c_end)
        if end - open_from >= least_s:
            stretches.append(Stretch(round(open_from, 3), round(end, 3)))
    return stretches
