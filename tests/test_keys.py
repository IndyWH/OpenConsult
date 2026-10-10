"""The keys of the cloud services (spec 7.3 rule 3; 15.9, the details of
5b): one module reads them, a worker holds its own key and no other, and
a key appears nowhere it should not. Every key here is made up."""

from openconsult import words
from openconsult.settings import keys
from openconsult.speech import environment
from openconsult.speech.choices import ASSEMBLYAI, NEMOTRON, SPEECHMATICS, WHISPERX_PYANNOTE
from openconsult.speech.door import make_door

MADE_UP = "made-up-key-0123456789"


def test_7_3_rule_3_a_key_comes_from_the_environment_or_the_env_file(tmp_path):
    assert keys.read_key("SPEECHMATICS_API_KEY", tmp_path, {}) is None
    assert keys.read_key("SPEECHMATICS_API_KEY", tmp_path, {"SPEECHMATICS_API_KEY": MADE_UP}) == MADE_UP
    (tmp_path / ".env").write_text(
        "# the keys\r\nSPEECHMATICS_API_KEY='made-up-from-file'\r\nASSEMBLYAI_API_KEY=\r\nno equals sign\r\n"
        'OTHER="x=y"\n', encoding="utf-8")
    assert keys.read_key("SPEECHMATICS_API_KEY", tmp_path, {}) == "made-up-from-file"
    assert keys.read_key("ASSEMBLYAI_API_KEY", tmp_path, {}) is None               # an empty value is no key
    assert keys.read_key("SPEECHMATICS_API_KEY", tmp_path, {"SPEECHMATICS_API_KEY": MADE_UP}) == MADE_UP   # the environment first
    assert keys.parse_env('OTHER="x=y"\n') == {"OTHER": "x=y"}


def test_a_worker_holds_its_own_key_and_no_other(tmp_path):
    both = {"PATH": "x", "SPEECHMATICS_API_KEY": "made-up-s", "ASSEMBLYAI_API_KEY": "made-up-a"}
    for choice in (WHISPERX_PYANNOTE, NEMOTRON):
        env = environment.worker_env(both, choice.key, None)
        assert "SPEECHMATICS_API_KEY" not in env and "ASSEMBLYAI_API_KEY" not in env and env["PATH"] == "x"
    env = environment.worker_env(both, SPEECHMATICS.key, "made-up-s")
    assert env["SPEECHMATICS_API_KEY"] == "made-up-s" and "ASSEMBLYAI_API_KEY" not in env
    env = environment.worker_env(both, ASSEMBLYAI.key, "made-up-a")
    assert env["ASSEMBLYAI_API_KEY"] == "made-up-a" and "SPEECHMATICS_API_KEY" not in env
    for choice in (SPEECHMATICS, ASSEMBLYAI, NEMOTRON, WHISPERX_PYANNOTE):
        command = environment.worker_command(tmp_path, choice, "Linux")
        assert all("made-up" not in part for part in command)                       # never on a command line


def test_6_4_a_cloud_choice_is_installed_with_the_base_app_alone(tmp_path):
    import sys
    for choice in (SPEECHMATICS, ASSEMBLYAI):
        assert environment.installed(tmp_path, choice, "Windows")
        command = environment.worker_command(tmp_path, choice, "Windows")
        assert command == [sys.executable, str(choice.worker_folder / "worker.py")]
    assert not environment.installed(tmp_path, NEMOTRON, "Linux")


def test_10_4_the_apps_door_fails_plainly_with_no_key_and_starts_nothing(tmp_path):
    door = make_door(tmp_path, SPEECHMATICS, environ={})
    failed = door.open(16000, speakers=1)
    assert (failed.failure, failed.detail) == ("no_key", words.NO_KEY.format(service="Speechmatics", name="SPEECHMATICS_API_KEY"))
    assert not (tmp_path / "speech").exists()                                       # no log, no worker
    (tmp_path / ".env").write_text(f"SPEECHMATICS_API_KEY={MADE_UP}\n")
    assert door.open(16000, speakers=1).failure != "no_key"
    door.close()
    log = tmp_path / "speech" / "speechmatics" / "worker.log"
    assert not log.exists() or MADE_UP not in log.read_text(errors="replace")      # the log never holds the key
