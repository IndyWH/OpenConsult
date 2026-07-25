"""The transcript guarantee: our own voice can never enter the transcript.

`PHASE_7_SPEC.md` § 7a, hard requirement: system-spoken utterances are
excluded from the patient transcript **by construction** — never by
prompt, never by post-hoc filtering. `PHASE_7A_SPEC.md` §§1.1–1.3 spell
out what that forces: server-held knowledge of when we were speaking,
applied to *both* transcription paths.

    STRING COMPARISON AGAINST THE SPOKEN TEXT IS LEGITIMATE AS A TEST
    ASSERTION AND FORBIDDEN AS A RUNTIME MECHANISM.

That sentence is here because it is exactly the kind of thing a future
contributor will find in these tests and "helpfully" promote into the
pipeline as a safeguard. Do not. Matching text at runtime is *detection*,
and detection that works 98% of the time is worse than useless here: a
rare fabrication is more dangerous than a frequent one, because nobody
builds the habit of checking for it. The shipped mechanism is that the
server refuses to hand speaking-window audio to the transcriber at all —
`app/live.py::append_pcm16`. The tests below assert the outcome; the code
must keep achieving it structurally.

What is genuinely covered here, stated plainly: the live path end to end
through `LiveSession`, the window arithmetic, and the persistence of
spans. Real Piper audio is not involved — the "TTS" in these tests is a
loud synthetic tone, which is a stronger test of the exclusion than
speech would be (a tone that survives is unmistakable) but is not
evidence about Piper.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from app import speech
from app.live import BYTES_PER_MS, LiveSession, bytes_to_ms
from app.transcription import SAMPLE_RATE, Segment

FRAME_SAMPLES = 4000                       # live.html's CHUNK_SAMPLES
FRAME_BYTES = FRAME_SAMPLES * 2            # 0.25 s per frame
TTS_AMPLITUDE = 20000                      # unmistakably loud
PATIENT_AMPLITUDE = 3000


def tone(samples: int, amplitude: int) -> bytes:
    t = np.arange(samples)
    wave = (amplitude * np.sin(2 * np.pi * 440 * t / SAMPLE_RATE)).astype(np.int16)
    return wave.tobytes()


class LeakDetector:
    """A transcriber that reports what it can actually hear.

    Any buffer region above the patient's amplitude is the system's own
    voice, so it returns a segment saying so. If the exclusion works, that
    segment can never appear.
    """

    def transcribe(self, buffer: np.ndarray) -> list[Segment]:
        peak = float(np.max(np.abs(buffer))) if len(buffer) else 0.0
        text = ("SYSTEM-VOICE-LEAKED" if peak > (PATIENT_AMPLITUDE + 2000) / 32768.0
                else "patient speech")
        return [Segment(start=0.0, end=len(buffer) / SAMPLE_RATE, text=text)]


def feed(session: LiveSession, frames: int, amplitude: int) -> None:
    for _ in range(frames):
        session.append_pcm16(tone(FRAME_SAMPLES, amplitude))


def buffer_of(session: LiveSession) -> np.ndarray:
    return session._buffer


# --- the keystone ----------------------------------------------------------

def test_keystone_system_audio_in_the_room_never_reaches_the_transcriber():
    """The one that must never be allowed to go green for the wrong reason.

    The captured audio genuinely contains the system's voice during the
    window — that is what `TTS_AMPLITUDE` frames are — and the transcriber
    sees none of it.
    """
    session = LiveSession(LeakDetector())

    feed(session, 4, PATIENT_AMPLITUDE)                 # 1.0 s of patient
    session.open_speaking_window("U1", duration_ms=1000, tail_ms=200)
    feed(session, 4, TTS_AMPLITUDE)                     # 1.0 s of us, in the room
    session.close_speaking_window("complete")
    session.append_pcm16(tone(200 * 16, TTS_AMPLITUDE))  # 200 ms of room decay
    feed(session, 4, PATIENT_AMPLITUDE)                 # patient again

    committed, partial = asyncio.run(session.process())
    heard = " ".join(s.text for s in committed) + " " + partial
    assert "SYSTEM-VOICE-LEAKED" not in heard, (
        "the system's own voice reached the transcriber — the guarantee is broken")

    # And directly: the whole excluded region of the buffer is silent,
    # while the patient audio either side of it is not.
    window_start = 4 * FRAME_SAMPLES
    window_end = window_start + 1200 * 16          # duration + tail, in samples
    assert np.all(buffer_of(session)[window_start:window_end] == 0.0)
    assert np.max(np.abs(buffer_of(session)[:window_start])) > 0
    assert np.max(np.abs(buffer_of(session)[window_end:])) > 0


def test_the_recording_keeps_the_real_audio():
    """The room is recorded as it was. Only the transcript is of the
    patient alone — `_recording` is the faithful record, and the retention
    sweep and FLAC-on-approval operate on it."""
    session = LiveSession(LeakDetector())
    feed(session, 2, PATIENT_AMPLITUDE)
    session.open_speaking_window("U1", duration_ms=500, tail_ms=200)
    loud = tone(FRAME_SAMPLES, TTS_AMPLITUDE)
    session.append_pcm16(loud)
    session.close_speaking_window("complete")

    recorded = b"".join(session._recording)
    assert loud in recorded, "the recording lost the system's audio"
    assert len(recorded) == 3 * FRAME_BYTES


def test_buffer_receives_silence_not_nothing_so_the_clock_stays_aligned():
    """Dropping the samples would shift every later timestamp relative to
    the recording — the urgency alarm's first-fired times read that clock."""
    session = LiveSession(LeakDetector())
    feed(session, 4, PATIENT_AMPLITUDE)
    session.open_speaking_window("U1", duration_ms=1000, tail_ms=0)
    feed(session, 4, TTS_AMPLITUDE)
    session.close_speaking_window("complete")
    feed(session, 4, PATIENT_AMPLITUDE)

    assert len(buffer_of(session)) == session.recorded_bytes // 2
    assert session.audio_seconds == pytest.approx(3.0)


# --- window arithmetic -----------------------------------------------------

def test_tail_is_applied_after_playback_ends():
    session = LiveSession(LeakDetector())
    session.open_speaking_window("U1", duration_ms=1000, tail_ms=200)
    feed(session, 4, TTS_AMPLITUDE)            # exactly the 1.0 s of playback
    span = session.close_speaking_window("complete")

    assert span["start_byte"] == 0
    assert span["end_byte"] == 4 * FRAME_BYTES + 200 * BYTES_PER_MS
    assert bytes_to_ms(span["end_byte"]) == 1200


def test_missing_speak_ended_closes_at_start_plus_duration_plus_tail():
    """Spec §2.3: the synthesised duration is known, so the fallback is
    exact rather than a guess. There is no timer — the ceiling is set when
    the window opens."""
    session = LiveSession(LeakDetector())
    feed(session, 2, PATIENT_AMPLITUDE)                # 0.5 s before
    start = session.open_speaking_window("U1", duration_ms=1000, tail_ms=200)
    feed(session, 20, TTS_AMPLITUDE)                   # 5 s, no speak_ended ever

    spans = session.speaking_spans()
    assert len(spans) == 1
    assert spans[0]["start_byte"] == start == 2 * FRAME_BYTES
    assert spans[0]["end_byte"] == start + 1200 * BYTES_PER_MS
    assert spans[0]["end_reason"] == "window_ceiling"

    # Audio past the ceiling cannot contain our voice, so it must reach
    # the transcriber — over-excluding costs patient speech for nothing.
    past_ceiling = spans[0]["end_byte"] // 2
    assert np.any(buffer_of(session)[past_ceiling + 100:] != 0.0)


def test_late_speak_ended_is_clamped_to_the_ceiling():
    session = LiveSession(LeakDetector())
    session.open_speaking_window("U1", duration_ms=500, tail_ms=200)
    feed(session, 12, TTS_AMPLITUDE)           # 3 s — far past the 0.7 s ceiling
    span = session.close_speaking_window("complete")
    assert span["end_byte"] == 700 * BYTES_PER_MS


def test_barge_in_closes_the_window_early_with_its_reason():
    session = LiveSession(LeakDetector())
    session.open_speaking_window("U1", duration_ms=5000, tail_ms=200)
    feed(session, 2, TTS_AMPLITUDE)            # cut after 0.5 s
    span = session.close_speaking_window("barge_in")

    assert span["end_reason"] == "barge_in"
    assert span["end_byte"] == 2 * FRAME_BYTES + 200 * BYTES_PER_MS
    # From the cut onward, audio re-enters the transcript path — the cost
    # of gate-and-cut is truncation of the first ~200 ms, not fabrication.
    feed(session, 4, PATIENT_AMPLITUDE)
    assert np.any(buffer_of(session)[span["end_byte"] // 2 + 10:] != 0.0)


def test_a_frame_straddling_the_window_edge_is_muted_only_where_it_overlaps():
    """Frames are 0.25 s and the tail is 200 ms, so straddling is normal.
    Zero-filling only the overlap avoids discarding patient speech that
    happens to share a frame with the tail."""
    session = LiveSession(LeakDetector())
    session.open_speaking_window("U1", duration_ms=100, tail_ms=0)  # 0.1 s
    session.append_pcm16(tone(FRAME_SAMPLES, TTS_AMPLITUDE))        # 0.25 s frame
    session.close_speaking_window("complete")

    buffer = buffer_of(session)
    assert np.all(buffer[:1600] == 0.0), "the overlapping part must be silenced"
    assert np.any(buffer[1700:] != 0.0), "the rest of the frame must survive"


def test_two_windows_do_not_overlap_and_both_are_excluded():
    session = LiveSession(LeakDetector())
    session.open_speaking_window("U1", duration_ms=500, tail_ms=200)
    feed(session, 2, TTS_AMPLITUDE)
    session.close_speaking_window("complete")
    feed(session, 4, PATIENT_AMPLITUDE)
    session.open_speaking_window("U2", duration_ms=500, tail_ms=200)
    feed(session, 2, TTS_AMPLITUDE)
    session.close_speaking_window("complete")

    spans = session.speaking_spans()
    assert len(spans) == 2
    assert spans[0]["end_byte"] <= spans[1]["start_byte"]
    committed, partial = asyncio.run(session.process())
    assert "SYSTEM-VOICE-LEAKED" not in " ".join(s.text for s in committed) + partial


def test_opening_a_second_window_while_one_is_open_is_refused():
    """Queue depth zero (spec §2.3). Overlapping windows would make the
    exclusion span ambiguous, and ambiguity here means a possible leak."""
    session = LiveSession(LeakDetector())
    session.open_speaking_window("U1", duration_ms=500, tail_ms=200)
    with pytest.raises(RuntimeError):
        session.open_speaking_window("U2", duration_ms=500, tail_ms=200)


def test_no_window_means_no_exclusion():
    """`speak_started` never arriving is harmless: nothing was played into
    the room, so there is nothing to exclude (spec §2.3, failed_to_play)."""
    session = LiveSession(LeakDetector())
    feed(session, 4, PATIENT_AMPLITUDE)
    assert session.speaking_spans() == []
    assert np.max(np.abs(buffer_of(session))) > 0, "nothing should have been muted"


def test_close_without_open_is_an_error_not_a_silent_no_op():
    session = LiveSession(LeakDetector())
    with pytest.raises(RuntimeError):
        session.close_speaking_window("complete")


def test_committing_and_dropping_buffer_head_does_not_disturb_later_windows():
    """`process()` drops committed audio from the head of the buffer while
    windows are held as offsets into the recording — the two must not
    interfere."""
    session = LiveSession(LeakDetector())
    feed(session, 20, PATIENT_AMPLITUDE)           # 5 s
    asyncio.run(session.process())                 # commits and drops the head
    start = session.open_speaking_window("U1", duration_ms=1000, tail_ms=200)
    feed(session, 4, TTS_AMPLITUDE)
    span = session.close_speaking_window("complete")

    assert start == 20 * FRAME_BYTES, "window offsets are recording-relative"
    assert span["end_byte"] - span["start_byte"] == 4 * FRAME_BYTES + 200 * BYTES_PER_MS
    committed, partial = asyncio.run(session.process())
    assert "SYSTEM-VOICE-LEAKED" not in " ".join(s.text for s in committed) + partial


# --- bytes are authoritative ----------------------------------------------

def test_byte_offsets_are_exact_and_milliseconds_are_derived():
    """32 bytes per millisecond at 16 kHz mono 16-bit. The ms columns round;
    the byte columns are what finalisation mutes."""
    assert BYTES_PER_MS == 32
    assert bytes_to_ms(32000) == 1000
    session = LiveSession(LeakDetector())
    session.append_pcm16(b"\x00" * 18)            # deliberately not frame-aligned
    assert session.recorded_bytes == 18


# --- the phrase table cannot become a text channel -------------------------

def test_the_protocol_has_no_path_from_client_text_to_audio():
    """Belt and braces on app/speech.py's resolution tests: the only way to
    obtain audio is a ref the server can resolve to its own words."""
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"text": "You'll be fine."})
    # A ref that IS resolvable still yields only the server's own words,
    # whatever else the client attached to it.
    resolved = speech.resolve(
        {"kind": "phrase", "id": "invitation", "text": "You'll be fine."})
    assert resolved.text == speech.render_phrase("invitation")


# ==========================================================================
# Protocol level: the same guarantee through a real WebSocket.
#
# These drive /ws/transcribe with a fake transcriber and a stub speech
# service, so they test the protocol and the exclusion wiring — not Piper
# and not Whisper. Reference resolution is the real thing. Postgres is
# required (sessions are real accounts), so they self-skip without it.

import json        # noqa: E402
import os          # noqa: E402
import secrets     # noqa: E402
import struct      # noqa: E402

import psycopg     # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402

from app import auth, consultations, system_utterances   # noqa: E402
from app import main as appmain                          # noqa: E402


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


class StubSpeech:
    """Fake audio, REAL reference resolution — the logic under test is the
    shipped one; only Piper is stubbed out."""

    def __init__(self):
        self.utterances = {}

    def prepare(self, ref, agenda, *, user_id=None, consultation_id=None,
                doctor=None):
        resolution = speech.resolve(ref, agenda, doctor)
        self.last_doctor = doctor
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


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def speech_state(monkeypatch, tmp_path):
    """Manual app.state (no lifespan), matching tests/test_resilience.py."""
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    appmain.app.state.transcriber = SilentTranscriber()
    appmain.app.state.speech = StubSpeech()
    appmain.app.state.cds_engine = object()   # never invoked: no transcript text
    appmain.app.state.rag = object()
    appmain.app.state.live_sessions = {}
    appmain.app.state.finalize_queue = asyncio.Queue()
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    yield appmain.app.state
    appmain.app.state.live_sessions = {}


def _frame(seq: int, samples: int, amplitude: int) -> bytes:
    return struct.pack(">I", seq) + tone(samples, amplitude)


def _drain_until(ws, wanted, limit=60):
    """Read until one of `wanted` arrives.

    `speak_refused` is ALWAYS accepted, whether asked for or not: without
    that, a test whose speak is unexpectedly refused blocks forever on the
    next receive instead of failing with a useful message.
    """
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("type") in wanted:
            return message
        if message.get("type") == "speak_refused":
            raise AssertionError(
                f"speak refused while waiting for {wanted}: {message['detail']}")
    raise AssertionError(f"none of {wanted} arrived")


def _disclose(ws):
    """Satisfy the hard-rule-4 lock the way a doctor would with the
    checkbox. Question chips and clinical phrases are refused until this
    has happened — that is the point, and it is server-side."""
    ws.send_text(json.dumps({"type": "disclosure_given"}))
    return _drain_until(ws, {"disclosure"})


@needs_db
def test_speak_carrying_text_is_rejected_outright(speech_state):
    """Spec §2.1. Rejected, not sanitised: sanitising would make this a
    filter, and a filter is detection."""
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "text": "You are having a heart attack."}))
        message = _drain_until(ws, {"speak_refused", "speak_ready"})
    assert message["type"] == "speak_refused"
    assert "text" in message["detail"]


@needs_db
def test_speak_with_text_inside_the_ref_is_also_rejected(speech_state):
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation",
                                         "text": "You'll be fine."}}))
        message = _drain_until(ws, {"speak_refused", "speak_ready"})
    assert message["type"] == "speak_refused"


@needs_db
def test_phrase_reference_produces_the_servers_own_words(speech_state):
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        _disclose(ws)
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _drain_until(ws, {"speak_ready", "speak_refused"})
    assert ready["type"] == "speak_ready"
    assert ready["duration_ms"] == 1000
    assert ready["url"] == f"/api/speech/{ready['utterance_id']}.wav"
    # The server tells the client WHAT IT WILL SAY, so the live transcript
    # can log the utterance rather than the button label. This is the
    # server informing the client; the client still cannot supply text.
    assert ready["text"] == speech.render_phrase("invitation")
    assert speech_state.speech.get(ready["utterance_id"]).text == \
        speech.render_phrase("invitation")


@needs_db
def test_an_unknown_phrase_id_is_refused_over_the_protocol(speech_state):
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "reassurance"}}))
        message = _drain_until(ws, {"speak_refused", "speak_ready"})
    assert message["type"] == "speak_refused"


@needs_db
def test_a_second_speak_while_a_window_is_open_is_rejected(speech_state):
    """One utterance at a time, queue depth zero (spec §2.3): overlapping
    windows would make the exclusion span ambiguous."""
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        _disclose(ws)
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        first = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": first["utterance_id"], "seq": 1}))
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "go_on"}}))
        second = _drain_until(ws, {"speak_refused", "speak_ready"})
    assert second["type"] == "speak_refused"
    assert "already in flight" in second["detail"]


@needs_db
def test_receptionist_cannot_open_the_stream_at_all(speech_state):
    """The WS wall is the RBAC: a receptionist never reaches `speak`."""
    client = _client_for(_make_user("receptionist"))
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/transcribe") as ws:
            ws.send_json({"session_id": secrets.token_hex(8)})
            ws.receive_json()


@needs_db
def test_a_foreign_doctor_resuming_the_session_may_not_speak(speech_state):
    """Ownership is checked on `speak` itself, not only at connect."""
    owner, intruder = _make_user("doctor"), _make_user("doctor")
    session_id = secrets.token_hex(8)

    with _client_for(owner).websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ws.send_bytes(_frame(1, 4000, PATIENT_AMPLITUDE))
        _drain_until(ws, {"ack"})

    with _client_for(intruder).websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id, "resume": True})
        _drain_until(ws, {"resume"})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        message = ws.receive_json()
        while message.get("type") not in ("speak_refused", "speak_ready"):
            message = ws.receive_json()
    assert message["type"] == "speak_refused"
    # Ownership is checked BEFORE the disclosure lock, so this is the
    # reason returned even though the intruder also has not disclosed.
    assert "only the doctor running this consultation" in message["detail"]


@needs_db
def test_spans_are_persisted_as_bytes_and_milliseconds(speech_state):
    """The durable artifact both transcription paths read (spec §2.2 step
    5). From here the spans live in the database, not the session object —
    which is why a post-restart finalisation still excludes correctly."""
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        _disclose(ws)
        ws.send_bytes(_frame(1, 4000, PATIENT_AMPLITUDE))       # 0.25 s
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": ready["utterance_id"], "seq": 2}))
        for seq in range(2, 6):
            ws.send_bytes(_frame(seq, 4000, TTS_AMPLITUDE))     # 1.0 s of us
        ws.send_text(json.dumps({"type": "speak_ended",
                                 "utterance_id": ready["utterance_id"],
                                 "seq": 6, "reason": "complete"}))
        ws.send_text("stop")
        done = _drain_until(ws, {"done"})
    cid = done["consultation_id"]

    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert len(rows) == 1
    assert rows[0]["text"] == speech.render_phrase("invitation")
    assert rows[0]["ref_kind"] == "phrase"
    assert rows[0]["end_reason"] == "complete"
    assert rows[0]["started_offset_ms"] == 250   # after the first 0.25 s frame

    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    assert spans == [(8000, 8000 + 4 * 8000 + 200 * BYTES_PER_MS)]


@needs_db
def test_a_failed_to_play_utterance_leaves_no_span(speech_state):
    """`speak_started` never arrives: nothing played into the room, so
    there is nothing to exclude — and the row says so rather than
    inventing a window (spec §2.3)."""
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_bytes(_frame(1, 4000, PATIENT_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "go_on"}}))
        _drain_until(ws, {"speak_ready"})
        ws.send_text("stop")                    # never started playing
        done = _drain_until(ws, {"done"})
    cid = done["consultation_id"]

    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert len(rows) == 1
    assert rows[0]["end_reason"] == "failed_to_play"
    assert rows[0]["started_offset_ms"] is None
    assert asyncio.run(system_utterances.exclusion_spans(cid)) == []


@needs_db
def test_reconnect_cancels_playback_and_never_resumes_it(speech_state):
    """Spec §2.3. The client has stopped playing, so the window must close
    rather than keep excluding live patient audio."""
    doctor = _make_user("doctor")
    session_id = secrets.token_hex(8)
    client = _client_for(doctor)

    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        _disclose(ws)
        ws.send_bytes(_frame(1, 4000, PATIENT_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": ready["utterance_id"], "seq": 2}))
        ws.send_bytes(_frame(2, 4000, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})

    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id, "resume": True})
        _drain_until(ws, {"resume"})
        # Audio after the reconnect must reach the transcript path again.
        ws.send_bytes(_frame(3, 4000, PATIENT_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text("stop")
        done = _drain_until(ws, {"done"})
    cid = done["consultation_id"]

    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert len(rows) == 1
    assert rows[0]["end_reason"] == "cancelled"
    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    assert len(spans) == 1 and spans[0][0] == 8000


@needs_db
def test_speech_events_are_audited(speech_state):
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        _disclose(ws)
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": ready["utterance_id"], "seq": 1}))
        ws.send_bytes(_frame(1, 4000, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended",
                                 "utterance_id": ready["utterance_id"],
                                 "seq": 2, "reason": "barge_in",
                                 "cut_latency_ms": 180}))
        ws.send_text("stop")
        _drain_until(ws, {"done"})

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        actions = [r[0] for r in conn.execute(
            "SELECT action FROM audit_event WHERE action LIKE 'speech.%'"
            " ORDER BY id DESC LIMIT 5")]
    assert "speech.requested" in actions
    assert "speech.barge_in" in actions


# --- the disclosure lock (hard rule 4) -------------------------------------
#
# Enforced SERVER-SIDE, not by a disabled button. A disabled button can be
# re-enabled from the browser console in ten seconds; a server refusal
# cannot. The UI's disabling is a courtesy on top of this.

@needs_db
def test_a_cds_question_is_refused_before_the_disclosure(speech_state):
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": 1, "index": 0}}))
        message = ws.receive_json()
        while message.get("type") not in ("speak_refused", "speak_ready"):
            message = ws.receive_json()
    assert message["type"] == "speak_refused"
    assert "talking to a machine" in message["detail"]


@needs_db
def test_clinical_phrases_are_refused_before_the_disclosure(speech_state):
    client = _client_for(_make_user("doctor"))
    for phrase_id in speech.DISCLOSURE_GATED_PHRASES:
        with client.websocket_connect("/ws/transcribe") as ws:
            ws.send_json({"session_id": secrets.token_hex(8)})
            ws.send_text(json.dumps({"type": "speak",
                                     "ref": {"kind": "phrase", "id": phrase_id}}))
            message = ws.receive_json()
            while message.get("type") not in ("speak_refused", "speak_ready"):
                message = ws.receive_json()
        assert message["type"] == "speak_refused", phrase_id


@needs_db
def test_the_disclosure_itself_is_never_gated(speech_state):
    """It cannot require itself."""
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "disclosure"}}))
        assert _drain_until(ws, {"speak_ready"})["type"] == "speak_ready"


@needs_db
def test_encouragers_are_not_gated(speech_state):
    """"mm-hm" is not a clinical interaction; gating it would make the
    lock feel like a nuisance rather than a rule."""
    client = _client_for(_make_user("doctor"))
    for phrase_id in speech.ENCOURAGER_IDS:
        with client.websocket_connect("/ws/transcribe") as ws:
            ws.send_json({"session_id": secrets.token_hex(8)})
            ws.send_text(json.dumps({"type": "speak",
                                     "ref": {"kind": "phrase", "id": phrase_id}}))
            assert _drain_until(ws, {"speak_ready"})["type"] == "speak_ready", phrase_id


@needs_db
def test_speaking_the_disclosure_through_unlocks_the_agenda(speech_state):
    """And only when it played THROUGH: a cut-off disclosure has not been
    given."""
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "disclosure"}}))
        ready = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": ready["utterance_id"], "seq": 1}))
        ws.send_bytes(_frame(1, 4000, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended",
                                 "utterance_id": ready["utterance_id"],
                                 "seq": 2, "reason": "complete"}))
        assert _drain_until(ws, {"disclosure"})["given"] is True
        # Now a gated phrase goes through.
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        assert _drain_until(ws, {"speak_ready"})["type"] == "speak_ready"


@needs_db
def test_a_cut_off_disclosure_does_not_count(speech_state):
    client = _client_for(_make_user("doctor"))
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "disclosure"}}))
        ready = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": ready["utterance_id"], "seq": 1}))
        ws.send_bytes(_frame(1, 4000, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended",
                                 "utterance_id": ready["utterance_id"],
                                 "seq": 2, "reason": "doctor_stop"}))
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        message = ws.receive_json()
        while message.get("type") not in ("speak_refused", "speak_ready"):
            message = ws.receive_json()
    assert message["type"] == "speak_refused"


@needs_db
def test_the_doctors_attestation_unlocks_and_is_audited(speech_state):
    """The doctor may give the disclosure in their own words instead."""
    doctor = _make_user("doctor")
    with _client_for(doctor).websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "disclosure_given"}))
        assert _drain_until(ws, {"disclosure"})["how"] == "doctor_attested"
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "invitation"}}))
        assert _drain_until(ws, {"speak_ready"})["type"] == "speak_ready"

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(
            "SELECT user_id, at, detail FROM audit_event"
            " WHERE action = 'speech.disclosure_given'"
            " ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == doctor["id"], "the audit row must carry the attesting user"
    assert row[1] is not None, "and its timestamp"
    assert row[2]["how"] == "doctor_attested"


# --- UI faults found in the 2026-07-25 room test ---------------------------

def test_the_live_transcript_logs_what_was_spoken_not_the_button_label():
    """It logged "Disclosure" where the room heard three sentences. A
    record whose whole purpose is fidelity must not show the label, and
    the live page must agree with the review page, which was already
    right."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "addSpoken(msg.text || label);" in html
    assert "Log WHAT WAS SPOKEN, not the button that was pressed" in html


def test_the_disclosure_button_shows_itself_as_given():
    """It returned to looking like an outstanding action and could be
    re-tapped, repeating it. It stays available on purpose — someone may
    join the room — but it must stop looking outstanding."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "'✓ Disclosure given'" in html
    assert ".phrase.given" in html
    assert "tap again only if someone new has joined the room" in html


def test_say_to_patient_buttons_explain_themselves_when_not_connected():
    """They were tappable while disconnected, producing the red "Not
    connected — cannot speak" panel, which reads as a fault when it is
    only a not-started-yet."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "b.disabled = busy || !live || gated;" in html
    assert "Start the consultation first — the system can only speak" in html


# ===========================================================================
# HARD RULE 3 — the doctor always wins (consultations 446/447, 2026-07-25)
#
# In 447 the doctor tapped a long question, wanted to cut it off, and found
# nothing to press. He tapped the chip again — speaking it a second time —
# and finally STOPPED THE WHOLE CONSULTATION RECORDING to silence the
# machine. Ending a consultation is not an acceptable way to cancel an
# utterance.
#
# The control was never absent. `#speakStop` was in the DOM the whole time.
# It was in NORMAL FLOW at the top of `.stack`, so on any page taller than
# the viewport it scrolled out of sight exactly when it was needed. That is
# why these assertions are mostly about POSITION: the failure was never
# "does it exist" but "can it be seen".
#
# Scope, stated plainly: no browser is driven anywhere in this suite, so
# these check the page's source, not its rendering. What they would have
# caught is the actual regression — a Stop control that scrolls away.

def _live_html() -> str:
    from pathlib import Path

    return Path("app/static/live.html").read_text()


def test_a_stop_control_exists_inside_the_speaking_bar():
    html = _live_html()
    bar = html[html.index('id="speakingBar"'):]
    bar = bar[:bar.index("</div>")]
    assert 'id="speakStop"' in bar, "Stop must live on the speaking bar itself"
    assert ">Stop<" in bar


def test_the_speaking_bar_is_fixed_to_the_viewport():
    """THE regression. In normal flow it scrolled out of view — which is
    how a doctor came to have no way of stopping the machine talking."""
    html = _live_html()
    css = html[html.index("  .speaking {"):html.index("  .speaking.on {")]
    assert "position: fixed" in css, (
        "the speaking bar must not return to normal flow — consultation 447")
    assert "z-index" in css


def test_the_speaking_bar_is_outside_the_scrolling_stack():
    """Belt and braces on the CSS: it must not be a child of .stack, so a
    future layout change cannot quietly re-parent it into the scroll."""
    html = _live_html()
    # The stack's last child is the live-transcript pane; the bar must come
    # after the stack closes, at document level, not inside it.
    stack_start = html.index('<div class="stack">')
    last_pane = html.index('<!-- 4. LIVE TRANSCRIPT')
    bar = html.index('id="speakingBar"')
    assert 'id="speakingBar"' not in html[stack_start:last_pane]
    assert bar > last_pane
    closing = html.index("\n</div>\n", last_pane)   # closes .stack
    assert bar > closing, "the speaking bar must not be a child of .stack"


def test_the_bar_is_shown_exactly_while_a_speaking_window_is_open():
    """Rendered during the window, hidden outside it: setSpeakingUI(true)
    on playback start, and every path that ends an utterance calls
    setSpeakingUI(false)."""
    html = _live_html()
    assert "speakingBar.classList.toggle('on', on);" in html
    assert ".speaking.on { display: flex; }" in html
    assert "setSpeakingUI(true, label);" in html
    # Every termination path clears it.
    assert html.count("setSpeakingUI(false, '');") >= 2


def test_stop_cancels_immediately_and_is_recorded_as_doctor_stop():
    html = _live_html()
    assert "() => stopSpeaking('doctor_stop'));" in html
    stop = html[html.index("function stopSpeaking"):]
    stop = stop[:stop.index("\n}")]
    assert "audio.pause()" in stop, "Stop must halt playback, not merely tell the server"
    assert "speak_ended" in stop and "reason: reason" in stop


def test_escape_is_a_second_one_tap_path():
    """A false stop costs a re-tap; not being able to stop cost a whole
    consultation."""
    html = _live_html()
    assert "e.key === 'Escape' && speaking" in html
    assert "stopSpeaking('doctor_stop')" in html


def test_an_already_asked_question_shows_that_it_was_asked():
    """447 spoke the same question three times because nothing showed it
    had gone out. Re-asking stays allowed — the panel lags and repetition
    is sometimes right — but it must be visible."""
    html = _live_html()
    assert "askedQuestions" in html
    assert "li.classList.toggle('asked', asked);" in html
    assert "content: ' ✓ asked'" in html
    # Tracked by TEXT, not index: the index moves when the agenda revises.
    assert "askedQuestions.add(msg.text)" in html
    # And it must not disable the chip.
    assert "asked ? '↻' : '🔊'" in html


# ===========================================================================
# THE STANDING RULE (adopted 2026-07-25, third instance in one evening)
#
#   Never swallow an action and explain it in a banner. Either PERFORM the
#   action, or VISIBLY DISABLE the control with the reason attached to the
#   control itself.
#
# Three controls did nothing that evening while a small banner elsewhere
# explained why: the "Not connected — cannot speak" panel, the
# finalisation page stuck on "processing", and the sound-check offer
# eating question-chip taps. The owner missed all three. This is an
# accessibility requirement, not a preference — a quiet explanation placed
# away from the control just pressed is, for a dyslexic reader with ADHD,
# no explanation at all, and in a consultation room it is no explanation
# for anyone.

def test_the_rule_is_written_down_in_the_page():
    html = _live_html()
    assert "STANDING RULE FOR THIS PAGE — never swallow an action." in html
    assert "VISIBLY DISABLE the control with the" in html
    assert "reason attached to the control itself" in html
    assert "dyslexic with ADHD" in html, (
        "the rule must keep its reason, or it reads as a style preference")


def test_speak_controls_go_dead_looking_when_the_socket_drops():
    """They stayed enabled after a drop, so a tap produced the "Not
    connected" banner — a swallowed action explained elsewhere."""
    html = _live_html()
    close = html[html.index("function onWsClose()"):]
    close = close[:close.index("\n}")]
    assert "refreshSpeechControls();" in close


def test_the_not_connected_banner_is_only_a_last_resort():
    html = _live_html()
    assert "LAST-RESORT guard only" in html
    assert "not as the way the doctor finds out" in html


def test_the_mic_picker_is_visibly_disabled_during_recording():
    """It used to `return` silently while recording, keeping its pointer
    cursor and chevron. The .mic.disabled style existed and nothing ever
    applied it."""
    html = _live_html()
    assert "function refreshMicPickerState()" in html
    assert "micPill.classList.toggle('disabled', recording);" in html
    assert "Microphone cannot be changed during a consultation" in html
    assert ".mic.disabled .chev { display: none; }" in html


def test_every_disabled_speak_control_carries_its_reason():
    """The reason is on the control, via title, not in a banner."""
    html = _live_html()
    refresh = html[html.index("function refreshSpeechControls()"):]
    refresh = refresh[:refresh.index("\nfunction ")]
    assert "b.disabled =" in refresh and "b.title =" in refresh
    assert "Start the consultation first" in refresh
    assert "soundCheckBtn.title" in refresh
