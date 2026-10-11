"""The three commands of the speech bench (spec 15.9, the details of 5c;
R18; 13.4 rule 3; ruling 14; ruling 15). A made-up door; the recordings
are made sound."""

import json
from pathlib import Path

import pytest

from openconsult import words
from openconsult.bench import cli
from openconsult.bench.speech import commands
from openconsult.bench.speech.sound import read_wav
from openconsult.bench.writer import ResultWriter
from openconsult.settings import paths
from openconsult.speech import environment
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from tests.fakes import MadeUpWorker
from tests.made_up_recordings import made_up_recordings, scripts_folder, write_wav
from tests.test_speech_replay import FakeClock
from tests.test_speech_tables import MARKS


@pytest.fixture
def bench(tmp_path, recordings_kept, monkeypatch):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    folder = made_up_recordings(recordings_kept.folder)
    recordings_kept.settle()
    data = tmp_path / "data"
    for choice in (WHISPERX_PYANNOTE, NEMOTRON):
        python = environment.python(data, choice)
        python.parent.mkdir(parents=True)
        python.write_text("")
    built, said, clock = [], [], FakeClock()

    def make_door(arm, data_folder):
        built.append(MadeUpWorker())
        return Door(arm.choice, make_worker=lambda: built[-1], installed=lambda: True)

    def run(arm, out, names=None, recordings=None):
        return commands.speech_run(recordings or folder, arm, data, out, names, say=said.append, make_door=make_door,
                                   sleep=clock.sleep, clock=clock)

    return {"folder": folder, "data": data, "built": built, "said": said, "run": run}


def test_the_commands_refuse_before_anything_is_fed(tmp_path, bench):
    folder, data, built, said, run = (bench[k] for k in ("folder", "data", "built", "said", "run"))
    for place in (commands.REPO / "x", tmp_path / "owner-data" / "out", data / "out", folder / "results"):
        assert run("nemotron", place) == 6 and built == []
    assert said[-1].startswith("Results may not go under")
    assert run("nemotron", tmp_path / "out", ["not-listed"]) == 3 and built == []
    assert words.BENCH_NOT_LISTED.format(name="not-listed") in said
    assert run("speechmatics", tmp_path / "out2", ["one"]) == 0 and built == []     # consent: refused, no door
    assert words.BENCH_NO_CLOUD_CONSENT.format(name="one", service="Speechmatics") in said
    assert run("speechmatics", tmp_path / "out2", ["two"]) == 0 and len(built) == 1
    # A changed file and a bad list, in a folder of their own (the guarded folder is never written).
    other = made_up_recordings(tmp_path / "other")
    pcm = read_wav(other / "one.wav", 16000)
    write_wav(other / "one.wav", pcm[:-2] + b"\0\1")
    assert run("nemotron", tmp_path / "out3", ["one"], recordings=other) == 3 and len(built) == 1
    assert any(line.startswith("The recording one is not the file the list describes") for line in said)
    (other / "recordings.json").write_text(json.dumps({"recordings": [{"name": "x"}]}))
    assert run("nemotron", tmp_path / "out4", recordings=other) == 3 and said[-1].startswith("The banked list cannot be used")


def test_speech_run_writes_one_result_per_recording_and_carries_on(tmp_path, bench):
    folder, said, run, built = bench["folder"], bench["said"], bench["run"], bench["built"]
    assert run("nemotron", tmp_path / "out") == 0
    results = ResultWriter(tmp_path / "out").read_all()
    assert sorted(results) == [("nemotron", "one"), ("nemotron", "two")] and len(built) == 2
    assert run("nemotron", tmp_path / "out") == 0 and len(built) == 2             # nothing to do, nothing started
    assert words.BENCH_RESULT_EXISTS.format(arm="nemotron", name="one") in said
    # An arm whose environment is not in the data folder is refused with the sentence.
    assert commands.speech_run(folder, "nemotron_tied_pair", tmp_path / "no-env", tmp_path / "out4", None, say=said.append) == 7
    assert said[-1] == words.BENCH_ARM_NEEDS_ENVIRONMENT.format(arm="nemotron_tied_pair", choice="nemotron")


def test_speech_score_writes_the_tables_once_from_the_stored_results(tmp_path, bench):
    folder, said, run = bench["folder"], bench["said"], bench["run"]
    run("nemotron", tmp_path / "out")
    marks = tmp_path / "marks.json"
    marks.write_text(json.dumps(MARKS))
    scripts = scripts_folder(tmp_path)
    assert commands.speech_score(tmp_path / "out", folder, [tmp_path / "nowhere", scripts], marks, tmp_path / "w", say=said.append) == 0
    assert (tmp_path / "w" / "report.md").exists() and (tmp_path / "w" / "scores.json").exists()
    assert said[-1].startswith("Scored 2 results of 1 arms")
    assert commands.speech_score(tmp_path / "out", folder, [scripts], marks, tmp_path / "w", say=said.append) == 6
    assert said[-1].endswith("exists and is never written over.")
    assert commands.speech_score(tmp_path / "out", folder, [tmp_path / "nowhere"], marks, tmp_path / "w2", say=said.append) == 8


def test_the_command_names_the_six_arms_and_no_other(tmp_path, bench, monkeypatch):
    folder, data, run = bench["folder"], bench["data"], bench["run"]
    with pytest.raises(SystemExit) as refused:
        cli.main(["speech-run", "--recordings", str(folder), "--arm", "made-up", "--data-folder", str(data), "--out", str(tmp_path / "o")])
    assert refused.value.code == 2
    seen = []
    monkeypatch.setattr(commands, "speech_run", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["speech-run", "--recordings", str(folder), "--arm", "whisperx_v1_line", "--data-folder", str(data),
                     "--out", str(tmp_path / "o"), "--recording", "one"]) == 0
    assert seen[0][1] == "whisperx_v1_line" and seen[0][4] == ["one"]
    monkeypatch.setattr(commands, "speech_score", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["speech-score", "--out", str(tmp_path / "o"), "--recordings", str(folder), "--scripts", "a", "--scripts", "b",
                     "--marks", "m.json", "--write", str(tmp_path / "w")]) == 0
    assert [str(p) for p in seen[1][2]] == ["a", "b"]
    monkeypatch.setattr(commands, "speech_fetch", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["speech-fetch", "--data-folder", str(data)]) == 0 and seen[2][0] == data


def test_speech_fetch_runs_the_tied_pairs_fetch_with_the_nemotron_environment(tmp_path, bench):
    data, said = bench["data"], bench["said"]
    calls = []

    class Done:
        returncode, stderr = 0, ""
        stdout = json.dumps({"model": "words: made-up", "found": True, "fetched": False, "bytes": 5, "ok": True}) + "\n"

    def run(command, **kwargs):
        calls.append(command)
        return Done()

    assert commands.speech_fetch(data, say=said.append, run=run) == 0
    assert calls[0][0] == str(environment.python(data, NEMOTRON))
    assert Path(calls[0][1]).parts[-2:] == ("tied", "fetch.py")           # by parts: the separator differs by system
    assert said[-1] == words.MODEL_FOUND.format(model="words: made-up", size="1 kB")
    assert commands.speech_fetch(tmp_path / "no-env", say=said.append, run=run) == 7
