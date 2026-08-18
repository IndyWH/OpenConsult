"""Phase 7a session 3 — the barge-in detector (spec build item 5, Part 9 D5).

What is genuinely covered here, stated plainly: the playback-envelope
function, the server's config plumbing (the `barge_in` block on
speech_config, the loopback level read from the `speech.sound_check`
audit rows, the envelope riding speak_ready only when the flag is up),
and the client's decision object executed under Node (the
tests/test_silence_nudge_client.py convention). No real microphone and no
real echo are involved — the detector's accuracy in the room is exactly
what `scripts/calibrate_barge_in.py` exists to measure, and D5's target
is met or missed there, not here.

The two standing constraints — the detector stream never wired to the
mic meter, the disclosure never gaining an interruption line — are
enforced separately in tests/test_barge_in_constraints.py.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import audit, auth, consultations, speech, system_utterances
from app import main as appmain


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

NODE = shutil.which("node")


# --- helpers ----------------------------------------------------------------

def _wav(*segments: tuple[float, int], rate: int = 16000) -> bytes:
    """Mono 16-bit WAV of consecutive (seconds, amplitude) sine segments."""
    parts = []
    for seconds, amplitude in segments:
        t = np.arange(int(rate * seconds))
        parts.append((amplitude * np.sin(2 * np.pi * 440 * t / rate))
                     .astype(np.int16))
    samples = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return out.getvalue()


# --- the playback envelope (pure) -------------------------------------------

def test_envelope_is_normalised_and_follows_the_playback_loudness():
    """One value per 100 ms window, 0..1 against the utterance's own
    loudest window — the shape the threshold is proportional to."""
    envelope = speech.playback_envelope(_wav((0.5, 16000), (0.5, 1600)))
    assert len(envelope) == 10
    assert max(envelope) == 1.0
    assert all(v >= 0.99 for v in envelope[:5]), "loud half must read ~1.0"
    assert all(v == pytest.approx(0.1, rel=0.05) for v in envelope[5:]), (
        "the quiet half is a tenth of the amplitude, so a tenth of the RMS")


def test_envelope_of_pure_silence_is_all_zero_not_a_division_error():
    envelope = speech.playback_envelope(_wav((0.3, 0)))
    assert envelope == [0.0, 0.0, 0.0]


def test_envelope_covers_a_partial_trailing_window():
    assert len(speech.playback_envelope(_wav((1.05, 8000)))) == 11


def test_envelope_raises_on_malformed_audio():
    """The caller degrades to absolute-floor detection, never to silence —
    but this function itself must not guess at garbage."""
    with pytest.raises(Exception):
        speech.playback_envelope(b"RIFF not really a wav")


def test_envelope_rejects_non_16_bit_audio():
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)          # 8-bit
        w.setframerate(16000)
        w.writeframes(b"\x80" * 1600)
    with pytest.raises(ValueError):
        speech.playback_envelope(out.getvalue())


# --- shipped defaults -------------------------------------------------------

def test_barge_in_ships_disabled_with_the_documented_defaults(tmp_path):
    """BARGE_IN_ENABLED is FALSE until calibration meets both sides of the
    D5 target, and flipping it is the owner's act. Run from a directory
    with no .env and with the machine's own BARGE_IN_* stripped, so this
    asserts the SHIPPED defaults rather than this machine's settings."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("BARGE_IN")}
    repo = str(Path(__file__).resolve().parent.parent)
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {repo!r});"
         "from app import speech;"
         "print(speech.BARGE_IN_ENABLED, speech.BARGE_IN_MIN_MS,"
         " speech.BARGE_IN_MARGIN, speech.BARGE_IN_RMS_THRESHOLD)"],
        capture_output=True, text=True, cwd=tmp_path, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["False", "150", "2.0", "0.02"]


def test_the_example_env_ships_barge_in_off():
    assert "BARGE_IN_ENABLED=false" in Path(".env.example").read_text()


# --- the threshold scale (Part 10 amendment, 2026-07-30) --------------------

def test_the_scale_is_the_residual_when_the_row_carries_one():
    scale = speech.barge_in_scale({"peak_rms": 0.4,
                                   "residual": {"peak_rms": 0.012}})
    assert scale == {"raw_peak_rms": 0.4, "residual_peak_rms": 0.012,
                     "clamped": None, "anomaly": None}


def test_the_scale_falls_back_to_raw_without_a_residual():
    """Conservative on purpose: a raw-scaled threshold misses soft
    interruptions, and a miss is hard mute — the blessed failure."""
    scale = speech.barge_in_scale({"peak_rms": 0.4})
    assert scale["residual_peak_rms"] is None
    assert scale["raw_peak_rms"] == 0.4
    assert speech.barge_in_scale(None) == {
        "raw_peak_rms": None, "residual_peak_rms": None,
        "clamped": None, "anomaly": None}


def test_a_residual_far_above_raw_is_clamped_and_reported_as_an_anomaly():
    """Beyond what the window-length effect can explain (x2, the sqrt of
    the two analysers' fftSize ratio), residual > raw is still wrong — a
    gain difference or a stream mix-up. The value is clamped to the raw
    bound and the anomaly handed back — never silently used, never
    silently dropped. (Updated 2026-08-18: this pin used to say ANY excess
    was physically wrong; see the test below for the expected case.)"""
    scale = speech.barge_in_scale({"peak_rms": 0.1,
                                   "residual": {"peak_rms": 0.3}})
    assert scale["residual_peak_rms"] == 0.1
    assert scale["anomaly"] == {"residual_peak_rms": 0.3, "raw_peak_rms": 0.1,
                                "ratio": 3.0}
    assert scale["clamped"] is None


def test_a_residual_modestly_above_raw_is_the_expected_effect_clamped_not_an_anomaly():
    """The read-only analysis of the 2026-08-18 batches: on most MacBook
    Air readings the residual PEAK exceeded the raw PEAK (0.24 vs 0.14)
    although the residual MEAN sat below the raw mean — because the
    detector stream's analyser reads ~11 ms windows without AGC and the
    main stream's ~43 ms windows with AGC, so the two peaks are not one
    scale and the shorter window's may exceed the longer's by up to x2
    for the same signal. That is the measurement, not the acoustics: the
    value is still clamped to raw (the conservative bound, unchanged), the
    excess is reported as `clamped` for the log, and no anomaly is raised.
    Deliberately repinned from "any excess is an anomaly"."""
    assert speech.RESIDUAL_EXCESS_MAX == 2.0
    scale = speech.barge_in_scale({"peak_rms": 0.131,
                                   "residual": {"peak_rms": 0.24}})
    assert scale["residual_peak_rms"] == 0.131                # clamp unchanged
    assert scale["anomaly"] is None
    assert scale["clamped"] == {"residual_peak_rms": 0.24, "raw_peak_rms": 0.131,
                                "ratio": pytest.approx(1.832)}
    # Exactly at the bound is still the expected case; just over is not.
    at_bound = speech.barge_in_scale({"peak_rms": 0.1, "residual": {"peak_rms": 0.2}})
    assert at_bound["clamped"] is not None and at_bound["anomaly"] is None
    over = speech.barge_in_scale({"peak_rms": 0.1, "residual": {"peak_rms": 0.2001}})
    assert over["anomaly"] is not None and over["clamped"] is None
    # residual <= raw: neither.
    plain = speech.barge_in_scale({"peak_rms": 0.4, "residual": {"peak_rms": 0.4}})
    assert plain["clamped"] is None and plain["anomaly"] is None


# --- audit read: the loopback level -----------------------------------------

@needs_db
def test_latest_detail_returns_the_newest_row_for_that_user_only():
    auth.ensure_schema()
    audit.ensure_schema()
    mine = asyncio.run(auth.create_user(
        f"doctor_{secrets.token_hex(4)}", "test-password-123", "Doctor", "doctor"))
    other = asyncio.run(auth.create_user(
        f"doctor_{secrets.token_hex(4)}", "test-password-123", "Doctor", "doctor"))
    asyncio.run(audit.log(mine["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.03, "device_label": "Old speakers"}))
    asyncio.run(audit.log(mine["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.05, "device_label": "Speakers"}))
    asyncio.run(audit.log(other["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.9, "device_label": "Not mine"}))

    detail = asyncio.run(audit.latest_detail("speech.sound_check", mine["id"]))
    assert detail == {"peak_rms": 0.05, "device_label": "Speakers"}
    assert asyncio.run(audit.latest_detail("speech.sound_check", -1)) is None


# --- server plumbing over the WebSocket -------------------------------------

class StubSpeech:
    """Fake audio, REAL reference resolution (test_speech_exclusion's
    convention) — but with a genuine WAV so the envelope path is the
    shipped one, not a special case."""

    def __init__(self, wav_bytes: bytes | None = None):
        self.utterances = {}
        self.wav_bytes = wav_bytes if wav_bytes is not None else _wav(
            (0.5, 16000), (0.5, 1600))

    def prepare(self, ref, agenda, *, user_id=None, consultation_id=None,
                doctor=None):
        resolution = speech.resolve(ref, agenda, doctor)
        utterance = speech.Utterance(
            utterance_id=secrets.token_hex(8), text=resolution.text, voice="stub",
            wav=self.wav_bytes, duration_ms=1000, synth_ms=1,
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
def barge_env(monkeypatch, tmp_path):
    """app.state install/restore per test_speech_exclusion.py's
    restore-in-finally discipline (the 2026-07-28 ordering incident,
    HANDOVER 9d)."""
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    audit.ensure_schema()
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": StubSpeech(),
        "cds_engine": object(),
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


def _drain_until(ws, wanted, limit=60):
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("type") in wanted:
            return message
        if message.get("type") == "speak_refused":
            raise AssertionError(
                f"speak refused while waiting for {wanted}: {message['detail']}")
    raise AssertionError(f"none of {wanted} arrived")


@needs_db
def test_speech_config_ships_the_detector_disabled(barge_env, monkeypatch):
    """The shipped state: enabled false, no audit read, and speak_ready
    without an envelope — byte-identical protocol to session 2."""
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", False)
    client = _client_for(_make_user())
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        config = _drain_until(ws, {"speech_config"})
        assert config["barge_in"]["enabled"] is False
        assert config["barge_in"]["loopback_peak_rms"] is None
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "mm-hm"}}))
        ready = _drain_until(ws, {"speak_ready"})
        assert "envelope" not in ready


@needs_db
def test_enabled_config_reads_the_loopback_from_this_doctors_audit_rows(
        barge_env, monkeypatch):
    """The threshold's input is READ from the newest speech.sound_check
    row — measured in the room, never re-measured (spec Part 10.5)."""
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    doctor = _make_user()
    asyncio.run(audit.log(doctor["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.031, "noise_floor_rms": 0.004,
                           "device_label": "Room speakers"}))
    client = _client_for(doctor)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        config = _drain_until(ws, {"speech_config"})
    block = config["barge_in"]
    assert block["enabled"] is True
    assert block["loopback_peak_rms"] == pytest.approx(0.031)
    assert block["loopback_device"] == "Room speakers"
    assert block["min_ms"] == speech.BARGE_IN_MIN_MS
    assert block["margin"] == speech.BARGE_IN_MARGIN
    assert block["abs_floor"] == speech.BARGE_IN_RMS_THRESHOLD


@needs_db
def test_the_residual_reaches_the_client_through_speech_config(
        barge_env, monkeypatch):
    """Part 10 amendment: the threshold scale the client receives is the
    detector-stream residual from the newest reading, with the raw
    loopback alongside as the sanity bound."""
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    doctor = _make_user()
    asyncio.run(audit.log(doctor["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.41, "noise_floor_rms": 0.004,
                           "device_label": "Room speakers",
                           "residual": {"peak_rms": 0.011, "mean_rms": 0.006,
                                        "series": [0.03, 0.01, 0.006],
                                        "window_ms": 250}}))
    client = _client_for(doctor)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        config = _drain_until(ws, {"speech_config"})
    block = config["barge_in"]
    assert block["residual_peak_rms"] == pytest.approx(0.011)
    assert block["loopback_peak_rms"] == pytest.approx(0.41)


@needs_db
def test_a_doctor_with_no_sound_check_rows_gets_a_null_loopback(
        barge_env, monkeypatch):
    """No reading means no echo prediction: the client falls back to its
    absolute floor rather than to an invented number."""
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    client = _client_for(_make_user())
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        config = _drain_until(ws, {"speech_config"})
    assert config["barge_in"]["enabled"] is True
    assert config["barge_in"]["loopback_peak_rms"] is None


@needs_db
def test_speak_ready_carries_the_envelope_when_enabled(barge_env, monkeypatch):
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    client = _client_for(_make_user())
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "mm-hm"}}))
        ready = _drain_until(ws, {"speak_ready"})
    assert ready["envelope_window_ms"] == speech.ENVELOPE_WINDOW_MS
    envelope = ready["envelope"]
    assert len(envelope) == 10 and max(envelope) == 1.0
    assert envelope[-1] == pytest.approx(0.1, rel=0.05)


@needs_db
def test_a_bad_wav_degrades_to_no_envelope_never_to_no_speech(
        barge_env, monkeypatch):
    """A comfort feature must not stop the system speaking: envelope
    computation failing leaves speak_ready intact, just envelope-less."""
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    appmain.app.state.speech = StubSpeech(wav_bytes=b"RIFF")
    client = _client_for(_make_user())
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        ws.send_text(json.dumps({"type": "speak",
                                 "ref": {"kind": "phrase", "id": "mm-hm"}}))
        ready = _drain_until(ws, {"speak_ready"})
    assert "envelope" not in ready
    assert ready["text"] == "Mm-hm."


# --- the audit row's shape, with and without a residual ---------------------

@needs_db
def test_the_row_carries_the_residual_when_measured(barge_env):
    doctor = _make_user()
    client = _client_for(doctor)
    residual = {"peak_rms": 0.031, "mean_rms": 0.012,
                "series": [0.05, 0.02, 0.008, 0.007], "window_ms": 250}
    result = client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 2e-4, "peak_rms": 0.4, "answer": "yes",
        "device_label": "Room speakers",
        "chain": {"ec": False, "ns": True, "agc": True},
        "residual": residual})
    assert result.status_code == 200
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        detail = conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'speech.sound_check'"
            " ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert detail["residual"] == residual
    assert "residual_unavailable" not in detail


@needs_db
def test_a_missing_residual_is_visible_never_a_silent_zero(barge_env):
    """The reading stores raw-only AND says so: the row carries WHY there
    is no residual — the client's reason when it sent one, 'not measured'
    when it sent nothing at all (an old client)."""
    doctor = _make_user()
    client = _client_for(doctor)
    client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 2e-4, "peak_rms": 0.4, "answer": "yes",
        "residual": None, "residual_unavailable": "Permission denied"})
    client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 2e-4, "peak_rms": 0.4, "answer": "yes"})
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        details = [r[0] for r in conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'speech.sound_check'"
            " ORDER BY id DESC LIMIT 2")]
    assert details[0]["residual_unavailable"] == "not measured"
    assert details[1]["residual_unavailable"] == "Permission denied"
    for detail in details:
        assert "residual" not in detail


@needs_db
def test_the_clamp_anomaly_fires_when_residual_exceeds_the_raw_bound(
        barge_env, monkeypatch):
    """Beyond the window-length bound (here x3), residual > raw is still
    unexplained: the client receives the clamped value and the anomaly is
    AUDITED — something wrong must leave a record, not a quietly corrected
    number. (The expected within-bound excess is the next test.)"""
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    doctor = _make_user()
    asyncio.run(audit.log(doctor["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.1, "device_label": "Room speakers",
                           "residual": {"peak_rms": 0.3, "series": [0.3]}}))
    client = _client_for(doctor)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": secrets.token_hex(8)})
        config = _drain_until(ws, {"speech_config"})
    assert config["barge_in"]["residual_peak_rms"] == pytest.approx(0.1)
    assert config["barge_in"]["loopback_peak_rms"] == pytest.approx(0.1)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(
            "SELECT detail FROM audit_event"
            " WHERE action = 'speech.barge_in_anomaly'"
            " ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    assert row[0]["kind"] == "residual_exceeds_raw_loopback"
    assert row[0]["residual_peak_rms"] == pytest.approx(0.3)
    assert row[0]["raw_peak_rms"] == pytest.approx(0.1)


@needs_db
def test_the_expected_excess_is_clamped_and_logged_not_audited(barge_env, monkeypatch, caplog):
    """The 2026-08-18 MacBook case: residual peak 0.24 over raw 0.131 is the
    window-length/AGC effect. The client still receives the clamped value
    (the conservative bound is unchanged); no anomaly row is written; the
    clamp is logged so it is not silent."""
    import logging
    monkeypatch.setattr(speech, "BARGE_IN_ENABLED", True)
    doctor = _make_user()
    asyncio.run(audit.log(doctor["id"], "speech.sound_check", None, None,
                          {"peak_rms": 0.131, "device_label": "MacBook Air Speakers",
                           "residual": {"peak_rms": 0.24, "series": [0.05, 0.088]}}))
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        before = conn.execute("SELECT count(*) FROM audit_event"
                              " WHERE action = 'speech.barge_in_anomaly'").fetchone()[0]
    client = _client_for(doctor)
    with caplog.at_level(logging.INFO, logger="app.main"):
        with client.websocket_connect("/ws/transcribe") as ws:
            ws.send_json({"session_id": secrets.token_hex(8)})
            config = _drain_until(ws, {"speech_config"})
    assert config["barge_in"]["residual_peak_rms"] == pytest.approx(0.131)
    assert config["barge_in"]["loopback_peak_rms"] == pytest.approx(0.131)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        after = conn.execute("SELECT count(*) FROM audit_event"
                             " WHERE action = 'speech.barge_in_anomaly'").fetchone()[0]
    assert after == before, "the expected excess is not an anomaly"
    assert any("window-length/AGC effect; clamped to raw" in r.getMessage()
               for r in caplog.records)


# --- the client's decision object, executed under Node ----------------------

def _extract_barge_in() -> str:
    source = Path("app/static/live.html").read_text()
    start = source.index("const bargeIn = {")
    return source[start:source.index("\n};", start) + 3]


_HARNESS = """
%(barge_in)s
const out = {};
bargeIn.configure({enabled: true, min_ms: 150, margin: 2.0, abs_floor: 0.02,
                   loopback_peak_rms: 0.05, loopback_device: 'Speakers'});
out.enabled = bargeIn.enabled;

// The envelope-proportional threshold: loud playback demands more energy.
bargeIn.begin([1.0, 0.1], 100, 0);
out.thresholdLoud = bargeIn.threshold(50);     // 2.0 * 0.05 * 1.0
out.thresholdQuiet = bargeIn.threshold(150);   // the absolute floor bites
out.thresholdPastEnd = bargeIn.threshold(1000);// clamped to the last window

// Residual echo below the margin never cuts, however long it lasts...
out.echoCut = [bargeIn.sample(0.08, 0), bargeIn.sample(0.08, 60),
               bargeIn.sample(0.08, 99)];
// ...while the SAME level during the quiet window is real energy, and a
// sustained run of it cuts with its measured latency.
out.quietOnset = bargeIn.sample(0.08, 100);
out.quietEarly = bargeIn.sample(0.08, 200);
out.quietCut = bargeIn.sample(0.08, 260);

// A dip below the threshold resets the onset — a spike is not speech.
bargeIn.begin(null, null, 0);                  // no envelope: floor only
out.dipA = bargeIn.sample(0.5, 0);
out.dipB = bargeIn.sample(0.001, 50);
out.dipC = bargeIn.sample(0.5, 100);
out.dipD = bargeIn.sample(0.5, 200);
out.dipE = bargeIn.sample(0.5, 260);
out.noEnvThreshold = bargeIn.threshold(0);

bargeIn.end();
out.afterEndOnset = bargeIn.onsetAt;
out.afterEndEnvelope = bargeIn.envelope;

// Part 10 amendment: with a residual reading the threshold scales by
// what the detector's canceller LEAVES of our playback, not by the raw
// loopback — which is what lets quiet real speech (0.056 RMS) cross it.
bargeIn.configure({enabled: true, min_ms: 150, margin: 2.0, abs_floor: 0.02,
                   loopback_peak_rms: 0.41, residual_peak_rms: 0.015});
bargeIn.begin([1.0, 0.1], 100, 0);
out.residualThresholdLoud = bargeIn.threshold(50);    // 2.0 * 0.015
out.residualThresholdQuiet = bargeIn.threshold(150);  // the floor bites
out.softSpeechCrosses = 0.056 >= bargeIn.threshold(50);

// A disabled config stays disabled — the client never self-enables.
bargeIn.configure({enabled: false});
out.disabled = bargeIn.enabled;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_shipped_detector_logic_executed_under_node():
    script = _HARNESS % {"barge_in": _extract_barge_in()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)

    assert out["enabled"] is True
    assert out["thresholdLoud"] == pytest.approx(0.1)
    assert out["thresholdQuiet"] == pytest.approx(0.02)
    assert out["thresholdPastEnd"] == pytest.approx(0.02)

    assert out["echoCut"] == [None, None, None], (
        "predicted residual echo must never fire the cut")
    assert out["quietOnset"] is None and out["quietEarly"] is None
    assert out["quietCut"] == 160, "sustained real energy cuts, with latency"

    assert out["dipA"] is None and out["dipB"] is None
    assert out["dipC"] is None and out["dipD"] is None
    assert out["dipE"] == 160, "the run restarts after a dip"
    assert out["noEnvThreshold"] == pytest.approx(0.02)

    assert out["afterEndOnset"] is None and out["afterEndEnvelope"] is None

    assert out["residualThresholdLoud"] == pytest.approx(0.03)
    assert out["residualThresholdQuiet"] == pytest.approx(0.02)
    assert out["softSpeechCrosses"] is True, (
        "the amendment's whole point: quiet speech must clear a "
        "residual-derived threshold where the raw-derived one (0.82 here) "
        "was unreachable")

    assert out["disabled"] is False


def test_the_cut_goes_through_the_stop_buttons_own_path():
    """Same server-audited path as the Stop button, with the end_reason
    telling a barge-in apart from a manual stop, and the measured latency
    riding speak_ended for the server's `cut_latency_ms` column."""
    source = Path("app/static/live.html").read_text()
    assert "stopSpeaking('barge_in', latency)" in source
    assert "cut_latency_ms: Math.round(cutLatencyMs)" in source
    # Detection runs ONLY while a system utterance is playing.
    assert "if (!speaking || !bargeAnalyser" in source
    # The stream lives only while recording; Stop tears it down.
    assert "stopBargeDetector();" in source
