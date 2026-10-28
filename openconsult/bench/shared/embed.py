"""The two ways to an embedding model in the test of 5d (spec 15.9,
rulings 24 and 25), behind one small joint: the first EmbeddingGemma
through the Ollama service, as v1 calls it, on the card or on the
processor; and EmbeddingGemma 2 as a worker of the bench in an
environment of its own, over the frames the speech workers use. Also
the reading of Ollama's list of loaded models, which is the proof of
where a model sits (ruling 24). Standard library only on the bench's
side; the worker's heavy libraries never load here."""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Mapping, Protocol

from openconsult.guidelines import environment
from openconsult.guidelines.embedder import Vectors  # noqa: F401 - the app's, since 8b
from openconsult.guidelines.embedder import WorkerEmbedder as AppWorkerEmbedder
from openconsult.llm.ollama import DEFAULT_ADDRESS, encode

# The model's name on the Ollama service, as v1 names it (V1/app/rag.py).
FIRST_MODEL = "embeddinggemma"
# A field of the call, not a setting of the service: the model stays loaded
# through the 15 s before the searches begin and between a base line's
# searches (Ollama's own default is 5 minutes). The same value the door
# gives the language model.
KEEP_ALIVE = "30m"
WHERE = ("card", "processor")
EMBED_TIMEOUT_S = 120.0
STATUS_TIMEOUT_S = 5.0



class Embedder(Protocol):
    name: str
    where: str

    def embed(self, texts: list[str]) -> Vectors: ...

    def info(self) -> dict: ...

    def close(self) -> None: ...


# ----------------------------------------------------- the Ollama service

def embed_body(texts: list[str], where: str, model: str = FIRST_MODEL) -> dict:
    """The request, as v1 sends it (model and input), with keep_alive, and
    on the processor the option num_gpu 0 that the spec names."""
    body = {"model": model, "input": list(texts), "keep_alive": KEEP_ALIVE}
    if where == "processor":
        body["options"] = {"num_gpu": 0}
    return body


def _exchange(address: str, path: str, data: bytes | None, timeout_s: float, urlopen: Callable) -> tuple[int, str]:
    request = urllib.request.Request(address + path, data=data,
                                     headers={"Content-Type": "application/json"} if data else {})
    try:
        with urlopen(request, timeout=timeout_s) as answer:
            return answer.status, answer.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, http.client.HTTPException) as failed:
        return 0, f"{type(failed).__name__}: {getattr(failed, 'reason', failed)}"


class OllamaEmbedder:
    name = "first"

    def __init__(self, where: str, address: str = DEFAULT_ADDRESS, model: str = FIRST_MODEL,
                 urlopen: Callable = urllib.request.urlopen, clock: Callable = time.perf_counter):
        if where not in WHERE:
            raise ValueError(f"not a place for a model: {where}")
        self.where, self.address, self.model = where, address.rstrip("/"), model
        self._urlopen, self._clock = urlopen, clock

    def embed(self, texts: list[str]) -> Vectors:
        started = self._clock()
        status, text = _exchange(self.address, "/api/embed", encode(embed_body(texts, self.where, self.model)),
                                 EMBED_TIMEOUT_S, self._urlopen)
        wall = self._clock() - started
        if status != 200:
            return Vectors(False, [], wall, f"HTTP {status}: {text[:300]}")
        try:
            reply = json.loads(text)
            vectors = reply["embeddings"]
        except (ValueError, KeyError, TypeError) as odd:
            return Vectors(False, [], wall, f"not an embeddings reply: {odd}")
        own = {k: reply.get(k) for k in ("total_duration", "load_duration", "prompt_eval_count")}
        return Vectors(True, list(vectors), wall, None, own)

    def info(self) -> dict:
        found = where_is(loaded_models(self.address, self._urlopen), self.model)
        return {"model": self.model, "address": self.address, "where_asked": self.where, "listed": found}

    def unload(self) -> tuple[int, str]:
        body = {"model": self.model, "input": [], "keep_alive": 0}
        return _exchange(self.address, "/api/embed", encode(body), STATUS_TIMEOUT_S, self._urlopen)

    def close(self) -> None:
        pass


def loaded_models(address: str = DEFAULT_ADDRESS, urlopen: Callable = urllib.request.urlopen) -> list[dict] | None:
    """Ollama's own list of loaded models, or None when it cannot be read."""
    status, text = _exchange(address.rstrip("/"), "/api/ps", None, STATUS_TIMEOUT_S, urlopen)
    if status != 200:
        return None
    try:
        return list(json.loads(text).get("models") or [])
    except (ValueError, AttributeError):
        return None


def placement(entry: dict) -> str:
    """Where a listed model sits, by Ollama's own two fields: wholly on the
    card when size_vram equals size, wholly on the processor when
    size_vram is 0, split otherwise (its FAQ's 100% GPU, 100% CPU and
    the mixed figure)."""
    size, vram = int(entry.get("size") or 0), int(entry.get("size_vram") or 0)
    if vram == 0:
        return "processor"
    if vram == size:
        return "card"
    return "split"


def where_is(listed: list[dict] | None, model: str) -> dict | None:
    """The listed entry for a model, by its name with or without a tag,
    with its placement; None when it is not loaded (or the list could
    not be read, which the caller tells by the list itself)."""
    for entry in listed or []:
        name = str(entry.get("name") or entry.get("model") or "")
        if name == model or name.startswith(model + ":"):
            return {"name": name, "size": entry.get("size"), "size_vram": entry.get("size_vram"),
                    "context_length": entry.get("context_length"), "placement": placement(entry)}
    return None


# --------------------------------------------- the worker of version 2

# The worker is the app's since 8b (openconsult/guidelines): its folder,
# its environment and its door are read from there; the bench's name for
# it stays.
WORKER_FOLDER = environment.WORKER_FOLDER
folder, venv, python, model_folder, installed = (environment.folder, environment.venv, environment.python,
                                                 environment.model_folder, environment.installed)
worker_env = environment.worker_env


def worker_command(data_folder: Path, where: str, system: str | None = None) -> list[str]:
    return environment.worker_command(data_folder, where, system)


class WorkerEmbedder(AppWorkerEmbedder):
    """The app's worker door with the bench's start: start and wait, the reason when it is not ready."""
    name = "second"

    def start(self) -> str | None:
        super().start()
        return self.ready()
