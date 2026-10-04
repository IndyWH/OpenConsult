"""The first run (spec 7.1, 15.6 ruling 4): the statement, This machine,
the user, in that order. The user can leave and come back; the app
resumes at the first step not done."""

from __future__ import annotations

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local
from openconsult.patients.users import Users

STEPS = ("statement", "machine", "user")


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

    def mark_done(self, step: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO first_run (step, done_at) VALUES (?, ?)",
            (step, self._clock().isoformat(timespec="seconds")),
        )
