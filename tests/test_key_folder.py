"""The key folder of the speech bench (spec 15.9, the details of 5e: the
keys; 7.3 rule 3). A cloud arm of the bench takes its key from a folder
apart from the data folder of its workers, read by the one module that
reads keys; nothing is written there, no copy is made, and the app's own
door and self-test read a key as before. Every key here is made up."""

from pathlib import Path

from openconsult import cli as app_cli
from openconsult.bench import cli
from openconsult.bench.speech import arms, commands
from openconsult.bench.speech.arms import ARMS, door_for
from openconsult.settings import paths
from openconsult.speech.choices import SPEECHMATICS
from openconsult.speech.door import make_door
from tests.fakes import MadeUpWorker

MADE_UP, OTHER = "made-up-key-of-the-key-folder", "made-up-key-of-the-data-folder"


def _listing(folder: Path) -> list:
    return sorted((str(p.relative_to(folder)), p.stat().st_size) for p in folder.rglob("*"))


def test_the_keys_a_cloud_arm_takes_its_key_from_the_key_folder_alone(tmp_path, monkeypatch):
    built = []

    class RecordingWorker(MadeUpWorker):
        def __init__(self, command, log_path=None, env=None):
            super().__init__()
            built.append((command, log_path, env))

    monkeypatch.setattr(arms, "Worker", RecordingWorker)
    data, key_folder = tmp_path / "data", tmp_path / "keys"
    data.mkdir()
    key_folder.mkdir()
    (data / ".env").write_bytes(f"SPEECHMATICS_API_KEY={OTHER}\n".encode())
    # No key in the key folder: no key, whatever the data folder and the process environment hold.
    door = door_for(ARMS["speechmatics"], data, environ={"SPEECHMATICS_API_KEY": OTHER, "PATH": "x"}, key_folder=key_folder)
    assert door.open(48000, speakers=2).failure == "no_key" and built == []
    (key_folder / ".env").write_bytes(f"SPEECHMATICS_API_KEY={MADE_UP}\nASSEMBLYAI_API_KEY=made-up-a\n".encode())
    before = _listing(key_folder)
    door = door_for(ARMS["speechmatics"], data, environ={"SPEECHMATICS_API_KEY": OTHER, "PATH": "x"}, key_folder=key_folder)
    assert door.open(48000, speakers=2).ok
    command, log_path, env = built[0]
    assert env["SPEECHMATICS_API_KEY"] == MADE_UP and "ASSEMBLYAI_API_KEY" not in env     # its own key and no other
    assert all(MADE_UP not in part for part in command)                                    # never on a command line
    assert log_path.is_relative_to(data)                                                   # the log goes to the data folder
    door.close()
    assert _listing(key_folder) == before                                                  # nothing written in the key folder
    # A local arm is given no key, with or without a key folder.
    python = arms.environment.python(data, ARMS["nemotron"].environment_of)
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    local = door_for(ARMS["nemotron"], data, environ={"PATH": "x"}, key_folder=key_folder)
    assert local.choice is ARMS["nemotron"].choice


def test_the_keys_speech_run_refuses_results_under_the_key_folder_and_the_parser_takes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    key_folder = tmp_path / "keys"
    assert Path(key_folder) in commands.forbidden_for(tmp_path / "data", [], key_folder)
    seen = {}
    monkeypatch.setattr(commands, "speech_run", lambda *a, **k: seen.update(run=k["key_folder"]) or 0)
    monkeypatch.setattr(commands, "speech_selftest", lambda *a, **k: seen.update(selftest=a) or 0)
    assert cli.main(["speech-run", "--recordings", "r", "--arm", "speechmatics", "--data-folder", "d", "--out", "o",
                     "--key-folder", str(key_folder)]) == 0
    assert cli.main(["speech-selftest", "--choice", "assemblyai", "--data-folder", "d", "--key-folder", str(key_folder)]) == 0
    assert seen == {"run": key_folder, "selftest": ("assemblyai", Path("d"), key_folder)}


def test_the_keys_the_bench_self_test_stores_its_result_in_the_data_folder_given(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner-data")
    data, key_folder, asked = tmp_path / "data", tmp_path / "keys", []
    key_folder.mkdir()
    (key_folder / ".env").write_bytes(f"SPEECHMATICS_API_KEY={MADE_UP}\n".encode())
    before = _listing(key_folder)

    def self_test(data_folder, choice, say, make_speech, sleep):
        asked.append((data_folder, choice))
        make_speech(data_folder, choice).close()
        return 0

    monkeypatch.setattr(app_cli, "self_test", self_test)
    made = []

    def make(arm, folder, key_folder=None):
        made.append((arm.name, folder, key_folder))
        return door_for(arm, folder, environ={}, key_folder=key_folder)

    assert commands.speech_selftest("speechmatics", data, key_folder, say=lambda line: None, make_door=make) == 0
    assert asked == [(data, SPEECHMATICS)] and made == [("speechmatics", data, key_folder)]
    assert _listing(key_folder) == before
    # The owner's own data folder, and the key folder itself, are never the bench's data folder.
    said = []
    assert commands.speech_selftest("speechmatics", key_folder, key_folder, say=said.append, make_door=make) == 6
    assert commands.speech_selftest("speechmatics", tmp_path / "owner-data", key_folder, say=said.append, make_door=make) == 6
    assert len(asked) == 1 and len(said) == 2


def test_7_3_rule_3_the_apps_own_door_and_self_test_read_a_key_as_before(tmp_path):
    # The app's door: the environment first, then the data folder's own file; it knows no key folder.
    (tmp_path / ".env").write_bytes(f"SPEECHMATICS_API_KEY={OTHER}\n".encode())
    assert make_door(tmp_path, SPEECHMATICS, environ={}).has_key
    assert make_door(tmp_path, SPEECHMATICS, environ={"SPEECHMATICS_API_KEY": MADE_UP}).has_key
    assert not make_door(tmp_path / "empty", SPEECHMATICS, environ={}).has_key
    import inspect
    assert "key_folder" not in inspect.signature(make_door).parameters
    assert "key_folder" not in inspect.signature(app_cli.self_test).parameters
    # With no key folder, the bench builds the app's own door for a choice.
    assert door_for(ARMS["speechmatics"], tmp_path, environ={}).has_key
