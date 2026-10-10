"""Where a speech choice's environment lives and how it is built (spec
6.2, 6.4; 15.9): in the user's data folder, from the lock file committed
in the worker's folder, by uv. Then every model the worker loads is
found or fetched by the worker folder's own fetch script, run with the
environment's Python, so the worker never fetches: nothing downloads
without a click, and a consultation never waits on the internet (spec
6.4). The worker is run with the model hub's network switched off.

A cloud choice has no environment: its worker runs on the app's own
Python, so the base app alone is the whole install (spec 6.4). Its key
goes into that worker's environment, and no worker holds any other key."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from openconsult import words
from openconsult.speech.choices import CHOICES, Choice

SPEECH = "speech"
PYTHON = "3.12"
UV = "uv"
KEY_NAMES = tuple(choice.key for choice in CHOICES.values() if choice.key)


@dataclass(frozen=True)
class Report:
    ok: bool
    built: bool                 # packages were installed this time
    models: list[dict] = field(default_factory=list)
    detail: str | None = None


def folder(data_folder: Path, choice: Choice) -> Path:
    return Path(data_folder) / SPEECH / choice.name


def venv(data_folder: Path, choice: Choice) -> Path:
    return folder(data_folder, choice) / ".venv"


def python_in(venv_path: Path, system: str | None = None) -> Path:
    system = system or platform.system()
    if system == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def python(data_folder: Path, choice: Choice, system: str | None = None) -> Path:
    return python_in(venv(data_folder, choice), system)


def installed(data_folder: Path, choice: Choice, system: str | None = None) -> bool:
    """A path check only: nothing is started and nothing is loaded. A
    choice with no environment is installed with the base app."""
    if not choice.environment:
        return True
    return python(data_folder, choice, system).exists()


def log_path(data_folder: Path, choice: Choice) -> Path:
    where = folder(data_folder, choice)
    where.mkdir(parents=True, exist_ok=True)      # a cloud choice has no install to make it
    return where / "worker.log"


def worker_command(data_folder: Path, choice: Choice, system: str | None = None) -> list[str]:
    interpreter = python(data_folder, choice, system) if choice.environment else Path(sys.executable)
    return [str(interpreter), str(choice.worker_folder / "worker.py")]


def worker_env(environ: Mapping[str, str] = os.environ, key_name: str | None = None,
               key: str | None = None) -> dict:
    """The app's environment, so the hub's own settings and sign-in are
    found by the hub itself, with its network switched off: the worker
    loads from disk only. Every key's name is taken out, then the one key
    this worker needs is put in: a worker holds its own key and no other,
    and never on its command line."""
    env = {name: value for name, value in environ.items() if name not in KEY_NAMES}
    env.update(HF_HUB_OFFLINE="1", PYTHONUNBUFFERED="1")
    if key_name and key:
        env[key_name] = key
    return env


def build(data_folder: Path, choice: Choice, say: Callable = lambda line: None,
          run: Callable = subprocess.run, which: Callable = shutil.which,
          environ: Mapping[str, str] = os.environ, system: str | None = None) -> Report:
    """The command: uv sync from the lock file into the data folder, then
    the models. Run again, uv audits and changes nothing."""
    uv = which(UV)
    if uv is None:
        say(words.UV_MISSING)
        return Report(False, False, detail=words.UV_MISSING)
    target = venv(data_folder, choice)
    target.parent.mkdir(parents=True, exist_ok=True)
    done = run([uv, "sync", "--locked", "--project", str(choice.worker_folder), "--python", PYTHON],
               env={**environ, "UV_PROJECT_ENVIRONMENT": str(target)},
               capture_output=True, text=True)
    if done.returncode != 0:
        reason = _last_line(done.stderr) or _last_line(done.stdout) or f"uv exit code {done.returncode}"
        say(words.SPEECH_BUILD_FAILED.format(reason=reason))
        return Report(False, False, detail=words.SPEECH_BUILD_FAILED.format(reason=reason))
    built = "Installed" in (done.stderr or "")
    say(words.SPEECH_BUILT if built else words.SPEECH_ALREADY_BUILT)
    return _models(data_folder, choice, built, say, run, environ, system)


def _models(data_folder, choice, built, say, run, environ, system) -> Report:
    fetched = run([str(python(data_folder, choice, system)), str(choice.worker_folder / "fetch.py")],
                  env=dict(environ), capture_output=True, text=True)
    models = []
    for line in (fetched.stdout or "").splitlines():
        if line.startswith("{"):
            models.append(json.loads(line))
    for model in models:
        say(_model_sentence(model))
    ok = fetched.returncode == 0 and bool(models) and all(m.get("ok") for m in models)
    if ok:
        say(words.MODELS_READY)
        return Report(True, built, models)
    detail = _last_line(fetched.stderr) if not models else None
    if detail:
        say(words.SPEECH_BUILD_FAILED.format(reason=detail))
    return Report(False, built, models, detail)


def _model_sentence(model: dict) -> str:
    size = plain_size(int(model.get("bytes") or 0))
    if not model.get("ok"):
        return words.MODEL_FAILED.format(model=model.get("model"), reason=model.get("error"))
    if model.get("fetched"):
        return words.MODEL_FETCHED.format(model=model.get("model"), size=size)
    return words.MODEL_FOUND.format(model=model.get("model"), size=size)


def plain_size(n: int) -> str:
    if n >= 10 ** 9:
        return f"{n / 10 ** 9:.1f} GB"
    if n >= 10 ** 6:
        return f"{n / 10 ** 6:.0f} MB"
    return f"{max(1, round(n / 1000))} kB"


def _last_line(text: str | None) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1][:300] if lines else ""
