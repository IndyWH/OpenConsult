"""The app's door to Claude (spec 15.13, rulings 15 and 21, the details
of run 9b; 10.4). One door for the run, behind which the Claude engine
holds the key in use: when the doctor connects another key or removes
it, the next call is made with what is in use then. With no key in use
every call fails plainly as unreachable and is recorded; nothing is
sent, and nothing else is tried in its place."""

from __future__ import annotations

from typing import Callable

from openconsult.llm import claude
from openconsult.llm.door import Door
from openconsult.llm.engine import Call, EngineStatus, EngineUnreachable, Reply
from openconsult.llm.profile import CLAUDE
from openconsult.llm.record import ModelCalls

NOT_CONNECTED = "Claude is not connected: no key is in use"


class NotConnected:
    """Stands behind the door while no key is in use."""
    name = "claude"
    address = claude.ADDRESS

    def chat(self, call: Call) -> Reply:
        raise EngineUnreachable(NOT_CONNECTED)

    def version(self, timeout_s: float = claude.STATUS_TIMEOUT_S) -> str | None:
        return claude.ENGINE_VERSION

    def model_digest(self, tag: str, timeout_s: float = claude.STATUS_TIMEOUT_S) -> str | None:
        return None

    def status(self, tag: str, timeout_s: float = claude.STATUS_TIMEOUT_S) -> EngineStatus:
        return EngineStatus(False, None, None, None)


class ClaudeDoors:
    def __init__(self, key: Callable[[], str | None], record: ModelCalls, make_engine: Callable):
        self._key, self._record, self._make_engine = key, record, make_engine
        self._held: str | None = None
        self._door: Door | None = None

    def door(self) -> Door:
        """The door with the key in use now; made again only when the key has changed."""
        key = self._key()
        if self._door is None or key != self._held:
            self._held = key
            self._door = Door(self._make_engine(key) if key else NotConnected(), self._record, CLAUDE)
        return self._door
