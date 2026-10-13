"""The two arms that belong to the bench (spec 15.9, rulings 3, 8, 12, 14
and 15; R31): the app cannot reach them. No model runs here."""

import hashlib
import json
from pathlib import Path

import pytest

from openconsult.bench.speech import arms
from openconsult.bench.speech.arms import ARMS, TIED_PAIR, V1_LINE, door_for
from openconsult.cli import main
from openconsult.speech import environment
from openconsult.speech.choices import CHOICES, NEMOTRON, NEMOTRON_TIME_SLACK_S, WHISPERX_PYANNOTE
from openconsult.speech.door import Door, make_door
from tests.fakes import MadeUpWorker

REPO = Path(arms.__file__).resolve().parents[3]
LINE_SHA256 = "c72f4adcebbc7907cb6ad55b21c7bc1484f3aa5d2d428d70cf537cf0b2bb9981"


def test_ruling_15_the_app_cannot_reach_an_arm_of_the_bench(tmp_path):
    for name in ("nemotron_tied_pair", "whisperx_v1_line"):
        assert name not in CHOICES
        started = []
        for command in ("self-test", "install-speech"):
            with pytest.raises(SystemExit) as refused:
                main([command, "--choice", name, "--data-folder", str(tmp_path)], say=lambda line: None,
                     make_speech=lambda folder, choice: started.append(choice), run_process=lambda *a, **k: started.append(a))
            assert refused.value.code == 2 and started == []
    # Every door the app can build runs a worker under openconsult/speech, never under the bench.
    for choice in CHOICES.values():
        command = environment.worker_command(tmp_path, choice)
        assert Path(command[1]).is_relative_to(REPO / "openconsult" / "speech") and "bench" not in command[1]
        door = make_door(tmp_path, choice)
        assert door.choice is choice


def test_ruling_15_an_arm_of_the_bench_runs_its_own_worker_in_a_choices_environment(tmp_path, monkeypatch):
    built = []

    class RecordingWorker(MadeUpWorker):
        def __init__(self, command, log_path=None, env=None):
            super().__init__(ready=False)
            built.append((command, log_path, env))

    monkeypatch.setattr(arms, "Worker", RecordingWorker)
    tied = door_for(ARMS["nemotron_tied_pair"], tmp_path, environ={"SPEECHMATICS_API_KEY": "made-up", "HOME": "x"})
    assert tied.choice is TIED_PAIR and not tied.installed                 # the Nemotron environment is not built here
    assert tied.open(16000, speakers=2).failure == "not_installed" and built == []
    python = environment.python(tmp_path, NEMOTRON)
    python.parent.mkdir(parents=True)
    python.write_text("")
    tied = door_for(ARMS["nemotron_tied_pair"], tmp_path, environ={"SPEECHMATICS_API_KEY": "made-up", "HOME": "x"})
    assert tied.installed and tied.open(16000, speakers=2).failure == "died"
    command, log_path, env = built[0]
    assert command == [str(python), str(REPO / "openconsult" / "bench" / "speech" / "tied" / "worker.py")]
    assert log_path.name == "nemotron_tied_pair.log" and "SPEECHMATICS_API_KEY" not in env and env["HF_HUB_OFFLINE"] == "1"
    line = door_for(ARMS["whisperx_v1_line"], tmp_path)
    assert line.choice is V1_LINE and ARMS["whisperx_v1_line"].environment_of is WHISPERX_PYANNOTE
    assert ARMS["whisperx_v1_line"].worker_script == REPO / "openconsult" / "bench" / "speech" / "v1line" / "worker.py"


def test_ruling_3_v1s_line_is_a_file_of_the_bench_with_this_hash():
    path = REPO / "openconsult" / "bench" / "speech" / "v1line" / "v1_live_line.txt"
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == LINE_SHA256
    assert data.endswith(b"\n") and not data.endswith(b"\n\n") and b"\n" not in data[:-1]     # one line, one break after it
    assert ARMS["whisperx_v1_line"].choice.declares == WHISPERX_PYANNOTE.declares             # the same choice, one change


def test_ruling_8_the_tied_pair_declares_no_confidence_live_labels_one_transcript_and_the_wide_figure():
    declares = TIED_PAIR.declares
    assert (declares.confidence, declares.speakers, declares.second_transcript) == ("none", "live", False)
    assert declares.time_slack_s == NEMOTRON_TIME_SLACK_S == 1.0
    # The tied pair's speaker model is the one of the Nemotron choice, at its revision.
    tied = json.loads((REPO / "openconsult" / "bench" / "speech" / "tied" / "models.json").read_text(encoding="utf-8"))
    app = json.loads((REPO / "openconsult" / "speech" / "nemotron" / "models.json").read_text(encoding="utf-8"))
    assert tied["speakers"] == app["speakers"]
    assert tied["words"]["revision"] == "ea30d66debe3740a08b573244286791d423d6b3e"        # v1's revision of the 3.5 model


def test_the_arms_table_is_the_four_choices_and_the_two_of_the_bench_with_their_cloud_service():
    assert list(ARMS) == ["whisperx_pyannote", "whisperx_v1_line", "nemotron", "nemotron_tied_pair", "speechmatics", "assemblyai"]
    assert {name: arm.cloud_service for name, arm in ARMS.items()} == {
        "whisperx_pyannote": None, "whisperx_v1_line": None, "nemotron": None, "nemotron_tied_pair": None,
        "speechmatics": "speechmatics", "assemblyai": "assemblyai"}
    assert all(ARMS[name].choice is CHOICES[name] for name in CHOICES)


def test_a_workers_notes_at_stop_pass_through_the_door_unread():
    worker = MadeUpWorker(final={"last_live": [], "revisions": [], "seconds": {},
                                 "notes": {"late_changes": [{"id": 1, "text": "later words.", "end": 2.0}]}})
    door = Door(TIED_PAIR, make_worker=lambda: worker, installed=lambda: True)
    door.open(16000, speakers=2)
    final = door.stop(speakers=2)
    assert final.ok and final.notes == {"late_changes": [{"id": 1, "text": "later words.", "end": 2.0}]}
    assert final.lines == () and final.revisions == ()                                    # the notes changed nothing
    plain = Door(WHISPERX_PYANNOTE, make_worker=lambda: MadeUpWorker(), installed=lambda: True)
    plain.open(16000)
    assert plain.stop(speakers=1).notes == {}
