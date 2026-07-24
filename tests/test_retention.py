"""Audio retention (plan §8): FLAC compression on approval, the
retention sweep (audio only, keep_for_research exempts), and the admin
research-flag endpoint's RBAC."""

import asyncio
import os
import secrets

import numpy as np
import psycopg
import pytest
import soundfile
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import audit, auth, consultations, retention

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _write_wav(path, seconds=0.2, rate=16000):
    t = np.arange(int(seconds * rate)) / rate
    data = (np.sin(2 * np.pi * 440 * t) * 0.3 * 32767).astype(np.int16)
    soundfile.write(path, data, rate, subtype="PCM_16")
    return data, rate


# ------------------------------------------------------------- compression

def test_flac_compression_is_lossless_and_removes_wav(tmp_path):
    wav = tmp_path / "consultation_1.wav"
    original, rate = _write_wav(wav)

    flac_path, wav_bytes, flac_bytes = retention.compress_to_flac(str(wav))

    assert flac_path.endswith(".flac") and os.path.exists(flac_path)
    assert not wav.exists()
    assert 0 < flac_bytes and wav_bytes > 0
    decoded, decoded_rate = soundfile.read(flac_path, dtype="int16")
    assert decoded_rate == rate                       # sample rate untouched
    assert np.array_equal(decoded, original)          # bit-exact — lossless


def test_compress_skips_missing_and_non_wav(tmp_path):
    assert retention.compress_to_flac(str(tmp_path / "nope.wav")) is None
    flac = tmp_path / "already.flac"
    flac.write_bytes(b"x")
    assert retention.compress_to_flac(str(flac)) is None


# ------------------------------------------------------------------ sweep

def _make_consultation(audio_path=None, days_old=0, keep=False,
                       doctor_id=None) -> int:
    consultations.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation(None, doctor_id)
        async with await psycopg.AsyncConnection.connect(
                os.environ["DATABASE_URL"]) as conn:
            await conn.execute(
                "UPDATE consultation SET audio_path = %s, keep_for_research = %s,"
                " started_at = now() - make_interval(days => %s) WHERE id = %s",
                (audio_path, keep, days_old, cid),
            )
        return cid

    return asyncio.run(build())


@needs_db
def test_sweep_deletes_only_expired_unflagged_audio(tmp_path):
    old_wav = tmp_path / "old.wav"
    kept_wav = tmp_path / "kept.wav"
    fresh_wav = tmp_path / "fresh.wav"
    for w in (old_wav, kept_wav, fresh_wav):
        _write_wav(w)
    expired = _make_consultation(str(old_wav), days_old=120)
    flagged = _make_consultation(str(kept_wav), days_old=120, keep=True)
    fresh = _make_consultation(str(fresh_wav), days_old=1)
    # A note survives retention even when its audio goes.
    asyncio.run(consultations.save_note(
        expired, {"subjective": [{"text": "x", "turns": [], "uncited": True,
                                  "flagged": False}],
                  "objective": [], "assessment": [], "plan": []}))

    # only_ids keeps the sweep surgical: the suite runs against the real
    # dev database and must never touch the owner's recordings.
    result = asyncio.run(retention.sweep_expired_audio(
        only_ids=[expired, flagged, fresh]))

    assert not old_wav.exists()                       # expired: deleted
    assert kept_wav.exists() and fresh_wav.exists()   # exempt + fresh: intact
    row = asyncio.run(consultations.get_consultation(expired))
    assert row["audio_path"] is None
    assert asyncio.run(consultations.latest_note(expired)) is not None  # audio only
    assert asyncio.run(consultations.get_consultation(flagged))["audio_path"] == str(kept_wav)
    assert asyncio.run(consultations.get_consultation(fresh))["audio_path"] == str(fresh_wav)
    assert result["consultations"] >= 1
    assert result["bytes_freed"] > 0

    events = asyncio.run(audit.recent(20))
    purge = next(e for e in events if e["action"] == "data.audio_purged")
    assert expired in purge["detail"]["consultation_ids"]
    assert flagged not in purge["detail"]["consultation_ids"]
    assert purge["detail"]["bytes_freed"] > 0


@needs_db
def test_sweep_is_idempotent(tmp_path):
    wav = tmp_path / "gone.wav"
    _write_wav(wav)
    cid = _make_consultation(str(wav), days_old=120)
    asyncio.run(retention.sweep_expired_audio(only_ids=[cid]))
    again = asyncio.run(retention.sweep_expired_audio(only_ids=[cid]))
    assert again["consultations"] == 0
    # Row already stamped audio_path NULL: nothing left to purge for cid.
    row = asyncio.run(consultations.get_consultation(cid))
    assert row["audio_path"] is None


# ----------------------------------------------- approval-time compression

def _client_for(user: dict) -> TestClient:
    from app.main import app

    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role
    ))


@needs_db
def test_approval_compresses_wav_to_flac(tmp_path):
    doctor = _make_user("doctor")
    wav = tmp_path / "consultation_approve.wav"
    _write_wav(wav)
    cid = _make_consultation(str(wav), days_old=0, doctor_id=doctor["id"])
    asyncio.run(consultations.save_turns(
        cid, [{"role": "Doctor", "start": 0.0, "end": 1.0, "text": "Hello.",
               "confidence": 0.9}]))
    asyncio.run(consultations.save_note(
        cid, {"subjective": [{"text": "Hi", "turns": [0], "uncited": False,
                              "flagged": False}],
              "objective": [], "assessment": [], "plan": []}))
    asyncio.run(consultations.set_status(cid, "awaiting_review"))

    client = _client_for(doctor)
    assert client.post(f"/api/consultations/{cid}/approve",
                       json={"text": "S:\n  Hi"}).status_code == 200

    row = asyncio.run(consultations.get_consultation(cid))
    assert row["audio_path"].endswith(".flac")
    assert os.path.exists(row["audio_path"])
    assert not wav.exists()


@needs_db
def test_keep_for_research_is_admin_only():
    doctor, recep, admin = (_make_user("doctor"), _make_user("receptionist"),
                            _make_user("admin"))
    cid = _make_consultation(None)
    for user in (doctor, recep):
        assert _client_for(user).post(
            f"/api/consultations/{cid}/keep-for-research".replace(
                "/api/", "/api/admin/"),
            json={"value": True}).status_code == 403
    admin_client = _client_for(admin)
    assert admin_client.post(
        f"/api/admin/consultations/{cid}/keep-for-research",
        json={"value": True}).status_code == 200
    events = asyncio.run(audit.recent(10))
    assert any(e["action"] == "consultation.keep_for_research"
               and e["subject_id"] == cid and e["detail"]["value"] is True
               for e in events)
