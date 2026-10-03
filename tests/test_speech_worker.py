"""Task 13 item 7: the Nemotron worker process and the app's client of it.

No GPU and no Nemotron environment: the worker side is speech_nemotron/
worker.py's real `serve` loop, driven in-process or through
tests/fake_speech_worker.py (the real loop with a scripted stream).

Pinned: the wire protocol round-trips; the client waits for `ready`
without blocking; a worker that will not load, dies, or does not answer
in time is FAILED with a plain reason (never quietly replaced); a
missing environment names setup.sh; and the status sentences the live
page shows say whether recording can start.
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import pytest

from app import speech_pipeline
from app.speech_pipeline import SpeechWorker, WorkerError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "speech_nemotron"))
import worker as worker_proto  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_speech_worker.py"


def _spawn(tmp_path, script: dict, **kwargs) -> SpeechWorker:
    path = tmp_path / "script.json"
    path.write_text(json.dumps(script))
    w = SpeechWorker([sys.executable, str(FAKE), str(path)],
                     log_path=tmp_path / "worker.log", **kwargs)
    w.start()
    return w


def _wait_state(w: SpeechWorker, wanted: set[str], timeout: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if w.state in wanted:
            return w.state
        time.sleep(0.02)
    raise AssertionError(f"worker stayed {w.state!r}, wanted {wanted}")


# --- the protocol, in-process ----------------------------------------------

class _Stream:
    def __init__(self):
        self.got = b""

    def accept(self, pcm):
        self.got += pcm
        return {"segments": [{"id": 0, "speaker": 1, "start": 0.5, "end": 1.0, "text": "hi"}],
                "revisions": [], "watermark": 0.2, "partial": "open", "processed_s": 1.0}

    def flush(self):
        return {"segments": [], "revisions": [], "watermark": None, "partial": "", "processed_s": 1.0}

    def stats(self):
        return {"bytes": len(self.got)}


def _requests(*frames) -> io.BytesIO:
    buf = io.BytesIO()
    for header, payload in frames:
        worker_proto.write_frame(buf, header, payload)
    buf.seek(0)
    return buf


def _replies(out: io.BytesIO) -> list[dict]:
    out.seek(0)
    replies = []
    while (frame := worker_proto.read_frame(out)) is not None:
        replies.append(frame[0])
    return replies


def test_serve_answers_every_request_in_order_and_carries_the_payload():
    streams = []
    inp = _requests(({"type": "ping"}, b""),
                    ({"type": "open", "session": "s1"}, b""),
                    ({"type": "audio", "session": "s1"}, b"\x01\x00" * 8),
                    ({"type": "flush", "session": "s1"}, b""),
                    ({"type": "close", "session": "s1"}, b""))
    out = io.BytesIO()
    assert worker_proto.serve(inp, out, lambda: streams.append(_Stream()) or streams[-1]) == 0
    replies = _replies(out)
    assert [r["type"] for r in replies] == ["pong", "opened", "lines", "flushed", "closed"]
    assert replies[2]["segments"][0]["text"] == "hi" and replies[2]["watermark"] == 0.2
    assert replies[3]["stats"] == {"bytes": 16}       # the payload reached the stream
    assert streams[0].got == b"\x01\x00" * 8


def test_serve_refuses_an_unknown_session_without_dying():
    inp = _requests(({"type": "audio", "session": "nope"}, b"\x00\x00"),
                    ({"type": "ping"}, b""))
    out = io.BytesIO()
    assert worker_proto.serve(inp, out, _Stream) == 0
    replies = _replies(out)
    assert replies[0]["type"] == "error" and replies[0]["fatal"] is False
    assert replies[1]["type"] == "pong"


def test_serve_reports_a_stream_exception_as_fatal_and_ends():
    class Broken(_Stream):
        def accept(self, pcm):
            raise RuntimeError("CUDA error: an illegal memory access was encountered")
    inp = _requests(({"type": "open", "session": "s"}, b""),
                    ({"type": "audio", "session": "s"}, b"\x00\x00"),
                    ({"type": "ping"}, b""))
    out = io.BytesIO()
    assert worker_proto.serve(inp, out, Broken) == 1
    replies = _replies(out)
    assert replies[-1]["type"] == "error" and replies[-1]["fatal"] is True
    assert "illegal memory access" in replies[-1]["message"]
    assert len(replies) == 2                           # the ping after it was never served


def test_app_and_worker_framing_agree():
    """The app keeps its own copy of the framing (it never imports the
    worker); a frame written by one must read back in the other."""
    import os
    r, w = os.pipe()
    with os.fdopen(w, "wb") as fh:
        worker_proto.write_frame(fh, {"type": "lines", "x": 1}, b"abc")
    header, payload = speech_pipeline._read_frame(r, 2.0)
    os.close(r)
    assert header["type"] == "lines" and header["x"] == 1 and payload == b"abc"
    buf = io.BytesIO()
    speech_pipeline._write_frame(buf, {"type": "audio"}, b"\x00\x01")
    buf.seek(0)
    assert worker_proto.read_frame(buf) == ({"type": "audio", "nbytes": 2}, b"\x00\x01")


# --- the client, against the fake process -------------------------------------

def test_start_returns_at_once_and_the_worker_becomes_ready(tmp_path):
    w = _spawn(tmp_path, {"ready_delay_s": 0.5})
    try:
        assert w.state == "starting"                    # start() did not wait for the load
        assert _wait_state(w, {"ready", "failed"}) == "ready"
        assert w.request({"type": "ping"})["type"] == "pong"
    finally:
        w.stop()


def test_a_load_error_fails_the_worker_with_its_reason(tmp_path):
    w = _spawn(tmp_path, {"load_error": "could not load the models: OutOfMemoryError"})
    assert _wait_state(w, {"ready", "failed"}) == "failed"
    assert "OutOfMemoryError" in w.reason
    with pytest.raises(WorkerError):
        w.request({"type": "ping"})


def test_a_worker_that_dies_mid_request_is_failed_not_replaced(tmp_path):
    w = _spawn(tmp_path, {"die_on_audio": 1})
    try:
        _wait_state(w, {"ready"})
        w.request({"type": "open", "session": "s"})
        with pytest.raises(WorkerError) as err:
            w.request({"type": "audio", "session": "s"}, b"\x00\x00" * 10)
        assert "exited" in str(err.value) and "exit code 3" in str(err.value)
        assert w.state == "failed" and w.ready is False
    finally:
        w.stop()


def test_no_answer_within_the_deadline_fails_the_worker(tmp_path):
    w = _spawn(tmp_path, {"flush_hang": True})
    try:
        _wait_state(w, {"ready"})
        w.request({"type": "open", "session": "s"})
        started = time.monotonic()
        with pytest.raises(WorkerError) as err:
            w.request({"type": "flush", "session": "s"}, timeout_s=0.5)
        assert time.monotonic() - started < 3.0
        assert "did not answer a flush request within" in str(err.value)
        assert w.state == "failed"
    finally:
        w.stop()


def test_a_missing_environment_names_the_setup_script(tmp_path):
    w = SpeechWorker([str(tmp_path / "no" / "python"), "worker.py"])
    w.start()
    assert w.state == "failed" and "speech_nemotron/setup.sh" in w.reason


def test_a_failed_worker_is_restarted_only_after_the_cooldown(tmp_path, monkeypatch):
    w = _spawn(tmp_path, {"load_error": "boom"})
    _wait_state(w, {"failed"})
    w.command = [sys.executable, str(FAKE), str(tmp_path / "ok.json")]
    (tmp_path / "ok.json").write_text("{}")
    w.ensure_running()
    assert w.state == "failed"                          # inside the cooldown: untouched
    monkeypatch.setattr(speech_pipeline, "RESTART_COOLDOWN_S", 0.0)
    w.ensure_running()
    try:
        assert _wait_state(w, {"ready", "failed"}) == "ready"
    finally:
        w.stop()


# --- what the live page is told ------------------------------------------------

def test_status_on_whisper_is_always_ready_and_names_no_worker(monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "whisper")
    assert speech_pipeline.status(None) == {"pipeline": "whisper", "ready": True,
                                            "state": "ready", "detail": None}


def test_status_on_nemotron_says_plainly_why_recording_cannot_start(monkeypatch, tmp_path):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemotron")
    stopped = speech_pipeline.status(None)
    assert stopped["ready"] is False and "Recording cannot start" in stopped["detail"]

    w = _spawn(tmp_path, {"ready_delay_s": 30})
    try:
        loading = speech_pipeline.status(w)
        assert loading["ready"] is False and loading["state"] == "starting"
        assert "still loading" in loading["detail"]
    finally:
        w.stop()

    broken = _spawn(tmp_path, {"load_error": "could not load the models: OOM"})
    _wait_state(broken, {"failed"})
    failed = speech_pipeline.status(broken)
    assert failed["ready"] is False and "OOM" in failed["detail"]
    assert "not replaced by Whisper" in failed["detail"]


def test_status_reports_a_bad_setting_instead_of_falling_back(monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemo")
    st = speech_pipeline.status(None)
    assert st["ready"] is False and st["state"] == "misconfigured" and "'nemo'" in st["detail"]
