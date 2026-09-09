"""The shared harness for the Phase 7c auto-mode protocol tests (slice 5
onward): a live session on a real socket with the client's part played
from the test, a real SpeechService on a fake command, and a scripted
engine standing in for MedGemma. Not a test module. Lifted from
tests/test_auto_questions.py so a fourth copy did not have to exist;
the older files keep their own copies deliberately — each is
self-describing.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import struct
import sys
import time

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, auto_mode, consultations, speech, system_utterances
from app import main as appmain
from app.auto_mode import AutoPhase
from app.cds import OfficerVerdict, RerankVerdict, TopicVerdict
from app.transcription import SAMPLE_RATE


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

FRAME_SAMPLES = 4000
PATIENT_AMPLITUDE = 3000
TTS_AMPLITUDE = 20000

Q_RADIATE = "Does the pain radiate to your jaw or arm?"
Q_ONSET = "When did the chest pain first start?"
Q_SLEEP = "How have you been sleeping?"
Q_TABLETS = "Have you missed any of your tablets?"

# Long enough that one injected line clears CDS_MIN_NEW_CHARS on its own.
PASS_FILLER = "The patient describes the pain in detail, at length, over several sentences here. " * 3


def _tone(samples: int, amplitude: int) -> bytes:
    t = np.arange(samples)
    return (amplitude * np.sin(2 * np.pi * 440 * t / SAMPLE_RATE)).astype(np.int16).tobytes()


def _frame(seq: int, amplitude: int = PATIENT_AMPLITUDE) -> bytes:
    return struct.pack(">I", seq) + _tone(FRAME_SAMPLES, amplitude)


def fake_command(tmp_path, seconds: float = 0.5) -> str:
    script = tmp_path / f"fake_tts_{secrets.token_hex(4)}.py"
    script.write_text(
        "import sys, wave\n"
        "sys.stdin.buffer.read()\n"
        "with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        f"    w.writeframes(b'\\x00\\x00' * int({seconds} * 22050))\n")
    (tmp_path / "voice.onnx").write_bytes(b"never read")
    return f"{sys.executable} {script} --model {{model}} --output-file {{output}}"


class SilentTranscriber:
    def transcribe(self, buffer):
        return []


def _assessment(questions, reasoning="why these"):
    return {"reasoning": reasoning, "differentials": [], "questions_to_ask": list(questions),
            "signs_to_check": [], "urgent_actions": [], "patient_affect": "neutral",
            "urgency_check": {"time_critical_possible": False,
                              "already_done_or_arranged": False, "reason": ""}}


class ScriptedEngine:
    """MedGemma stood in for. `verdicts` (officer) and `agendas` (CDS
    passes) are consumed in order, the last repeating; `topics` maps a
    question to the topic the topic call names (missing → a failed topic
    verdict). `gate_event`, when set, holds every CDS pass until released."""

    def __init__(self):
        self.verdicts = [OfficerVerdict(True, False)]
        self.agendas = [[Q_RADIATE]]
        self.topics = {Q_RADIATE: "the chest pain", Q_ONSET: "the chest pain",
                       Q_SLEEP: "your sleep", Q_TABLETS: "your tablets"}
        self.asked: list[str] = []
        self.updates: list[str] = []
        self.topic_calls: list[str] = []
        self.gate_event: asyncio.Event | None = None
        self.timeouts: list[float | None] = []   # the bound each ask came with (E4)
        # The re-ranker (slice 3): scripted verdicts consumed in order, the
        # last repeating; none scripted → a verdict that keeps the order.
        # `rerank_gate`, when set, holds every re-rank call until released.
        self.rerank_verdicts: list[RerankVerdict] = []
        self.rerank_calls: list[tuple[list, str]] = []
        self.rerank_during_pass: list[bool] = []   # was a full pass running when each call was issued?
        self.rerank_gate: asyncio.Event | None = None
        self.pass_in_flight = False
        # Short calls before the pass (slice 4 of the pilot fixes, G4):
        # `topic_gate`, when set, holds every topic call until released;
        # `order` is the engine's own view of arrivals — "rerank", "topic",
        # "topic_done", "pass" — so a test can pin what reached the slot
        # before what.
        self.topic_gate: asyncio.Event | None = None
        self.order: list[str] = []
        # Lay wording (slice 4 of the pilot fixes, the D1 extension): the
        # plain-English wording the topic call returns for a question;
        # missing → none, so the question is spoken verbatim as before.
        self.lays: dict[str, str] = {}

    async def end_of_turn(self, transcript, *, timeout_s=None):
        self.asked.append(transcript)
        self.timeouts.append(timeout_s)
        return self.verdicts.pop(0) if len(self.verdicts) > 1 else self.verdicts[0]

    async def topic_for(self, question):
        self.topic_calls.append(question)
        self.order.append("topic")
        if self.topic_gate is not None:
            await self.topic_gate.wait()
        self.order.append("topic_done")
        topic = self.topics.get(question)
        lay = self.lays.get(question)
        if topic is None:
            return TopicVerdict(None, failed="unusable: ''", elapsed_ms=7, lay=lay,
                                lay_failed=None if lay else "unusable: None")
        return TopicVerdict(topic, elapsed_ms=9, lay=lay, lay_failed=None if lay else "unusable: None")

    async def rerank(self, pending, excerpt):
        self.rerank_calls.append((list(pending), excerpt))
        self.rerank_during_pass.append(self.pass_in_flight)
        self.order.append("rerank")
        if self.rerank_gate is not None:
            await self.rerank_gate.wait()
        if not self.rerank_verdicts:
            return RerankVerdict(tuple(item_id for item_id, _ in pending), {}, elapsed_ms=5)
        return (self.rerank_verdicts.pop(0) if len(self.rerank_verdicts) > 1
                else self.rerank_verdicts[0])

    async def update(self, transcript, previous=None):
        self.pass_in_flight = True
        self.order.append("pass")
        try:
            if self.gate_event is not None:
                await self.gate_event.wait()
            self.updates.append(transcript)
            questions = self.agendas.pop(0) if len(self.agendas) > 1 else self.agendas[0]
            return _assessment(questions, reasoning=f"pass {len(self.updates)}")
        finally:
            self.pass_in_flight = False


def _make_user(role: str = "doctor") -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", "Herath", role))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def gate(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    monkeypatch.setattr(speech, "TTS_ENABLED", True)
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", True)
    # Encouragers are slice 3's subject (tests/test_auto_golden.py); here
    # they would only take the one utterance slot at the wrong moment, so
    # both thresholds — the golden window's minimum quiet and the bridge's
    # — are parked out of reach except where a test wants them.
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 100.0)
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 100.0)
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": speech.SpeechService(voice="test", model_path=str(tmp_path / "voice.onnx"),
                                       cache_dir=tmp_path / "cache",
                                       command=fake_command(tmp_path)),
        "cds_engine": ScriptedEngine(),
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


def _collect_until(ws, wanted, limit=80):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if message.get("type") in wanted:
            return seen
        if message.get("type") in ("speak_refused", "auto_refused") and "refused" not in "".join(wanted):
            raise AssertionError(f"refused while waiting for {wanted}: {message['detail']}")
    raise AssertionError(f"none of {wanted} arrived; saw {[m.get('type') for m in seen]}")


def _until(ws, wanted, limit=80):
    return _collect_until(ws, wanted, limit)[-1]


class Session:
    def __init__(self, state, ws, session_id):
        self.state, self.ws, self.session_id = state, ws, session_id
        self.seq = 0
        self.quiet_s = 0.0
        self.since = "speech"        # what began the current quiet span (E2)

    @property
    def entry(self):
        return self.state.live_sessions[self.session_id]

    @property
    def auto(self):
        return self.entry["auto"]

    @property
    def phase(self):
        return self.auto["controller"].phase

    def disclose(self):
        self.ws.send_text(json.dumps({"type": "disclosure_given"}))
        return _until(self.ws, {"disclosure"})

    def frame(self, amplitude=PATIENT_AMPLITUDE):
        self.seq += 1
        self.ws.send_bytes(_frame(self.seq, amplitude))

    def probe(self):
        self.frame()
        return _collect_until(self.ws, {"ack"})[:-1]

    def play(self, utterance_id, reason="complete"):
        self.ws.send_text(json.dumps({"type": "speak_started",
                                      "utterance_id": utterance_id, "seq": self.seq + 1}))
        self.frame(TTS_AMPLITUDE)
        _until(self.ws, {"ack"})
        self.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                                      "seq": self.seq + 1, "reason": reason}))
        self.quiet_s = 0.0                    # our playback ended: a fresh span
        self.since = "playback"

    def abort(self, utterance_id):
        self.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                                      "seq": self.seq + 1, "reason": "politeness_abort",
                                      "rms": 0.07}))
        self.quiet_s = 0.0

    def toggle(self, on: bool):
        self.ws.send_text(json.dumps({"type": "auto", "on": on}))

    def quiet(self, quiet_s: float):
        self.quiet_s = quiet_s
        self.ws.send_text(json.dumps({"type": "quiet", "quiet_s": quiet_s, "since": self.since}))

    def commit_transcript(self, *lines: str):
        def _inject():
            self.entry["transcript_parts"].extend(lines)
            self.entry["cds_sent_len"] = len("\n".join(self.entry["transcript_parts"]))
        self.ws.portal.call(_inject)
        self.quiet_s = 0.0
        self.since = "speech"                 # the patient spoke: a fresh span of theirs

    def seed_agenda(self, *questions):
        """A pre-existing agenda version, as an earlier CDS pass would have
        left it — without running the engine, so NOT merged into the
        standing queue (a seed is a panel the machine never saw land)."""
        return self.ws.portal.call(lambda: self.entry["agenda"].record(_assessment(questions)))

    def land_pass(self, *lines: str, tries: int = 60):
        """Let a CDS pass run on transcript growth — not one auto mode asked
        for — and wait for it to land (and, with the machine on, merge into
        the standing queue). commit_transcript moves the sent-length marker
        so passes never fire from it; here the marker is left behind, as
        live transcription leaves it. Returns the new agenda version."""
        before = self.entry["agenda"].current_version
        filler = lines or (PASS_FILLER,)
        def _inject():
            self.entry["transcript_parts"].extend(filler)
        self.ws.portal.call(_inject)
        for _ in range(tries):
            self.probe()
            if self.entry["agenda"].current_version > before:
                return self.entry["agenda"].current_version
            time.sleep(0.03)
        raise AssertionError("no CDS pass landed")

    def to_golden(self):
        self.disclose()
        self.toggle(True)
        seen = _collect_until(self.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        self.play(invitation["utterance_id"])
        self.probe()
        assert self.phase is AutoPhase.GOLDEN

    def to_open(self):
        """GOLDEN → OPEN by a hand-back at the end of the patient's turn.
        The engine's first officer verdict must be a hand-back."""
        self.commit_transcript("It started on Tuesday.", "That's all really.")
        self.quiet(3.1)
        self.probe()
        assert self.phase is AutoPhase.OPEN

    def turn_end(self, *said: str, quiet: float = 3.2):
        """The patient says something, goes quiet, and the officer judges
        the turn ended (the engine's current verdict must say so)."""
        self.commit_transcript(*said)
        self.quiet(quiet)
        self.probe()

    def wait_for_auto_speak(self, *, start_quiet=None, tries=40):
        """Keep the quiet span going with reports and loop ticks until the
        server issues an utterance (background work — the CDS pass, the
        topic call, pre-synthesis — needs ticks to land)."""
        q = start_quiet if start_quiet is not None else max(self.quiet_s, 3.3)
        for _ in range(tries):
            q += 0.7
            self.quiet(q)
            seen = self.probe()
            spoken = [m for m in seen if m.get("type") == "auto_speak"]
            if spoken:
                return spoken[0]
            time.sleep(0.03)
        raise AssertionError("no auto utterance was issued")

    def expect_silence(self, *, tries=6):
        q = max(self.quiet_s, 3.3)
        for _ in range(tries):
            q += 0.7
            self.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in self.probe())
            time.sleep(0.02)


@contextlib.contextmanager
def live(state, user=None):
    user = user or _make_user()
    client = _client_for(user)
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        yield Session(state, ws, session_id)


def _audit(action: str, session_id: str) -> list[dict]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT detail FROM audit_event WHERE action = %s"
            " AND detail->>'session_id' = %s ORDER BY id",
            (action, session_id)).fetchall()
    return [r[0] for r in rows]


def _stop(s: Session):
    s.ws.send_text("stop")
    return _until(s.ws, {"done"})["consultation_id"]


def _rows(cid):
    return asyncio.run(system_utterances.for_consultation(cid))


