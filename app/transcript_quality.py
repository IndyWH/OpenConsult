"""Finalisation transcript-quality gate — refuse tier.

Spec: `TRANSCRIPT_QUALITY_GATE_SPEC.md`, and **read its §11 first** — the
2026-07-25 calibration run swapped which signals act.

Why it exists (spec §1): consultation #70's Sinhala audio went through
the English-forced pipeline and did not fail. It produced a fluent
hallucinated English translation and a normal-looking draft SOAP note,
which was reviewed and approved. The note was faithful to a transcript
that was not faithful to the audio — one level above anything else the
project checks. Not a Sinhala problem: Whisper loops on near-silence in
English too, and #78 was an English precedent.

Four signals are measured on EVERY consultation and stored whether or
not anything fires, so calibration data for the follow-up accumulates
for free. **Only two act:**

    S2  duration-weighted mean confidence   refuse below 0.60   ACTS
    S4  truncation gap (seconds)            refuse above 20 s   ACTS
    S1  language detection                  measured only       DOES NOT ACT
    S3  repetition                          measured only       DOES NOT ACT

S1 and S3 do not act because the calibration showed they cannot yet:
single-window language detection returns English at p=0.90 for #70 (the
script opens with an English-heavy greeting), and S3's cross-segment run
length is 1 in all five recordings. Both need a redesign and their own
calibration run before they are trusted — spec §11, "S1 and S3 redesign".
Do not wire them into the decision here without that.

The two acting signals fire INDEPENDENTLY — either alone refuses. There
is no co-occurrence rule; #70 trips both, so requiring both would only
weaken the guard.

The flag tier (amber banner, approval blocked until acknowledged) is
deliberately not implemented here. Its thresholds are recorded in the
spec and its config keys exist unused in `.env.example`, so the
follow-up sets behaviour rather than inventing numbers.

Refusal means: no draft note generated, status `unreliable_transcript`,
review page shows the diarised transcript under a red banner. Transcript
and audio are retained — this is evidence, not rubbish. Same shape as
the note grounding gate's refusal.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter

logger = logging.getLogger(__name__)

# --- configuration (spec §11, replaces §6) --------------------------------

GATE_ENABLED = os.getenv("TRANSCRIPT_GATE_ENABLED", "true").lower() != "false"

# Acting thresholds, owner-set 2026-07-25 from the calibration table.
# S2: the good four sit 0.785-0.810, #70 at 0.505. 0.60 sits 0.185 below
# the worst good recording and 0.095 above #70 — deliberately biased
# toward missing a bad recording rather than blocking a good one.
MIN_AVG_CONFIDENCE_REFUSE = float(os.getenv("TRANSCRIPT_MIN_AVG_CONFIDENCE_REFUSE", "0.60"))
# S4: the good four sit 0.1-4.4 s, #70 at 33.3 s.
TRUNCATION_REFUSE_S = float(os.getenv("TRANSCRIPT_TRUNCATION_REFUSE_S", "20"))

# Measured, not acted on. Kept here so the stored signals are
# self-describing; changing them changes no behaviour.
EXPECTED_LANGUAGE = os.getenv("TRANSCRIPT_EXPECTED_LANGUAGE", "en")

NGRAM_N = 4

OUTCOME_PASS = "pass"
OUTCOME_REFUSED = "refused"
STATUS_UNRELIABLE = "unreliable_transcript"


def _tokenise(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


# --- signals ---------------------------------------------------------------

def s2_weighted_confidence(turns: list[dict]) -> float | None:
    """Mean per-segment confidence weighted by segment duration, so a long
    garbled stretch is not cancelled by a short clean one."""
    total = weight = 0.0
    for turn in turns:
        duration = max(0.0, float(turn.get("end", 0)) - float(turn.get("start", 0)))
        total += float(turn.get("confidence", 0)) * duration
        weight += duration
    return (total / weight) if weight > 0 else None


def s3_repetition(turns: list[dict]) -> dict:
    """Measured only. Largest share of tokens taken by one 4-gram, plus the
    longest run of identical consecutive segments (which the calibration
    showed is dead at 1 everywhere — retained because it costs nothing)."""
    tokens: list[str] = []
    for turn in turns:
        tokens.extend(_tokenise(turn.get("text", "")))
    share, gram = 0.0, None
    if len(tokens) >= NGRAM_N:
        grams = Counter(" ".join(tokens[i:i + NGRAM_N])
                        for i in range(len(tokens) - NGRAM_N + 1))
        gram, count = grams.most_common(1)[0]
        share = (count * NGRAM_N) / len(tokens)
    best = run = 0
    previous = None
    for turn in turns:
        normalised = " ".join(_tokenise(turn.get("text", "")))
        run = run + 1 if previous is not None and normalised == previous else 1
        previous = normalised
        best = max(best, run)
    return {"max_ngram_share": round(share, 4), "max_ngram": gram,
            "max_consecutive_identical": best}


def s4_truncation_gap(turns: list[dict], audio_duration_s: float | None) -> float | None:
    """Seconds of audio after the last stored segment ends. None when the
    audio duration is unknown — never a fabricated zero."""
    if audio_duration_s is None or not turns:
        return None
    return max(0.0, float(audio_duration_s) - max(float(t.get("end", 0)) for t in turns))


def compute_signals(turns: list[dict], *, audio_duration_s: float | None = None,
                    detected_language: str | None = None,
                    language_probability: float | None = None) -> dict:
    """All four signals. Always computed, always stored (spec §3, §7)."""
    return {
        "s1_language": {
            "detected": detected_language,
            "probability": language_probability,
            "expected": EXPECTED_LANGUAGE,
            "acts": False,   # see module docstring / spec §11
        },
        "s2_confidence": {
            "weighted_mean": s2_weighted_confidence(turns),
            "refuse_below": MIN_AVG_CONFIDENCE_REFUSE,
            "acts": True,
        },
        "s3_repetition": {**s3_repetition(turns), "acts": False},
        "s4_truncation": {
            "gap_s": s4_truncation_gap(turns, audio_duration_s),
            "audio_duration_s": audio_duration_s,
            "refuse_above_s": TRUNCATION_REFUSE_S,
            "acts": True,
        },
        "segments": len(turns),
    }


# --- decision --------------------------------------------------------------

def evaluate(signals: dict) -> dict:
    """Decide from measured signals. Pure — no I/O, no model.

    Only S2 and S4 are consulted. They fire independently: either alone
    refuses. A signal that could not be measured (None) never refuses —
    an unmeasurable signal is not evidence of a bad transcript.
    """
    fired: list[dict] = []

    confidence = signals.get("s2_confidence", {}).get("weighted_mean")
    if confidence is not None and confidence < MIN_AVG_CONFIDENCE_REFUSE:
        fired.append({
            "signal": "S2",
            "name": "low average confidence",
            "value": round(confidence, 3),
            "threshold": MIN_AVG_CONFIDENCE_REFUSE,
            "detail": (f"duration-weighted mean ASR confidence {confidence:.3f} "
                       f"is below {MIN_AVG_CONFIDENCE_REFUSE}"),
        })

    gap = signals.get("s4_truncation", {}).get("gap_s")
    if gap is not None and gap > TRUNCATION_REFUSE_S:
        fired.append({
            "signal": "S4",
            "name": "audio truncation",
            "value": round(gap, 1),
            "threshold": TRUNCATION_REFUSE_S,
            "detail": (f"{gap:.1f}s of audio after the last transcribed "
                       f"segment, tolerance {TRUNCATION_REFUSE_S:.0f}s"),
        })

    if not GATE_ENABLED:
        # Break-glass switch, not a demo convenience — say so loudly.
        if fired:
            logger.warning(
                "TRANSCRIPT_GATE_ENABLED=false — the transcript-quality gate "
                "WOULD have refused (%s) but is disabled; a draft note will be "
                "generated from a transcript that failed the gate",
                ", ".join(f["signal"] for f in fired))
        else:
            logger.warning("TRANSCRIPT_GATE_ENABLED=false — transcript-quality "
                           "gate disabled; signals measured but not enforced")
        return {"outcome": OUTCOME_PASS, "fired": [], "enabled": False,
                "would_have_fired": fired}

    return {"outcome": OUTCOME_REFUSED if fired else OUTCOME_PASS,
            "fired": fired, "enabled": True}


def refusal_summary(fired: list[dict]) -> str:
    """One line for the banner and the audit detail."""
    if not fired:
        return ""
    return "; ".join(f["detail"] for f in fired)
