"""Phase 7b item 4 — the face over the EXISTING WebSocket, off by default.

Off is a first-class state (the control arm of the planned CARE study):
when the face is off the server sends no face_state messages at all.
On: payloads arrive at the tick rate. Every toggle writes an audit row,
and completion writes one consultation-linked face.arms row so a study
arm is one query.

The app.state fixture copies tests/test_speech_exclusion.py's discipline:
everything installed is removed again in a finally — the 2026-07-28
ordering incident (HANDOVER 9d) is why that is not optional.
"""

import asyncio
import json
import os
import secrets
import struct
import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, consultations, face as face_mod, system_utterances
from app import main as appmain


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


class SilentTranscriber:
    def transcribe(self, buffer):
        return []


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def face_state_env(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": object(),       # never invoked: no speak in these tests
        "cds_engine": object(),   # never invoked: no transcript text
        "rag": object(),
        "live_sessions": {},
        "finalize_queue": asyncio.Queue(),
    }
    previous = {name: getattr(state, name, missing) for name in installed}
    for name, value in installed.items():
        setattr(state, name, value)
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    # A fast tick so the rate test measures pacing, not patience.
    monkeypatch.setattr(face_mod, "FACE_TICK_HZ", 20.0)
    try:
        yield state
    finally:
        for name, old in previous.items():
            if old is missing:
                delattr(state, name)
            else:
                setattr(state, name, old)


def _frame(seq: int) -> bytes:
    return struct.pack(">I", seq) + b"\x00\x00" * 4000


def _audit_rows(action: str) -> list[tuple]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT subject_type, subject_id, detail FROM audit_event"
                " WHERE action = %s ORDER BY id", (action,))
            return cur.fetchall()


@needs_db
def test_face_off_by_default_sends_no_face_state_at_all(face_state_env):
    client = _client_for(_make_user("doctor"))
    seen: list[dict] = []
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        for seq in range(1, 6):
            ws.send_bytes(_frame(seq))
        time.sleep(0.5)  # long enough for several ticks, had a loop started
        ws.send_text("stop")
        while True:
            msg = ws.receive_json()
            seen.append(msg)
            if msg["type"] == "done":
                break
    assert not [m for m in seen if m["type"] == "face_state"], (
        "face_state traffic with the face off — off must be silent")


@needs_db
def test_face_on_ticks_then_off_goes_silent_and_both_are_audited(face_state_env):
    user = _make_user("doctor")
    client = _client_for(user)
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ws.send_text(json.dumps({"type": "face", "on": True}))

        # Confirmation first, then payloads at the tick rate (20 Hz here):
        # ten arrivals paced by the loop, not one burst.
        started = None
        states = 0
        while states < 10:
            msg = ws.receive_json()
            if msg["type"] == "face_toggled":
                assert msg["on"] is True
                started = time.monotonic()
            elif msg["type"] == "face_state":
                assert started is not None, "face_state before the toggle ack"
                states += 1
                assert set(msg["muscles"]) == (
                    face_mod.PINNED_MUSCLES | face_mod.BANDED_MUSCLES)
        elapsed = time.monotonic() - started
        assert elapsed >= 10 / 20.0 * 0.5, (
            f"10 ticks in {elapsed:.3f}s — not paced at the tick rate")
        assert elapsed < 10.0, "tick rate far below the configured 20 Hz"

        # Toggle off: after the ack, the stream is silent — the next
        # message the server sends is the stop acknowledgement, with no
        # face_state in between.
        ws.send_text(json.dumps({"type": "face", "on": False}))
        while True:
            msg = ws.receive_json()
            if msg["type"] == "face_toggled":
                assert msg["on"] is False
                break
            assert msg["type"] == "face_state"  # in-flight ticks only
        time.sleep(0.4)  # room for ~8 ticks, were the loop still alive
        ws.send_text("stop")
        after_off = []
        while True:
            msg = ws.receive_json()
            after_off.append(msg["type"])
            if msg["type"] == "done":
                cid = msg["consultation_id"]
                break
        assert "face_state" not in after_off, "face_state after toggling off"

    toggles = [(detail["on"], detail["session_id"])
               for _, _, detail in _audit_rows("face.toggled")
               if detail["session_id"] == session_id]
    assert toggles == [(True, session_id), (False, session_id)]

    arms = [(sid, detail) for _, sid, detail in _audit_rows("face.arms")
            if sid == cid]
    assert len(arms) == 1
    assert arms[0][1]["face_ever_on"] is True
    assert [t["on"] for t in arms[0][1]["toggles"]] == [True, False]
