"""No words from silence (spec 15.9 ruling 1; 11.5 rule 1). The loudness
of the sound fed to a speech choice, in windows of 100 ms on the session
clock, and the rule: a line is refused when even its loudest window says
nobody spoke. Pure Python, so the base app needs no numpy (spec 5.1)."""

from __future__ import annotations

import math
from array import array

from openconsult.speech.lines import Line, Refused

WINDOW_S = 0.1

# The threshold, as the loudest 100 ms window of a line in dBFS. Its
# source: v1 measured the sound under the fifteen "Thank you." lines
# Whisper wrote into the silence of consultation 445 at an RMS of 0.0077
# to 0.0105 (-42 to -40 dBFS), against 0.153 (-16 dBFS) for real speech
# (v1 HANDOVER, the 445 entry; V1_LESSONS 1.6). This is the top of that
# band. Measured on sound the browser had tidied: NOT YET MEASURED ON RAW
# SOUND, which v2 records (ruling 7). It is measured again in 5e.
QUIET_DBFS = -40.0

FULL_SCALE = 32768.0


def dbfs(rms: float) -> float:
    """RMS as a fraction of full scale, in decibels. Silence is -inf."""
    return 20 * math.log10(rms) if rms > 0 else -math.inf


def rms_of(samples: array) -> float:
    if not len(samples):
        return 0.0
    return math.sqrt(math.sumprod(samples, samples) / len(samples)) / FULL_SCALE


class Loudness:
    """The loudness of every piece fed so far, 16-bit mono PCM at the
    session's rate, as one dBFS figure for each full window."""

    def __init__(self, rate: int):
        if rate <= 0:
            raise ValueError("the rate is samples a second")
        self.rate = rate
        self.window = max(1, int(round(rate * WINDOW_S)))
        self.windows: list[float] = []
        self._carry = array("h")

    def add(self, pcm: bytes) -> None:
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        self._carry += samples
        while len(self._carry) >= self.window:
            self.windows.append(dbfs(rms_of(self._carry[: self.window])))
            self._carry = self._carry[self.window:]

    @property
    def seconds(self) -> float:
        return (len(self.windows) * self.window + len(self._carry)) / self.rate

    def _last_window(self, end_s: float) -> int:
        # In whole samples, so 0.3 s is window 3 and not 2.999 of one.
        return -(-int(round(end_s * self.rate)) // self.window)

    def reaches_past(self, end_s: float) -> bool:
        """Whether a span ending here reaches into sound not yet fed: past
        the full windows and past the piece still in hand."""
        return self._last_window(end_s) > len(self.windows) + (1 if len(self._carry) else 0)

    def loudest(self, start_s: float, end_s: float) -> float:
        """The loudest window that overlaps the span. A span that reaches
        past the full windows also sees the piece still in hand; a span
        with no sound at all is -inf, as silence is."""
        first = max(0, int(round(start_s * self.rate)) // self.window)
        last = max(first + 1, self._last_window(end_s))
        found = self.windows[first:last]
        if last > len(self.windows) and len(self._carry):
            found = [*found, dbfs(rms_of(self._carry))]
        return max(found) if found else -math.inf


def refuse_quiet(lines: list[Line], loudness: Loudness, threshold: float = QUIET_DBFS,
                 slack_s: float = 0.0, more_to_come: bool = True) -> tuple[list[Line], list[Refused]]:
    """The rule. What it refuses is kept and marked (V1_LESSONS 1.2).

    It looks slack_s to each side of the line, as wide as the choice's
    times allow (ruling 12), and refuses only if all of that stretch is
    quiet. While more sound is still to come, a stretch that reaches past
    the sound fed counts as not quiet, so in doubt the word stays and no
    line waits for more sound. At Stop nothing is still to come: the
    stretch is cut at the end of the sound, and a quiet last line is
    refused, because v1 wrote words into the silence at the end of a
    consultation, where safety nets are said."""
    accepted, refused = [], []
    for line in lines:
        start, end = max(0.0, line.start - slack_s), line.end + slack_s
        if more_to_come and loudness.reaches_past(end):
            accepted.append(line)
            continue
        loudest = loudness.loudest(start, end)
        if loudest <= threshold:
            refused.append(Refused(line, loudest, threshold))
        else:
            accepted.append(line)
    return accepted, refused
