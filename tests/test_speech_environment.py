"""Where a speech environment lives and how it is built (spec 6.2, 6.4;
15.9; V1_LESSONS 7.2, 7.5; plan review, change 1). A made-up uv and a
made-up fetch: nothing is downloaded and no environment is built."""

import json
from types import SimpleNamespace

import pytest

from openconsult import words
from openconsult.cli import main
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE as CHOICE


@pytest.mark.parametrize("system, tail", [
    ("Linux", ("bin", "python")), ("Darwin", ("bin", "python")), ("Windows", ("Scripts", "python.exe")),
])
def test_7_2_the_workers_python_for_each_system(tmp_path, system, tail):
    python = environment.python(tmp_path, CHOICE, system)
    assert python == tmp_path / "speech" / "whisperx_pyannote" / ".venv" / tail[0] / tail[1]
    assert not environment.installed(tmp_path, CHOICE, system)       # a path check only
    python.parent.mkdir(parents=True)
    python.write_text("")
    assert environment.installed(tmp_path, CHOICE, system)
    command = environment.worker_command(tmp_path, CHOICE, system)
    assert command[0] == str(python) and command[1].endswith("worker.py") and len(command) == 2
    env = environment.worker_env({"HF_HOME": "/made-up", "PATH": "x"})
    assert env["HF_HUB_OFFLINE"] == "1" and env["HF_HOME"] == "/made-up"     # the hub finds its own settings


class MadeUpRun:
    """Records each command; answers as uv and the fetch script would."""

    def __init__(self, installed=True, uv_fails=False, models=None):
        self.commands, self.envs = [], []
        self.installed, self.uv_fails = installed, uv_fails
        self.models = models if models is not None else [
            {"model": "made-up live", "found": True, "fetched": False, "bytes": 1_500_000_000, "ok": True},
            {"model": "made-up stop", "found": False, "fetched": True, "bytes": 2_900_000_000, "ok": True},
        ]

    def __call__(self, command, env=None, **kwargs):
        self.commands.append(command)
        self.envs.append(env)
        if command[0] == "/made-up/uv":
            if self.uv_fails:
                return SimpleNamespace(returncode=1, stdout="", stderr="error: made-up: no such lock\n")
            text = "Installed 156 packages\n" if self.installed else "Audited 156 packages\n"
            return SimpleNamespace(returncode=0, stdout="", stderr=text)
        out = "\n".join(json.dumps(m) for m in self.models)
        return SimpleNamespace(returncode=0, stdout=out + "\n", stderr="")


def test_15_9_the_environment_is_built_from_the_lock_file_into_the_data_folder(tmp_path):
    said, run = [], MadeUpRun()
    report = environment.build(tmp_path, CHOICE, say=said.append, run=run, which=lambda name: "/made-up/uv",
                               environ={"HF_HOME": "/made-up"}, system="Linux")
    assert report.ok and report.built
    uv, fetch = run.commands
    venv = tmp_path / "speech" / "whisperx_pyannote" / ".venv"
    assert uv == ["/made-up/uv", "sync", "--locked", "--project", str(CHOICE.worker_folder), "--python", "3.12"]
    assert run.envs[0] == {"HF_HOME": "/made-up", "UV_PROJECT_ENVIRONMENT": str(venv)}
    assert fetch == [str(venv / "bin" / "python"), str(CHOICE.worker_folder / "fetch.py")]
    assert said == [words.SPEECH_BUILT, words.MODEL_FOUND.format(model="made-up live", size="1.5 GB"),
                    words.MODEL_FETCHED.format(model="made-up stop", size="2.9 GB"), words.MODELS_READY]
    # A second run: the same command; uv audits and changes nothing.
    again = MadeUpRun(installed=False)
    report = environment.build(tmp_path, CHOICE, say=said.clear() or said.append, run=again,
                               which=lambda name: "/made-up/uv", environ={}, system="Linux")
    assert report.ok and not report.built and again.commands[0] == uv and said[0] == words.SPEECH_ALREADY_BUILT


def test_15_9_a_build_that_cannot_happen_says_so(tmp_path):
    said = []
    report = environment.build(tmp_path, CHOICE, say=said.append, run=MadeUpRun(), which=lambda name: None)
    assert not report.ok and said == [words.UV_MISSING]
    said.clear()
    report = environment.build(tmp_path, CHOICE, say=said.append, run=MadeUpRun(uv_fails=True),
                               which=lambda name: "/made-up/uv", environ={}, system="Linux")
    assert not report.ok and said == [words.SPEECH_BUILD_FAILED.format(reason="error: made-up: no such lock")]
    said.clear()
    missing = [{"model": "made-up stop", "found": False, "fetched": False, "bytes": 0, "ok": False, "error": "no network"}]
    report = environment.build(tmp_path, CHOICE, say=said.append, run=MadeUpRun(models=missing),
                               which=lambda name: "/made-up/uv", environ={}, system="Linux")
    assert not report.ok and said[-1] == words.MODEL_FAILED.format(model="made-up stop", reason="no network")


def test_15_9_the_install_command(tmp_path):
    said, run = [], MadeUpRun()
    code = main(["install-speech", "--data-folder", str(tmp_path)], say=said.append, run_process=run,
                which=lambda name: "/made-up/uv")
    assert code == 0 and said[0] == words.SPEECH_BUILDING.format(folder=tmp_path / "speech" / "whisperx_pyannote")
    assert said[-1] == words.MODELS_READY and len(run.commands) == 2
    assert main(["install-speech", "--data-folder", str(tmp_path)], say=said.append, run_process=run,
                which=lambda name: None) == 1
