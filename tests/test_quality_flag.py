"""The transcript-quality gate's FLAG tier (spec §11, built 2026-07-31).

A flagged transcript is the amber middle: the draft note proceeds, and
approval waits on an explicit, audited acknowledgement — the urgency
banner's pattern exactly. The thresholds are the owner's 2026-07-25
numbers (S2 < 0.70, S4 > 10 s), wired here, invented nowhere.

The decision tests drive the REAL compute_signals -> evaluate path; the
endpoint tests drive the REAL approve gate. The client-side rule — that
refreshApproveGate stays the SINGLE writer of Approve's disabled state —
is asserted structurally, because three renderers each setting the flag
is how a gate quietly stops gating.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from pathlib import Path

import psycopg
import pytest
from conftest import approve_account
from fastapi.testclient import TestClient

from app import auth, consultations, transcript_quality as tq


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


# --- the decision (pure) ----------------------------------------------------

def _signals(confidence: float, *, gap_s: float = 0.0,
             trailing: dict | None = None) -> dict:
    # Distinct words, deliberately: repeated filler would trip the S3
    # flag (live since 2026-07-30) and muddy every S2/S4 assertion here.
    turns = [{"start": 0.0, "end": 100.0,
              "text": " ".join(f"word{i}" for i in range(50)),
              "confidence": confidence}]
    return tq.compute_signals(
        turns, audio_duration_s=100.0 + gap_s,
        trailing_speech=trailing if trailing is not None
        else {"measured": True, "has_speech": False})


def test_marginal_confidence_flags_and_does_not_refuse():
    verdict = tq.evaluate(_signals(0.65))
    assert verdict["outcome"] == tq.OUTCOME_FLAGGED
    assert verdict["fired"] == []
    assert verdict["flags"][0]["signal"] == "S2"
    assert "0.650" in verdict["flags"][0]["detail"]


def test_low_confidence_refuses_and_is_never_also_flagged():
    """A refusal is never also a flag — the flag tier only describes
    transcripts that survived refusal."""
    verdict = tq.evaluate(_signals(0.55))
    assert verdict["outcome"] == tq.OUTCOME_REFUSED
    assert verdict["flags"] == []


def test_the_recorded_boundaries_are_exact():
    """0.70 exactly passes (flag is strictly below); 0.60 exactly flags
    rather than refuses (refusal is strictly below) — the §11 table's
    wording, encoded."""
    assert tq.evaluate(_signals(0.70))["outcome"] == tq.OUTCOME_PASS
    at_refuse = tq.evaluate(_signals(0.60))
    assert at_refuse["outcome"] == tq.OUTCOME_FLAGGED
    assert at_refuse["fired"] == []


def test_a_long_silent_tail_flags_where_content_refusal_does_not_apply():
    """The recorded S4 semantics: a >10 s untranscribed tail whose content
    measured as NON-speech is amber — worth a human eye, not a refusal
    (silence is ignored for refusal, however long)."""
    verdict = tq.evaluate(_signals(0.80, gap_s=15.0,
                                   trailing={"measured": True,
                                             "has_speech": False}))
    assert verdict["outcome"] == tq.OUTCOME_FLAGGED
    assert verdict["flags"][0]["signal"] == "S4"
    assert "no speech detected" in verdict["flags"][0]["detail"]


def test_measured_missing_speech_still_refuses_never_downgrades_to_flag():
    verdict = tq.evaluate(_signals(0.80, gap_s=15.0,
                                   trailing={"measured": True,
                                             "has_speech": True,
                                             "longest_run_s": 5.0,
                                             "min_run_s": 3.0,
                                             "over_threshold_s": 6.0,
                                             "peak_rms": 0.1,
                                             "reference_rms": 0.1,
                                             "threshold_rms": 0.05}))
    assert verdict["outcome"] == tq.OUTCOME_REFUSED
    assert verdict["flags"] == []


def test_an_unmeasurable_mid_size_tail_flags_and_a_huge_one_refuses():
    """The fallback ladder when the audio cannot be checked: >20 s refuses
    (the pre-existing fallback), 10–20 s now flags, under 10 s passes."""
    unmeasured = {"measured": False, "has_speech": None}
    assert tq.evaluate(_signals(0.80, gap_s=25.0, trailing=unmeasured)
                       )["outcome"] == tq.OUTCOME_REFUSED
    mid = tq.evaluate(_signals(0.80, gap_s=15.0, trailing=unmeasured))
    assert mid["outcome"] == tq.OUTCOME_FLAGGED
    assert "could not be checked" in mid["flags"][0]["detail"]
    assert tq.evaluate(_signals(0.80, gap_s=8.0, trailing=unmeasured)
                       )["outcome"] == tq.OUTCOME_PASS


def test_the_four_good_recordings_do_not_flag():
    """The calibration's good four sit at S2 0.785–0.810 with gaps
    0.1–4.4 s: none may flag under the wired thresholds, or the tier
    would nag on every healthy consultation."""
    for s2, gap in ((0.798, 0.1), (0.804, 1.3), (0.810, 4.4), (0.785, 0.7)):
        verdict = tq.evaluate(_signals(s2, gap_s=gap))
        assert verdict["outcome"] == tq.OUTCOME_PASS, (s2, gap)


def test_disabled_gate_reports_would_have_flagged_and_passes():
    signals = _signals(0.65)
    real = tq.GATE_ENABLED
    try:
        tq.GATE_ENABLED = False
        verdict = tq.evaluate(signals)
    finally:
        tq.GATE_ENABLED = real
    assert verdict["outcome"] == tq.OUTCOME_PASS
    assert verdict["would_have_flagged"][0]["signal"] == "S2"


def test_signals_carry_the_flag_thresholds_for_the_banner():
    signals = _signals(0.80)
    assert signals["s2_confidence"]["flag_below"] == tq.MIN_AVG_CONFIDENCE_FLAG
    assert signals["s4_truncation"]["flag_above_s"] == tq.TRUNCATION_FLAG_S
    assert signals["s3_repetition"]["flag_above_floored"] == tq.S3_WITHIN_FLAG


# --- S3 joins the flag tier (owner decision 2026-07-30) ---------------------

def _with_floored_s3(value: float) -> dict:
    """Healthy S2/S4, with the floored S3 share pinned to a measured
    value — the signals_for convention, applied to S3."""
    signals = _signals(0.80)
    signals["s3_repetition"]["max_within_segment_share_floored"] = value
    return signals


def test_70s_stored_floored_share_flags_at_the_owners_threshold():
    """#70's re-calibrated number, 0.727, against the owner's 0.5: flags
    through the same amber path, never refuses. (In reality #70 refuses
    on S2 and S4 first — this isolates the S3 tier with those healthy.)"""
    verdict = tq.evaluate(_with_floored_s3(0.727))
    assert verdict["outcome"] == tq.OUTCOME_FLAGGED
    assert verdict["fired"] == []
    assert [f["signal"] for f in verdict["flags"]] == ["S3"]
    assert verdict["flags"][0]["value"] == 0.727
    assert "looped" in verdict["flags"][0]["detail"]


def test_the_four_good_recordings_floored_shares_do_not_flag():
    """The re-calibration's measured values for 66-69 at the >=12-token
    floor: 0.286 / 0.333 / 0.267 / 0.333 — all clear of 0.5 with the
    corridor the owner decided on."""
    for value in (0.286, 0.333, 0.267, 0.333):
        verdict = tq.evaluate(_with_floored_s3(value))
        assert verdict["outcome"] == tq.OUTCOME_PASS, value


def test_s3_flag_threshold_is_the_owners_recorded_value():
    assert tq.S3_WITHIN_FLAG == 0.5
    assert "TRANSCRIPT_S3_WITHIN_FLAG=0.5" in Path(".env.example").read_text()


def test_the_s3_reason_reaches_the_banner_and_only_the_single_writer_gates():
    """The banner lists the S3 reason; the Approve gate is untouched —
    the generic flagged reason already joins through refreshApproveGate,
    the single writer, and nothing new writes the button."""
    banner = REVIEW[REVIEW.index("function renderQualityFlagBanner"):
                    REVIEW.index("function renderUrgentBanner")]
    assert "max_within_segment_share_floored" in banner
    assert "flag_above_floored" in banner
    assert REVIEW.count("approveBtn.disabled =") == 1


# --- the approve gate and the acknowledgement (endpoints) -------------------

def _doctor_client() -> TestClient:
    auth.ensure_schema()
    from app.main import app
    client = TestClient(app)
    username = f"doc_{secrets.token_hex(4)}"
    assert client.post("/api/register", json={
        "username": username, "password": "test-password-123",
        "display_name": "Doc", "role": "doctor"}).status_code == 200
    approve_account(username)
    assert client.post("/api/login", json={
        "username": username, "password": "test-password-123"}).status_code == 200
    return client


@pytest.fixture()
def flagged_consultation():
    consultations.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(cid, [
            {"role": "Doctor", "start": 0.0, "end": 4.0,
             "text": "Any chest pain?", "confidence": 0.65},
            {"role": "Patient", "start": 4.0, "end": 9.0,
             "text": "Sometimes when I climb stairs.", "confidence": 0.65}])
        await consultations.save_note(cid, {
            "subjective": [{"text": "Exertional chest pain", "turns": [1],
                            "uncited": False, "flagged": False}],
            "objective": [], "assessment": [], "plan": []})
        signals = _signals(0.65)
        verdict = tq.evaluate(signals)
        assert verdict["outcome"] == tq.OUTCOME_FLAGGED
        await consultations.save_quality(cid, signals, verdict["outcome"])
        await consultations.set_status(cid, "awaiting_review")
        return cid

    return asyncio.run(build())


@needs_db
def test_flagged_approval_is_blocked_until_acknowledged(flagged_consultation):
    cid = flagged_consultation
    client = _doctor_client()

    state = client.get(f"/api/consultations/{cid}").json()
    assert state["quality_outcome"] == "flagged"
    assert state["quality_ack_at"] is None
    plain = state["plain_text"]

    blocked = client.post(f"/api/consultations/{cid}/approve",
                          json={"text": plain})
    assert blocked.status_code == 409
    assert "flagged" in blocked.json()["error"]

    acked = client.post(f"/api/consultations/{cid}/acknowledge-quality")
    assert acked.status_code == 200 and acked.json()["acknowledged_at"]

    approved = client.post(f"/api/consultations/{cid}/approve",
                           json={"text": plain})
    assert approved.status_code == 200

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        actions = [r[0] for r in conn.execute(
            "SELECT action FROM audit_event WHERE subject_id = %s"
            " AND action IN ('quality.acknowledged', 'note.approved')"
            " ORDER BY id", (cid,))]
    assert actions == ["quality.acknowledged", "note.approved"]


@needs_db
def test_acknowledgement_is_idempotent_first_timestamp_wins(flagged_consultation):
    cid = flagged_consultation
    client = _doctor_client()
    first = client.post(f"/api/consultations/{cid}/acknowledge-quality").json()
    second = client.post(f"/api/consultations/{cid}/acknowledge-quality").json()
    assert first["acknowledged_at"] == second["acknowledged_at"]


@needs_db
def test_receptionist_cannot_acknowledge_the_flag(flagged_consultation):
    from app.main import app
    client = TestClient(app)
    username = f"rec_{secrets.token_hex(4)}"
    client.post("/api/register", json={
        "username": username, "password": "test-password-123",
        "display_name": "R", "role": "receptionist"})
    approve_account(username)
    client.post("/api/login", json={"username": username,
                                    "password": "test-password-123"})
    response = client.post(
        f"/api/consultations/{flagged_consultation}/acknowledge-quality")
    assert response.status_code == 403


# --- the client: one writer, amber banner -----------------------------------

REVIEW = Path("app/static/review.html").read_text()


def test_the_flag_reason_joins_the_single_writer():
    """refreshApproveGate is the ONLY writer of Approve's disabled state;
    the flag tier's reason must live inside it, and the banner renderer
    must touch no button."""
    gate = REVIEW[REVIEW.index("function refreshApproveGate"):
                  REVIEW.index("document.getElementById('approve')"
                               ".addEventListener")]
    assert "quality_outcome === 'flagged'" in gate
    assert "quality_ack_at" in gate
    banner = REVIEW[REVIEW.index("function renderQualityFlagBanner"):
                    REVIEW.index("function renderUrgentBanner")]
    for token in ("approveBtn", "getElementById('approve')", ".disabled"):
        assert token not in banner, (
            f"the banner renderer must not touch the Approve button "
            f"(found {token!r}) — that is refreshApproveGate's single job")
    # And nothing outside the gate writes approveBtn.disabled.
    assert REVIEW.count("approveBtn.disabled =") == 1


def test_the_flag_banner_is_amber_and_acknowledge_gated():
    banner = REVIEW[REVIEW.index("function renderQualityFlagBanner"):
                    REVIEW.index("function renderUrgentBanner")]
    assert "'urgency flagged'" in banner
    assert "ackButton('acknowledge-quality')" in banner
    assert ".urgency.flagged" in REVIEW, "the amber styling exists"
