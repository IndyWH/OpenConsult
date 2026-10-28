"""The app's door to the embedding worker (spec 15.12, The embedding
worker in the app; 15.8 ruling 32; 6.2; 10.4): one joint the loader, the
search and the bench speak to, behind which stands the worker of
EmbeddingGemma 2 in its own environment, or nothing when it is not
installed. A call gives back vectors or a failure with its reason; it
never raises into a consultation, and a worker that has died is not
started again by itself."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol

from openconsult import words
from openconsult.guidelines import environment
from openconsult.speech.worker import Worker, WorkerGone

WHERE = ("card", "processor")
NOT_INSTALLED, STARTING, READY, FAILED, STOPPED = "not_installed", "starting", "ready", "failed", "stopped"
# The load took up to about ten seconds in 5d; a cold cache after a reboot is slower (the speech workers' figure).
WORKER_READY_S = 300.0
# A search's call is a few texts; a load of a document sends 16 at a time.
WORKER_REQUEST_S = 120.0


@dataclass(frozen=True)
class Vectors:
    """What one call gave: the vectors, or a failure with its reason."""
    ok: bool
    vectors: list = field(default_factory=list)
    wall_s: float = 0.0
    error: str | None = None
    own: dict = field(default_factory=dict)      # the worker's own figures


@dataclass(frozen=True)
class Scores:
    """What one rerank gave: one score for each text, or a failure."""
    ok: bool
    scores: list = field(default_factory=list)
    wall_s: float = 0.0
    error: str | None = None


class Embedder(Protocol):
    where: str

    @property
    def installed(self) -> bool: ...

    @property
    def state(self) -> str: ...

    @property
    def reason(self) -> str | None: ...

    @property
    def model_id(self) -> str | None: ...

    def ready(self) -> str | None: ...

    def embed(self, texts: list[str]) -> Vectors: ...

    def rerank(self, query: str, texts: list[str]) -> Scores: ...

    def info(self) -> dict: ...

    def close(self) -> None: ...


class NotInstalled:
    """The door with no worker behind it: every call is a failure that
    says so, and the page shows Add disabled with the reason (7.3 rule 1)."""

    def __init__(self, where: str):
        if where not in WHERE:
            raise ValueError(f"not a place for a model: {where}")
        self.where = where

    installed = False
    state = NOT_INSTALLED
    reason = None
    model_id = None

    def ready(self) -> str | None:
        return words.GUIDELINE_NOT_INSTALLED

    def embed(self, texts: list[str]) -> Vectors:
        return Vectors(False, [], 0.0, words.GUIDELINE_NOT_INSTALLED)

    def rerank(self, query: str, texts: list[str]) -> Scores:
        return Scores(False, [], 0.0, words.GUIDELINE_NOT_INSTALLED)

    def info(self) -> dict:
        return {"where_asked": self.where, "state": self.state}

    def close(self) -> None:
        pass


class WorkerEmbedder:
    """The worker of EmbeddingGemma 2 behind the door (6.2): started once
    and left to load; the first use waits for it; a death is a failure
    with its reason and nothing is started again by itself (10.4)."""

    def __init__(self, where: str, data_folder: Path, environ: Mapping[str, str] = os.environ,
                 command: list[str] | None = None, clock: Callable = time.perf_counter, reranker: bool = False,
                 reranker_where: str | None = None):
        if where not in WHERE:
            raise ValueError(f"not a place for a model: {where}")
        self.where, self.data_folder, self.reranker = where, Path(data_folder), reranker
        self._worker = Worker(command or environment.worker_command(self.data_folder, where, reranker=reranker,
                                                                     reranker_where=reranker_where),
                              log_path=environment.log_path(self.data_folder), env=environment.worker_env(self.data_folder, environ),
                              ready_timeout_s=WORKER_READY_S, request_timeout_s=WORKER_REQUEST_S)
        self._clock = clock

    installed = True

    def start(self) -> None:
        """Spawn the process and return at once; the models load in it."""
        self._worker.start()

    def ready(self) -> str | None:
        """Wait once for the load; None when ready, else the reason."""
        if self._worker.state == "ready":
            return None
        if self._worker.state == "starting" and self._worker.wait_ready():
            return None
        return self._worker.reason or words.GUIDELINE_WORKER_NOT_READY

    @property
    def state(self) -> str:
        return self._worker.state

    @property
    def reason(self) -> str | None:
        return self._worker.reason

    @property
    def model_id(self) -> str | None:
        info = self._worker.info
        return f"{info.get('model')}@{info.get('revision')}" if info.get("model") else None

    def embed(self, texts: list[str]) -> Vectors:
        started = self._clock()
        try:
            reply = self._worker.request({"type": "embed", "texts": list(texts)})
        except WorkerGone as gone:
            return Vectors(False, [], self._clock() - started, f"{gone.kind}: {gone.detail}")
        wall = self._clock() - started
        if reply.get("type") != "vectors":
            return Vectors(False, [], wall, str(reply.get("message") or f"an answer of type {reply.get('type')!r}"))
        return Vectors(True, list(reply.get("vectors") or []), wall, None, {"seconds": reply.get("seconds")})

    def rerank(self, query: str, texts: list[str]) -> Scores:
        started = self._clock()
        try:
            reply = self._worker.request({"type": "rerank", "query": query, "texts": list(texts)})
        except WorkerGone as gone:
            return Scores(False, [], self._clock() - started, f"{gone.kind}: {gone.detail}")
        wall = self._clock() - started
        if reply.get("type") != "scores":
            return Scores(False, [], wall, str(reply.get("message") or f"an answer of type {reply.get('type')!r}"))
        return Scores(True, [float(x) for x in (reply.get("scores") or [])], wall, None)

    def info(self) -> dict:
        info = dict(self._worker.info)
        info.pop("type", None)
        info.pop("nbytes", None)
        return {"where_asked": self.where, "state": self.state, **info}

    def close(self) -> None:
        self._worker.stop()


def make_embedder(data_folder: Path, where: str, environ: Mapping[str, str] = os.environ, reranker: bool = False,
                  reranker_where: str | None = None, start: bool = True):
    """The app's embedder for a data folder: the worker, started, when its
    environment and model are installed there, else the door with no
    worker behind it."""
    if not environment.installed(Path(data_folder)):
        return NotInstalled(where)
    worker = WorkerEmbedder(where, Path(data_folder), environ, reranker=reranker, reranker_where=reranker_where)
    if start:
        worker.start()
    return worker


def state_line(embedder) -> str:
    """The one sentence of the Guidelines section about the worker."""
    fill = {"where": words.WHERE_WORDS.get(embedder.where, embedder.where), "model": embedder.model_id or "",
            "reason": embedder.reason or ""}
    return words.GUIDELINE_WORKER_LINE.format(state=words.WORKER_STATES[embedder.state].format(**fill))
