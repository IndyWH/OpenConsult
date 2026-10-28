"""Where the embedding worker's environment and models live and how they
are installed (spec 15.12, The embedding worker in the app; 15.9 ruling
25; 6.2, 6.4; the plan review of 8b, points 1 and 4): in the user's data
folder, under embedding, from the lock file committed beside the worker,
by uv; then EmbeddingGemma 2's one fetch and, only when asked, the
reranker's one fetch, each with no token, each skipped when its weights
are there and match the pinned hash. openconsult install-guidelines runs
it; the reranker is fetched for the bench alone, with --reranker, since
ruling 9's mark did not hold and the app does not use it (R31)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Mapping

from openconsult import words
from openconsult.speech import environment as speech_environment

HERE = Path(__file__).resolve().parent
WORKER_FOLDER = HERE / "embedding2"
EMBEDDING = "embedding"
MODEL_NAME, RERANKER_NAME = "embeddinggemma2", "bge-reranker-v2-m3"
WEIGHTS = "model.safetensors"


def folder(data_folder: Path) -> Path:
    return Path(data_folder) / EMBEDDING / MODEL_NAME


def venv(data_folder: Path) -> Path:
    return folder(data_folder) / ".venv"


def python(data_folder: Path, system: str | None = None) -> Path:
    return speech_environment.python_in(venv(data_folder), system or platform.system())


def model_folder(data_folder: Path) -> Path:
    return folder(data_folder) / "model"


def reranker_folder(data_folder: Path) -> Path:
    return Path(data_folder) / EMBEDDING / RERANKER_NAME / "model"


def installed(data_folder: Path, system: str | None = None) -> bool:
    """A path check only: the environment's Python and the model's weights."""
    return python(data_folder, system).exists() and (model_folder(data_folder) / WEIGHTS).exists()


def reranker_installed(data_folder: Path) -> bool:
    return (reranker_folder(data_folder) / WEIGHTS).exists() and (reranker_folder(data_folder) / ".revision").exists()


def log_path(data_folder: Path) -> Path:
    where = folder(data_folder)
    where.mkdir(parents=True, exist_ok=True)
    return where / "worker.log"


def worker_command(data_folder: Path, where: str, system: str | None = None, reranker: bool = False,
                   reranker_where: str | None = None) -> list[str]:
    command = [str(python(data_folder, system)), str(WORKER_FOLDER / "worker.py"),
               "--model", str(model_folder(data_folder)), "--device", where]
    if reranker:
        command += ["--reranker", str(reranker_folder(data_folder)), "--reranker-device", reranker_where or where]
    return command


def worker_env(data_folder: Path, environ: Mapping[str, str] = os.environ) -> dict:
    """The speech workers' environment (the hub's network off, no key),
    with the hub's home inside the data folder, so the shared cache is
    never touched."""
    env = speech_environment.worker_env(environ)
    env["HF_HOME"] = str(folder(data_folder) / "hub")
    return env


def _fetch(data_folder: Path, which: str, target: Path, run: Callable, environ: Mapping[str, str]) -> dict | None:
    env = {k: v for k, v in environ.items() if k not in speech_environment.KEY_NAMES and k != "HF_HUB_OFFLINE"}
    env.update(HF_HUB_DISABLE_IMPLICIT_TOKEN="1", HF_HOME=str(folder(data_folder) / "hub"))
    done = run([str(python(data_folder)), str(WORKER_FOLDER / "fetch.py"), "--folder", str(target), "--model", which],
               env=env, capture_output=True, text=True)
    reports = [json.loads(line) for line in (done.stdout or "").splitlines() if line.startswith("{")]
    if not reports:
        return {"ok": False, "error": speech_environment._last_line(done.stderr) or f"exit code {done.returncode}", "fetched": False}
    return reports[-1]


def install(data_folder: Path, say: Callable = print, run: Callable = subprocess.run, which: Callable = shutil.which,
            environ: Mapping[str, str] = os.environ, reranker: bool = False, closing: bool = True) -> int:
    """The environment from the lock file (uv audits and changes nothing
    when it is complete), then each model's one fetch, skipped when its
    weights are there and match. Exit codes: 7 uv or the environment, 8 a fetch."""
    uv = which(speech_environment.UV)
    if uv is None:
        say(words.UV_MISSING)
        return 7
    target = venv(Path(data_folder))
    target.parent.mkdir(parents=True, exist_ok=True)
    say(words.EMBED_BUILDING.format(folder=target.parent))
    done = run([uv, "sync", "--locked", "--project", str(WORKER_FOLDER), "--python", speech_environment.PYTHON],
               env={**environ, "UV_PROJECT_ENVIRONMENT": str(target)}, capture_output=True, text=True)
    if done.returncode != 0:
        say(words.EMBED_BUILD_FAILED.format(reason=speech_environment._last_line(done.stderr) or speech_environment._last_line(done.stdout)))
        return 7
    say(words.EMBED_BUILT if "Installed" in (done.stderr or "") else words.EMBED_ALREADY_BUILT)
    say(words.EMBED_FETCHING.format(revision="pinned", folder=model_folder(data_folder)))
    report = _fetch(data_folder, "embedding", model_folder(data_folder), run, environ)
    if not report["ok"]:
        say(words.EMBED_GATED if "account" in (report.get("error") or "") else words.EMBED_FETCH_FAILED.format(reason=report.get("error")))
        return 8
    size = speech_environment.plain_size(int(report["bytes"]))
    say((words.EMBED_FETCHED if report["fetched"] else words.EMBED_FOUND).format(revision=report["revision"], size=size))
    if not reranker:
        if closing:
            say(words.GUIDELINES_INSTALLED)
        return 0
    say(words.RERANKER_FETCHING.format(folder=reranker_folder(data_folder)))
    report = _fetch(data_folder, "reranker", reranker_folder(data_folder), run, environ)
    if not report["ok"]:
        say(words.RERANKER_GATED if "account" in (report.get("error") or "") else words.RERANKER_FETCH_FAILED.format(reason=report.get("error")))
        return 8
    size = speech_environment.plain_size(int(report["bytes"]))
    say((words.RERANKER_FETCHED if report["fetched"] else words.RERANKER_FOUND).format(revision=report["revision"], size=size))
    say(words.GUIDELINES_INSTALLED)
    return 0
