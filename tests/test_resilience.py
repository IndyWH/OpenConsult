"""Connection resilience: abrupt disconnect holds the session, reconnect
resumes with resend (duplicates skipped by sequence number), and grace
expiry finalises the received audio with the connection-lost flag —
audio is never abandoned.

The live transcriber is faked (returns no segments) so these tests run
without loading Whisper; the protocol and session-registry logic are the
subject, not ASR.
"""

import asyncio
import json
import os
import secrets
import struct
import time
import wave

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import audit, auth, consultations
from app import main as appmain

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

CHUNK = b"\x00\x01" * 4000  # 0.25 s of 16-bit samples


class FakeTranscriber:
    def transcribe(self, buffer):
        return []


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role
    ))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def live_state(monkeypatch, tmp_path):
    """Manual app.state (no lifespan): fake transcriber, fresh registry,
    fresh finalise queue, recordings into tmp."""
    consultations.ensure_schema()
    appmain.app.state.transcriber = FakeTranscriber()
    # Present but never invoked: the fake transcriber yields no text, so
    # the CDS/guideline thresholds are never reached.
    appmain.app.state.cds_engine = object()
    appmain.app.state.rag = object()
    appmain.app.state.live_sessions = {}
    appmain.app.state.finalize_queue = asyncio.Queue()
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    yield appmain.app.state
    appmain.app.state.live_sessions = {}


def _frame(seq: int, payload: bytes = CHUNK) -> bytes:
    return struct.pack(">I", seq) + payload


def _stream_and_drop(client, sid, n_chunks=2):
    """Open a session, send config + chunks, then drop WITHOUT stop."""
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": sid, "patient_id": None}))
        for i in range(1, n_chunks + 1):
            ws.send_bytes(_frame(i))
        # Wait for the ack so we know the server consumed the audio
        # before we cut the connection.
        while True:
            msg = ws.receive_json()
            if msg.get("type") == "ack" and msg["seq"] == n_chunks:
                break
    # context exit closes the socket with no "stop" — an abrupt drop


def _wait_for_detach(state, sid, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entry = state.live_sessions.get(sid)
        if entry is not None and not entry["attached"]:
            return entry
        time.sleep(0.05)
    raise AssertionError("session was not held for reconnect")


def test_disconnect_mid_stream_holds_session_for_reconnect(live_state):
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    sid = f"s_{secrets.token_hex(4)}"

    _stream_and_drop(client, sid, n_chunks=2)

    entry = _wait_for_detach(live_state, sid)
    assert entry["last_seq"] == 2
    assert entry["stopped"] is False
    # No consultation yet: the audio is being held, not abandoned/finalised.
    assert live_state.finalize_queue.qsize() == 0


def test_reconnect_resumes_resends_and_skips_duplicates(live_state):
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    sid = f"s_{secrets.token_hex(4)}"

    _stream_and_drop(client, sid, n_chunks=2)
    _wait_for_detach(live_state, sid)

    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": sid, "resume": True}))
        msg = ws.receive_json()
        assert msg == {"type": "resume", "last_seq": 2}
        # Client resends the unacked tail: one duplicate (2) + one new (3).
        ws.send_bytes(_frame(2))
        ws.send_bytes(_frame(3))
        ws.send_text("stop")
        while True:
            msg = ws.receive_json()
            if msg.get("type") == "done":
                cid = msg["consultation_id"]
                break

    # The recording holds exactly 3 chunks: the duplicate was skipped.
    row = asyncio.run(consultations.get_consultation(cid))
    assert row["status"] == "queued"
    assert row["connection_lost"] is False   # it reconnected and stopped cleanly
    with wave.open(row["audio_path"]) as w:
        assert w.getnframes() == 3 * 4000
    assert live_state.finalize_queue.qsize() == 1
    assert sid not in live_state.live_sessions


def test_grace_expiry_finalises_received_audio_as_connection_lost(
        live_state, monkeypatch):
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    sid = f"s_{secrets.token_hex(4)}"

    _stream_and_drop(client, sid, n_chunks=2)
    _wait_for_detach(live_state, sid)

    monkeypatch.setattr(appmain, "LIVE_RECONNECT_GRACE_S", 0.01)
    asyncio.run(appmain._grace_finalise(live_state, sid))

    assert sid not in live_state.live_sessions
    assert live_state.finalize_queue.qsize() == 1
    cid, wav_path = live_state.finalize_queue.get_nowait()
    row = asyncio.run(consultations.get_consultation(cid))
    assert row["connection_lost"] is True    # review shows the warning banner
    assert row["status"] == "queued"
    assert os.path.exists(wav_path)
    with wave.open(wav_path) as w:
        assert w.getnframes() == 2 * 4000    # everything received was kept
    events = asyncio.run(audit.recent(20))
    created = next(e for e in events if e["action"] == "consultation.created"
                   and e["subject_id"] == cid)
    assert created["detail"]["connection_lost"] is True


def test_resume_of_finalised_session_reports_it(live_state):
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": "long-gone", "resume": True}))
        msg = ws.receive_json()
        assert msg["type"] == "resume_failed"
        assert "consultations tab" in msg["detail"].lower()
