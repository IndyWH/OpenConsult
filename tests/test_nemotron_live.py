"""Task 13 item 7: the live path with SPEECH_PIPELINE=nemotron.

The speech process is faked: in-process for the session's own rules, and
tests/fake_speech_worker.py (the real worker loop, a scripted stream) for
the socket. No GPU.

Pinned:
- Lines reach transcript_parts — what the CDS reads — in START-TIME order,
  even when the speakers' lines arrive out of order (owner, at approval).
- Every line is stored, with speaker and times, the moment it arrives,
  before any ordering.
- Alba's speaking windows reach the worker as zeros; the recording keeps
  the real audio (the guarantee in app/live.py, unchanged).
- A worker failure mid-consultation is told to the page at once, and the
  session keeps the reason so finalisation can refuse.
- An unready engine refuses the socket with a plain reason: no recording,
  no session, no fallback to whisper.
- With whisper, the socket builds today's LiveSession and never touches the
  worker.
- Auto mode runs on the Nemotron session through the same hooks, with no
  change to auto-mode logic (owner's point 6).
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import struct
import sys
import time
import wave
from pathlib import Path

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, consultations, live_segments, speech_pipeline
from app import main as appmain
from app.live import LiveSession
from app.speech_pipeline import NemotronLiveSession, SpeechWorker, WorkerError

FAKE = Path(__file__).resolve().parent / "fake_speech_worker.py"
SAMPLES = 4000                                   # 0.25 s, the page's chunk


def _tone(amplitude: int, n: int = SAMPLES) -> bytes:
    t = np.arange(n)
    return (amplitude * np.sin(2 * np.pi * 440 * t / 16000)).astype("<i2").tobytes()


def _line(i, speaker, start, end, text):
    return {"id": i, "speaker": speaker, "start": start, "end": end, "text": text}


# --- the session's own rules, with an in-process worker ------------------------

class _Store:
    def __init__(self):
        self.saved, self.revised = [], []

    async def save(self, sid, lines):
        self.saved.extend(dict(ln) for ln in lines)

    async def revise(self, sid, revisions):
        self.revised.extend(revisions)


class _Worker:
    """Answers each audio request with the next scripted reply."""

    def __init__(self, replies=(), flush=None, fail_on=None):
        self.replies, self.flush_reply, self.fail_on = list(replies), flush, fail_on
        self.audio: list[bytes] = []

    async def arequest(self, header, payload=b"", timeout_s=None):
        kind = header["type"]
        if kind == self.fail_on:
            raise WorkerError(f"the speech worker did not answer a {kind} request within 20 s")
        if kind == "audio":
            self.audio.append(payload)
            reply = self.replies.pop(0) if self.replies else {}
            return {"type": "lines", "segments": [], "revisions": [], "watermark": 0.0,
                    "partial": "", **reply}
        if kind == "flush":
            return {"type": "flushed", "segments": [], "revisions": [], "stats": {},
                    **(self.flush_reply or {})}
        return {"type": "opened"}


def _session(worker, store=None) -> NemotronLiveSession:
    return NemotronLiveSession(worker, "sess", store or _Store())


def test_lines_from_two_speakers_arriving_out_of_order_are_released_in_spoken_order():
    store = _Store()
    worker = _Worker(replies=[
        # Speaker 1's line commits first, though it started later; the
        # watermark (4.0) says a line starting before 4.0 may still come.
        {"segments": [_line(0, 1, 10.0, 11.0, "Second, from speaker one.")], "watermark": 4.0},
        # Now speaker 0's earlier line commits, and the watermark passes both.
        {"segments": [_line(1, 0, 6.0, 7.0, "First, from speaker zero.")], "watermark": 12.0},
    ])
    s = _session(worker, store)

    async def run():
        s.append_pcm16(_tone(3000))
        first, _ = await s.process()
        # Held, not released — but STORED the moment it arrived.
        assert first == []
        assert [ln["id"] for ln in store.saved] == [0]
        s.append_pcm16(_tone(3000))
        second, _ = await s.process()
        return second

    released = asyncio.run(run())
    assert [seg.text for seg in released] == ["First, from speaker zero.",
                                              "Second, from speaker one."]
    assert [seg.start for seg in released] == [6.0, 10.0]
    assert [ln["id"] for ln in store.saved] == [0, 1]          # arrival order, both kept
    assert {ln["speaker"] for ln in store.saved} == {0, 1}
    assert s.order_violations == 0


def test_flush_releases_everything_held_and_the_last_lines_in_order():
    worker = _Worker(replies=[{"segments": [_line(0, 0, 5.0, 6.0, "Held.")], "watermark": 1.0}],
                     flush={"segments": [_line(1, 1, 2.0, 3.0, "Earlier, at flush.")]})
    s = _session(worker)

    async def run():
        s.append_pcm16(_tone(3000))
        assert (await s.process())[0] == []
        s.append_pcm16(_tone(3000))                # unsent audio goes before the flush
        return await s.flush()

    released = asyncio.run(run())
    assert [seg.text for seg in released] == ["Earlier, at flush.", "Held."]
    assert len(worker.audio) == 2 and s.flushed and s.failure is None


def test_a_revision_is_stored_against_the_line_it_revises():
    store = _Store()
    worker = _Worker(replies=[{"segments": [_line(0, 0, 1.0, 2.0, "This is new")],
                               "watermark": 5.0},
                              {"revisions": [{"id": 0, "text": "This is new.", "end": 2.1}],
                               "watermark": 6.0}])
    s = _session(worker, store)

    async def run():
        for _ in range(2):
            s.append_pcm16(_tone(3000))
            await s.process()

    asyncio.run(run())
    assert store.revised == [{"id": 0, "text": "This is new.", "end": 2.1}]


def test_alba_speaking_window_reaches_the_worker_as_zeros_and_the_recording_keeps_it():
    worker = _Worker()
    s = _session(worker)
    patient, alba = _tone(3000), _tone(20000)
    s.append_pcm16(patient)
    start = s.open_speaking_window("u1", duration_ms=250, tail_ms=0)
    assert start == len(patient)                    # the window opened where Alba began
    s.append_pcm16(alba)
    s.close_speaking_window()
    s.append_pcm16(patient)
    asyncio.run(s.process())

    sent = np.frombuffer(b"".join(worker.audio), dtype="<i2")
    assert np.abs(np.frombuffer(alba, dtype="<i2")).max() > 15000   # the attack was real
    assert sent.size == 3 * SAMPLES
    assert np.all(sent[SAMPLES:2 * SAMPLES] == 0)                    # Alba: silence
    assert np.array_equal(sent[:SAMPLES], np.frombuffer(patient, dtype="<i2"))
    assert np.array_equal(sent[2 * SAMPLES:], np.frombuffer(patient, dtype="<i2"))
    recording = b"".join(s._recording)
    assert recording == patient + alba + patient                     # the room, as it was
    assert s.audio_seconds == pytest.approx(0.75)


def test_a_worker_failure_mid_consultation_is_told_at_once_and_kept_for_stop():
    worker = _Worker(fail_on="audio")
    s = _session(worker)
    s.append_pcm16(_tone(3000))
    committed, partial = asyncio.run(s.process())
    assert (committed, partial) == ([], "")
    assert "did not answer" in s.failure
    notices = s.take_notices()
    assert len(notices) == 1 and notices[0]["type"] == "speech_failed"
    assert "will be refused at Stop" in notices[0]["detail"]
    assert s.take_notices() == []                   # told once
    # Later audio is recorded but not sent; flush builds nothing.
    s.append_pcm16(_tone(3000))
    assert asyncio.run(s.process()) == ([], "")
    assert asyncio.run(s.flush()) == []
    assert len(b"".join(s._recording)) == 2 * SAMPLES * 2


def test_a_flush_that_times_out_is_a_failure_and_returns_no_lines():
    worker = _Worker(replies=[{"segments": [_line(0, 0, 1.0, 2.0, "Committed before Stop.")],
                               "watermark": 0.5}], fail_on="flush")
    s = _session(worker)

    async def run():
        s.append_pcm16(_tone(3000))
        await s.process()
        return await s.flush()

    assert asyncio.run(run()) == []
    assert s.failure.startswith("at Stop:") and "flush" in s.failure
    assert s.flushed is False


# --- the socket, with the fake worker process ------------------------------------

def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


class _HeldEngine:
    """A CDS engine whose pass never lands: the lines reach it (that is the
    point), and nothing downstream of an assessment runs."""

    def __init__(self):
        self.transcripts: list[str] = []

    async def update(self, transcript, previous=None, **kwargs):
        self.transcripts.append(transcript)
        await asyncio.Event().wait()


class _MustNotTranscribe:
    def transcribe(self, buffer):
        raise AssertionError("faster-whisper must not run on the nemotron path")


def _fake_worker(tmp_path, script: dict) -> SpeechWorker:
    path = tmp_path / f"script_{secrets.token_hex(3)}.json"
    path.write_text(json.dumps(script))
    w = SpeechWorker([sys.executable, str(FAKE), str(path)], log_path=tmp_path / "worker.log")
    w.start()
    deadline = time.monotonic() + 10
    while w.state == "starting" and time.monotonic() < deadline:
        time.sleep(0.02)
    return w


@pytest.fixture()
def nemotron_state(monkeypatch, tmp_path):
    consultations.ensure_schema()
    live_segments.ensure_schema()
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemotron")
    state = appmain.app.state
    state.transcriber = _MustNotTranscribe()
    state.cds_engine = _HeldEngine()
    state.rag = object()
    state.live_sessions = {}
    state.finalize_queue = asyncio.Queue()
    state.speech_worker = None
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    yield state
    if state.speech_worker is not None:
        state.speech_worker.stop()
    state.speech_worker = None
    state.live_sessions = {}


def _client(role="doctor") -> TestClient:
    auth.ensure_schema()
    user = asyncio.run(auth.create_user(f"{role}_{secrets.token_hex(4)}", "test-password-123",
                                        role.title(), role))
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _frame(seq: int, amplitude: int = 3000) -> bytes:
    return struct.pack(">I", seq) + _tone(amplitude)


def _until(ws, wanted: set[str], limit=60):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if message.get("type") in wanted:
            return seen
    raise AssertionError(f"none of {wanted}; saw {[m.get('type') for m in seen]}")


def _rows(session_id: str) -> list[tuple]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(
            "SELECT line_id, speaker, start_s, end_s, text FROM live_speech_segment"
            " WHERE session_id = %s ORDER BY line_id", (session_id,)).fetchall()


@needs_db
def test_an_unready_engine_refuses_recording_with_a_plain_reason(nemotron_state, tmp_path):
    nemotron_state.speech_worker = _fake_worker(tmp_path, {"load_error": "could not load the models: OOM"})
    sid = secrets.token_hex(6)
    with _client().websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": sid}))
        message = ws.receive_json()
    assert message["type"] == "speech_unavailable"
    assert "OOM" in message["detail"] and "Recording cannot start" in message["detail"]
    assert sid not in nemotron_state.live_sessions     # no session, so nothing recorded
    assert nemotron_state.finalize_queue.qsize() == 0
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        audited = conn.execute(
            "SELECT count(*) FROM audit_event WHERE action = 'live.speech_unavailable'"
            " AND detail->>'detail' LIKE %s", ("%OOM%",)).fetchone()[0]
    assert audited >= 1


@needs_db
def test_the_status_endpoint_tells_the_page_the_same(nemotron_state, tmp_path):
    client = _client()
    assert client.get("/api/speech-pipeline").json()["ready"] is False   # no worker at all
    nemotron_state.speech_worker = _fake_worker(tmp_path, {})
    body = client.get("/api/speech-pipeline").json()
    assert body == {"pipeline": "nemotron", "ready": True, "state": "ready", "detail": None,
                    "max_speakers": 2}


@needs_db
def test_live_lines_reach_the_page_and_the_cds_input_in_spoken_order_and_are_stored(
        nemotron_state, tmp_path):
    nemotron_state.speech_worker = _fake_worker(tmp_path, {"replies": [
        {"segments": [_line(0, 1, 10.0, 11.0, "Since Tuesday, doctor.")], "watermark": 4.0,
         "partial": "and it"},
        {"segments": [_line(1, 0, 6.0, 7.0, "When did it start?")], "watermark": 12.0},
    ]})
    sid = secrets.token_hex(6)
    with _client().websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": sid}))
        for seq in range(1, 7):                     # 1.5 s: one process() call
            ws.send_bytes(_frame(seq))
        seen = _until(ws, {"ack"})
        while not (seen[-1]["type"] == "ack" and seen[-1]["seq"] == 6):
            seen += _until(ws, {"ack"})
        assert [m for m in seen if m["type"] == "final"] == []           # held for order
        assert {"type": "partial", "text": "and it"} in seen
        assert [r[0] for r in _rows(sid)] == [0]                         # stored on arrival
        for seq in range(7, 13):
            ws.send_bytes(_frame(seq))
        finals = []
        while len(finals) < 2:
            finals += [m for m in _until(ws, {"final"}) if m["type"] == "final"]
        entry = nemotron_state.live_sessions[sid]
        assert [f["text"] for f in finals] == ["When did it start?", "Since Tuesday, doctor."]
        assert entry["transcript_parts"] == ["When did it start?", "Since Tuesday, doctor."]
        assert isinstance(entry["session"], NemotronLiveSession)
        for _ in range(100):                        # the CDS pass reads them in that order
            if nemotron_state.cds_engine.transcripts:
                break
            time.sleep(0.02)
        assert nemotron_state.cds_engine.transcripts[0].index("When did it start?") < \
            nemotron_state.cds_engine.transcripts[0].index("Since Tuesday, doctor.")
    rows = _rows(sid)
    assert [(r[0], r[1], r[4]) for r in rows] == [(0, 1, "Since Tuesday, doctor."),
                                                 (1, 0, "When did it start?")]


@needs_db
def test_a_worker_crash_mid_consultation_is_announced_on_the_page(nemotron_state, tmp_path):
    nemotron_state.speech_worker = _fake_worker(tmp_path, {"die_on_audio": 1})
    sid = secrets.token_hex(6)
    with _client().websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": sid}))
        for seq in range(1, 7):
            ws.send_bytes(_frame(seq))
        seen = _until(ws, {"speech_failed"})
        assert "will be refused at Stop" in seen[-1]["detail"]
        entry = nemotron_state.live_sessions[sid]
        assert "exited" in entry["session"].failure
        for seq in range(7, 13):                    # the recording carries on
            ws.send_bytes(_frame(seq))
        while _until(ws, {"ack"})[-1]["seq"] != 12:
            pass
        assert entry["session"].recorded_bytes == 12 * SAMPLES * 2


@needs_db
def test_with_whisper_the_socket_builds_todays_session_and_never_touches_the_worker(
        monkeypatch, tmp_path):
    consultations.ensure_schema()
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "whisper")

    class Untouchable:
        def __getattr__(self, name):
            raise AssertionError(f"the whisper path used the worker ({name})")

    class Silent:
        calls = 0

        def transcribe(self, buffer):
            Silent.calls += 1
            return []

    state = appmain.app.state
    state.transcriber, state.speech_worker = Silent(), Untouchable()
    state.cds_engine, state.rag = object(), object()
    state.live_sessions, state.finalize_queue = {}, asyncio.Queue()
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    sid = secrets.token_hex(6)
    try:
        with _client().websocket_connect("/ws/transcribe") as ws:
            ws.send_text(json.dumps({"session_id": sid}))
            for seq in range(1, 7):
                ws.send_bytes(_frame(seq))
            while _until(ws, {"ack"})[-1]["seq"] != 6:
                pass
            session = state.live_sessions[sid]["session"]
            assert type(session) is LiveSession
            assert Silent.calls >= 1                      # faster-whisper's path ran
    finally:
        state.speech_worker = None
        state.live_sessions = {}


# --- auto mode on the Nemotron session (owner's point 6) ---------------------------

from auto_harness import _stop, gate, live, needs_db as _auto_needs_db  # noqa: E402,F401


@_auto_needs_db
def test_auto_mode_runs_on_the_nemotron_session_and_alba_reaches_it_as_silence(
        gate, monkeypatch, tmp_path):
    """The harness's own auto run — disclosure, the invitation spoken, the
    golden minutes, the hand-back to OPEN, Alba's next question — on a
    Nemotron session fed by the fake worker. Nothing in auto mode changes;
    the session only has to honour the same hooks. Every frame Alba spoke
    over must reach the worker as zeros."""
    from app.cds import OfficerVerdict
    gate.cds_engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    log = tmp_path / "audio.raw"
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemotron")
    live_segments.ensure_schema()
    gate.speech_worker = _fake_worker(tmp_path, {"audio_log": str(log)})
    try:
        with live(gate) as s:
            assert isinstance(s.entry["session"], NemotronLiveSession)
            s.to_golden()                         # disclosure + the invitation, played
            s.to_open()                           # golden → open by a hand-back
            s.turn_end("It is a tight pain in the middle of my chest.")
            spoken = s.wait_for_auto_speak()      # Alba asks the next question
            s.play(spoken["utterance_id"])
            from app.auto_mode import AutoPhase
            assert s.phase is AutoPhase.OPEN
            cid = _stop(s)
    finally:
        gate.speech_worker.stop()
        gate.speech_worker = None

    with wave.open(str(tmp_path / f"consultation_{cid}.wav")) as w:
        recording = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    sent = np.frombuffer(log.read_bytes(), dtype="<i2")
    assert sent.size == recording.size              # every sample went, flush included
    # The exclusion spans as stored for finalisation: the speaking windows,
    # each with its 200 ms tail — the same rule as on the whisper path.
    from app import system_utterances
    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    muted = np.zeros(recording.size, dtype=bool)
    for start_byte, end_byte in spans:
        muted[start_byte // 2:end_byte // 2] = True
    loud = np.abs(recording) > 15000                # TTS_AMPLITUDE frames: Alba playing
    assert len(spans) >= 2 and loud.sum() >= 2 * 1000   # invitation and question: not vacuous
    assert np.all(muted[loud])                      # Alba lies inside the windows
    assert np.all(sent[muted] == 0)                 # and none of it reached the engine
    assert np.array_equal(sent[~muted], recording[~muted])   # the patient's audio, untouched
    assert (np.abs(recording[~muted]) > 1000).sum() > 0
