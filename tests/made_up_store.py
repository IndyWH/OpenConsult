"""A made secure store for the suite (spec 7.2; the details of run 9b): a
dict in memory behind the four calls the app makes of a store. The suite
never touches the system's own store; this stands in its place. It can
be made to give no answer, as a computer with no store does."""

from __future__ import annotations

from openconsult.settings.secure import NoStore

NO_ANSWER = "a made-up reason: no store answers here"


class MadeStore:
    def __init__(self, held: dict | None = None, answers: bool = True, keeps: bool = True):
        self.held = dict(held or {})
        self._answers = answers
        self._keeps = keeps            # False: the store takes a key and does not keep it
        self.calls: list[tuple] = []   # (what, name), never a value

    def _check(self) -> None:
        if not self._answers:
            raise NoStore(NO_ANSWER)

    def get(self, name: str) -> str | None:
        self.calls.append(("get", name))
        self._check()
        return self.held.get(name) or None

    def put(self, name: str, value: str) -> None:
        self.calls.append(("put", name))
        self._check()
        if not self._keeps:
            raise NoStore("the secure store did not keep the key")
        self.held[name] = value

    def take_out(self, name: str) -> None:
        self.calls.append(("take_out", name))
        self._check()
        self.held.pop(name, None)

    def answers(self) -> bool:
        return self._answers

    def why_not(self) -> str | None:
        return None if self._answers else NO_ANSWER
