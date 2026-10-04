"""Task 19 item 3: the gap check at Stop (owner's option F, 4 Oct 2026).

Task 18 found the final pass had silently dropped passages — safety nets
among them — from 13 of 59 stored consultations, 7 of them approved, and
nothing marked a single one. The guarantee pinned here: where the live
transcript heard speech for TRANSCRIPT_GAP_MIN_S or more and the final
transcript has none, the consultation is flagged with the time of the
gap, the note is still drafted, approval waits on the acknowledged
banner, and the acknowledgement is audited. A shorter hole is not
flagged. WhisperX is faked; everything after it is the shipped pipeline.

Research and education prototype; synthetic consultations only.
"""

from __future__ import annotations

import asyncio
import os
import secrets

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, consultations, finalize, raw_segments, system_utterances, transcript_quality
from app import main as appmain


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _turn(speaker, start, end, text):
    return {"speaker": speaker, "start": start, "end": end, "text": text, "confidence": 0.9}


# The final transcript: the safety net said at 6 to 12.5 s is missing
# (a 6 s gap once the 1 s word tolerance is applied), and 20 to 25 s is
# missing too, but that hole is only 4 s and must not be flagged.
FINAL = [_turn("SPEAKER_00", 0.0, 2.0, "Good morning, what brings you in?"),
         _turn("SPEAKER_01", 3.0, 5.5, "Chest pain when I walk uphill."),
         _turn("SPEAKER_00", 14.0, 15.0, "Any questions?"),
         _turn("SPEAKER_01", 19.0, 19.5, "No."),
         _turn("SPEAKER_00", 25.5, 26.0, "Goodbye.")]
LIVE = [{"start": 0.0, "end": 2.0, "text": "good morning what brings you in"},
        {"start": 3.0, "end": 5.5, "text": "chest pain when I walk uphill"},
        {"start": 6.0, "end": 8.5, "text": "if the pain lasts more than fifteen minutes"},
        {"start": 9.0, "end": 12.5, "text": "call 999 and go straight to the hospital"},
        {"start": 14.0, "end": 15.0, "text": "any questions"},
        {"start": 19.0, "end": 19.5, "text": "no"},
        {"start": 20.0, "end": 25.0, "text": "and the tablets twice a day with food"},
        {"start": 25.5, "end": 26.0, "text": "goodbye"}]


def test_a_gap_against_the_live_transcript_is_flagged_with_its_time_and_gates_approval(monkeypatch):
    for module in (auth, consultations, system_utterances, raw_segments):
        module.ensure_schema()

    async def no_unload():
        return None

    def fake_transcribe(wav_path, spans, speakers):
        return {"turns": [dict(t) for t in FINAL], "audio_duration_s": 26.0,
                "final_words": [(t["start"], t["end"]) for t in FINAL],
                "excluded_spans_s": [], "raw_segments": []}

    drafted = []

    async def fake_note(turns):
        drafted.append(turns)
        return {"reasoning": "", "subjective": [{"text": "Chest pain.", "turns": [1]}],
                "objective": [], "assessment": [], "plan": []}

    monkeypatch.setattr(finalize, "unload_medgemma", no_unload)
    monkeypatch.setattr(finalize, "transcribe_and_diarise", fake_transcribe)
    monkeypatch.setattr(finalize, "draft_note", fake_note)

    doctor = asyncio.run(auth.create_user(f"doc_{secrets.token_hex(4)}", "test-password-123",
                                          "Doctor", "doctor"))
    cid = asyncio.run(consultations.create_consultation(None, doctor["id"]))
    asyncio.run(consultations.save_live_transcript(cid, LIVE))
    asyncio.run(finalize.finalize_consultation(cid, "unused.wav"))

    c = asyncio.run(consultations.get_consultation(cid))
    gaps = c["quality_signals"]["s5_live_gaps"]
    assert gaps["measured"] is True
    assert gaps["gaps"] == [{"start_s": 6.5, "end_s": 12.5, "length_s": 6.0}]  # not the 4 s hole
    assert c["quality_outcome"] == transcript_quality.OUTCOME_FLAGGED
    flags = transcript_quality.evaluate(c["quality_signals"])["flags"]
    assert [f["signal"] for f in flags] == ["S5"]
    assert "0:06 to 0:12" in flags[0]["detail"]
    # The warning does not block the note.
    assert len(drafted) == 1 and c["status"] == "awaiting_review"

    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(doctor["id"]))
    blocked = client.post(f"/api/consultations/{cid}/approve", json={"text": "x"})
    assert blocked.status_code == 409 and "live transcript" in blocked.json()["error"]
    assert client.post(f"/api/consultations/{cid}/acknowledge-quality").status_code == 200
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        acks = conn.execute("SELECT count(*) FROM audit_event WHERE action = 'quality.acknowledged'"
                            " AND subject_id = %s", (cid,)).fetchone()[0]
    assert acks == 1
    assert client.post(f"/api/consultations/{cid}/approve", json={"text": "x"}).status_code == 200
