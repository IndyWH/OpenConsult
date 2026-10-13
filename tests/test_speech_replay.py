"""The replay through the door (spec 13.4 rule 1; 15.9, the details of 5c;
ruling 14; R20; V1_LESSONS 9.4). A made-up worker behind the door; the
recordings are made sound."""

import datetime as dt

from openconsult import words
from openconsult.bench.speech import replay
from openconsult.bench.speech.arms import ARMS, Arm
from openconsult.bench.speech.banked import load_list, named
from openconsult.bench.speech.replay import run, run_many
from openconsult.bench.writer import ResultWriter
from openconsult.speech.choices import NEMOTRON, SPEECHMATICS, WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from tests.fakes import MadeUpWorker
from tests.made_up_recordings import made_up_recordings
from tests.test_speech_door import seg

NOW = dt.datetime(2026, 10, 10, 12, 0, 0)


class FakeClock:
    """A clock that the fake sleep moves, so the replay waits for nothing
    and the order of waiting and feeding can be seen."""

    def __init__(self):
        self.now, self.events = 100.0, []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.events.append(("sleep", round(seconds, 3)))
        self.now += seconds

    def fed(self):
        self.events.append(("feed",))


def door_of(worker, choice=NEMOTRON, clock=None):
    door = Door(choice, make_worker=lambda: worker, installed=lambda: True)
    if clock is not None:
        feed = door.feed

        def noted(piece):
            clock.fed()
            return feed(piece)
        door.feed = noted
    return door


def recordings_of(kept, **over):
    folder = made_up_recordings(kept.folder, **over)
    kept.settle()
    return load_list(folder)


def test_13_4_rule_1_a_piece_is_fed_when_its_sound_has_ended_at_the_files_rate(recordings_kept):
    for rate in (16000, 48000):
        listed = recordings_of(recordings_kept, rate=rate, seconds=1.0)
        from openconsult.bench.speech import sound
        one = named(listed, "one")
        pcm = sound.read_wav(one.path, rate)
        worker, clock = MadeUpWorker(), FakeClock()
        result = run(door_of(worker, NEMOTRON, clock), ARMS["nemotron"], one, pcm, sleep=clock.sleep, clock=clock, now=lambda: NOW)
        audio = worker.requested("audio")
        assert len(audio) == 4 and all(len(p) == rate // 4 * 2 for _, p in audio)
        assert worker.requested("open")[0][0]["rate"] == rate and worker.requested("open")[0][0]["speakers"] == 2
        assert worker.requested("stop")[0][0]["speakers"] == 2
        # Wait, then feed: piece n goes in when the clock reads n times 0.25 s.
        assert clock.events == [("sleep", 0.25), ("feed",)] * 4
        assert result["failure"] is None and result["rate"] == rate and result["piece_s"] == 0.25
        for path in recordings_kept.folder.iterdir():
            path.unlink()
        recordings_kept.settle()


def test_everything_the_door_gives_is_kept(recordings_kept):
    listed = recordings_of(recordings_kept)                       # 3.0 s: 12 pieces
    one = named(listed, "one")
    from openconsult.bench.speech import sound
    pcm = sound.read_wav(one.path, 16000)
    live = [[] for _ in range(12)]
    live[7] = [{"start": 0.6, "end": 1.6, "text": "made up words"}]
    pending = [[] for _ in range(12)]
    pending[5] = [{"start": 0.6, "end": 1.4, "text": "made up"}]
    pending[6] = [{"start": 0.6, "end": 1.4, "text": "made up"}]
    final = {"last_live": [{"start": 1.8, "end": 2.4, "text": "the tail"}],
             "segments": [seg(0.6, 2.4, "made up words the tail", "S0", 0.9)], "seconds": {"stop": 1.0}}
    worker, clock = MadeUpWorker(live=live, pending=pending, final=final), FakeClock()
    result = run(door_of(worker, WHISPERX_PYANNOTE), ARMS["whisperx_pyannote"], one, pcm,
                 sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert [p["n"] for p in result["pieces"]] == [6, 8]           # piece 7 repeats the partial: nothing new, not stored
    assert result["pieces"][0]["partial"] == "made up" and result["pieces"][0]["t"] == 1.5
    stored = result["pieces"][1]
    assert stored["lines"][0]["text"] == "made up words" and stored["partial"] == "" and stored["t"] == 2.0
    assert stored["fed_s"] == 2.0 and stored["refused"] == [] and stored["revisions"] == []
    stop = result["stop"]
    assert stop["t"] == 3.0 and [line["text"] for line in stop["lines"]] == ["made up words the tail"]
    assert stop["last_live"][0]["text"] == "the tail" and stop["raw"][0]["refused"] is False
    assert stop["seconds"] == {"stop": 1.0} and stop["speakers"] == {} and stop["notes"] == {}
    assert len(result["loudness"]["dbfs"]) == 30 and result["loudness"]["window_s"] == 0.1
    assert result["loudness"]["dbfs"][0] is None and abs(result["loudness"]["dbfs"][10] + 20.0) < 0.5
    assert result["stamp"]["choice"] == "whisperx_pyannote" and result["time_slack_s"] == 0.0
    assert result["started_at"] == "2026-10-10T12:00:00" and result["quiet_dbfs"] == -40.0
    assert result["recording_sha256"] == one.sha256 and result["script_sha256"] == one.script_sha256


def test_a_failure_in_the_middle_is_kept_as_failed_and_the_run_goes_on(tmp_path, recordings_kept):
    listed = recordings_of(recordings_kept)
    said, clock = [], FakeClock()
    dying = [MadeUpWorker(live=[[{"start": 0.0, "end": 0.3, "text": "x"}]], die_after=5), MadeUpWorker()]
    writer = ResultWriter(tmp_path / "out")
    summary = run_many(ARMS["whisperx_pyannote"], listed, lambda: door_of(dying.pop(0), WHISPERX_PYANNOTE), writer,
                       say=said.append, sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert summary == {"run": ["two"], "kept": [], "failed": ["one"], "refused": []}
    failed = writer.read("whisperx_pyannote", "one")
    assert failed["failure"] == {"at": "feed", "piece": 4, "failure": "died", "detail": "made-up: died with exit code 3"}
    assert [p["n"] for p in failed["pieces"]] == [1] and failed["stop"] is None
    assert len(failed["loudness"]["dbfs"]) == 10                  # the four pieces fed, the last one measured before the death
    assert any(line.startswith("whisperx_pyannote on one failed at feed") for line in said)
    assert writer.read("whisperx_pyannote", "two")["failure"] is None


def test_9_4_a_stopped_run_carries_on_with_the_recordings_that_have_no_result(tmp_path, recordings_kept):
    listed = recordings_of(recordings_kept)
    clock, said = FakeClock(), []
    writer = ResultWriter(tmp_path / "out")
    first = run_many(ARMS["nemotron"], listed[:1], lambda: door_of(MadeUpWorker()), writer, say=said.append,
                     sleep=clock.sleep, clock=clock, now=lambda: NOW)
    made = []
    again = run_many(ARMS["nemotron"], listed, lambda: made.append(door_of(MadeUpWorker())) or made[-1], writer,
                     say=said.append, sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert first["run"] == ["one"] and again == {"run": ["two"], "kept": ["one"], "failed": [], "refused": []}
    assert len(made) == 1 and words.BENCH_RESULT_EXISTS.format(arm="nemotron", name="one") in said


def test_ruling_14_consent_is_held_by_code(tmp_path, recordings_kept):
    listed = recordings_of(recordings_kept)                       # one: no cloud consent; two: both services
    clock, said, built = FakeClock(), [], []
    writer = ResultWriter(tmp_path / "out")
    cloud = Arm("speechmatics", SPEECHMATICS, SPEECHMATICS, None, "speechmatics")

    def make():
        built.append(MadeUpWorker())
        return door_of(built[-1], SPEECHMATICS)

    summary = run_many(cloud, listed, make, writer, say=said.append, sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert summary == {"run": ["two"], "kept": [], "failed": [], "refused": ["one"]}
    assert words.BENCH_NO_CLOUD_CONSENT.format(name="one", service="Speechmatics") in said
    assert len(built) == 1 and built[0].starts == 1               # no worker for one; one worker for two
    assert not writer.exists("speechmatics", "one") and writer.exists("speechmatics", "two")
    # A local arm never asks the cloud field: both run.
    local = run_many(ARMS["nemotron"], listed, lambda: door_of(MadeUpWorker()), ResultWriter(tmp_path / "local"),
                     say=said.append, sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert local["run"] == ["one", "two"] and not ARMS["nemotron"].cloud and ARMS["assemblyai"].cloud


def test_R20_the_result_carries_the_stamp_and_an_arms_hash_when_the_worker_gives_one(recordings_kept):
    listed = recordings_of(recordings_kept)
    from openconsult.bench.speech import sound
    one = named(listed, "one")
    info = {"type": "ready", "models": {"live": {"revision": "r1"}, "live_line": {"sha256": "c72f4adc"}},
            "versions": {"made-up": "0.0"}}
    clock = FakeClock()
    result = run(door_of(MadeUpWorker(info=info), WHISPERX_PYANNOTE), ARMS["whisperx_pyannote"], one,
                 sound.read_wav(one.path, 16000), sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert result["stamp"]["models"]["live_line"] == {"sha256": "c72f4adc"} and result["stamp"]["versions"] == {"made-up": "0.0"}
    assert replay.PIECE_S == 0.25


def test_15_9_5d_the_feed_start_is_written_to_the_started_file_and_the_moment_stop_was_asked_is_kept(recordings_kept, tmp_path):
    """Two switches of the replay for the test of 5d. Given, the moment the
    feed began goes to the file and t_asked into the result; not given,
    nothing is written and the result is as today, plus t0_epoch."""
    listed = recordings_of(recordings_kept)
    one = named(listed, "one")
    from openconsult.bench.speech import sound
    pcm = sound.read_wav(one.path, 16000)
    worker, clock = MadeUpWorker(), FakeClock()
    started = tmp_path / "feeding.json"
    result = run(door_of(worker), ARMS["nemotron"], one, pcm, sleep=clock.sleep, clock=clock, now=lambda: NOW,
                 wall=lambda: 1234.5, started_file=started)
    import json
    assert json.loads(started.read_text(encoding="utf-8")) == {"arm": "nemotron", "recording": "one", "t0_epoch": 1234.5}
    assert result["t0_epoch"] == 1234.5 and result["stop"]["t_asked"] == 3.0 and result["stop"]["t"] == 3.0
    assert "stop_pause" not in result
    plain = run(door_of(MadeUpWorker()), ARMS["nemotron"], one, pcm, sleep=clock.sleep, clock=clock, now=lambda: NOW)
    assert not (tmp_path / "x").exists() and plain["stop"]["t_asked"] == plain["stop"]["t"] - 0.0
    assert sorted(plain) == sorted(result)                              # no switch: the same shape


def test_15_9_5d_the_pause_before_stop_waits_for_the_go_file_and_stops_anyway_at_its_limit(recordings_kept, tmp_path, monkeypatch):
    listed = recordings_of(recordings_kept)
    one = named(listed, "one")
    from openconsult.bench.speech import sound
    pcm = sound.read_wav(one.path, 16000)
    folder = tmp_path / "pause"
    clock = FakeClock()
    real_sleep = clock.sleep

    def sleeping(seconds):
        real_sleep(seconds)
        if (folder / replay.STOP_WANTED).exists() and clock.now >= 104.0:
            (folder / replay.STOP_GO).write_text("go", encoding="utf-8")        # the driver answers after 1 s
    result = run(door_of(MadeUpWorker()), ARMS["nemotron"], one, pcm, sleep=sleeping, clock=clock, now=lambda: NOW,
                 wall=lambda: 7.0, pause_at_stop=folder)
    assert result["stop_pause"]["went_ahead"] is False and result["stop_pause"]["waited_s"] == 1.0
    assert result["stop"]["t_asked"] == 4.0 and result["stop"]["t"] == 4.0        # Stop was asked after the pause
    monkeypatch.setattr(replay, "PAUSE_LIMIT_S", 2.0)
    late = run(door_of(MadeUpWorker()), ARMS["nemotron"], one, pcm, sleep=real_sleep, clock=clock, now=lambda: NOW,
               wall=lambda: 7.0, pause_at_stop=tmp_path / "nobody")
    assert late["stop_pause"]["went_ahead"] is True and late["stop_pause"]["waited_s"] == 2.0 and late["stop"]
