"""The two thresholds of the gate (spec 7.3; 15.13, the details of run 9c).

The fewest words a note is drafted from, and the score under which a line
is marked as low confidence. Each is a setting with its default; a
consultation holds the two values it started with in its own row, and its
gate and its review page read them there, so a change in Settings never
reaches a consultation that has begun. An older row holds none and reads
the defaults.

The lowest and the highest value of each are the owner's, 18 Nov 2026.
Fewest words, 30 to 300: a greeting and one question came to about 30
words in the room run of 15 Nov, and the field must not be able to switch
the gate off; the shortest stored page has 671 words and 300 is about two
minutes of speech. Low score, 0.40 to 0.80, counted on the stored pages:
of 3,781 live lines of the cloud service none is under 0.40, and of 99
lines of WhisperX 32 are under 0.80, so outside these the mark is on no
line or on most."""

from __future__ import annotations

import re

# Too short: a design choice, not a measurement, a tenth of the shortest
# script of the bank (script 01, 667 words by the bench's parser; the
# shortest of the sixteen cases is 07 at 619).
FEWEST_WORDS_DEFAULT = 60
FEWEST_WORDS_LOW, FEWEST_WORDS_HIGH = 30, 300
# The low-confidence line: v1's 0.60, for a choice that gives a score
# (V1_LESSONS 1.10: 468, a news broadcast, was refused at 0.549).
LOW_SCORE_DEFAULT = 0.60
LOW_SCORE_LOW, LOW_SCORE_HIGH = 0.40, 0.80

# A score is shown with two places everywhere, so a threshold has no more.
_SCORE = re.compile(r"[01]?\.\d{1,2}|[01]")


def fewest_words_of(text: str) -> int | None:
    """The whole number a form gave, or None when it is not one within the bounds."""
    text = (text or "").strip()
    if not text.isascii() or not text.isdigit() or len(text) > 4:
        return None
    number = int(text)
    return number if FEWEST_WORDS_LOW <= number <= FEWEST_WORDS_HIGH else None


def low_score_of(text: str) -> float | None:
    """The score a form gave, or None when it is not a number of at most
    two places within the bounds. Judged in hundredths, so that 0.40 and
    0.80 themselves are inside whatever a float makes of them."""
    text = (text or "").strip()
    if not _SCORE.fullmatch(text):
        return None
    whole, _, places = text.partition(".")
    hundredths = int(whole or "0") * 100 + int(places.ljust(2, "0") or "0")
    if not round(LOW_SCORE_LOW * 100) <= hundredths <= round(LOW_SCORE_HIGH * 100):
        return None
    return hundredths / 100


def of_row(row) -> tuple[int, float]:
    """The two values a consultation started with, from its own row; the
    defaults for a row from before the thresholds could be set."""
    row = dict(row)
    fewest, low = row.get("fewest_words"), row.get("low_score")
    return (int(fewest) if fewest is not None else FEWEST_WORDS_DEFAULT,
            float(low) if low is not None else LOW_SCORE_DEFAULT)
