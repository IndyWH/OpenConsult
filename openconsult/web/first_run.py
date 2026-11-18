"""The first run (spec 7.1, 15.6 ruling 4; 15.13, ruling 7 and the details
of run 9b). The steps, in order: the statement; This machine; connect
the language model and connect transcription, each only when its path
is the cloud; the self-test; the microphone test; the user. The user
can leave and come back; the app resumes at the first step not done.

Two things are kept apart here. The steps that guard set-up are the
three of stage 2: nobody sets up a user before the statement is
accepted and This machine is seen (ruling 4). The four steps between
This machine and the user are walked in their order, and each can be
left with Not now: a step left is not done, and Start names it on its
control (R15). Without that a computer with nothing installed could
never reach the user step. A data folder that finished the first run
before these steps existed meets them once, at its next login."""

from __future__ import annotations

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local
from openconsult.patients.users import Users

STEPS = ("statement", "machine", "user")
CONNECT_LANGUAGE_MODEL, CONNECT_TRANSCRIPTION, SELF_TEST, MICROPHONE = "connect_language_model", "connect_transcription", "self_test", "microphone"
# The steps between This machine and the user, in their order (7.1).
MIDDLE = (CONNECT_LANGUAGE_MODEL, CONNECT_TRANSCRIPTION, SELF_TEST, MICROPHONE)


class FirstRun:
    def __init__(self, db: Database, users: Users, clock: Clock = now_local):
        self._db = db
        self._users = users
        self._clock = clock

    def next_step(self) -> str | None:
        """The first step not done, or None when the first run is over."""
        done = {row["step"] for row in self._db.query("SELECT step FROM first_run")}
        for step in STEPS[:-1]:
            if step not in done:
                return step
        return None if self._users.exists() else "user"

    def done(self) -> set[str]:
        return {row["step"] for row in self._db.query("SELECT step FROM first_run")}

    def done_at(self, step: str) -> str | None:
        """When a step was done, or None when it is not done."""
        row = self._db.query_one("SELECT done_at FROM first_run WHERE step = ?", (step,))
        return row["done_at"] if row else None

    def left(self) -> set[str]:
        """The steps left with Not now: met, and not done."""
        return {row["step"] for row in self._db.query("SELECT step FROM first_run_left")}

    def mark_left(self, step: str) -> None:
        if step not in MIDDLE:
            raise ValueError(f"not a step that can be left: {step}")
        self._db.execute("INSERT OR IGNORE INTO first_run_left (step, left_at) VALUES (?, ?)",
                         (step, self._clock().isoformat(timespec="seconds")))

    def mark_done(self, step: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO first_run (step, done_at) VALUES (?, ?)",
            (step, self._clock().isoformat(timespec="seconds")),
        )
