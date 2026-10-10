"""The worker frame (spec 6.2, 15.9; 10.4): start, ready, talk, death,
stop, with a made-up worker run as a real subprocess, so the frame is
proven on GitHub's three systems (rule 13). No sound, no model."""

import io
import sys
from pathlib import Path

import pytest

from openconsult import words
from openconsult.speech import frames
from openconsult.speech.worker import Worker, WorkerGone, plain_last_line
from tests.made_up_worker import load_frames

SCRIPT = Path(__file__).parent / "made_up_worker.py"


def command(mode, *args):
    return [sys.executable, "-u", str(SCRIPT), mode, *map(str, args)]


def started(mode, tmp_path, *args, **kwargs):
    worker = Worker(command(mode, *args), log_path=tmp_path / "worker.log",
                    ready_timeout_s=kwargs.pop("ready", 20.0), request_timeout_s=kwargs.pop("request", 20.0))
    worker.start()
    return worker


def test_worker_frame_start_ready_talk_stop(tmp_path):
    worker = started("ready", tmp_path)
    assert worker.wait_ready() and worker.state == "ready"
    assert worker.info["type"] == "ready" and worker.info["models"] == {"made-up": {"revision": "0"}}
    assert worker.request({"type": "ping"}) == {"type": "pong", "nbytes": 0}
    reply = worker.request({"type": "audio", "session": "s"}, b"\0" * 8000)
    assert (reply["type"], reply["bytes"]) == ("lines", 8000)
    worker.stop()
    assert worker.state == "stopped" and worker.exit_code is not None     # the process is gone
    with pytest.raises(WorkerGone):
        worker.request({"type": "ping"})


def test_10_4_a_worker_that_dies_at_start_is_a_failure_with_its_reason(tmp_path):
    worker = started("die_at_start", tmp_path)
    assert not worker.wait_ready()
    assert worker.state == "failed" and worker.kind == "died"
    assert worker.reason == words.WORKER_REFUSED.format(message="made-up: could not load")


def test_10_4_a_worker_that_dies_mid_request_is_a_failure_with_its_exit_code_and_last_words(tmp_path):
    worker = started("die_mid", tmp_path)
    assert worker.wait_ready()
    with pytest.raises(WorkerGone) as gone:
        worker.request({"type": "ping"})
    assert gone.value.kind == "died"
    assert gone.value.detail == words.WORKER_DIED_SAYING.format(code=3, last="made-up: last words")
    assert worker.state == "failed" and worker.exit_code == 3


def test_10_4_a_worker_that_never_answers_is_a_failure_within_the_limit(tmp_path):
    hung = started("hang", tmp_path)
    assert hung.wait_ready()
    with pytest.raises(WorkerGone) as gone:
        hung.request({"type": "ping"}, timeout_s=0.5)
    assert gone.value.kind == "no_answer" and gone.value.detail == words.WORKER_NO_ANSWER.format(seconds="0")
    assert hung.state == "failed" and hung.exit_code is not None          # it was ended
    silent = started("no_ready", tmp_path, ready=0.5)
    assert not silent.wait_ready()
    assert silent.kind == "no_answer" and silent.exit_code is not None


def test_a_new_start_after_a_death_works(tmp_path):
    worker = started("die_once", tmp_path, tmp_path / "marker")
    assert worker.wait_ready()
    with pytest.raises(WorkerGone):
        worker.request({"type": "ping"})
    assert worker.state == "failed"
    worker.start()
    assert worker.wait_ready() and worker.request({"type": "ping"})["type"] == "pong"
    worker.stop()


def test_a_command_that_cannot_start_is_a_failure_not_an_error(tmp_path):
    worker = Worker([str(tmp_path / "no-such-python"), "x"], log_path=tmp_path / "worker.log")
    worker.start()
    assert not worker.wait_ready(0.1) and worker.kind == "died"
    assert worker.reason.startswith(words.WORKER_NOT_STARTED.format(reason="")[:30])


def test_frames_round_trip_and_a_too_long_header_is_refused():
    theirs = load_frames()
    stream = io.BytesIO()
    frames.write_frame(stream, {"type": "audio", "session": "s"}, b"pcm")
    theirs.write_frame(stream, {"type": "lines", "segments": []})
    stream.seek(0)
    assert theirs.read_frame(stream) == ({"type": "audio", "session": "s", "nbytes": 3}, b"pcm")
    assert frames.read_frame(stream) == ({"type": "lines", "segments": [], "nbytes": 0}, b"")
    assert frames.read_frame(stream) is None and theirs.read_frame(stream) is None
    too_long = io.BytesIO(frames.HEADER.pack(frames.MAX_HEADER + 1) + b"x")
    with pytest.raises(frames.BadFrame):
        frames.read_frame(too_long)
    with pytest.raises(ValueError):
        theirs.read_frame(io.BytesIO(theirs.HEADER.pack(theirs.MAX_HEADER + 1) + b"x"))
    with pytest.raises(frames.BadFrame):
        frames.read_frame(io.BytesIO(frames.HEADER.pack(3) + b"[1]"))


def test_15_9_a_deaths_reason_is_one_plain_sentence_never_a_warning():
    # Carried from 5a: a library's terminal codes and traceback stay in the
    # log, and a harmless warning after the real reason is not the reason.
    log = (
        "\x1b[33mWARNING\x1b[0m something harmless\n"
        "Traceback (most recent call last):\n"
        '  File "/made-up/lib.py", line 12, in load\n'
        "    raise RuntimeError(\"made-up: the card is full\")\n"
        "\x1b[31mRuntimeError: made-up: the card is full\x1b[0m\n"
        "/made-up/lib.py:9: UserWarning: made-up: a deprecation\n"
        "  warnings.warn(\"made-up\")\n"
        "WARNING: made-up: the last harmless line\n"
    )
    assert plain_last_line(log) == "RuntimeError: made-up: the card is full"
    assert plain_last_line("WARNING only\n  warnings.warn(x)\n") == ""
    assert plain_last_line("") == ""
