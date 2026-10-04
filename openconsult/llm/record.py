"""The record of every model call: one row for each, written by the door
(spec 15.7; V1_LESSONS 3.12, 3.13). This is the stamp of R20."""

from __future__ import annotations

from dataclasses import dataclass, fields

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local

OUTCOMES = ("ok", "too_slow", "too_long", "unreachable", "bad_form", "did_not_fit")


@dataclass(frozen=True)
class CallRow:
    job: str
    engine: str
    engine_version: str | None
    model_tag: str
    model_digest: str | None
    prompt_sha256: str
    request: str
    reply: str | None
    prompt_tokens: int | None
    output_tokens: int | None
    wall_ms: int
    total_ms: int | None
    load_ms: int | None
    read_ms: int | None
    write_ms: int | None
    outcome: str
    detail: str | None


COLUMNS = tuple(f.name for f in fields(CallRow))


class ModelCalls:
    """Adds rows and reads them back. Nothing here changes or removes one."""

    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock

    def add(self, row: CallRow) -> int:
        if row.outcome not in OUTCOMES:
            raise ValueError(f"not an outcome: {row.outcome}")
        names = ", ".join(("at", *COLUMNS))
        marks = ", ".join("?" for _ in range(len(COLUMNS) + 1))
        values = (self._clock().isoformat(timespec="milliseconds"),
                  *(getattr(row, name) for name in COLUMNS))
        cursor = self._db.execute(f"INSERT INTO model_call ({names}) VALUES ({marks})", values)
        return int(cursor.lastrowid)

    def rows(self, newest_first: bool = True) -> list[dict]:
        order = "DESC" if newest_first else "ASC"
        return [dict(r) for r in self._db.query(f"SELECT * FROM model_call ORDER BY id {order}")]

    def get(self, row_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM model_call WHERE id = ?", (row_id,))
        return dict(found) if found else None
