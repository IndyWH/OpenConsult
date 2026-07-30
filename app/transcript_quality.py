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

    S2  duration-weighted mean confidence   refuse < 0.60, flag < 0.70   ACTS
    S4  truncation gap / trailing content   refuse (content), flag >10s  ACTS
    S3  repetition (floored within-segment) flag > 0.5, never refuses    ACTS (flag only, 2026-07-30)
    S1  language (median window prob.)      measured only                DOES NOT ACT

S1 does not act, deliberately (owner decision 2026-07-30): the
re-calibration killed the designed fraction metric (1.00 everywhere,
#70 included — the recording is code-switched throughout) and the
surviving candidate, median window probability, has a corridor only
0.013 wide. Too thin to act on; see the comment at the thresholds. S3
acts at the FLAG tier only, on the ≥12-token-floored within-segment
share the same re-calibration validated (2.2× corridor).

The two acting signals fire INDEPENDENTLY — either alone refuses. There
is no co-occurrence rule; #70 trips both, so requiring both would only
weaken the guard.

The FLAG tier (spec §11) is live since 2026-07-31: S2 in [0.60, 0.70)
or a trailing gap over 10 s that did not refuse produces outcome
`flagged` — the draft note proceeds, and approval is blocked behind an
amber acknowledge-gated banner on the review page (the urgency-banner
pattern; `quality_ack_at` on the consultation). The thresholds are the
owner-set numbers recorded in §11 on 2026-07-25, wired not invented.

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
# S4 FALLBACK ONLY (see s4_trailing_region). The duration tolerance is no
# longer how S4 decides — it survives for the one case where the trailing
# region cannot be measured at all, e.g. the audio has been purged by the
# retention sweep. Retaining the previous behaviour there is not a weakening;
# silently passing an unmeasurable gap would be.
TRUNCATION_REFUSE_S = float(os.getenv("TRANSCRIPT_TRUNCATION_REFUSE_S", "20"))

# S4 speech detection in the trailing region (owner's rule, 2026-07-28):
# SILENCE IS IGNORED HOWEVER LONG IT IS, AND SPEECH THAT WAS NOT TRANSCRIBED
# REFUSES HOWEVER SHORT IT IS.
#
# Windowed RMS from the ORIGINAL WAV, relative to the recording's own noise
# floor. Deliberately NOT silero VAD: the VAD deciding there was no speech is
# frequently what created the gap, so re-running it would make the gate agree
# with itself and become decorative. The check has to be independent of the
# thing it audits, and acoustic energy is the independent signal available.
#
# Separation measured during the 445 filler assessment: 0.008-0.010 RMS under
# genuine silence against 0.153 for real speech — more than tenfold. A 4x
# floor-relative ratio sits well inside that, and floor-relative is what stops
# a quietly-spoken patient reading as silence.
TRAILING_WINDOW_S = float(os.getenv("TRANSCRIPT_TRAILING_WINDOW_S", "0.25"))

# The reference is THIS RECORDING'S OWN TRANSCRIBED SPEECH, at p75 of window
# energy, and the threshold is a fraction of it. Self-calibrating per room, mic
# and gain, which no global constant can be.
#
# A noise-floor multiple was tried first and MEASURED WRONG, which is why it is
# not what ships: 449's five silent minutes drag a whole-recording low
# percentile down to 0.0012, below the 0.008-0.010 that the 445 filler
# assessment measured for genuine silence, so a 4x floor threshold lands at
# 0.0048 and anything faintly audible clears it. The quieter the room, the more
# sensitive the detector became — backwards.
TRAILING_SPEECH_FRACTION = float(os.getenv("TRANSCRIPT_TRAILING_SPEECH_FRACTION", "0.5"))
TRAILING_REFERENCE_PERCENTILE = float(os.getenv("TRANSCRIPT_TRAILING_REF_PCT", "75"))

# Decide on a CONTINUOUS run, not on a total. This is the residual allowance,
# and it is an allowance for the SPEECH DETECTOR's noise rather than a length of
# audio we are willing to ignore: energy is not speech, and a cough, a chair or
# a page turn is exactly the broadband transient an energy measure mistakes for
# a voice. Speech runs on for seconds; a transient does not.
#
# Measured on the real recordings at this fraction (longest run above threshold
# in the trailing region):
#     449, silent room      2.25 s   -> passes
#     445, missed speech    4.75 s   -> refuses (the regression fixture)
#     constructed 10 s      9.50 s   -> refuses (the blind spot being closed)
# 3.0 s separates all three. THE MARGIN ON 445 IS 1.75 s AND THAT IS THIN;
# every measured value is stored on the consultation so this can be set from
# more rooms rather than re-guessed. The residual risk is stated rather than
# hidden: a genuine utterance shorter than the run threshold, at the very end of
# a recording, still passes.
TRAILING_MIN_RUN_S = float(os.getenv("TRANSCRIPT_TRAILING_MIN_RUN_S", "3.0"))

# Flag tier (spec §11, built 2026-07-31 — the follow-up the v1 build
# scope deferred). Thresholds are the OWNER-SET numbers recorded in §11
# on 2026-07-25; this commit wires them, it does not invent them.
# A flagged transcript still gets a draft note; approval is blocked
# behind an amber acknowledge-gated banner (the urgency pattern).
MIN_AVG_CONFIDENCE_FLAG = float(os.getenv("TRANSCRIPT_MIN_AVG_CONFIDENCE_FLAG", "0.70"))
# S4's flag keeps the RECORDED duration semantics: a trailing gap over
# 10 s that did NOT refuse (its content measured as non-speech, or it
# was unmeasurable but under the 20 s fallback) is exactly the amber
# case — a sizeable untranscribed tail worth a human eye, not a refusal.
# Measured missing SPEECH refuses regardless (the 2026-07-28 rule); the
# flag never overrides that.
TRUNCATION_FLAG_S = float(os.getenv("TRANSCRIPT_TRUNCATION_FLAG_S", "10"))

# Measured, not acted on. Kept here so the stored signals are
# self-describing; changing them changes no behaviour.
EXPECTED_LANGUAGE = os.getenv("TRANSCRIPT_EXPECTED_LANGUAGE", "en")

# S1 multi-window (spec §11 redesign, built 2026-07-31, MEASURE-ONLY):
# language is detected on windows spread evenly across the audio and the
# reported figure is the FRACTION detected as the expected language —
# single-window detection returned English at p=0.90 for #70 because the
# script opens at its most English-looking. Neither parameter has a
# calibrated threshold yet; nothing here acts until the owner sets one
# from the re-calibration run.
S1_WINDOW_S = float(os.getenv("TRANSCRIPT_S1_WINDOW_S", "30"))
S1_MAX_WINDOWS = int(os.getenv("TRANSCRIPT_S1_MAX_WINDOWS", "10"))

# S3's within-segment share saturates at 1.0 on SHORT segments — measured
# on the 2026-07-31 re-calibration: seven healthy recordings hit 1.0
# through segments of a few tokens, while #70's genuine loops sit at
# 0.727 among segments of ≥12 tokens against ≤0.333 everywhere else.
S3_MIN_SEGMENT_TOKENS = int(os.getenv("TRANSCRIPT_S3_MIN_SEGMENT_TOKENS", "12"))
# ACTS at the FLAG tier since 2026-07-30 (owner decision, from the
# measured 2.2x corridor above): a floored within-segment share over
# this flags — amber banner, acknowledge-gated approval — never refuses.
S3_WITHIN_FLAG = float(os.getenv("TRANSCRIPT_S3_WITHIN_FLAG", "0.5"))

# S1 (median window probability) stays MEASURE-ONLY, deliberately — the
# owner's 2026-07-30 decision alongside the S3 one. Its corridor is
# 0.013 wide (#70's median 0.902 against 0.943 for the closest healthy
# consultation, 457), which is too thin to act on: one quiet room or one
# soft-spoken patient could cross it. What would change this: more
# stored consultations widening the corridor (act) or collapsing it
# (redesign again). Every consultation stores the windows, and the
# calibration harness keeps reporting the median, so the data
# accumulates without further work.

NGRAM_N = 4

OUTCOME_PASS = "pass"
OUTCOME_FLAGGED = "flagged"
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


def _ngram_share(tokens: list[str]) -> tuple[float, str | None]:
    """Largest share of tokens taken by one repeated 4-gram. The same
    formula everywhere it is used, so figures are comparable."""
    if len(tokens) < NGRAM_N:
        return 0.0, None
    grams = Counter(" ".join(tokens[i:i + NGRAM_N])
                    for i in range(len(tokens) - NGRAM_N + 1))
    gram, count = grams.most_common(1)[0]
    return (count * NGRAM_N) / len(tokens), gram


def s3_repetition(turns: list[dict]) -> dict:
    """MEASURED ONLY — the SHARED S3 implementation (pipeline and
    calibration harness both call this; two copies would diverge).

    Three figures:
    - `max_ngram_share`: the original whole-transcript 4-gram share.
    - `max_within_segment_share` (§11 redesign, 2026-07-31): the same
      measure computed INSIDE each segment's text, maximum across
      segments — the calibration showed #70's repetition lives within
      segments, so the whole-transcript figure dilutes exactly the
      signal it is meant to catch. No threshold exists yet; it acts on
      nothing until re-calibrated.
    - `max_consecutive_identical`: the dead cross-segment run length
      (1 everywhere measured), retained as a reported value because it
      costs nothing — but never thresholded (§11).
    """
    tokens: list[str] = []
    for turn in turns:
        tokens.extend(_tokenise(turn.get("text", "")))
    share, gram = _ngram_share(tokens)

    within_share, within_gram, within_idx = 0.0, None, None
    floored_share = 0.0
    for i, turn in enumerate(turns):
        turn_tokens = _tokenise(turn.get("text", ""))
        turn_share, turn_gram = _ngram_share(turn_tokens)
        if turn_share > within_share:
            within_share, within_gram, within_idx = turn_share, turn_gram, i
        if len(turn_tokens) >= S3_MIN_SEGMENT_TOKENS:
            floored_share = max(floored_share, turn_share)

    best = run = 0
    previous = None
    for turn in turns:
        normalised = " ".join(_tokenise(turn.get("text", "")))
        run = run + 1 if previous is not None and normalised == previous else 1
        previous = normalised
        best = max(best, run)
    return {"max_ngram_share": round(share, 4), "max_ngram": gram,
            "max_within_segment_share": round(within_share, 4),
            "max_within_segment_ngram": within_gram,
            "max_within_segment_idx": within_idx,
            "max_within_segment_share_floored": round(floored_share, 4),
            "min_segment_tokens": S3_MIN_SEGMENT_TOKENS,
            "max_consecutive_identical": best}


# --- S1 multi-window (spec §11 redesign; shared, measure-only) --------------

def s1_window_starts(duration_s: float, window_s: float = S1_WINDOW_S,
                     max_windows: int = S1_MAX_WINDOWS) -> list[float]:
    """Evenly-spread window start times across the audio. Pure, and the
    ONLY place window placement is decided — the pipeline and the
    calibration harness must sample the same audio the same way."""
    if duration_s <= window_s:
        return [0.0]
    count = max(1, min(max_windows, int(duration_s // window_s)))
    if count == 1:
        return [0.0]
    span = duration_s - window_s
    return [round(i * span / (count - 1), 3) for i in range(count)]


def s1_language_windows(samples, sample_rate: int, detect, *,
                        expected: str = EXPECTED_LANGUAGE,
                        window_s: float = S1_WINDOW_S,
                        max_windows: int = S1_MAX_WINDOWS) -> dict:
    """The SHARED S1 implementation (the standing requirement: ONE
    function, or the calibration stops describing what the pipeline
    does). `detect` is caller-supplied — callable(window_samples) ->
    (language, probability) — because the pipeline and the harness hold
    different loaded models; everything that DECIDES (window placement,
    the expected-language fraction) lives here and only here.

    MEASURE-ONLY: the returned figures act on nothing. #70's prediction
    (spec §11): English in a minority of windows, where the single
    window said English at p=0.90. A window whose detection fails is
    recorded with language None and excluded from the fraction — an
    unmeasured window is not evidence either way.
    """
    duration_s = len(samples) / sample_rate if sample_rate > 0 else 0.0
    windows: list[dict] = []
    for start in s1_window_starts(duration_s, window_s, max_windows):
        lo = int(start * sample_rate)
        hi = min(len(samples), lo + int(window_s * sample_rate))
        language, probability = None, None
        try:
            language, probability = detect(samples[lo:hi])
        except Exception:  # noqa: BLE001 - a measurement must not raise
            logger.warning("S1 window at %.1fs: language detection failed", start)
        windows.append({
            "start_s": round(start, 1), "language": language,
            "probability": round(float(probability), 3)
            if probability is not None else None})
    detected = [w for w in windows if w["language"] is not None]
    fraction = (sum(1 for w in detected if w["language"] == expected)
                / len(detected)) if detected else None
    return {"windows": windows, "n_windows": len(windows),
            "n_detected": len(detected), "expected": expected,
            "expected_fraction": round(fraction, 3) if fraction is not None else None,
            "window_s": window_s}


def _window_rms(samples, sample_rate: int, window_s: float):
    """Per-window RMS over a 1-D float array. Pure numeric, no I/O."""
    import numpy as np

    size = max(1, int(round(window_s * sample_rate)))
    usable = (len(samples) // size) * size
    if usable == 0:
        return np.empty(0, dtype="float64")
    block = np.asarray(samples[:usable], dtype="float64").reshape(-1, size)
    return np.sqrt((block * block).mean(axis=1))


def _longest_run(mask) -> int:
    best = current = 0
    for value in mask:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def measure_trailing_speech(samples, sample_rate: int, turns: list[dict],
                            audio_duration_s: float, *,
                            excluded_spans_s: list[tuple[float, float]] | None = None,
                            window_s: float = TRAILING_WINDOW_S,
                            fraction: float = TRAILING_SPEECH_FRACTION,
                            reference_percentile: float = TRAILING_REFERENCE_PERCENTILE,
                            min_run_s: float = TRAILING_MIN_RUN_S) -> dict:
    """Is there SPEECH in the untranscribed trailing region?

    `samples` must be the ORIGINAL audio, not the muted derived copy — the muted
    copy is zero exactly where the system spoke, and consultation 445's failure
    was segments transcribed and then LOST downstream, which only the unmuted
    audio can still show.

    The threshold is a fraction of this recording's own transcribed-speech
    energy, so it self-calibrates to the room, the microphone and the gain. The
    verdict is the longest CONTINUOUS run above it, because energy is not speech
    and a transient is what an energy measure mistakes for a voice.

    Phase 7a speaking windows are dropped: our own voice is not missed patient
    speech, and counting it would refuse a good consultation.

    Returns every measured value, so the stored signals are the calibration data
    for these thresholds rather than a verdict nobody can re-derive — the same
    convention as the sound check's audit row.
    """
    import numpy as np

    out = {"measured": False, "has_speech": None, "window_s": window_s,
           "fraction": fraction, "reference_percentile": reference_percentile,
           "min_run_s": min_run_s}
    if samples is None or sample_rate <= 0 or len(samples) == 0:
        return {**out, "why_unmeasured": "no audio"}
    all_rms = _window_rms(samples, sample_rate, window_s)
    if all_rms.size == 0:
        return {**out, "why_unmeasured": "recording shorter than one window"}

    def _drop_excluded(mask):
        for start, end in (excluded_spans_s or []):
            lo = max(0, int(np.floor(float(start) / window_s)))
            hi = min(all_rms.size, int(np.ceil(float(end) / window_s)))
            if hi > lo:
                mask[lo:hi] = False
        return mask

    # The speech reference: windows inside a stored turn, minus our own voice.
    inside = np.zeros(all_rms.size, dtype=bool)
    for turn in turns or []:
        lo = max(0, int(float(turn.get("start", 0)) / window_s))
        hi = min(all_rms.size, int(np.ceil(float(turn.get("end", 0)) / window_s)))
        if hi > lo:
            inside[lo:hi] = True
    spoken = all_rms[_drop_excluded(inside)]
    if spoken.size == 0:
        # Nothing was transcribed, so there is no measured idea of what speech
        # sounds like here. Cannot decide on content; the caller falls back.
        return {**out, "why_unmeasured": "no transcribed audio to calibrate against"}
    reference = float(np.percentile(spoken, reference_percentile))
    threshold = reference * fraction

    first = max(0, int(round(_last_end(turns) / window_s)))
    trailing_mask = np.zeros(all_rms.size, dtype=bool)
    trailing_mask[first:] = True
    considered_mask = _drop_excluded(trailing_mask)
    considered = all_rms[considered_mask]
    if considered.size == 0:
        return {**out, "measured": True, "has_speech": False,
                "reference_rms": round(reference, 6),
                "threshold_rms": round(threshold, 6),
                "region_from_s": round(_last_end(turns), 2),
                "region_to_s": round(audio_duration_s, 2),
                "windows": 0, "longest_run_s": 0.0, "over_threshold_s": 0.0,
                "peak_rms": 0.0}

    over = considered >= threshold
    longest_run_s = _longest_run(over) * window_s
    return {
        "measured": True,
        "has_speech": bool(longest_run_s >= min_run_s),
        "reference_rms": round(reference, 6),
        "threshold_rms": round(threshold, 6),
        "peak_rms": round(float(considered.max()), 6),
        "mean_rms": round(float(considered.mean()), 6),
        "longest_run_s": round(longest_run_s, 2),
        "over_threshold_s": round(float(over.sum()) * window_s, 2),
        "windows": int(considered.size),
        "region_from_s": round(_last_end(turns), 2),
        "region_to_s": round(audio_duration_s, 2),
        "window_s": window_s, "fraction": fraction,
        "reference_percentile": reference_percentile, "min_run_s": min_run_s,
    }


def _last_end(turns: list[dict]) -> float:
    return max((float(t.get("end", 0)) for t in (turns or [])), default=0.0)


def s4_truncation_gap(turns: list[dict], audio_duration_s: float | None,
                      excluded_spans_s: list[tuple[float, float]] | None = None
                      ) -> float | None:
    """Seconds of audio after the last stored segment ends. None when the
    audio duration is unknown — never a fabricated zero.

    Note what this measures, because it is narrower than "silence": the
    **trailing** gap only. Muted spans in the middle of a recording do not
    touch it, because the last segment still ends where it ended.

    `excluded_spans_s` (Phase 7a) discounts audio the system was speaking
    over. Only the trailing region matters, and it matters in exactly one
    case: the system speaks last — the examination handover, say — and the
    recording ends. Zero-filling that span means the last transcribed
    segment now ends before it, so the gap would grow by the length of our
    own utterance and could manufacture an `unreliable_transcript` refusal
    on a perfectly good consultation. Discounting it is spec §2.4's
    requirement that the measurement be told about the exclusions.
    """
    if audio_duration_s is None or not turns:
        return None
    last_end = max(float(t.get("end", 0)) for t in turns)
    gap = max(0.0, float(audio_duration_s) - last_end)
    for start, end in (excluded_spans_s or []):
        overlap = min(float(end), float(audio_duration_s)) - max(float(start), last_end)
        if overlap > 0:
            gap -= overlap
    return max(0.0, gap)


def compute_signals(turns: list[dict], *, audio_duration_s: float | None = None,
                    detected_language: str | None = None,
                    language_probability: float | None = None,
                    excluded_spans_s: list[tuple[float, float]] | None = None,
                    trailing_speech: dict | None = None,
                    language_windows: dict | None = None) -> dict:
    """All four signals. Always computed, always stored (spec §3, §7).

    `excluded_spans_s` are the Phase 7a speaking windows in seconds. Only
    S4 consults them (see its docstring). S2 needs no adjustment: an
    excluded span produces no segments, so it contributes no confidence
    and no duration weight — it is absent from the mean rather than
    dragging it down.
    """
    return {
        "s1_language": {
            "detected": detected_language,
            "probability": language_probability,
            "expected": EXPECTED_LANGUAGE,
            # The §11 redesign's multi-window measurement (2026-07-31),
            # stored on every consultation so calibration data
            # accumulates for free. MEASURE-ONLY like the rest of S1.
            "multi_window": language_windows,
            "acts": False,   # see module docstring / spec §11
        },
        "s2_confidence": {
            "weighted_mean": s2_weighted_confidence(turns),
            "refuse_below": MIN_AVG_CONFIDENCE_REFUSE,
            "flag_below": MIN_AVG_CONFIDENCE_FLAG,
            "acts": True,
        },
        # S3 ACTS at the flag tier only (owner decision 2026-07-30): the
        # floored within-segment share flags above S3_WITHIN_FLAG. It
        # never refuses. The raw share and the run length stay reported.
        "s3_repetition": {**s3_repetition(turns),
                          "flag_above_floored": S3_WITHIN_FLAG,
                          "acts": True},
        # S4 measures the gap as before — it is useful context and it is the
        # fallback — but it DECIDES on `trailing_speech`. A duration cannot tell
        # missed speech from an empty room, which is the only reason a tolerance
        # ever existed.
        "s4_truncation": {
            "gap_s": s4_truncation_gap(turns, audio_duration_s, excluded_spans_s),
            "audio_duration_s": audio_duration_s,
            "excluded_s": round(sum(e - s for s, e in (excluded_spans_s or [])), 2),
            "refuse_above_s": TRUNCATION_REFUSE_S,
            "flag_above_s": TRUNCATION_FLAG_S,
            "trailing_speech": trailing_speech or {"measured": False,
                                                   "has_speech": None},
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

    Two tiers (spec §11): REFUSE (no draft, status unreliable_transcript)
    and FLAG (draft proceeds; approval blocked behind an acknowledged
    amber banner). A refusal is never also a flag — the flag tier only
    describes transcripts that survived refusal.
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

    # S4 decides on CONTENT, not duration (owner's rule, 2026-07-28): silence is
    # ignored however long it is, and untranscribed speech refuses however short
    # it is. The old tolerance cut both ways and the second way was the serious
    # one — 20 s of allowance meant up to twenty seconds of genuinely missed
    # speech at the END of a consultation passed silently, and the end is where
    # the plan lives. #70 lost its last 33 s.
    s4 = signals.get("s4_truncation", {})
    gap = s4.get("gap_s")
    trailing = s4.get("trailing_speech") or {}
    if trailing.get("measured"):
        if trailing.get("has_speech"):
            fired.append({
                "signal": "S4",
                "name": "untranscribed speech at the end of the recording",
                "value": trailing.get("longest_run_s"),
                "threshold": trailing.get("min_run_s"),
                "detail": (
                    f"{trailing.get('longest_run_s')}s of continuous speech-level "
                    f"audio in the {gap:.1f}s after the last transcribed segment "
                    f"({trailing.get('over_threshold_s')}s over threshold in "
                    f"total; peak RMS {trailing.get('peak_rms')} against a "
                    f"transcribed-speech reference of "
                    f"{trailing.get('reference_rms')}, threshold "
                    f"{trailing.get('threshold_rms')}) — this speech is missing "
                    f"from the transcript"),
            })
    elif gap is not None and gap > TRUNCATION_REFUSE_S:
        # FALLBACK, and only when the region could not be measured at all (no
        # audio on disk). Passing an unmeasurable gap silently would be the
        # weakening; keeping the previous behaviour here is not.
        fired.append({
            "signal": "S4",
            "name": "audio truncation (unmeasured)",
            "value": round(gap, 1),
            "threshold": TRUNCATION_REFUSE_S,
            "detail": (f"{gap:.1f}s of audio after the last transcribed segment "
                       f"could not be checked for speech; refusing above "
                       f"{TRUNCATION_REFUSE_S:.0f}s"),
        })

    # The FLAG tier (spec §11), evaluated only when nothing refused: a
    # refusal already blocks harder than a flag could, and stacking an
    # acknowledgement on top of "no note exists" would gate nothing.
    flags: list[dict] = []
    if not fired:
        if (confidence is not None
                and MIN_AVG_CONFIDENCE_REFUSE <= confidence < MIN_AVG_CONFIDENCE_FLAG):
            flags.append({
                "signal": "S2",
                "name": "marginal average confidence",
                "value": round(confidence, 3),
                "threshold": MIN_AVG_CONFIDENCE_FLAG,
                "detail": (f"duration-weighted mean ASR confidence "
                           f"{confidence:.3f} is below {MIN_AVG_CONFIDENCE_FLAG} "
                           f"(refusal starts at {MIN_AVG_CONFIDENCE_REFUSE})"),
            })
        if gap is not None and gap > TRUNCATION_FLAG_S:
            # The recorded §11 semantics: a sizeable untranscribed tail
            # that did NOT refuse — measured as non-speech, or
            # unmeasurable but under the 20 s fallback — is amber.
            measured = " (no speech detected in it)" if trailing.get("measured") \
                else " (its content could not be checked)"
            flags.append({
                "signal": "S4",
                "name": "long untranscribed tail",
                "value": round(gap, 1),
                "threshold": TRUNCATION_FLAG_S,
                "detail": (f"{gap:.1f}s of audio after the last transcribed "
                           f"segment{measured}; flagged above "
                           f"{TRUNCATION_FLAG_S:.0f}s"),
            })
        # S3, flag tier only (owner decision 2026-07-30, from the
        # measured corridor: #70 at 0.727 vs <= 0.333 everywhere else).
        s3 = signals.get("s3_repetition", {})
        floored = s3.get("max_within_segment_share_floored")
        if floored is not None and floored > S3_WITHIN_FLAG:
            flags.append({
                "signal": "S3",
                "name": "repetition loop inside a segment",
                "value": round(floored, 3),
                "threshold": S3_WITHIN_FLAG,
                "detail": (f"one repeated phrase accounts for {floored:.0%} of "
                           f"a segment of at least "
                           f"{s3.get('min_segment_tokens', S3_MIN_SEGMENT_TOKENS)} "
                           f"words (flagged above {S3_WITHIN_FLAG:.0%}) — the "
                           f"transcriber may have looped rather than "
                           f"transcribed"),
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
        return {"outcome": OUTCOME_PASS, "fired": [], "flags": [],
                "enabled": False, "would_have_fired": fired,
                "would_have_flagged": flags}

    outcome = (OUTCOME_REFUSED if fired
               else OUTCOME_FLAGGED if flags else OUTCOME_PASS)
    return {"outcome": outcome, "fired": fired, "flags": flags,
            "enabled": True}


def refusal_summary(fired: list[dict]) -> str:
    """One line for the banner and the audit detail."""
    if not fired:
        return ""
    return "; ".join(f["detail"] for f in fired)
