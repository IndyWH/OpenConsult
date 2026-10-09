"""The one door to transcription (spec 11.4; 11.5 rules 1 and 5; 10.4;
15.9 rulings 1 and 3; R20; V1_LESSONS 1.2, 1.7, 2.1, 7.1). A made-up
worker stands behind it; nothing here hears any sound."""

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from openconsult import words
from openconsult.speech.choices import WHISPERX_PYANNOTE, Choice
from openconsult.speech.door import Door
from openconsult.speech.lines import Line, Live, Refused
from openconsult.speech.loudness import QUIET_DBFS
from tests.fakes import MadeUpWorker
from tests.test_loudness import silence, sine

RATE = 16000
LOUD = sine(0.25, -20.0)
QUIET = silence(0.25)


def door_with(worker, installed=True):
    return Door(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: installed)


def seg(start, end, text, speaker=None, score=None):
    words_ = []
    for i, word in enumerate(text.split()):
        entry = {"word": word, "start": start + i * 0.1, "end": start + i * 0.1 + 0.05}
        if speaker:
            entry["speaker"] = speaker
        if score is not None:
            entry["score"] = score
        words_.append(entry)
    return {"start": start, "end": end, "text": text, "words": words_}


def test_11_4_the_door_gives_lines_with_a_speaker_or_none_times_and_a_confidence_or_none():
    worker = MadeUpWorker(live=[[{"start": 0.0, "end": 0.2, "text": " made up "}]],
                          final={"last_live": [{"start": 0.3, "end": 0.5, "text": "tail"}],
                                 "segments": [seg(0.0, 0.5, "a b", "S0", 0.8)], "seconds": {}})
    door = door_with(worker)
    assert door.open(RATE).ok
    live = door.feed(LOUD)
    assert live.ok and live.lines == (Line(None, 0.0, 0.2, "made up", None),)
    final = door.stop(speakers=1)
    assert final.ok and final.lines == (Line("S0", 0.0, 0.5, "a b", 0.8),)
    assert final.last_live == (Line(None, 0.3, 0.5, "tail", None),)


def test_11_5_rule_5_the_choice_declares_what_it_can_provide():
    door = door_with(MadeUpWorker())
    declares = door.declares
    assert (declares.confidence, declares.speakers, declares.second_transcript) == ("at_stop", "at_stop", True)


def test_R20_every_result_carries_the_stamp():
    door = door_with(MadeUpWorker())
    assert door.stamp is None                      # nothing started, nothing to stamp
    opened = door.open(RATE)
    assert opened.stamp.choice == "whisperx_pyannote"
    assert opened.stamp.models == {"made-up": {"revision": "r0"}} and opened.stamp.versions == {"made-up": "0.0"}
    assert door.feed(LOUD).stamp == opened.stamp
    assert door.stop(speakers=2).stamp == opened.stamp


def test_10_4_an_absent_choice_is_a_failure_and_nothing_is_started():
    worker = MadeUpWorker()
    door = door_with(worker, installed=False)
    result = door.open(RATE)
    assert (result.ok, result.failure, result.detail) == (False, "not_installed", words.SPEECH_NEEDS_INSTALL)
    assert worker.starts == 0 and worker.requests == []
    assert door.feed(LOUD).failure == "no_session" and door.stop(speakers=1).failure == "no_session"


def test_10_4_a_dead_worker_is_a_failure_with_its_reason_and_nothing_else_is_tried():
    worker = MadeUpWorker(die_after=3)             # open, one piece, then dead
    door = door_with(worker)
    assert door.open(RATE).ok and door.feed(LOUD).ok
    dead = door.feed(LOUD)
    assert (dead.ok, dead.failure, dead.detail) == (False, "died", "made-up: died with exit code 3")
    after = door.stop(speakers=1)
    assert after.failure == "no_session"           # the session ended with the worker
    assert worker.starts == 1                      # no second worker, nothing else tried
    refused = door_with(MadeUpWorker(ready=False)).open(RATE)
    assert (refused.failure, refused.detail) == ("died", "made-up: could not load")


def test_a_second_open_never_throws_sound_away():
    worker = MadeUpWorker(live=[[], [], [], [{"start": 0.0, "end": 0.5, "text": "made up"}]])
    door = door_with(worker)
    assert door.open(RATE).ok
    door.feed(LOUD)
    again = door.open(RATE)
    assert (again.ok, again.failure, again.detail) == (False, "session_open", words.DOOR_SESSION_OPEN)
    assert len(worker.requested("open")) == 1                        # the worker was not asked
    for _ in range(3):
        heard = door.feed(LOUD)
    assert [line.text for line in heard.lines] == ["made up"] and heard.fed_s == 1.0   # the first session goes on
    assert door.stop(speakers=1).ok and door.open(RATE).ok            # then a new one may open


def test_the_door_never_raises_a_bad_reply_is_a_failure():
    worker = MadeUpWorker(live=[[{"start": "soon", "end": 1.0, "text": "x"}], "not a list"])
    door = door_with(worker)
    door.open(RATE)
    assert door.feed(LOUD).failure == "bad_reply"
    assert door.feed(LOUD).failure == "bad_reply"
    worker.requests.clear()
    worker.final = {"segments": [{"no": "start"}]}
    assert door.stop(speakers=1).failure == "bad_reply"
    odd = MadeUpWorker()
    odd.request = lambda header, payload=b"", timeout_s=None: {"type": "error", "fatal": False, "message": "made-up: no"}
    assert door_with(odd).open(RATE).failure == "worker_error"


def test_ruling_1_no_words_from_silence_through_the_door():
    thanks = [{"start": 0.0, "end": 0.5, "text": "Thank you."}]
    worker = MadeUpWorker(live=[[], [], [], thanks], pending=[[], [], [], [{"start": 0.5, "end": 0.75, "text": "you"}]],
                          final={"last_live": thanks, "segments": [seg(0.0, 0.5, "Thank you.")], "seconds": {}})
    door = door_with(worker)
    door.open(RATE)
    for _ in range(3):
        door.feed(QUIET)
    quiet = door.feed(QUIET)
    assert quiet.lines == () and quiet.partial == ""
    assert [r.line.text for r in quiet.refused] == ["Thank you."]
    assert quiet.refused[0].loudest_dbfs == float("-inf") and quiet.refused[0].threshold_dbfs == QUIET_DBFS
    final = door.stop(speakers=1)
    assert final.lines == () and final.last_live == ()
    assert [r.line.text for r in final.refused] == ["Thank you.", "Thank you."]       # the tail, then the raw
    assert final.raw[0]["refused"] is True and final.raw[0]["text"] == "Thank you."   # kept and marked (1.2)
    # The twin: the same lines over sound that says somebody spoke.
    loud_worker = MadeUpWorker(live=[[], [], [], thanks], final={"last_live": thanks, "segments": [seg(0.0, 0.5, "Thank you.")],
                                                      "seconds": {}})
    door = door_with(loud_worker)
    door.open(RATE)
    for _ in range(3):
        door.feed(LOUD)
    heard = door.feed(LOUD)
    assert [line.text for line in heard.lines] == ["Thank you."] and heard.refused == ()
    final = door.stop(speakers=1)
    assert [line.text for line in final.lines] == ["Thank you."] and final.raw[0]["refused"] is False


def test_ruling_3_the_door_sends_no_text_to_a_speech_model():
    worker = MadeUpWorker()
    door = door_with(worker)
    door.open(RATE)
    door.feed(LOUD)
    door.stop(speakers=2)
    allowed = {"type", "session", "rate", "speakers"}
    for header, _ in worker.requests:
        assert set(header) <= allowed, header
        assert all(not isinstance(v, str) or v in ("open", "audio", "stop", "s1") for v in header.values())
    assert "prompt" not in {f.name for f in dataclasses.fields(Choice)}
    assert all(not isinstance(v, str) or "prompt" not in v.lower() for f in dataclasses.fields(Choice)
               for v in [getattr(WHISPERX_PYANNOTE, f.name)])


def test_2_1_the_number_of_speakers_is_given_never_worked_out():
    worker = MadeUpWorker()
    door = door_with(worker)
    door.open(RATE)
    door.stop(speakers=2)
    assert worker.requested("stop")[0][0]["speakers"] == 2
    with pytest.raises(TypeError):
        door.stop()                                 # no default
    # A number below one is refused by the door, and the session stays up.
    door.open(RATE)
    for bad in (0, -1):
        refused = door.stop(speakers=bad)
        assert (refused.failure, refused.detail) == ("bad_speakers", words.DOOR_BAD_SPEAKERS.format(speakers=bad))
    assert len(worker.requested("stop")) == 1 and door.feed(LOUD).ok and door.stop(speakers=1).ok


def test_1_7_raw_segments_are_kept_as_they_came():
    raw = [seg(0.0, 0.5, "a b", "S0", 0.9), seg(0.5, 1.0, "c", "S1", 0.4)]
    worker = MadeUpWorker(final={"last_live": [], "segments": raw, "seconds": {"stop": 1.5}})
    door = door_with(worker)
    door.open(RATE)
    for _ in range(4):
        door.feed(LOUD)
    final = door.stop(speakers=2)
    assert [{k: v for k, v in r.items() if k != "refused"} for r in final.raw] == raw
    assert [r["refused"] for r in final.raw] == [False, False] and final.seconds == {"stop": 1.5}


def test_13_2_ruling_7_the_rate_travels_with_the_session():
    worker = MadeUpWorker()
    door = door_with(worker)
    assert door.open(48000).ok and worker.requested("open")[0][0]["rate"] == 48000
    door.feed(sine(0.5, -20.0, rate=48000))
    assert len(door._loudness.windows) == 5 and door.fed_s == 0.5
    strict = door_with(MadeUpWorker(rate_only=16000))
    refused = strict.open(48000)
    assert (refused.failure, refused.detail) == ("rate_not_supported", "made-up: takes 16000 only")
    assert strict.feed(LOUD).failure == "no_session"


def test_11_5_rule_2_D45_the_last_live_lines_are_made_final_at_stop():
    tail = [{"start": 0.0, "end": 0.2, "text": "ask not"}, {"start": 0.3, "end": 0.5, "text": "what"}]
    worker = MadeUpWorker(final={"last_live": tail, "segments": [], "seconds": {}})
    door = door_with(worker)
    door.open(RATE)
    door.feed(LOUD)
    door.feed(QUIET)
    final = door.stop(speakers=1)
    assert [line.text for line in final.last_live] == ["ask not"]
    assert [r.line.text for r in final.refused] == ["what"]


def test_7_1_the_app_imports_no_speech_library_and_never_the_worker(tmp_path):
    # A fresh Python: the app as the command builds it, and the door run
    # through a worker subprocess, then the modules loaded (V1_LESSONS 1.11, 7.1).
    script = Path(__file__).parent / "made_up_worker.py"
    code = (
        "import sys\n"
        "import openconsult.cli\n"
        "from openconsult.app import build_app\n"
        "from openconsult.settings import store\n"
        "from openconsult.settings.machine import describe\n"
        "from openconsult.speech.choices import WHISPERX_PYANNOTE\n"
        "from openconsult.speech.door import Door\n"
        "from openconsult.speech.worker import Worker\n"
        "app = build_app(store.build(sys.argv[1], 8765), machine=describe('Linux', 'x86_64', []))\n"
        "assert app.state.parts.speech.open(16000).failure == 'not_installed'\n"
        f"door = Door(WHISPERX_PYANNOTE, lambda: Worker([sys.executable, '-u', {str(script)!r}, 'ready']), lambda: True)\n"
        "assert door.open(16000).ok and door.feed(bytes(8000)).ok and door.stop(speakers=1).ok\n"
        "door.close()\n"
        "heavy = ('torch', 'numpy', 'whisperx', 'faster_whisper', 'ctranslate2', 'pyannote', 'transformers')\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in heavy or m.startswith('openconsult.speech.whisperx')))\n"
    )
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
