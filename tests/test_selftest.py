"""The self-test (spec 11.5 rule 6; D46; 15.9; R18): the clip through
the door in live-sized pieces, the pass rule, the stored result, and the
command. A made-up worker: what a speech model hears is never asserted
here (spec 5.2)."""

import hashlib

import pytest

from openconsult import words
from openconsult.cli import main
from openconsult.db import open_database
from openconsult.speech import selftest
from openconsult.speech.choices import WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from openconsult.speech.selftest import CLIP, EXPECTED, ClipChanged, SelfTests, in_order, judge, read_clip, run
from tests.fakes import MadeUpWorker
from tests.test_speech_door import seg

FIRST = "And so, my fellow Americans: ask not what your country can do for you,"
SECOND = "ask what you can do for your country."
PIECES = 44                       # 11 s in pieces of 0.25 s
NO_SLEEP = lambda seconds: None   # noqa: E731


def worker_hearing(first=FIRST, second=SECOND, stop_text=FIRST + " " + SECOND, **kwargs):
    live = [[] for _ in range(PIECES)]
    live[-1] = [{"start": 0.5, "end": 7.5, "text": first}]
    return MadeUpWorker(live=live, final={"last_live": [{"start": 7.6, "end": 10.9, "text": second}],
                                           "segments": [seg(0.5, 10.9, stop_text, "S0", 0.9)],
                                           "seconds": {"stop": 3.0}}, **kwargs)


def door_with(worker):
    return Door(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: True)


def test_the_clip_is_the_one_with_this_checksum(tmp_path):
    rate, pcm = read_clip()
    assert (rate, len(pcm)) == (16000, 176000 * 2)
    assert hashlib.sha256(CLIP.read_bytes()).hexdigest() == selftest.CLIP_SHA256
    changed = tmp_path / "jfk.wav"
    changed.write_bytes(CLIP.read_bytes()[:-2] + b"\0\1")
    with pytest.raises(ClipChanged):
        read_clip(changed)


def test_D46_the_pass_rule():
    assert in_order(EXPECTED, EXPECTED) == 22
    assert judge(EXPECTED, EXPECTED) == (True, None)
    twenty = EXPECTED[:10] + EXPECTED[12:]
    assert judge(twenty, EXPECTED) == (True, None) and judge(EXPECTED, twenty) == (True, None)
    nineteen = EXPECTED[:10] + EXPECTED[13:]
    assert judge(nineteen, EXPECTED) == (False, words.SELF_TEST_TOO_FEW_LIVE.format(heard=19, total=22, needed=20))
    assert judge(EXPECTED, nineteen) == (False, words.SELF_TEST_TOO_FEW_STOP.format(heard=19, total=22, needed=20))
    assert not judge(list(reversed(EXPECTED)), EXPECTED)[0]            # order matters
    assert judge(["um"] + EXPECTED + ["um"], EXPECTED)[0]              # words between do not


def test_D46_the_self_test_feeds_the_clip_in_pieces_and_stores_the_result(tmp_path, clock):
    worker = worker_hearing()
    outcome = run(door_with(worker), sleep=NO_SLEEP)
    assert outcome.passed and outcome.reason is None
    assert outcome.live_words == EXPECTED and outcome.stop_words == EXPECTED
    audio = worker.requested("audio")
    assert len(audio) == PIECES and all(len(p) == 8000 for h, p in audio)
    assert worker.requested("open")[0][0]["rate"] == 16000 and worker.requested("stop")[0][0]["speakers"] == 1
    assert outcome.detail["delays_s"] == [round(11.0 - 7.5, 2)] and outcome.detail["seconds"] == {"stop": 3.0}
    assert outcome.detail["stamp"]["choice"] == "whisperx_pyannote" and outcome.detail["refused"] == []
    db = open_database(tmp_path / "openconsult.db")
    tests = SelfTests(db, clock)
    assert tests.last("whisperx_pyannote") is None
    tests.add("whisperx_pyannote", outcome)
    stored = tests.last("whisperx_pyannote")
    assert stored["passed"] and stored["at"] == clock().isoformat(timespec="seconds")
    assert stored["detail"]["live_words"] == EXPECTED and stored["detail"]["raw"][0]["refused"] is False


def test_D46_a_wrong_transcript_fails_and_is_stored_failed(tmp_path, clock):
    outcome = run(door_with(worker_hearing(first="And so my fellow Americans")), sleep=NO_SLEEP)
    assert not outcome.passed
    assert outcome.reason == words.SELF_TEST_TOO_FEW_LIVE.format(heard=13, total=22, needed=20)
    died = run(door_with(worker_hearing(die_after=5)), sleep=NO_SLEEP)
    assert not died.passed and died.detail["failure"] == "died" and died.reason == "made-up: died with exit code 3"
    tests = SelfTests(open_database(tmp_path / "openconsult.db"), clock)
    tests.add("whisperx_pyannote", outcome)
    tests.add("whisperx_pyannote", died)
    assert tests.last("whisperx_pyannote")["detail"]["reason"] == "made-up: died with exit code 3"


def test_D46_the_self_test_command_stores_and_says_the_result(tmp_path, clock):
    said = []
    worker = worker_hearing()
    code = main(["self-test", "--data-folder", str(tmp_path)], say=said.append,
                make_speech=lambda folder, choice: door_with(worker), sleep=NO_SLEEP)
    assert code == 0 and said[0] == words.SELF_TEST_RUNNING
    assert said[-1] == words.SELF_TEST_RESULT_PASSED.format(live=" ".join(EXPECTED), stop=" ".join(EXPECTED))
    assert worker.state == "stopped"                                     # the door was closed
    stored = SelfTests(open_database(tmp_path / "openconsult.db")).last("whisperx_pyannote")
    assert stored["passed"]
    failing = worker_hearing(first="nothing like it")
    code = main(["self-test", "--data-folder", str(tmp_path)], say=said.append,
                make_speech=lambda folder, choice: door_with(failing), sleep=NO_SLEEP)
    assert code == 1 and said[-1].startswith(words.SELF_TEST_RESULT_FAILED.format(reason="", live="", stop="")[:20])
    assert not SelfTests(open_database(tmp_path / "openconsult.db")).last("whisperx_pyannote")["passed"]


def test_D46_the_command_refuses_to_run_without_the_choice_installed(tmp_path):
    said = []
    absent = Door(WHISPERX_PYANNOTE, make_worker=lambda: worker_hearing(), installed=lambda: False)
    code = main(["self-test", "--data-folder", str(tmp_path)], say=said.append,
                make_speech=lambda folder, choice: absent, sleep=NO_SLEEP)
    assert code == 1 and said == [words.SPEECH_NEEDS_INSTALL]
    assert not (tmp_path / "openconsult.db").exists()                    # nothing started, nothing written


def test_R18_the_self_test_writes_only_in_the_data_folder_it_is_given(tmp_path):
    # The guard of R18 fails any test that reads the real folder; here the
    # command is given its folder and everything it wrote is under it.
    main(["self-test", "--data-folder", str(tmp_path / "data")], say=lambda line: None,
         make_speech=lambda folder, choice: door_with(worker_hearing()), sleep=NO_SLEEP)
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert written == {"data/openconsult.db"}


# ------------------------------------------- the three new choices (15.9, 5b)

from openconsult.speech.choices import NEMOTRON, SPEECHMATICS  # noqa: E402


def live_worker(first=FIRST, second=SECOND, **kwargs):
    live = [[] for _ in range(PIECES)]
    live[-1] = [{"id": 1, "start": 0.5, "end": 7.5, "text": first, "speaker": "S1", "confidence": None}]
    final = {"last_live": [{"id": 2, "start": 7.6, "end": 10.9, "text": second, "speaker": "S1", "confidence": None}],
             "revisions": [], "seconds": {"tail": 0.1}}
    info = {"type": "ready", "models": {"speechmatics": {"address": "wss://made-up", "model": "made-up"}},
            "versions": {"made-up": "0.0"}}
    return MadeUpWorker(live=live, final=final, info=info, **kwargs)


def test_D46_the_self_test_opens_with_one_speaker_for_a_live_label_choice_and_reads_the_same_lines(tmp_path, clock):
    worker = live_worker()
    door = Door(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)
    outcome = run(door, sleep=NO_SLEEP)
    assert outcome.passed and outcome.live_words == EXPECTED and outcome.stop_words == EXPECTED
    assert worker.requested("open")[0][0]["speakers"] == 1 and worker.requested("stop")[0][0]["speakers"] == 1
    assert outcome.detail["same_lines"] is True and outcome.detail["raw"] == []
    assert outcome.detail["stop_lines"] == outcome.detail["live_lines"]          # one transcript (11.1)
    assert outcome.detail["speakers_given"] == {"open": 1, "stop": 1} and outcome.detail["revisions"] == []
    said = []
    code = main(["self-test", "--choice", "nemotron", "--data-folder", str(tmp_path)], say=said.append,
                make_speech=lambda folder, choice: Door(choice, make_worker=lambda: live_worker(), installed=lambda: True),
                sleep=NO_SLEEP)
    assert code == 0 and said[0] == words.SELF_TEST_RUNNING and said[-1] == words.SELF_TEST_SAME_LINES
    assert SelfTests(open_database(tmp_path / "openconsult.db")).last("nemotron")["passed"]
    assert SelfTests(open_database(tmp_path / "openconsult.db")).last("whisperx_pyannote") is None


def test_7_2_the_self_test_of_a_cloud_choice_is_the_test_of_the_connection(tmp_path, clock):
    said = []
    no_key = Door(SPEECHMATICS, make_worker=lambda: live_worker(), installed=lambda: True, key_present=lambda: False)
    code = main(["self-test", "--choice", "speechmatics", "--data-folder", str(tmp_path)], say=said.append,
                make_speech=lambda folder, choice: no_key, sleep=NO_SLEEP)
    assert code == 1 and said[0] == words.SELF_TEST_RUNNING_CLOUD.format(service="Speechmatics")
    stored = SelfTests(open_database(tmp_path / "openconsult.db")).last("speechmatics")
    assert not stored["passed"] and stored["detail"]["failure"] == "no_key"
    assert stored["detail"]["reason"] == words.NO_KEY.format(service="Speechmatics", name="SPEECHMATICS_API_KEY")
    refused = live_worker()
    refused.request = lambda header, payload=b"", timeout_s=None: {"type": "error", "fatal": False, "reason": "key_refused",
                                                                  "message": "made-up", "detail": ""}
    outcome = run(Door(SPEECHMATICS, make_worker=lambda: refused, installed=lambda: True), sleep=NO_SLEEP)
    assert not outcome.passed and outcome.detail["failure"] == "key_refused"
    assert outcome.reason == words.KEY_REFUSED.format(service="Speechmatics")
    # R20: the stamp names the service, its address and its model; a key is nowhere in the record.
    passed = run(Door(SPEECHMATICS, make_worker=lambda: live_worker(), installed=lambda: True), sleep=NO_SLEEP)
    assert passed.detail["stamp"]["models"]["speechmatics"] == {"address": "wss://made-up", "model": "made-up"}
    assert "key" not in str(passed.detail["stamp"]).lower()
