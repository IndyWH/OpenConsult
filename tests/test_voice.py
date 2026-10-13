"""The voice method (spec 15.9, ruling 4; D53; the details of part two of
5c; R18; R31; V1_LESSONS 9.4). A made-up worker; made sound; the distances
are made up."""

import json
import sys
from pathlib import Path

import pytest

from openconsult import words
from openconsult.bench import cli
from openconsult.bench.speech import banked, commands, commands2, voice
from openconsult.bench.speech.sound import read_wav
from openconsult.bench.writer import ResultWriter
from openconsult.settings import paths
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE
from openconsult.speech.worker import Worker
from tests.made_up_recordings import entry, made_up_recordings, made_sound, write_wav
from tests.test_speech_tables import results_of

MADE_UP_VOICE_WORKER = Path(__file__).resolve().parent / "made_up_voice_worker.py"


class MadeUpVoiceWorker:
    """In this process: keeps every request, answers as the made-up script does."""

    def __init__(self):
        self.requests, self.starts, self.state = [], 0, "stopped"
        self.info, self.kind, self.reason = {}, None, None

    def start(self):
        self.starts += 1
        self.state = "starting"

    def wait_ready(self, timeout_s=None):
        self.state, self.info = "ready", {"type": "ready", "models": {"embed": {"repo": "made-up/voice", "revision": "0"}},
                                          "versions": {"made-up": "0"}, "device": "cpu", "least_s": 0.2}
        return True

    def stop(self):
        self.state = "stopped"

    def request(self, header, payload=b"", timeout_s=None):
        self.requests.append((header, payload, timeout_s))
        if header["type"] == "learn":
            return {"type": "learnt", "seconds": 0.1, "seconds_used": 2.0, "seconds_trimmed": 1.0}
        return {"type": "scored", "seconds": 0.2, "lines": [{"n": ln["n"], "distance": 0.3 if ln["n"] % 2 else 0.9, "seconds": 0.01}
                                                            for ln in header["lines"]]}


def test_D53_the_reading_of_a_line_from_its_distance_from_the_doctors_voice():
    assert voice.reading_of(0.45, 2.0) == "doctor"            # below the threshold less the band
    assert voice.reading_of(0.85, 2.0) == "not_doctor"        # above the threshold plus the band
    assert voice.reading_of(0.70, 2.0) == "unsure"            # between the two
    assert voice.reading_of(0.45, 0.8) == "unsure"            # shorter than 1.0 s, whatever the distance
    assert voice.reading_of(None, 2.0) == "unsure"            # no distance (too short for the model)
    assert voice.DOCTOR_DISTANCE_AT < voice.CLUSTER_THRESHOLD < voice.NOT_DOCTOR_DISTANCE_AT
    assert voice.figures()["least_line_s"] == 1.0


@pytest.fixture
def bench(tmp_path, recordings_kept, monkeypatch):
    """Stored pages for recording one (whose list entry names the minute) and
    recording two (whose entry names none), a minute marked voice only, and a
    made-up WhisperX environment."""
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    folder = recordings_kept.folder
    minute_sha = write_wav(folder / "minute.wav", made_sound(2.0))
    minute = entry("minute", "minute.wav", minute_sha, speakers=1, length_s=2.0, machine_voices=True, voice_only=True,
                   doctor_voice=None, parts={"DOCTOR": "a machine voice"})
    made_up_recordings(folder, extra=[minute])
    listed = json.loads((folder / "recordings.json").read_text(encoding="utf-8"))
    listed["recordings"][0]["doctor_voice"] = "minute"
    listed["recordings"][1]["doctor_voice"] = None
    (folder / "recordings.json").write_text(json.dumps(listed, indent=1), encoding="utf-8")
    recordings_kept.settle()
    out = tmp_path / "out"
    _, results = results_of(folder, out)
    two = dict(results[("nemotron", "one")], recording="two")
    ResultWriter(out).write("nemotron", "two", two)
    data = tmp_path / "data"
    python = environment.python(data, WHISPERX_PYANNOTE)
    python.parent.mkdir(parents=True)
    python.write_text("")
    workers, said = [], []

    def make_worker(data_folder):
        workers.append(MadeUpVoiceWorker())
        return workers[-1]

    def run(names=None, arms=None, out_folder=None, data_folder=None, make=make_worker):
        return commands2.speech_voice(out_folder or out, folder, data_folder or data, names, arms, say=said.append, make_worker=make)

    return {"folder": folder, "out": out, "data": data, "workers": workers, "said": said, "run": run}


def test_the_command_learns_the_voice_once_scores_each_page_and_writes_the_not_run_record(bench):
    out, workers, said, run = bench["out"], bench["workers"], bench["said"], bench["run"]
    assert run() == 0 and len(workers) == 1 and workers[0].starts == 1 and workers[0].state == "stopped"
    kinds = [h["type"] for h, _, _ in workers[0].requests]
    assert kinds == ["learn", "score", "score", "score"]                     # one voice learnt, three pages of one
    learn, pcm, timeout = workers[0].requests[0]
    assert (learn["rate"], learn["quiet_dbfs"], learn["window_s"], timeout) == (16000, -40.0, 0.1, 600.0)
    assert pcm == read_wav(bench["folder"] / "minute.wav", 16000)
    results = ResultWriter(out / "voice").read_all()
    assert sorted(results) == [("nemotron", "one"), ("nemotron", "two"), ("nemotron_tied_pair", "one"), ("whisperx_pyannote", "one")]
    nem = results[("nemotron", "one")]
    assert nem["doctor_voice"] == "minute" and nem["not_run"] is None and nem["figures"] == voice.figures()
    assert nem["learnt"] == {"seconds": 0.1, "seconds_used": 2.0, "seconds_trimmed": 1.0}
    # Line 1 is 1.0 s long; lines 2 and 3 are shorter than 1.0 s, so unsure whatever their distance.
    assert [(r["n"], r["distance"], r["reading"], r["length_s"]) for r in nem["lines"]] == [
        (1, 0.3, "doctor", 1.0), (2, 0.9, "unsure", 0.3), (3, 0.3, "unsure", 0.6)]
    assert results[("whisperx_pyannote", "one")]["learnt"] is None                   # the voice was learnt once
    two = results[("nemotron", "two")]
    assert two["not_run"] == voice.NOT_RUN and two["doctor_voice"] is None and all(r["distance"] is None for r in two["lines"])
    assert words.BENCH_VOICE_NOT_RUN.format(name="two") in said
    # A second run: every result is there; no worker is started.
    assert run() == 0 and len(workers) == 1
    assert said[-1] == words.BENCH_VOICE_DONE.format(run=0, not_run=0, failed=0, kept=4)
    # The real worker would run in the WhisperX environment, with the hub's network off.
    worker = voice.make_worker(bench["data"], environ={"PATH": "x"})
    assert Path(worker.command[0]).parts[-3:] == environment.python(bench["data"], WHISPERX_PYANNOTE).parts[-3:]
    assert Path(worker.command[1]).parts[-3:] == ("speech", "voice", "worker.py") and worker.env["HF_HUB_OFFLINE"] == "1"


def test_the_frames_of_the_voice_worker_on_this_system(tmp_path):
    worker = Worker([sys.executable, str(MADE_UP_VOICE_WORKER)], log_path=tmp_path / "voice.log")
    worker.start()
    try:
        assert worker.wait_ready() and worker.info["least_s"] == 0.2
        assert worker.request({"type": "score", "rate": 16000, "lines": []})["type"] == "error"      # nothing learnt yet
        assert worker.request({"type": "learn", "rate": 16000, "quiet_dbfs": -40.0, "window_s": 0.1}, b"\0" * 32000)["seconds_used"] == 1.0
        scored = worker.request({"type": "score", "rate": 48000, "lines": [{"n": 1, "start": 0.0, "end": 1.0}, {"n": 2, "start": 1.0, "end": 2.0}]}, b"\0" * 96)
        assert [(ln["n"], ln["distance"]) for ln in scored["lines"]] == [(1, 0.3), (2, 0.9)]
        refused = worker.request({"type": "learn", "rate": 44100, "quiet_dbfs": -40.0, "window_s": 0.1}, b"")
        assert refused["reason"] == "rate_not_supported"
    finally:
        worker.stop()
    assert worker.exit_code is not None


def test_R31_the_bench_command_names_speech_voice_and_the_app_cannot_reach_it(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(commands2, "speech_voice", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["speech-voice", "--out", str(tmp_path / "o"), "--recordings", str(tmp_path / "r"),
                     "--data-folder", str(tmp_path / "d"), "--recording", "one", "--arm", "nemotron"]) == 0
    assert seen[0][3] == ["one"] and seen[0][4] == ["nemotron"]
    assert voice.SHARES_STOP == ("whisperx_v1_line",)


def test_the_list_holds_the_voice_alone_and_who_it_belongs_to(tmp_path):
    folder = made_up_recordings(tmp_path / "r")
    listed = banked.load_list(folder)
    assert [r.doctor_voice for r in listed] == [None, None] and not any(r.voice_only for r in listed)   # part one's list loads
    bad_speakers = entry("m", "one.wav", listed[0].sha256, voice_only=True, speakers=2)
    bad_cloud = entry("m", "one.wav", listed[0].sha256, voice_only=True, speakers=1,
                      consent={"recording": True, "tests_on_this_computer": True, "cloud": ["speechmatics"]})
    bad_voice = entry("m", "one.wav", listed[0].sha256, doctor_voice=3)
    for bad in (bad_speakers, bad_cloud, bad_voice):
        (folder / "recordings.json").write_text(json.dumps({"recordings": [bad]}), encoding="utf-8")
        with pytest.raises(banked.BadList):
            banked.load_list(folder)
    good = entry("m", "one.wav", listed[0].sha256, voice_only=True, speakers=1, doctor_voice=None)
    (folder / "recordings.json").write_text(json.dumps({"recordings": [good]}), encoding="utf-8")
    assert banked.load_list(folder)[0].voice_only


def test_the_voice_alone_is_never_fed_as_a_consultation(bench, tmp_path):
    folder, data, said = bench["folder"], bench["data"], bench["said"]
    for choice in (WHISPERX_PYANNOTE,):
        environment.python(data, choice)
    built = []

    def make_door(arm, data_folder):
        built.append(arm.name)
        from openconsult.speech.door import Door
        from tests.fakes import MadeUpWorker
        return Door(arm.choice, make_worker=MadeUpWorker, installed=lambda: True)

    from tests.test_speech_replay import FakeClock
    clock = FakeClock()
    code = commands.speech_run(folder, "whisperx_pyannote", data, tmp_path / "o1", ["minute"], say=said.append,
                               make_door=make_door, sleep=clock.sleep, clock=clock)
    assert code == 3 and built == [] and said[-1] == words.BENCH_VOICE_ONLY_REFUSED.format(name="minute")
    code = commands.speech_run(folder, "whisperx_pyannote", data, tmp_path / "o2", None, say=said.append,
                               make_door=make_door, sleep=clock.sleep, clock=clock)
    assert code == 0 and sorted(ResultWriter(tmp_path / "o2").read_all()) == [("whisperx_pyannote", "one"), ("whisperx_pyannote", "two")]


def test_the_command_refuses_before_the_worker_is_started(bench, tmp_path):
    folder, out, data, workers, said, run = (bench[k] for k in ("folder", "out", "data", "workers", "said", "run"))
    for place in (commands.REPO / "x", tmp_path / "owner-data" / "o", data / "o", folder / "o"):
        assert run(out_folder=place) == 6 and workers == []
    assert run(data_folder=tmp_path / "no-env") == 7 and workers == []
    assert said[-1] == words.BENCH_ARM_NEEDS_ENVIRONMENT.format(arm="the voice method", choice="whisperx_pyannote")
    listed = json.loads((folder / "recordings.json").read_text(encoding="utf-8"))
    listed["recordings"][2]["voice_only"] = False
    other = tmp_path / "other"
    other.mkdir()
    for name in ("one.wav", "two.wav", "minute.wav"):
        (other / name).write_bytes((folder / name).read_bytes())
    (other / "recordings.json").write_text(json.dumps(listed), encoding="utf-8")
    assert commands2.speech_voice(out, other, data, None, None, say=said.append, make_worker=lambda d: workers.append(1)) == 4
    assert workers == [] and said[-1] == words.BENCH_VOICE_NEEDS_VOICE_ONLY.format(name="one", voice="minute")
