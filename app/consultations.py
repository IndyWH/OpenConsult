"""Consultation persistence (Phase 2).

Statuses: live → processing → awaiting_review → approved
(→ failed if the finalisation pipeline dies; the audio is kept so it can
be retried — raw audio is retained until finalisation succeeds, per plan).
"""

from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS consultation (
    id serial PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'live',
    audio_path text,
    error text
);
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS urgent_actions jsonb;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS urgent_ack_at timestamptz;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS patient_id int;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS doctor_id int;
CREATE TABLE IF NOT EXISTS transcript_turn (
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    idx int NOT NULL,
    role text NOT NULL,          -- 'Doctor' | 'Patient'
    start_s real NOT NULL,
    end_s real NOT NULL,
    text text NOT NULL,
    confidence real NOT NULL,    -- mean ASR word confidence, 0..1
    PRIMARY KEY (consultation_id, idx)
);
CREATE TABLE IF NOT EXISTS note (
    id serial PRIMARY KEY,
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    version int NOT NULL,
    content jsonb NOT NULL,      -- SOAP structure with per-claim turn citations
    status text NOT NULL DEFAULT 'draft',   -- 'draft' | 'approved'
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    approved_text text           -- the doctor-edited plain text, on approval
);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


async def create_consultation(
    patient_id: int | None = None, doctor_id: int | None = None
) -> int:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO consultation (patient_id, doctor_id)"
                " VALUES (%s, %s) RETURNING id",
                (patient_id, doctor_id),
            )
        ).fetchone()
        return row[0]


async def list_consultations() -> list[dict]:
    """Worklist rows: no clinical content — safe for all logged-in roles."""
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT c.id, c.started_at, c.status, p.name, u.display_name"
                " FROM consultation c"
                " LEFT JOIN patient p ON p.id = c.patient_id"
                " LEFT JOIN app_user u ON u.id = c.doctor_id"
                " ORDER BY c.id DESC"
            )
        ).fetchall()
    return [
        {"id": r[0], "started_at": str(r[1])[:16], "status": r[2],
         "patient_name": r[3] or "—", "doctor_name": r[4] or "—"}
        for r in rows
    ]


async def set_status(cid: int, status: str, *, audio_path: str | None = None,
                     error: str | None = None) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET status = %s,"
            " audio_path = COALESCE(%s, audio_path), error = %s WHERE id = %s",
            (status, audio_path, error, cid),
        )


async def get_consultation(cid: int) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT c.id, c.started_at, c.status, c.audio_path, c.error,"
                " c.urgent_actions, c.urgent_ack_at, c.patient_id, p.name"
                " FROM consultation c LEFT JOIN patient p ON p.id = c.patient_id"
                " WHERE c.id = %s", (cid,),
            )
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "started_at": str(row[1]),
        "status": row[2],
        "audio_path": row[3],
        "error": row[4],
        "urgent_actions": row[5] or [],
        "urgent_ack_at": str(row[6]) if row[6] else None,
        "patient_id": row[7],
        "patient_name": row[8],
    }


async def save_urgent_actions(cid: int, actions: list[dict]) -> None:
    """Persist the live session's final unresolved urgent actions."""
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET urgent_actions = %s WHERE id = %s",
            (json.dumps(actions), cid),
        )


async def acknowledge_urgent(cid: int) -> str:
    """Record the doctor's acknowledgement of the urgency banner."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE consultation SET urgent_ack_at = now()"
                " WHERE id = %s AND urgent_ack_at IS NULL"
                " RETURNING urgent_ack_at", (cid,),
            )
        ).fetchone()
        if row is None:  # already acknowledged: keep the original timestamp
            row = await (
                await conn.execute(
                    "SELECT urgent_ack_at FROM consultation WHERE id = %s", (cid,)
                )
            ).fetchone()
    return str(row[0])


async def save_turns(cid: int, turns: list[dict]) -> None:
    async with await _conn() as conn:
        await conn.execute("DELETE FROM transcript_turn WHERE consultation_id = %s", (cid,))
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO transcript_turn"
                " (consultation_id, idx, role, start_s, end_s, text, confidence)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    (cid, i, t["role"], t["start"], t["end"], t["text"], t["confidence"])
                    for i, t in enumerate(turns)
                ],
            )


async def get_turns(cid: int) -> list[dict]:
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT idx, role, start_s, end_s, text, confidence"
                " FROM transcript_turn WHERE consultation_id = %s ORDER BY idx", (cid,),
            )
        ).fetchall()
    return [
        {"idx": r[0], "role": r[1], "start": r[2], "end": r[3], "text": r[4],
         "confidence": r[5]}
        for r in rows
    ]


async def update_turn_text(cid: int, idx: int, text: str) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE transcript_turn SET text = %s, confidence = 1.0"
            " WHERE consultation_id = %s AND idx = %s",
            (text, cid, idx),  # a doctor-corrected turn is fully trusted
        )


async def swap_roles(cid: int) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE transcript_turn SET role ="
            " CASE role WHEN 'Doctor' THEN 'Patient' ELSE 'Doctor' END"
            " WHERE consultation_id = %s", (cid,),
        )


async def save_note(cid: int, content: dict) -> int:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO note (consultation_id, version, content)"
                " VALUES (%s, COALESCE((SELECT max(version) FROM note"
                "   WHERE consultation_id = %s), 0) + 1, %s) RETURNING version",
                (cid, cid, json.dumps(content)),
            )
        ).fetchone()
        return row[0]


async def latest_note(cid: int) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT version, content, status, approved_text FROM note"
                " WHERE consultation_id = %s ORDER BY version DESC LIMIT 1", (cid,),
            )
        ).fetchone()
    if row is None:
        return None
    return {"version": row[0], "content": row[1], "status": row[2],
            "approved_text": row[3]}


async def approve_note(cid: int, approved_text: str) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE note SET status = 'approved', approved_at = now(),"
            " approved_text = %s WHERE consultation_id = %s AND version ="
            " (SELECT max(version) FROM note WHERE consultation_id = %s)",
            (approved_text, cid, cid),
        )
        await conn.execute(
            "UPDATE consultation SET status = 'approved' WHERE id = %s", (cid,)
        )
