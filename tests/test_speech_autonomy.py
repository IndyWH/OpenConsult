"""Session 3 autonomy around the disclosure: auto-on, the invitation
chain, and the silence nudge's server-side cage.

The app.state fixture copies tests/test_speech_exclusion.py's restore-in-
finally discipline (the 2026-07-28 ordering incident, HANDOVER 9d).
StubSpeech uses the REAL reference resolution — only Piper is stubbed.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, consultations, speech, system_utterances
from app import main as appmain


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


class StubSpeech:
    """Fake audio, REAL reference resolution (same as test_speech_exclusion)."""

    def __init__(self):
        self.utterances = {}

    def prepare(self, ref, agenda, *, user_id=None, consultation_id=None,
                doctor=None):
        resolution = speech.resolve(ref, agenda, doctor)
        utterance = speech.Utterance(
            utterance_id=secrets.token_hex(8), text=resolution.text, voice="stub",
            wav=b"RIFF", duration_ms=1000, synth_ms=1,
            ref_kind=resolution.ref_kind, ref_detail=resolution.ref_detail,
            cds_rationale=resolution.cds_rationale, stale=resolution.stale,
            user_id=user_id)
        self.utterances[utterance.utterance_id] = utterance
        return utterance

    def get(self, utterance_id):
        return self.utterances.get(utterance_id)


class SilentTranscriber:
    def transcribe(self, buffer):
        return []


def _make_user() -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"doctor_{secrets.token_hex(4)}", "test-password-123", "Doctor", "doctor"))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def autonomy_env(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": StubSpeech(),
        "cds_engine": object(),   # never invoked: no transcript text
        "rag": object(),
        "live_sessions": {},
        "finalize_queue": asyncio.Queue(),
    }
    previous = {name: getattr(state, name, missing) for name in installed}
    for name, value in installed.items():
        setattr(state, name, value)
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    try:
        yield state
    finally:
        for name, old in previous.items():
            if old is missing:
                delattr(state, name)
            else:
                setattr(state, name, old)
        assert not isinstance(getattr(state, "speech", None), StubSpeech)


def _drain_until(ws, wanted, seen=None, limit=200):
    """Read until one of `wanted` arrives; face_state ticks are expected
    noise once the face is on. A speak_refused is surfaced with its
    detail unless explicitly wanted."""
    for _ in range(limit):
        message = ws.receive_json()
        if seen is not None:
            seen.append(message)
        if message.get("type") in wanted:
            return message
        if message.get("type") == "speak_refused":
            raise AssertionError(
                f"speak refused while waiting for {wanted}: {message['detail']}")
    raise AssertionError(f"none of {wanted} arrived")


def _speak(ws, phrase_id, seen=None, extra=None):
    ws.send_text(json.dumps({"type": "speak",
                             "ref": {"kind": "phrase", "id": phrase_id},
                             **(extra or {})}))
    return _drain_until(ws, {"speak_ready"}, seen)


def _play_through(ws, ready, reason="complete"):
    ws.send_text(json.dumps({"type": "speak_started",
                             "utterance_id": ready["utterance_id"], "seq": 1}))
    ws.send_text(json.dumps({"type": "speak_ended",
                             "utterance_id": ready["utterance_id"],
                             "reason": reason}))


def _face_toggle_audits(session_id: str) -> list[tuple]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT detail->>'on', detail->>'via' FROM audit_event"
                " WHERE action = 'face.toggled'"
                "   AND detail->>'session_id' = %s ORDER BY id", (session_id,))
            return cur.fetchall()


# --- item 2: auto-on at Disclosure ------------------------------------------

def test_spoken_disclosure_switches_the_face_on_once_audited_with_via(autonomy_env):
    client = _client_for(_make_user())
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        seen: list = []
        ready = _speak(ws, "disclosure", seen)
        # The face came on with the disclosure request, confirmed BEFORE
        # the utterance was ready to play.
        toggled = [m for m in seen if m.get("type") == "face_toggled"]
        assert [m["on"] for m in toggled] == [True]
        _play_through(ws, ready)
        _drain_until(ws, {"disclosure"})

        # Fires ONCE: a second disclosure with the face already on does
        # not toggle again.
        ready = _speak(ws, "disclosure", seen := [])
        assert not [m for m in seen if m.get("type") == "face_toggled"]
        _play_through(ws, ready)

    assert _face_toggle_audits(session_id) == [("true", "disclosure_auto")]


def test_the_own_words_tick_does_not_auto_on(autonomy_env):
    """The owner named the button: the SPOKEN disclosure auto-switches,
    the attestation checkbox does not."""
    client = _client_for(_make_user())
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ws.send_text(json.dumps({"type": "disclosure_given"}))
        message = _drain_until(ws, {"disclosure"}, seen := [])
        assert message["given"] is True
        assert not [m for m in seen if m.get("type") == "face_toggled"]
    assert _face_toggle_audits(session_id) == []


def test_auto_on_respects_the_flag(autonomy_env, monkeypatch):
    monkeypatch.setattr(appmain, "FACE_AUTO_ON_DISCLOSURE", False)
    client = _client_for(_make_user())
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ready = _speak(ws, "disclosure", seen := [])
        assert not [m for m in seen if m.get("type") == "face_toggled"]
        _play_through(ws, ready)
    assert _face_toggle_audits(session_id) == []


def test_a_manual_off_is_never_overridden(autonomy_env):
    client = _client_for(_make_user())
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ready = _speak(ws, "disclosure")
        _play_through(ws, ready)
        _drain_until(ws, {"disclosure"})
        # The doctor turns it off — that is final for the session.
        ws.send_text(json.dumps({"type": "face", "on": False}))
        _drain_until(ws, {"face_toggled"})
        # A repeated disclosure must NOT bring it back.
        ready = _speak(ws, "disclosure", seen := [])
        assert not [m for m in seen if m.get("type") == "face_toggled"]
        _play_through(ws, ready)

    assert _face_toggle_audits(session_id) == [
        ("true", "disclosure_auto"), ("false", "manual")]
