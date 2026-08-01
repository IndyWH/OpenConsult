"""Session 5: the first-call CDS trigger, and what must not move with it.

The session-4 latency report measured the 150-character gate costing
30-45 s of the ~50 s speech-to-questions latency. The first assessment
of a session now fires on the FIRST committed turn; every later call
keeps the 150-character cadence. The urgency officer rides the same
update it always has — asserted here — so the alarm can only arrive
EARLIER than before, never later.

The trigger lives in main.py's WebSocket loop, so it is tested through
the WebSocket with a scripted transcriber and a recording CDS stub; the
thin-first-transcript behaviour is additionally tested against the real
model (self-skips without Ollama, the test_cds.py convention).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import struct
import types

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, consultations, system_utterances
from app import main as appmain
from app.cds import (ASSESSMENT_PROMPT, CDS_MODEL, OLLAMA_URL, URGENCY_PROMPT,
                     CDSEngine)
from app.transcription import Segment


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


def _ollama_has_model() -> bool:
    try:
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0).json()
        return any(m["name"] == CDS_MODEL.removeprefix("hf.co/") or CDS_MODEL in m["name"]
                   for m in tags.get("models", []))
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


EMPTY_ASSESSMENT = {
    "reasoning": "", "differentials": [],
    "questions_to_ask": [], "signs_to_check": [],
    "urgency_check": {"time_critical_possible": False,
                      "already_done_or_arranged": False, "reason": ""},
    "urgent_actions": [],
}


class QueueTranscriber:
    """Returns the next queued segment list per process() call.

    process() runs once per 1.5 s of new audio, and a segment commits
    only when it ends more than 2 s before the buffer's end — so a
    segment queued behind two empty passes arrives when the buffer is
    ~4.5 s long and its 0-1 s span can actually commit."""

    def __init__(self):
        self.queue: list[list[Segment]] = []

    def transcribe(self, buffer):
        return self.queue.pop(0) if self.queue else []

    def say(self, *texts: str) -> None:
        """Queue segments behind two empty passes (see class docstring)."""
        self.queue.extend([[], []])
        for text in texts:
            self.queue.append([Segment(0.0, min(2.0, 0.05 * len(text)), text)])


class RecordingCDS:
    def __init__(self):
        self.calls: list[str] = []

    async def update(self, transcript, previous=None):
        self.calls.append(transcript)
        return dict(EMPTY_ASSESSMENT)


@pytest.fixture()
def first_call_env(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": QueueTranscriber(),
        "speech": object(),
        "cds_engine": RecordingCDS(),
        "rag": types.SimpleNamespace(
            answer_for_conditions=None),  # never invoked: no differentials
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


def _client() -> TestClient:
    auth.ensure_schema()
    user = asyncio.run(auth.create_user(
        f"doctor_{secrets.token_hex(4)}", "test-password-123", "Doctor", "doctor"))
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _feed_audio(ws, seconds: float, start_seq: int) -> int:
    seq = start_seq
    for _ in range(int(seconds * 4)):          # 0.25 s frames
        seq += 1
        ws.send_bytes(struct.pack(">I", seq) + b"\x00\x00" * 4000)
    return seq


def _drain_for_cds(ws, stop_at_done=True):
    """Send stop, read everything to `done`, return the cds messages."""
    ws.send_text("stop")
    cds = []
    while True:
        msg = ws.receive_json()
        if msg["type"] == "cds":
            cds.append(msg)
        elif msg["type"] == "done":
            return cds


@needs_db
def test_first_call_fires_on_the_first_committed_turn(first_call_env):
    transcriber: QueueTranscriber = first_call_env.transcriber
    engine: RecordingCDS = first_call_env.cds_engine
    # One short turn, far below the 150-char gate.
    transcriber.say("I have a pain in my chest.")
    client = _client()
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        _feed_audio(ws, 12.0, 0)
        cds = _drain_for_cds(ws)
    assert len(engine.calls) == 1, "the first committed turn must trigger a call"
    assert len(engine.calls[0]) < 150, "…without waiting for the 150-char gate"
    assert len(cds) == 1


@needs_db
def test_second_call_keeps_the_150_char_cadence(first_call_env):
    transcriber: QueueTranscriber = first_call_env.transcriber
    engine: RecordingCDS = first_call_env.cds_engine
    client = _client()
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        transcriber.say("I have a pain in my chest.")
        seq = _feed_audio(ws, 12.0, 0)
        # A second SHORT committed turn: well under 150 new chars — the
        # old cadence must hold, no second call.
        transcriber.say("It started yesterday.")
        seq = _feed_audio(ws, 12.0, seq)
        # Then a long turn crossing the 150-char gate: the second call.
        transcriber.say(
            "It presses in the middle of my chest and goes up to my jaw "
            "when I climb the stairs at home, with some sweating and a "
            "little nausea, and resting for a few minutes settles it down.")
        _feed_audio(ws, 12.0, seq)
        _drain_for_cds(ws)
    assert len(engine.calls) == 2, (
        f"expected first-turn call + one 150-char call, got {len(engine.calls)}")
    assert len(engine.calls[1]) - len(engine.calls[0]) >= 150


@needs_db
def test_the_flag_restores_the_old_behaviour(first_call_env, monkeypatch):
    monkeypatch.setattr(appmain, "CDS_FIRST_CALL_ON_FIRST_TURN", False)
    transcriber: QueueTranscriber = first_call_env.transcriber
    engine: RecordingCDS = first_call_env.cds_engine
    client = _client()
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        transcriber.say("I have a pain in my chest.")
        seq = _feed_audio(ws, 12.0, 0)
        transcriber.say(
            "It presses in the middle of my chest and goes up to my jaw "
            "when I climb the stairs at home, with some sweating and a "
            "little nausea, and resting for a few minutes settles it down.")
        _feed_audio(ws, 12.0, seq)
        _drain_for_cds(ws)
    assert len(engine.calls) == 1, "with the flag off, only the 150-char gate fires"
    assert len(engine.calls[0]) >= 150


def test_urgency_rides_the_same_update_assessment_first():
    """The officer's call order is untouched (a session-5 rule): one
    engine.update = assessment call, THEN urgency call, both in the same
    update whose result carries the urgent_actions. Firing the first
    update earlier therefore moves the alarm EARLIER, never later."""
    engine = CDSEngine()
    order: list[str] = []

    async def fake_chat(self, system, user, schema):
        if system == ASSESSMENT_PROMPT:
            order.append("assessment")
            return {k: v for k, v in EMPTY_ASSESSMENT.items()
                    if k not in ("urgency_check", "urgent_actions")}
        assert system == URGENCY_PROMPT
        order.append("urgency")
        return {"reasoning": "chest pain with red flags",
                "time_critical_possible": True,
                "already_done_or_arranged": False,
                "urgent_actions": [{"action": "Bedside ECG",
                                    "reason": "exclude ACS"}]}

    engine._chat = types.MethodType(fake_chat, engine)
    assessment = asyncio.run(engine.update("Patient: crushing chest pain."))
    assert order == ["assessment", "urgency"]
    # The same update's result carries the alarm — there is no separate,
    # later delivery for urgency.
    assert assessment["urgent_actions"] == [
        {"action": "Bedside ECG", "reason": "exclude ACS"}]


@pytest.mark.skipif(not _ollama_has_model(),
                    reason="Ollama with the CDS model is not available")
def test_a_one_line_first_transcript_produces_a_valid_first_assessment():
    """Session-4 report, now asserted: the revision rules tolerate a thin
    first list. A single committed line yields a schema-valid assessment,
    and a later revision from that thin previous behaves per the
    pinned/living rules (valid shape; the model revises rather than
    erroring on the small starting point)."""
    engine = CDSEngine()
    first = asyncio.run(engine.update("I have a pain in my chest."))
    # patient_affect is REQUIRED since 2026-08-01 — even on a one-line
    # transcript the model must commit to a reading rather than omit it.
    assert set(first) == {
        "reasoning", "differentials", "questions_to_ask", "signs_to_check",
        "urgency_check", "urgent_actions", "patient_affect"}
    assert first["patient_affect"] in {
        "happy", "positive", "neutral", "low", "anxious", "distressed",
        "angry"}
    assert isinstance(first["differentials"], list)

    revised = asyncio.run(engine.update(
        "I have a pain in my chest.\n"
        "It comes on when I climb stairs and settles when I rest. "
        "I smoke twenty a day and my father had a heart attack at fifty.",
        previous=first))
    assert set(revised) == set(first)
    assert revised["patient_affect"] in {
        "happy", "positive", "neutral", "low", "anxious", "distressed",
        "angry"}
    assert 1 <= len(revised["differentials"]) <= 5
    for d in revised["differentials"]:
        assert d["likelihood"] in {"high", "moderate", "low"}
