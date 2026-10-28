"""The app's door to the embedding worker (spec 15.12, The embedding
worker in the app; 15.8 ruling 32; 6.2; 10.4): one joint the loader, the
search and the bench speak to, behind which stands the worker of
EmbeddingGemma 2 in its own environment, or nothing when it is not
installed. A call gives back vectors or a failure with its reason; it
never raises into a consultation, and a worker that has died is not
started again by itself."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol

from openconsult import words

WHERE = ("card", "processor")
NOT_INSTALLED, STARTING, READY, FAILED, STOPPED = "not_installed", "starting", "ready", "failed", "stopped"


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


def make_embedder(data_folder: Path, where: str, environ: Mapping[str, str] = os.environ):
    """The app's embedder for a data folder: the worker when its
    environment and model are installed there, else the door with no
    worker. The worker arrives with the next commit of 8b."""
    return NotInstalled(where)


def state_line(embedder) -> str:
    """The one sentence of the Guidelines section about the worker."""
    fill = {"where": words.WHERE_WORDS.get(embedder.where, embedder.where), "model": embedder.model_id or "",
            "reason": embedder.reason or ""}
    return words.GUIDELINE_WORKER_LINE.format(state=words.WORKER_STATES[embedder.state].format(**fill))
