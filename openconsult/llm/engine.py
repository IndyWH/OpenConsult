"""The joint between the door and an engine (spec 15.7; plan review,
change 1). What crosses it is the parts of a call and one plain reply,
nothing in any one engine's shape. A second engine is one new module
that gives these four methods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Call:
    """Door to engine: the parts of one call."""
    job: str
    tag: str
    system: str
    user: str
    form: dict
    temperature: float
    seed: int
    context: int
    max_tokens: int
    think: bool
    timeout_s: float


@dataclass(frozen=True)
class Reply:
    """Engine to door: how the call ended, the answer text, the counts,
    the times, and the request and reply exactly as they crossed the
    wire, for the record."""
    ended: str  # complete, cut, did_not_fit or error
    text: str | None
    status: int | None
    error: str | None
    prompt_tokens: int | None
    output_tokens: int | None
    total_ms: int | None
    load_ms: int | None
    read_ms: int | None
    write_ms: int | None
    wall_ms: int
    request: str
    raw: str | None


ENDINGS = ("complete", "cut", "did_not_fit", "error")


@dataclass(frozen=True)
class EngineStatus:
    """Read only, for This machine. Never raises, never waits past its limit."""
    running: bool
    version: str | None
    model_present: bool | None
    digest: str | None


class EngineFailure(Exception):
    """Carries the request the engine tried to send, for the record."""

    def __init__(self, message: str, request: str | None = None):
        super().__init__(message)
        self.request = request


class EngineUnreachable(EngineFailure):
    """No connection, or the engine broke it."""


class EngineTimeout(EngineFailure):
    """The engine did not answer within the call's time limit."""


class Engine(Protocol):
    name: str

    def chat(self, call: Call) -> Reply: ...

    def version(self, timeout_s: float = 2.0) -> str | None: ...

    def model_digest(self, tag: str, timeout_s: float = 2.0) -> str | None: ...

    def status(self, tag: str, timeout_s: float = 2.0) -> EngineStatus: ...
