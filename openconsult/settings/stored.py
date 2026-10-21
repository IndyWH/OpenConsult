"""The settings a page can change (spec 7.3, rule 4; 15.11 ruling 7),
kept in the setting table of the data folder and read fresh at each
use, so a change takes effect at the next sweep or the next consultation
and never during one. Every change is written to the audit log, from
what to what. The first of them is the retention time for recordings:
days, default 90; 0 keeps a recording until its consultation is deleted.
No other code reads the table."""

from __future__ import annotations

from openconsult.db import Database
from openconsult.patients.audit import Audit, Clock, now_local

AUDIO_RETENTION_DAYS = "audio_retention_days"
# v1's default (its retention module; V1_LESSONS 10.5).
DEFAULT_RETENTION_DAYS = 90


def retention_problem(text: str) -> int | None:
    """The days a form gave, or None when it is not a whole number of
    days from 0 up."""
    text = (text or "").strip()
    if not text.isdigit():
        return None
    return int(text)


class Stored:
    def __init__(self, db: Database, audit: Audit, clock: Clock = now_local):
        self._db = db
        self._audit = audit
        self._clock = clock

    def _get(self, name: str) -> str | None:
        found = self._db.query_one("SELECT value FROM setting WHERE name = ?", (name,))
        return found["value"] if found else None

    def _set(self, name: str, value: str) -> None:
        before = self._get(name)
        self._db.execute("INSERT OR REPLACE INTO setting (name, value, changed_at) VALUES (?, ?, ?)",
                         (name, value, self._clock().isoformat(timespec="seconds")))
        self._audit.record("setting.changed", f"{name} from {before if before is not None else 'the default'} to {value}")

    @property
    def audio_retention_days(self) -> int:
        value = self._get(AUDIO_RETENTION_DAYS)
        return int(value) if value is not None and value.isdigit() else DEFAULT_RETENTION_DAYS

    def set_audio_retention_days(self, days: int) -> None:
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            raise ValueError("days is a whole number from 0 up")
        if days != self.audio_retention_days or self._get(AUDIO_RETENTION_DAYS) is None:
            self._set(AUDIO_RETENTION_DAYS, str(days))
