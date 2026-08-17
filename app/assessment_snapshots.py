"""One row per CDS revision of a live session: when it happened, which
agenda version it produced, and whether it raised the urgency alarm.

Phase 7c slice 5 (PHASE_7C_SPEC.md §7; the debt named in
PHASE_7B_FACE_DRIVE_SPEC.md §6). Two readers want it and neither could
have it before: prereg metric 7 — red-flag utterance → alarm fire →
pause — needs per-revision timing that until now existed only as a log
line; and replay wants a spine to walk a past consultation's assessments
against. Written on EVERY revision during a live session, auto mode on
or off — the cost is one small insert per ~17 s pass — and read by
nothing in this slice: the review page and the eval scripts will.

**Buffered in the session, persisted at completion.** A consultation
row does not exist until Stop (`_complete_session` creates it), so
revisions are collected in the live entry with their wall-clock time and
audio position and inserted with the consultation id when it exists —
the same pattern as `system_utterance`, and the same reason a
connection-lost finalisation still gets them. `created_at` is therefore
the revision's own moment, supplied, not the insert's.

Rows cascade on consultation delete, so the void-then-purge path takes
them with it.
"""

from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS assessment_snapshot (
    id serial PRIMARY KEY,
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    version int NOT NULL,                -- the AgendaLog version this pass produced
    created_at timestamptz NOT NULL,     -- the revision's own moment (buffered, supplied)
    at_audio_s real,                     -- position in the recording, seconds
    urgent boolean NOT NULL DEFAULT false,
    urgent_actions jsonb,                -- [{"action": text, "reason": text}] when urgent
    UNIQUE (consultation_id, version)
);
CREATE INDEX IF NOT EXISTS assessment_snapshot_consultation_idx
    ON assessment_snapshot (consultation_id, version);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


def snapshot_of(assessment: dict, version: int, created_at, at_audio_s: float) -> dict:
    """The row for one revision, built at the moment it lands. `urgent` is
    the CDS engine's own bookkept verdict — non-empty `urgent_actions`
    after its arranged-latch — never re-derived here."""
    actions = [{"action": str(a.get("action", "")), "reason": str(a.get("reason", ""))}
               for a in (assessment.get("urgent_actions") or [])]
    return {"version": int(version), "created_at": created_at,
            "at_audio_s": round(float(at_audio_s), 1),
            "urgent": bool(actions), "urgent_actions": actions or None}


async def save(consultation_id: int, rows: list[dict]) -> None:
    """Persist a session's snapshots. Called once, at session completion."""
    if not rows:
        return
    async with await _conn() as conn:
        for row in rows:
            await conn.execute(
                "INSERT INTO assessment_snapshot"
                " (consultation_id, version, created_at, at_audio_s, urgent, urgent_actions)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (consultation_id, version) DO NOTHING",
                (consultation_id, row["version"], row["created_at"], row.get("at_audio_s"),
                 bool(row.get("urgent")),
                 json.dumps(row["urgent_actions"]) if row.get("urgent_actions") else None),
            )
        await conn.commit()


async def for_consultation(consultation_id: int) -> list[dict]:
    """Every snapshot of a consultation, in version order."""
    async with await _conn() as conn:
        cursor = await conn.execute(
            "SELECT version, created_at, at_audio_s, urgent, urgent_actions"
            " FROM assessment_snapshot WHERE consultation_id = %s ORDER BY version",
            (consultation_id,))
        columns = [c.name for c in cursor.description]
        return [dict(zip(columns, row)) for row in await cursor.fetchall()]
