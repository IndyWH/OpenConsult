"""The one recorder for the audit log (spec 6.5, 15.6).

It adds the time itself. The app only adds lines: the table's triggers
refuse any change or removal. Nothing that calls it passes a password or
a secret, and the test of 15.6 checks the log for one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from openconsult.db import Database

Clock = Callable[[], datetime]


def now_local() -> datetime:
    return datetime.now().astimezone()


@dataclass(frozen=True)
class Line:
    at: str
    event: str
    detail: str | None


class Audit:
    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock

    def record(self, event: str, detail: str | None = None) -> None:
        at = self._clock().isoformat(timespec="seconds")
        self._db.execute(
            "INSERT INTO audit_log (at, event, detail) VALUES (?, ?, ?)", (at, event, detail)
        )

    def lines(self) -> list[Line]:
        """Every line, newest first."""
        rows = self._db.query("SELECT at, event, detail FROM audit_log ORDER BY id DESC")
        return [Line(row["at"], row["event"], row["detail"]) for row in rows]
