"""Audit log (Phase 6): who viewed/edited/approved/acknowledged what, when.

Append-only. Every clinically meaningful action writes a row; the
existing urgent_ack_at column on consultation remains as the quick-read
flag, with the who/when detail folded in here.
"""

from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_event (
    id serial PRIMARY KEY,
    at timestamptz NOT NULL DEFAULT now(),
    user_id int REFERENCES app_user(id),
    action text NOT NULL,
    subject_type text,
    subject_id int,
    detail jsonb
);
CREATE INDEX IF NOT EXISTS audit_event_subject_idx
    ON audit_event (subject_type, subject_id);
-- The monitoring pulse counts today's events per action; this index
-- keeps that query an index-range scan however large the log grows.
CREATE INDEX IF NOT EXISTS audit_event_action_at_idx
    ON audit_event (action, at);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def log(
    user_id: int | None,
    action: str,
    subject_type: str | None = None,
    subject_id: int | None = None,
    detail: dict | None = None,
) -> None:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        await conn.execute(
            "INSERT INTO audit_event (user_id, action, subject_type, subject_id, detail)"
            " VALUES (%s, %s, %s, %s, %s)",
            (user_id, action, subject_type, subject_id,
             json.dumps(detail) if detail else None),
        )


async def latest_detail(action: str, user_id: int) -> dict | None:
    """Newest detail payload this user recorded for one action, or None.

    Added for the barge-in threshold (Phase 7a session 3): the measured
    loopback level lives in the `speech.sound_check` rows, stored flat and
    raw exactly so later consumers READ them rather than re-measure.
    """
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        row = await (
            await conn.execute(
                "SELECT detail FROM audit_event"
                " WHERE action = %s AND user_id = %s"
                " ORDER BY id DESC LIMIT 1", (action, user_id),
            )
        ).fetchone()
    return row[0] if row else None


async def for_subject(subject_type: str, subject_id: int, action: str) -> list[dict]:
    """Every row of one action about one subject, oldest first, with who
    wrote it. Added for the review page's live-acknowledgement display
    (Phase 7c slice 5): display only, read from the trail, no gate."""
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        rows = await (
            await conn.execute(
                "SELECT a.at, u.username, u.display_name, a.detail"
                " FROM audit_event a LEFT JOIN app_user u ON u.id = a.user_id"
                " WHERE a.subject_type = %s AND a.subject_id = %s AND a.action = %s"
                " ORDER BY a.id", (subject_type, subject_id, action),
            )
        ).fetchall()
    return [{"at": str(r[0]), "username": r[1], "display_name": r[2], "detail": r[3]}
            for r in rows]


async def recent(limit: int = 200) -> list[dict]:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        rows = await (
            await conn.execute(
                "SELECT a.at, u.username, u.role, a.action, a.subject_type,"
                " a.subject_id, a.detail"
                " FROM audit_event a LEFT JOIN app_user u ON u.id = a.user_id"
                " ORDER BY a.id DESC LIMIT %s", (limit,),
            )
        ).fetchall()
    return [
        {"at": str(r[0]), "username": r[1], "role": r[2], "action": r[3],
         "subject_type": r[4], "subject_id": r[5], "detail": r[6]}
        for r in rows
    ]
