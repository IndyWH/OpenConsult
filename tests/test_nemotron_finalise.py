"""Task 13 item 8: Stop and finalisation with SPEECH_PIPELINE=nemotron.

The final transcript is built from the live lines stored as they arrived.
Pinned by making the other path impossible: unload_medgemma and
transcribe_and_diarise are replaced with functions that FAIL the test if
called — so "nothing unloads, nothing loads" is asserted, not hoped.

Also pinned, on this path:
- the first-speaker rule, as today; "Only the patient" labels every line
  Patient and raises the single-voice notice, as today;
- the silence invariant still drops a line inside Alba's span;
- the trailing-audio rule (S4) still refuses on untranscribed speech;
- no confidence is invented: turns carry NULL, S2 is unmeasured, and every
  transcript is FLAGGED, approval waiting on the acknowledgement (owner);
- an engine failure, or a Stop flush that does not answer in time, REFUSES
  — no transcript from a partial flush, even with the gate's break-glass off;
- the review tools still work: line edit, label change, Swap, Regenerate;
- a whisper consultation (no pipeline recorded) still takes today's path.
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

from app import (auth, consultations, finalize, live_segments, notes, raw_segments,
                 speech_pipeline, system_utterances, transcript_quality)
from app import main as appmain


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

SR = 16000
FAKE = Path(__file__).resolve().parent / "fake_speech_worker.py"


def _write_wav(path: Path, seconds: float, speech: list[tuple[float, float]]) -> None:
    audio = np.zeros(int(seconds * SR), dtype=np.float32)
    t = np.arange(audio.size) / SR
    for a, b in speech:
        idx = (t >= a) & (t < b)
        audio[idx] = 0.2 * np.sin(2 * np.pi * 220 * t[idx])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype("<i2").tobytes())


def _line(i, speaker, start, end, text):
    return {"id": i, "speaker": speaker, "start": start, "end": end, "text": text}


LINES = [_line(0, 0, 0.5, 2.5, "Good morning, what brings you in today?"),
         _line(1, 1, 3.0, 5.5, "I have had a tight pain in my chest for two weeks."),
         _line(2, 0, 6.0, 8.0, "Does it come on when you walk uphill?"),
         _line(3, 1, 8.5, 10.5, "Yes, and it goes when I rest.")]
SPEECH = [(ln["start"], ln["end"]) for ln in LINES]


@pytest.fixture()
def setup(monkeypatch, tmp_path):
    for module in (auth, consultations, system_utterances, raw_segments, live_segments):
        module.ensure_schema()

    async def must_not_unload():
        raise AssertionError("the CDS model must not be unloaded on the nemotron path")

    def must_not_transcribe(*args, **kwargs):
        raise AssertionError("WhisperX/pyannote must not run on the nemotron path")

    drafted: list[list[dict]] = []

    async def fake_note(turns):
        drafted.append(turns)
        return {"reasoning": "", "subjective": [{"text": "Chest pain.", "turns": [1]}],
                "objective": [], "assessment": [], "plan": []}

    monkeypatch.setattr(finalize, "unload_medgemma", must_not_unload)
    monkeypatch.setattr(finalize, "transcribe_and_diarise", must_not_transcribe)
    monkeypatch.setattr(finalize, "draft_note", fake_note)
    doctor = asyncio.run(auth.create_user(f"doc_{secrets.token_hex(4)}", "test-password-123",
                                          "Doctor", "doctor"))
    return {"tmp": tmp_path, "drafted": drafted, "doctor": doctor}


def _nemotron_consultation(setup, lines=LINES, speech=SPEECH, seconds=12.0,
                           failure=None, declared=None) -> tuple[int, str]:
    cid = asyncio.run(consultations.create_consultation(None, setup["doctor"]["id"]))
    wav = setup["tmp"] / f"consultation_{cid}.wav"
    _write_wav(wav, seconds, speech)
    sid = f"s_{secrets.token_hex(4)}"
    asyncio.run(live_segments.save(sid, lines))
    asyncio.run(live_segments.link(sid, cid))
    asyncio.run(consultations.set_speech_pipeline(cid, "nemotron", failure))
    if declared is not None:
        asyncio.run(consultations.declare_speakers(cid, declared))
    return cid, str(wav)


def _turns(cid):
    return asyncio.run(consultations.get_turns(cid))


def _consultation(cid):
    return asyncio.run(consultations.get_consultation(cid))


def _client(user) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


# --- the transcript from the stored lines ------------------------------------------

def test_stop_builds_the_transcript_from_the_stored_lines_with_no_model_swap(setup):
    cid, wav = _nemotron_consultation(setup)
    asyncio.run(finalize.finalize_consultation(cid, wav))   # the queue's own entry point

    c = _consultation(cid)
    assert c["status"] == "awaiting_review"
    turns = _turns(cid)
    assert [t["text"] for t in turns] == [ln["text"] for ln in LINES]
    # The first-speaker rule, as today: speaker 0 opened, so speaker 0 is Doctor.
    assert [t["role"] for t in turns] == ["Doctor", "Patient", "Doctor", "Patient"]
    assert all(t["confidence"] is None for t in turns)      # not measured, never invented
    assert c["speakers_used"] == finalize.DEFAULT_SPEAKERS
    raw = asyncio.run(raw_segments.for_consultation(cid))
    assert [r["cluster"] for r in raw] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00", "SPEAKER_01"]
    assert all(r["confidence"] is None for r in raw)
    assert len(setup["drafted"]) == 1                      # straight on to the note


def test_every_nemotron_transcript_is_flagged_confidence_not_checked(setup):
    cid, wav = _nemotron_consultation(setup)
    asyncio.run(finalize.finalize_consultation(cid, wav))
    c = _consultation(cid)
    assert c["quality_outcome"] == transcript_quality.OUTCOME_FLAGGED
    signals = c["quality_signals"]
    assert signals["s2_confidence"]["weighted_mean"] is None          # S2 unmeasured
    assert signals["speech_pipeline"]["confidence_measured"] is False
    verdict = transcript_quality.evaluate(signals)
    assert [f["signal"] for f in verdict["flags"]] == ["P2"]
    # Approval waits on the acknowledged banner, as for every flag.
    client = _client(setup["doctor"])
    blocked = client.post(f"/api/consultations/{cid}/approve", json={"text": "x"})
    assert blocked.status_code == 409 and "acknowledge the notice first" in blocked.json()["error"]


def test_only_the_patient_labels_every_line_patient_and_raises_the_notice(setup):
    cid, wav = _nemotron_consultation(setup, declared=1)
    asyncio.run(finalize.finalize_consultation(cid, wav))
    c = _consultation(cid)
    assert {t["role"] for t in _turns(cid)} == {"Patient"}
    assert c["single_voice_detected"] is True and c["speakers_used"] == 1
    assert len(_turns(cid)) == 4                            # boundaries kept, as today


def test_a_line_inside_albas_span_is_dropped_by_the_silence_invariant(setup):
    alba = _line(9, 1, 11.0, 11.8, "Thank you, I will pass that on to the doctor.")
    cid, wav = _nemotron_consultation(setup, lines=LINES + [alba], seconds=12.0)
    asyncio.run(system_utterances.save(cid, [{
        "utterance_id": "u1", "text": "Thank you, I will pass that on to the doctor.",
        "ref_kind": "phrase", "start_byte": int(10.9 * SR) * 2, "end_byte": int(11.9 * SR) * 2}]))
    asyncio.run(finalize.finalize_consultation(cid, wav))
    texts = [t["text"] for t in _turns(cid)]
    assert alba["text"] not in texts and len(texts) == 4
    raw = asyncio.run(raw_segments.for_consultation(cid))
    assert [r["dropped"] for r in raw if r["text"] == alba["text"]] == [True]   # shown, flagged


def test_the_trailing_audio_rule_still_refuses_untranscribed_speech(setup):
    # The stored lines stop at 10.5 s, but the room kept talking until 20 s.
    cid, wav = _nemotron_consultation(setup, seconds=22.0, speech=SPEECH + [(12.0, 20.0)])
    asyncio.run(finalize.finalize_consultation(cid, wav))
    c = _consultation(cid)
    assert c["status"] == transcript_quality.STATUS_UNRELIABLE
    assert c["quality_signals"]["s4_truncation"]["trailing_speech"]["has_speech"] is True
    assert setup["drafted"] == []                           # no note


# --- engine failure: refused, never a transcript from a partial flush --------------

def test_an_engine_failure_refuses_and_builds_no_transcript(setup, monkeypatch):
    monkeypatch.setattr(transcript_quality, "GATE_ENABLED", False)   # even with break-glass
    cid, wav = _nemotron_consultation(
        setup, failure="the speech worker exited (exit code 1)")
    asyncio.run(finalize.finalize_consultation(cid, wav))
    c = _consultation(cid)
    assert c["status"] == transcript_quality.STATUS_UNRELIABLE
    assert c["quality_outcome"] == transcript_quality.OUTCOME_REFUSED
    assert _turns(cid) == []                                # the stored lines were NOT used
    assert setup["drafted"] == []
    assert c["quality_signals"]["speech_pipeline"]["failure"].startswith("the speech worker exited")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        detail = conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'consultation.quality_refused'"
            " AND subject_id = %s", (cid,)).fetchone()[0]
    assert "exit code 1" in detail["summary"]


def _fake_worker(tmp_path, script):
    path = tmp_path / f"w_{secrets.token_hex(3)}.json"
    path.write_text(json.dumps(script))
    w = speech_pipeline.SpeechWorker([sys.executable, str(FAKE), str(path)],
                                     log_path=tmp_path / "worker.log")
    w.start()
    deadline = time.monotonic() + 10
    while w.state == "starting" and time.monotonic() < deadline:
        time.sleep(0.02)
    return w


@pytest.fixture()
def nemotron_socket(setup, monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemotron")
    state = appmain.app.state

    class Held:
        async def update(self, *a, **k):
            await asyncio.Event().wait()

    state.transcriber, state.cds_engine, state.rag = None, Held(), object()
    state.live_sessions, state.finalize_queue = {}, asyncio.Queue()
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", setup["tmp"])
    yield state
    if getattr(state, "speech_worker", None) is not None:
        state.speech_worker.stop()
    state.speech_worker = None
    state.live_sessions = {}


def _frame(seq: int) -> bytes:
    t = np.arange(4000)
    return struct.pack(">I", seq) + (3000 * np.sin(2 * np.pi * 440 * t / SR)).astype("<i2").tobytes()


def _until(ws, wanted, limit=80):
    for _ in range(limit):
        m = ws.receive_json()
        if m.get("type") in wanted:
            return m
    raise AssertionError(f"none of {wanted}")


def test_a_stop_flush_that_does_not_answer_is_a_crash_and_the_transcript_is_refused(
        setup, nemotron_socket, monkeypatch):
    """Owner, at approval: if `flushed` does not arrive in time, treat it as
    a worker crash — refuse at finalisation and give the reason. Lines were
    committed BEFORE Stop, so a transcript could have been built from them;
    it must not be."""
    monkeypatch.setattr(speech_pipeline, "FLUSH_TIMEOUT_S", 0.5)
    nemotron_socket.speech_worker = _fake_worker(setup["tmp"], {
        "flush_hang": True,
        "replies": [{"segments": [_line(0, 0, 0.1, 1.0, "Hello there.")], "watermark": 2.0}]})
    with _client(setup["doctor"]).websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": secrets.token_hex(6)}))
        for seq in range(1, 7):
            ws.send_bytes(_frame(seq))
        _until(ws, {"final"})                          # a line committed before Stop
        ws.send_text("stop")
        cid = _until(ws, {"done"})["consultation_id"]
    record = asyncio.run(consultations.speech_pipeline_of(cid))
    assert record["pipeline"] == "nemotron"
    assert "did not answer a flush request" in record["failure"]
    assert len(asyncio.run(live_segments.for_consultation(cid))) == 1   # stored, linked...
    cid_q, wav = nemotron_socket.finalize_queue.get_nowait()
    asyncio.run(finalize.finalize_consultation(cid_q, wav))
    c = _consultation(cid)
    assert c["status"] == transcript_quality.STATUS_UNRELIABLE          # ...and not used
    assert _turns(cid) == [] and setup["drafted"] == []
    assert "did not answer a flush request" in c["quality_signals"]["speech_pipeline"]["failure"]


def test_stop_flushes_links_the_lines_and_marks_the_pipeline(setup, nemotron_socket):
    nemotron_socket.speech_worker = _fake_worker(setup["tmp"], {
        "replies": [{"segments": [_line(0, 0, 0.1, 1.0, "Good morning.")], "watermark": 2.0}],
        "flush": {"segments": [_line(1, 1, 1.2, 1.4, "Morning, doctor.")]}})
    with _client(setup["doctor"]).websocket_connect("/ws/transcribe") as ws:
        ws.send_text(json.dumps({"session_id": secrets.token_hex(6)}))
        for seq in range(1, 7):
            ws.send_bytes(_frame(seq))
        _until(ws, {"final"})
        ws.send_text("stop")
        last = _until(ws, {"final"})                   # the flush's line reaches the page
        assert last["text"] == "Morning, doctor."
        done = _until(ws, {"done"})
    cid = done["consultation_id"]
    assert done["speaker_wait_s"] == finalize.SPEAKER_DECLARATION_WAIT_S   # "Who spoke?" kept
    assert asyncio.run(consultations.speech_pipeline_of(cid)) == {"pipeline": "nemotron",
                                                                 "failure": None}
    assert [ln["text"] for ln in asyncio.run(live_segments.for_consultation(cid))] == \
        ["Good morning.", "Morning, doctor."]
    assert Path(setup["tmp"] / f"consultation_{cid}.wav").exists()   # recording saved as today


# --- the review tools still work ------------------------------------------------------

def test_line_edit_label_change_swap_and_regenerate_work_on_a_nemotron_transcript(setup):
    cid, wav = _nemotron_consultation(setup)
    asyncio.run(finalize.finalize_consultation(cid, wav))
    client = _client(setup["doctor"])

    r = client.patch(f"/api/consultations/{cid}/turns/1", json={"text": "A tight chest pain."})
    assert r.status_code == 200
    turn1 = _turns(cid)[1]
    assert turn1["text"] == "A tight chest pain." and turn1["confidence"] == 1.0  # edited = checked

    r = client.patch(f"/api/consultations/{cid}/turns/2", json={"role": "Patient"})
    assert r.status_code == 200 and _turns(cid)[2]["role"] == "Patient"

    before = [t["role"] for t in _turns(cid)]
    assert client.post(f"/api/consultations/{cid}/swap-roles").status_code == 200
    after = [t["role"] for t in _turns(cid)]
    assert after == [{"Doctor": "Patient", "Patient": "Doctor"}[r] for r in before]

    assert client.post(f"/api/consultations/{cid}/regenerate").status_code == 200
    assert len(setup["drafted"]) == 2
    assert setup["drafted"][-1][1]["text"] == "A tight chest pain."   # from the corrected lines
    assert _consultation(cid)["status"] == "awaiting_review"


# --- the whisper path is untouched ----------------------------------------------------

def test_a_whisper_consultation_still_takes_todays_path(setup, monkeypatch):
    cid = asyncio.run(consultations.create_consultation(None, setup["doctor"]["id"]))
    wav = setup["tmp"] / f"consultation_{cid}.wav"
    _write_wav(wav, 2.0, [])
    asyncio.run(finalize.finalize_consultation(cid, str(wav)))
    # Today's path begins by unloading the CDS model: here that is the fixture's
    # failing stand-in, so reaching it proves the whisper path was taken.
    c = _consultation(cid)
    assert c["status"] == "failed" and "must not be unloaded" in c["error"]


# --- the pure pieces ------------------------------------------------------------------

def test_unmeasured_confidence_is_left_out_of_s2_and_never_marks_a_claim():
    turns = [{"start": 0, "end": 10, "confidence": None, "idx": 0, "text": "x"},
             {"start": 10, "end": 12, "confidence": 0.9, "idx": 1, "text": "y"}]
    assert transcript_quality.s2_weighted_confidence(turns) == pytest.approx(0.9)
    assert transcript_quality.s2_weighted_confidence(turns[:1]) is None
    note = {"reasoning": "", "subjective": [{"text": "Takes 5 mg ramipril.", "turns": [0]}],
            "objective": [], "assessment": [], "plan": []}
    gated = notes.validate_and_gate(note, turns)
    assert gated["subjective"][0]["flagged"] is False


def test_whisper_signals_carry_no_pipeline_and_raise_no_pipeline_flag():
    turns = [{"start": 0, "end": 10, "confidence": 0.8, "text": "hello there"}]
    signals = transcript_quality.compute_signals(turns, audio_duration_s=10.5)
    assert "speech_pipeline" not in signals
    verdict = transcript_quality.evaluate(signals)
    assert not [f for f in verdict["fired"] + verdict["flags"] if f["signal"].startswith("P")]


def test_the_review_page_neither_marks_unmeasured_lines_nor_hides_why():
    """Pinned by reading: JavaScript reads `null < 0.6` as true, so without
    the guard every Nemotron line would show as low-confidence audio. The
    banners name the engine failure (refusal) and the unchecked confidence
    (flag)."""
    review = Path("app/static/review.html").read_text()
    render = review[review.index("function renderTurn(t) {"):]
    assert "const lowconf = t.confidence != null && t.confidence < 0.6;" in render[:600]
    assert "(lowconf ? ' lowconf' : '')" in render[:800]
    assert "speech engine failed during the" in review
    assert "speech-recognition confidence was not checked" in review
