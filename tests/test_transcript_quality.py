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
    narrows, this test says so before a demo does."""
    worst_s2 = min(CALIBRATION[c]["s2"] for c in (66, 67, 68, 69))
    worst_s4 = max(CALIBRATION[c]["s4"] for c in (66, 67, 68, 69))
    assert worst_s2 - tq.MIN_AVG_CONFIDENCE_REFUSE >= 0.05, \
        "S2 margin below 0.05 — thinner than the calibration table suggested"
    assert tq.TRUNCATION_REFUSE_S - worst_s4 >= 5.0, \
        "S4 margin below 5 s — thinner than the calibration table suggested"


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


def test_flag_tier_is_not_implemented():
    """Guard against the flag tier arriving without its calibration."""
    source = tq.__doc__ or ""
    assert "flag tier" in source.lower()
    assert not hasattr(tq, "OUTCOME_FLAGGED")
    assert "MIN_AVG_CONFIDENCE_FLAG" not in dir(tq)


def test_flag_config_keys_exist_but_are_unused():
    from pathlib import Path
    env = (Path(__file__).parent.parent / ".env.example").read_text()
    assert "TRANSCRIPT_MIN_AVG_CONFIDENCE_FLAG=0.70" in env
    assert "TRANSCRIPT_TRUNCATION_FLAG_S=10" in env
    module = (Path(__file__).parent.parent / "app" / "transcript_quality.py").read_text()
    assert "TRANSCRIPT_MIN_AVG_CONFIDENCE_FLAG" not in module
    assert "TRANSCRIPT_TRUNCATION_FLAG_S" not in module


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
