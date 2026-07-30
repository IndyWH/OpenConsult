"""Finalisation transcript-quality gate — refuse tier.

Spec: `TRANSCRIPT_QUALITY_GATE_SPEC.md`, tests per its revised §8 (in §11).

The regression fixture is consultation #70: Sinhala audio through the
English-forced pipeline produced a fluent hallucinated English
translation and a normal-looking draft note, which was approved. Its
measured signals are asserted here as the incident, encoded.

**#70 must refuse on S2 and on S4 independently — and must NOT be
asserted to refuse on S1 or S3.** Under the current design it does not:
single-window language detection returns English at p=0.90, and S3's
cross-segment run length is 1. Encoding an S1/S3 expectation would hide
that finding, which is the whole reason the acting signals were swapped.
"""

from __future__ import annotations

import importlib

import pytest

from app import transcript_quality as tq

# Measured 2026-07-25 by scripts/calibrate_transcript_quality.py.
# evals/transcript_quality_calibration.json holds the full output.
CALIBRATION = {
    66: {"script": "01_chest_pain_en", "s2": 0.798, "s4": 0.1, "good": True},
    67: {"script": "02_febrile_child_en", "s2": 0.804, "s4": 1.3, "good": True},
    68: {"script": "03_diabetes_review_en", "s2": 0.810, "s4": 4.4, "good": True},
    69: {"script": "04_asthma_en", "s2": 0.785, "s4": 0.7, "good": True},
    70: {"script": "03_diabetes_review_si", "s2": 0.505, "s4": 33.3, "good": False},
}


def turn(idx, start, end, text, confidence):
    return {"idx": idx, "role": "Doctor", "start": start, "end": end,
            "text": text, "confidence": confidence}


def signals_for(s2: float | None, s4: float | None, *,
                language="en", probability=0.99, turns=None) -> dict:
    """Signals with S2 and S4 pinned to given values."""
    turns = turns if turns is not None else [
        turn(0, 0.0, 100.0, "some ordinary consultation speech here", s2 or 0.8)]
    computed = tq.compute_signals(
        turns, audio_duration_s=None, detected_language=language,
        language_probability=probability)
    computed["s2_confidence"]["weighted_mean"] = s2
    computed["s4_truncation"]["gap_s"] = s4
    return computed


# ------------------------------------------- the incident, encoded (§8/§11)

def test_consultation_70_refuses_on_s2_alone():
    """S2 independently. No co-occurrence rule to lean on."""
    verdict = tq.evaluate(signals_for(CALIBRATION[70]["s2"], s4=0.0))
    assert verdict["outcome"] == tq.OUTCOME_REFUSED
    assert [f["signal"] for f in verdict["fired"]] == ["S2"]


def test_consultation_70_refuses_on_s4_alone():
    """S4 independently."""
    verdict = tq.evaluate(signals_for(0.95, CALIBRATION[70]["s4"]))
    assert verdict["outcome"] == tq.OUTCOME_REFUSED
    assert [f["signal"] for f in verdict["fired"]] == ["S4"]


def test_consultation_70_refuses_on_its_real_measured_signals():
    verdict = tq.evaluate(signals_for(CALIBRATION[70]["s2"], CALIBRATION[70]["s4"]))
    assert verdict["outcome"] == tq.OUTCOME_REFUSED
    assert {f["signal"] for f in verdict["fired"]} == {"S2", "S4"}


def test_s1_and_s3_do_not_act():
    """#70's S1 is English at p=0.90 and its S3 run length is 1 — both
    would PASS. Asserting otherwise would hide the calibration finding
    that caused the acting signals to swap (spec §11)."""
    # Wrong language, at high confidence: still passes, because S1 is inert.
    verdict = tq.evaluate(signals_for(0.95, 0.0, language="si", probability=0.99))
    assert verdict["outcome"] == tq.OUTCOME_PASS

    # A blatant repetition loop: still passes, because S3 is inert.
    looped = [turn(0, 0.0, 60.0, " ".join(["the pain in the"] * 40), 0.95)]
    signals = tq.compute_signals(looped, audio_duration_s=60.0)
    assert signals["s3_repetition"]["max_ngram_share"] > 0.9
    assert tq.evaluate(signals)["outcome"] == tq.OUTCOME_PASS

    assert tq.compute_signals([])["s1_language"]["acts"] is False
    assert tq.compute_signals([])["s3_repetition"]["acts"] is False


@pytest.mark.parametrize("cid", [66, 67, 68, 69])
def test_good_recordings_pass_at_shipped_thresholds(cid):
    """All four known-good English recordings must pass. If one fails,
    the threshold is wrong and goes back to the owner (spec §8)."""
    row = CALIBRATION[cid]
    verdict = tq.evaluate(signals_for(row["s2"], row["s4"]))
    assert verdict["outcome"] == tq.OUTCOME_PASS, \
        f"#{cid} ({row['script']}) would be refused at the shipped thresholds"
    assert verdict["fired"] == []


def test_shipped_thresholds_are_the_owner_set_values():
    assert tq.MIN_AVG_CONFIDENCE_REFUSE == 0.60
    assert tq.TRUNCATION_REFUSE_S == 20


def test_margins_between_good_recordings_and_the_thresholds():
    """Records the actual headroom. The worst good recording is 0.185
    above the S2 threshold and 15.6 s below the S4 one — if either
    narrows, this test says so before a demo does.

    The S4 line now guards the FALLBACK tolerance only; S4's real decision is
    the content check below.
    """
    worst_s2 = min(CALIBRATION[c]["s2"] for c in (66, 67, 68, 69))
    worst_s4 = max(CALIBRATION[c]["s4"] for c in (66, 67, 68, 69))
    assert worst_s2 - tq.MIN_AVG_CONFIDENCE_REFUSE >= 0.05, \
        "S2 margin below 0.05 — thinner than the calibration table suggested"
    assert tq.TRUNCATION_REFUSE_S - worst_s4 >= 5.0, \
        "S4 margin below 5 s — thinner than the calibration table suggested"


# ------------------------- S4 decides on CONTENT, not duration (2026-07-28)
#
# The owner's rule, which SUPERSEDES the tolerance rather than tuning it:
# silence is ignored however long it is, and speech that was not transcribed
# refuses however short it is.
#
# A duration cannot tell missed speech from an empty room, and that is the only
# reason a tolerance ever existed — it was slack for the imprecision of a proxy.
# It cut both ways, and the second way was the serious one: 20 s of allowance
# meant up to twenty seconds of genuinely missed speech at the END of a
# consultation passed silently, and the end is where the plan lives. #70 lost
# its last 33 s.
#
# 449 is the case that forced this: refused on 307.8 s of trailing audio that
# was silent because the doctor was reading a checklist. Arithmetically correct,
# clinically wrong.

def _tone(seconds, amplitude, sample_rate=16000):
    """Speech-like energy: a loud-ish band-limited wobble, not pure silence."""
    import numpy as np

    t = np.arange(int(seconds * sample_rate)) / sample_rate
    return (amplitude * np.sin(2 * np.pi * 180 * t)
            * (1 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype("float32")


def _quiet(seconds, amplitude=0.001, sample_rate=16000):
    import numpy as np

    rng = np.random.default_rng(42)
    return (rng.normal(0, amplitude, int(seconds * sample_rate))).astype("float32")


def test_s4_ignores_a_long_silence_however_long_it_is():
    """449's shape. 300 s of quiet room after the last transcribed word must
    NOT refuse — the old tolerance refused it at 15x over.

    AMENDED for the flag tier (2026-07-31): the owner's rule — silence is
    ignored however long it is — is a rule about REFUSAL, and it still
    holds: nothing fires, the note is drafted. The §11 flag tier now
    additionally marks a >10 s untranscribed tail amber for the doctor's
    attention; a 300 s one certainly qualifies. Flagged, never refused."""
    import numpy as np

    audio = np.concatenate([_tone(30, 0.2), _quiet(300)])
    turns = [turn(0, 0.0, 30.0, "the transcribed part", 0.8)]
    trailing = tq.measure_trailing_speech(audio, 16000, turns, len(audio) / 16000)
    assert trailing["measured"] is True
    assert trailing["has_speech"] is False
    signals = tq.compute_signals(turns, audio_duration_s=len(audio) / 16000,
                                 trailing_speech=trailing)
    assert signals["s4_truncation"]["gap_s"] == pytest.approx(300.0, abs=0.5)
    verdict = tq.evaluate(signals)
    assert verdict["fired"] == [], (
        "a silent trailing region must not refuse, whatever its length")
    assert verdict["outcome"] == tq.OUTCOME_FLAGGED
    assert verdict["flags"][0]["signal"] == "S4"


def test_s4_refuses_short_untranscribed_speech():
    """THE BLIND SPOT BEING CLOSED, and the point of the change rather than a
    bonus: 10 s of real speech at the end passed under the 20 s tolerance."""
    import numpy as np

    audio = np.concatenate([_tone(30, 0.2), _quiet(5), _tone(10, 0.2)])
    turns = [turn(0, 0.0, 30.0, "the transcribed part", 0.8)]
    duration = len(audio) / 16000
    trailing = tq.measure_trailing_speech(audio, 16000, turns, duration)
    assert trailing["has_speech"] is True
    signals = tq.compute_signals(turns, audio_duration_s=duration,
                                 trailing_speech=trailing)
    gap = signals["s4_truncation"]["gap_s"]
    assert gap < tq.TRUNCATION_REFUSE_S, (
        "this case must be BELOW the old tolerance, or it proves nothing")
    assert tq.evaluate(signals)["outcome"] == tq.OUTCOME_REFUSED


def test_s4_decides_on_a_continuous_run_not_a_total():
    """Energy is not speech. A cough, a chair or a page turn is exactly the
    broadband transient an energy measure mistakes for a voice, so the verdict
    is the longest CONTINUOUS run. This is the residual allowance, and it is an
    allowance for the DETECTOR's noise rather than a length of audio we are
    willing to ignore."""
    import numpy as np

    # Six isolated 0.25 s transients: 1.5 s of energy in total, no run.
    parts = [_tone(30, 0.2)]
    for _ in range(6):
        parts += [_quiet(4), _tone(0.25, 0.2)]
    audio = np.concatenate(parts)
    turns = [turn(0, 0.0, 30.0, "the transcribed part", 0.8)]
    trailing = tq.measure_trailing_speech(audio, 16000, turns, len(audio) / 16000)
    assert trailing["over_threshold_s"] > 0, "the transients must be detected"
    assert trailing["longest_run_s"] < tq.TRAILING_MIN_RUN_S
    assert trailing["has_speech"] is False


def test_s4_never_counts_the_systems_own_voice_as_missed_speech():
    """Phase 7a: a spoken handover at the end is OUR voice in the original
    audio. Counting it would refuse a perfectly good consultation."""
    import numpy as np

    audio = np.concatenate([_tone(30, 0.2), _tone(8, 0.2)])
    turns = [turn(0, 0.0, 30.0, "the transcribed part", 0.8)]
    duration = len(audio) / 16000
    without = tq.measure_trailing_speech(audio, 16000, turns, duration)
    assert without["has_speech"] is True          # it is speech-level energy
    with_span = tq.measure_trailing_speech(audio, 16000, turns, duration,
                                           excluded_spans_s=[(30.0, 38.0)])
    assert with_span["has_speech"] is False       # ...but it was us


def test_s4_falls_back_to_the_duration_tolerance_only_when_unmeasurable():
    """No audio on disk (retention sweep) means no content check is possible.
    Passing an unmeasurable gap silently would be the weakening; keeping the
    previous behaviour there is not."""
    unmeasured = tq.measure_trailing_speech(None, 16000, [], 0.0)
    assert unmeasured["measured"] is False
    signals = tq.compute_signals([turn(0, 0.0, 417.0, "final words", 0.8)],
                                 audio_duration_s=450.0,
                                 trailing_speech=unmeasured)
    verdict = tq.evaluate(signals)
    assert verdict["outcome"] == tq.OUTCOME_REFUSED
    assert verdict["fired"][0]["name"] == "audio truncation (unmeasured)"
    # And a short unmeasurable gap still passes, exactly as before.
    short = tq.compute_signals([turn(0, 0.0, 447.0, "final words", 0.8)],
                               audio_duration_s=450.0, trailing_speech=unmeasured)
    assert tq.evaluate(short)["outcome"] == tq.OUTCOME_PASS


def test_s4_cannot_calibrate_without_transcribed_audio():
    """With nothing transcribed there is no measured idea of what speech sounds
    like in this room, so the content check must decline rather than guess."""
    trailing = tq.measure_trailing_speech(_quiet(60), 16000, [], 60.0)
    assert trailing["measured"] is False
    assert "no transcribed audio" in trailing["why_unmeasured"]


def test_the_speech_threshold_is_relative_to_this_recordings_own_speech():
    """A noise-floor multiple was tried and MEASURED WRONG: 449's five silent
    minutes drag a whole-recording low percentile below the level the 445 filler
    assessment measured for genuine silence, so the quieter the room the more
    sensitive the detector became. The reference is the transcribed speech."""
    import numpy as np

    loud = np.concatenate([_tone(30, 0.4), _quiet(60)])
    soft = np.concatenate([_tone(30, 0.05), _quiet(60)])
    turns = [turn(0, 0.0, 30.0, "the transcribed part", 0.8)]
    a = tq.measure_trailing_speech(loud, 16000, turns, len(loud) / 16000)
    b = tq.measure_trailing_speech(soft, 16000, turns, len(soft) / 16000)
    assert a["threshold_rms"] > b["threshold_rms"], (
        "the threshold must scale with the room's own speech level")
    assert a["has_speech"] is False and b["has_speech"] is False


def test_every_measured_value_is_stored_for_recalibration():
    """Same convention as the sound check: the stored signals must let the
    threshold be set from real data rather than re-guessed."""
    import numpy as np

    audio = np.concatenate([_tone(30, 0.2), _quiet(30)])
    turns = [turn(0, 0.0, 30.0, "the transcribed part", 0.8)]
    trailing = tq.measure_trailing_speech(audio, 16000, turns, len(audio) / 16000)
    for key in ("reference_rms", "threshold_rms", "peak_rms", "mean_rms",
                "longest_run_s", "over_threshold_s", "windows", "region_from_s",
                "region_to_s", "window_s", "fraction", "reference_percentile",
                "min_run_s"):
        assert key in trailing, f"{key} must be recorded for recalibration"
    stored = tq.compute_signals(turns, audio_duration_s=len(audio) / 16000,
                                trailing_speech=trailing)
    assert stored["s4_truncation"]["trailing_speech"] is trailing


def test_s4_does_not_re_run_the_vad_it_is_auditing():
    """The trap, asserted so it is not walked into later: the VAD deciding there
    was no speech is frequently what CREATED the gap, so re-running it would
    make the gate agree with itself and become decorative. The check has to be
    independent of the thing it audits."""
    from pathlib import Path

    source = Path("app/transcript_quality.py").read_text()
    code = "\n".join(line for line in source.splitlines()
                     if not line.lstrip().startswith("#"))
    for banned in ("silero", "vad", "load_vad", "whisperx"):
        assert banned not in code.lower(), (
            f"S4's content check must not use {banned} — it would be auditing "
            "the component that produced the gap")


# ------------------------------------------------------------ signal units

def test_s2_is_duration_weighted():
    turns = [turn(0, 0.0, 90.0, "long garbled stretch", 0.30),
             turn(1, 90.0, 92.0, "short clean bit", 1.00)]
    assert tq.s2_weighted_confidence(turns) == pytest.approx((0.30 * 90 + 2) / 92)
    assert tq.s2_weighted_confidence([]) is None


def test_s4_gap_and_absence():
    turns = [turn(0, 0.0, 417.0, "final words", 0.8)]
    assert tq.s4_truncation_gap(turns, 450.0) == pytest.approx(33.0)
    assert tq.s4_truncation_gap(turns, None) is None   # unknown, not zero
    assert tq.s4_truncation_gap(turns, 400.0) == 0.0   # never negative


def test_s3_measures_both_axes():
    looped = [turn(0, 0, 10, "the pain in the the pain in the the pain in the", 0.9)]
    result = tq.s3_repetition(looped)
    assert result["max_ngram_share"] > 0.5
    assert result["max_consecutive_identical"] == 1
    repeated = [turn(i, i, i + 1, "same text", 0.9) for i in range(3)]
    assert tq.s3_repetition(repeated)["max_consecutive_identical"] == 3


def test_unmeasurable_signals_never_refuse():
    """A signal that could not be measured is not evidence of a bad
    transcript — absence must not be treated as failure."""
    verdict = tq.evaluate(signals_for(None, None))
    assert verdict["outcome"] == tq.OUTCOME_PASS


def test_all_four_signals_are_always_computed():
    """Spec §3/§7: stored on every consultation, fired or not — that is
    how the S1/S3 redesign gets its calibration data for free."""
    signals = tq.compute_signals(
        [turn(0, 0.0, 10.0, "hello there doctor", 0.9)],
        audio_duration_s=12.0, detected_language="en", language_probability=0.98)
    assert set(signals) == {"s1_language", "s2_confidence", "s3_repetition",
                            "s4_truncation", "segments"}
    assert signals["s1_language"]["detected"] == "en"
    assert signals["s2_confidence"]["weighted_mean"] == pytest.approx(0.9)
    assert signals["s4_truncation"]["gap_s"] == pytest.approx(2.0)
    assert signals["segments"] == 1


# ----------------------------------------------------------- the kill switch

def test_gate_disabled_reproduces_todays_behaviour(monkeypatch):
    """TRANSCRIPT_GATE_ENABLED=false must pass everything through."""
    monkeypatch.setenv("TRANSCRIPT_GATE_ENABLED", "false")
    reloaded = importlib.reload(tq)
    try:
        verdict = reloaded.evaluate(signals_for(0.10, 300.0))  # egregious
        assert verdict["outcome"] == reloaded.OUTCOME_PASS
        assert verdict["enabled"] is False
        # It still says what it WOULD have done — silence would be worse.
        assert {f["signal"] for f in verdict["would_have_fired"]} == {"S2", "S4"}
    finally:
        monkeypatch.delenv("TRANSCRIPT_GATE_ENABLED")
        importlib.reload(tq)


def test_disabled_gate_logs_loudly(monkeypatch, caplog):
    monkeypatch.setenv("TRANSCRIPT_GATE_ENABLED", "false")
    reloaded = importlib.reload(tq)
    try:
        with caplog.at_level("WARNING"):
            reloaded.evaluate(signals_for(0.10, 300.0))
        assert any("TRANSCRIPT_GATE_ENABLED=false" in r.message for r in caplog.records)
    finally:
        monkeypatch.delenv("TRANSCRIPT_GATE_ENABLED")
        importlib.reload(tq)


# --------------------------------------------------- pipeline wiring (static)

def test_gate_runs_before_the_note_call():
    """A refusal must cost no MedGemma time (spec §3). Asserted on source
    order: the gate and its early return precede draft_note."""
    from pathlib import Path
    source = (Path(__file__).parent.parent / "app" / "finalize.py").read_text()
    gate = source.index("transcript_quality.evaluate")
    early_return = source.index("STATUS_UNRELIABLE")
    note_call = source.index("await draft_note(")
    assert gate < early_return < note_call


def test_refusal_status_is_not_failed():
    """The pipeline worked; the audio did not. A refused consultation must
    not read as a crash (spec §7)."""
    assert tq.STATUS_UNRELIABLE == "unreliable_transcript"
    assert tq.STATUS_UNRELIABLE != "failed"


def test_signals_are_stored_whether_or_not_anything_fires():
    from pathlib import Path
    source = (Path(__file__).parent.parent / "app" / "finalize.py").read_text()
    save = source.index("consultations.save_quality")
    refusal_branch = source.index("if verdict[\"outcome\"] ==")
    assert save < refusal_branch, "signals must be saved before the refusal branch"


def test_flag_tier_uses_the_recorded_thresholds_not_invented_ones():
    """AMENDED 2026-07-31: this used to guard against the flag tier
    arriving without its calibration. The tier has now arrived — built to
    §11's owner-set 2026-07-25 numbers, which is exactly the arrival the
    guard was protecting: wired, not invented. The guard's new job is
    that the wired values ARE the recorded ones."""
    assert tq.OUTCOME_FLAGGED == "flagged"
    assert tq.MIN_AVG_CONFIDENCE_FLAG == 0.70
    assert tq.TRUNCATION_FLAG_S == 10.0
    from pathlib import Path
    env = (Path(__file__).parent.parent / ".env.example").read_text()
    assert "TRANSCRIPT_MIN_AVG_CONFIDENCE_FLAG=0.70" in env
    assert "TRANSCRIPT_TRUNCATION_FLAG_S=10" in env


def _db_ready() -> bool:
    import os

    import psycopg
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")
def test_approve_409s_on_a_refused_consultation():
    """There is no note to approve, and there must not be one."""
    import asyncio
    import secrets

    from fastapi.testclient import TestClient

    from app import auth, consultations
    from app.main import app

    auth.ensure_schema()
    consultations.ensure_schema()
    doctor = asyncio.run(auth.create_user(
        f"doctor_{secrets.token_hex(4)}", "test-password-123", "Doc", "doctor"))

    async def build() -> int:
        cid = await consultations.create_consultation(doctor_id=doctor["id"])
        await consultations.save_turns(cid, [
            {"role": "Doctor", "start": 0.0, "end": 100.0,
             "text": "garbled", "confidence": 0.4}])
        signals = tq.compute_signals(
            await consultations.get_turns(cid), audio_duration_s=140.0)
        verdict = tq.evaluate(signals)
        assert verdict["outcome"] == tq.OUTCOME_REFUSED
        await consultations.save_quality(cid, signals, verdict["outcome"])
        await consultations.set_status(cid, tq.STATUS_UNRELIABLE)
        return cid

    cid = asyncio.run(build())
    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(doctor["id"]))

    response = client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert response.status_code == 409
    assert "quality gate" in response.json()["error"]

    # No note exists at all, and the state carries the verdict.
    assert asyncio.run(consultations.latest_note(cid)) is None
    state = client.get(f"/api/consultations/{cid}").json()
    assert state["status"] == "unreliable_transcript"
    assert state["quality_outcome"] == "refused"
    assert state["quality_signals"]["s2_confidence"]["weighted_mean"] < 0.60


def test_review_page_shows_a_red_banner_and_hides_approve():
    from pathlib import Path
    page = (Path(__file__).parent.parent / "app" / "static" / "review.html").read_text()
    assert "qualityBanner" in page
    assert "renderQualityBanner" in page
    # Reuses the urgency treatment — no new colour semantics (spec §7).
    assert 'id="qualityBanner"' in page and 'class="urgency"' in page
    assert "state.quality_outcome === 'refused'" in page


# --- S1 multi-window + S3 within-segment (spec §11 redesigns, 2026-07-31) ---
#
# MEASURE-ONLY, and the tests enforce it: neither signal may refuse, flag
# or banner anything in this build. Acting waits on the re-calibration and
# the owner's thresholds.

def test_s1_windows_are_spread_evenly_and_capped():
    assert tq.s1_window_starts(20.0) == [0.0]
    assert tq.s1_window_starts(45.0) == [0.0]
    assert tq.s1_window_starts(90.0) == [0.0, 30.0, 60.0]
    starts = tq.s1_window_starts(300.0)
    assert len(starts) == 10
    assert starts[0] == 0.0 and starts[-1] == 270.0
    # A very long recording still gets at most max_windows.
    assert len(tq.s1_window_starts(4000.0)) == tq.S1_MAX_WINDOWS


def test_s1_fraction_is_over_detected_windows_only():
    """#70's shape: an English-looking opening, non-English elsewhere.
    The fraction is what separates it — and a window whose detection
    FAILS is excluded, never counted as evidence either way."""
    import numpy as np

    samples = np.zeros(16000 * 90, dtype="float32")   # 90 s -> 3 windows
    answers = iter([("en", 0.9), ("si", 0.8), RuntimeError("no cuda")])

    def detect(window):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    result = tq.s1_language_windows(samples, 16000, detect)
    assert result["n_windows"] == 3 and result["n_detected"] == 2
    assert result["expected_fraction"] == 0.5
    assert result["windows"][2]["language"] is None


def test_s1_with_no_detected_windows_reports_none_not_zero():
    import numpy as np

    def detect(window):
        raise RuntimeError("model unavailable")

    result = tq.s1_language_windows(np.zeros(16000 * 40, dtype="float32"),
                                    16000, detect)
    assert result["expected_fraction"] is None


def test_s3_within_segment_catches_what_the_whole_transcript_dilutes():
    """The calibration's finding: #70's loops live INSIDE segments, where
    the whole-transcript share dilutes them and the cross-segment run
    stays 1. The within-segment maximum is the axis that separates."""
    loop = "thank you " * 12
    turns = [turn(0, 0.0, 30.0, "a perfectly ordinary clinical sentence about "
                                "chest pain and breathlessness today", 0.8),
             turn(1, 30.0, 40.0, loop, 0.8),
             turn(2, 40.0, 60.0, "another ordinary closing sentence with no "
                                 "repetition in it at all thanks", 0.8)]
    s3 = tq.s3_repetition(turns)
    assert s3["max_consecutive_identical"] == 1, "the dead axis stays dead"
    assert s3["max_within_segment_share"] > s3["max_ngram_share"], (
        "the within-segment maximum must not be diluted by the rest")
    assert s3["max_within_segment_share"] > 0.5
    assert s3["max_within_segment_idx"] == 1
    # The loop turn is 24 tokens, so the floored variant sees it too.
    assert s3["max_within_segment_share_floored"] > 0.5


def test_s3_floored_variant_ignores_short_saturating_segments():
    """The re-calibration's finding: a segment of a few tokens saturates
    the raw within-share at 1.0 on perfectly healthy speech ("thank you
    thank you" as a parting). The floored variant only consults segments
    of >= S3_MIN_SEGMENT_TOKENS, which is where #70's genuine loops live
    (0.727 there, vs <= 0.333 for everything healthy). Measure-only."""
    turns = [turn(0, 0.0, 5.0, "thank you thank you", 0.9),   # 4 tokens
             turn(1, 5.0, 60.0, "a perfectly ordinary consultation sentence "
                                "with plenty of distinct words in it and no "
                                "repetition anywhere at all today", 0.9)]
    s3 = tq.s3_repetition(turns)
    assert s3["max_within_segment_share"] == 1.0, "the raw variant saturates"
    assert s3["max_within_segment_share_floored"] < 0.3, (
        "the floored variant must not be moved by a 4-token segment")
    assert s3["min_segment_tokens"] == tq.S3_MIN_SEGMENT_TOKENS


def test_s1_and_s3_still_act_on_nothing():
    """The HARD CONSTRAINT of the redesign session: terrible S1 and S3
    values with healthy S2/S4 produce a clean pass — no refusal, no flag.
    Acting waits on the owner's thresholds."""
    turns = [turn(0, 0.0, 100.0, "thank you " * 50, 0.9)]
    signals = tq.compute_signals(
        turns, audio_duration_s=100.0,
        trailing_speech={"measured": True, "has_speech": False},
        language_windows={"windows": [], "n_windows": 10, "n_detected": 10,
                          "expected": "en", "expected_fraction": 0.1,
                          "window_s": 30.0})
    assert signals["s1_language"]["multi_window"]["expected_fraction"] == 0.1
    assert signals["s1_language"]["acts"] is False
    assert signals["s3_repetition"]["acts"] is False
    assert signals["s3_repetition"]["max_within_segment_share"] > 0.9
    verdict = tq.evaluate(signals)
    assert verdict["outcome"] == tq.OUTCOME_PASS
    assert verdict["fired"] == [] and verdict["flags"] == []


def test_the_last_two_path_signal_is_collapsed():
    """S1's two code paths — finalize.py and the calibration harness —
    must both go through the ONE shared implementation, or the
    calibration stops describing what the pipeline does. S3 likewise."""
    from pathlib import Path
    finalize_src = (Path(__file__).parent.parent / "app" / "finalize.py").read_text()
    harness_src = (Path(__file__).parent.parent / "scripts"
                   / "calibrate_transcript_quality.py").read_text()
    assert "transcript_quality.s1_language_windows" in finalize_src
    assert "s1_language_windows" in harness_src
    assert "s3_repetition" in harness_src
