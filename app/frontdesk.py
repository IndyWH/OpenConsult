"""Patients and today's walk-in queue (Phase 6).

Patients are minimal synthetic demographics behind queue entries — no
demographics tab (v2). The queue models the walk-in, take-a-number flow:
waiting → in_consultation → done, ordered by position, per day.
"""

from __future__ import annotations

import logging
import os

import psycopg
from dotenv import load_dotenv

from app import audit

load_dotenv()
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS patient (
    id serial PRIMARY KEY,
    name text NOT NULL,
    age int,
    sex text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS queue_entry (
    id serial PRIMARY KEY,
    patient_id int NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    queue_date date NOT NULL DEFAULT CURRENT_DATE,
    position int NOT NULL,
    status text NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'in_consultation', 'done', 'cancelled')),
    added_at timestamptz NOT NULL DEFAULT now()
);
-- migration for pre-'cancelled' databases (constraint name is Postgres's
-- auto-generated one for the inline CHECK above)
ALTER TABLE queue_entry DROP CONSTRAINT IF EXISTS queue_entry_status_check;
ALTER TABLE queue_entry ADD CONSTRAINT queue_entry_status_check
    CHECK (status IN ('waiting', 'in_consultation', 'done', 'cancelled'));
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


async def get_patient(patient_id: int) -> dict | None:
    """Server-side demographics (referral letters' Re: line reads this,
    never model output)."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, name, age, sex FROM patient WHERE id = %s",
                (patient_id,),
            )
        ).fetchone()
    return {"id": row[0], "name": row[1], "age": row[2], "sex": row[3]} if row else None


async def add_to_queue(name: str, age: int | None, sex: str | None) -> dict:
    async with await _conn() as conn:
        patient = await (
            await conn.execute(
                "INSERT INTO patient (name, age, sex) VALUES (%s, %s, %s) RETURNING id",
                (name, age, sex),
            )
        ).fetchone()
        entry = await (
            await conn.execute(
                "INSERT INTO queue_entry (patient_id, position) VALUES (%s,"
                " COALESCE((SELECT max(position) FROM queue_entry"
                "   WHERE queue_date = CURRENT_DATE), 0) + 1) RETURNING id, position",
                (patient[0],),
            )
        ).fetchone()
    return {"entry_id": entry[0], "patient_id": patient[0], "position": entry[1]}


async def start_walk_in(name: str, age: int | None, sex: str | None) -> dict | None:
    """Doctor-initiated walk-in: register a minimal patient and create the
    queue entry directly in 'in_consultation' — one transaction, so a crash
    can't leave a patient without a queue entry or vice versa."""
    async with await _conn() as conn:
        patient = await (
            await conn.execute(
                "INSERT INTO patient (name, age, sex) VALUES (%s, %s, %s) RETURNING id",
                (name, age, sex),
            )
        ).fetchone()
        # Refuses while another consultation is active (concurrency guard,
        # atomic with the insert): abandoned sessions must be resumed or
        # closed, not silently stacked.
        entry = await (
            await conn.execute(
                "INSERT INTO queue_entry (patient_id, position, status)"
                " SELECT %s, COALESCE((SELECT max(position) FROM queue_entry"
                "   WHERE queue_date = CURRENT_DATE), 0) + 1, 'in_consultation'"
                " WHERE NOT EXISTS (SELECT 1 FROM queue_entry"
                "   WHERE queue_date = CURRENT_DATE AND status = 'in_consultation')"
                " RETURNING id, position",
                (patient[0],),
            )
        ).fetchone()
        if entry is None:
            await conn.rollback()  # don't keep the patient row either
            return None
    return {"entry_id": entry[0], "patient_id": patient[0], "position": entry[1],
            "name": name, "age": age, "sex": sex}


def _entry_row_to_dict(r) -> dict:
    return {"entry_id": r[0], "position": r[1], "status": r[2], "patient_id": r[3],
            "name": r[4], "age": r[5], "sex": r[6]}


_ENTRY_SELECT = (
    "SELECT q.id, q.position, q.status, p.id, p.name, p.age, p.sex"
    " FROM queue_entry q JOIN patient p ON p.id = q.patient_id"
    " WHERE q.queue_date = CURRENT_DATE"
)


async def get_entry(entry_id: int) -> dict | None:
    """One of today's entries with its patient identity — the live page's
    patient banner is sourced from here, never from URL text."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(_ENTRY_SELECT + " AND q.id = %s", (entry_id,))
        ).fetchone()
    return _entry_row_to_dict(row) if row else None


async def current_entry() -> dict | None:
    """The most recently started of today's in-consultation entries (covers
    reaching /live through the nav tab, where no entry id is in the URL)."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                _ENTRY_SELECT + " AND q.status = 'in_consultation' ORDER BY q.id DESC LIMIT 1"
            )
        ).fetchone()
    return _entry_row_to_dict(row) if row else None


async def today_queue() -> list[dict]:
    async with await _conn() as conn:
        rows = await (
            await conn.execute(_ENTRY_SELECT + " ORDER BY q.position")
        ).fetchall()
    return [_entry_row_to_dict(r) for r in rows]


async def move_entry(entry_id: int, direction: str) -> bool:
    """Swap positions with the neighbour above/below (today, any status)."""
    op = "<" if direction == "up" else ">"
    order = "DESC" if direction == "up" else "ASC"
    async with await _conn() as conn:
        current = await (
            await conn.execute(
                "SELECT position FROM queue_entry WHERE id = %s"
                " AND queue_date = CURRENT_DATE", (entry_id,),
            )
        ).fetchone()
        if current is None:
            return False
        neighbour = await (
            await conn.execute(
                f"SELECT id, position FROM queue_entry WHERE queue_date = CURRENT_DATE"
                f" AND position {op} %s ORDER BY position {order} LIMIT 1",
                (current[0],),
            )
        ).fetchone()
        if neighbour is None:
            return False
        await conn.execute(
            "UPDATE queue_entry SET position = %s WHERE id = %s", (neighbour[1], entry_id)
        )
        await conn.execute(
            "UPDATE queue_entry SET position = %s WHERE id = %s", (current[0], neighbour[0])
        )
    return True


async def start_entry(entry_id: int) -> dict | None:
    """waiting → in_consultation; returns the patient for the live page.
    Atomically refuses while another entry is in consultation (concurrency
    guard) — the caller distinguishes the two failure reasons."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE queue_entry SET status = 'in_consultation'"
                " WHERE id = %s AND status = 'waiting'"
                " AND NOT EXISTS (SELECT 1 FROM queue_entry"
                "   WHERE queue_date = CURRENT_DATE AND status = 'in_consultation')"
                " RETURNING patient_id",
                (entry_id,),
            )
        ).fetchone()
        if row is None:
            return None
        patient = await (
            await conn.execute(
                "SELECT id, name, age, sex FROM patient WHERE id = %s", (row[0],)
            )
        ).fetchone()
    return {"entry_id": entry_id, "patient_id": patient[0], "name": patient[1],
            "age": patient[2], "sex": patient[3]}


async def close_entry(entry_id: int, outcome: str) -> dict | None:
    """Administrative closure when no recording happened: waiting or
    in_consultation → done/cancelled. Distinct from finish_entry (which is
    the Stop-button path for real consultations). Returns the prior state
    for the audit trail, or None if the entry isn't closable.

    DELIBERATELY NOT scoped to CURRENT_DATE, unlike every other query here
    (2026-07-28). Queue entry 164 is the specimen: a walk-in abandoned before
    Start on 2026-07-26 stayed `in_consultation`, and once the date rolled over
    BOTH recovery paths — Resume and Close — refused it, because both were
    day-scoped. Nothing was left that could close it, so it was permanent.

    The close path is the one that must be able to reach into the past: it is
    the escape hatch, and an escape hatch scoped to today cannot let anybody out
    of yesterday. `_ENTRY_SELECT` and the display queries stay day-scoped —
    today's queue is still today's queue.
    """
    if outcome not in ("done", "cancelled"):
        raise ValueError(f"invalid outcome {outcome!r}")
    async with await _conn() as conn:
        old = await (
            await conn.execute(
                "SELECT status, patient_id FROM queue_entry WHERE id = %s",
                (entry_id,),
            )
        ).fetchone()
        if old is None or old[0] not in ("waiting", "in_consultation"):
            return None
        await conn.execute(
            "UPDATE queue_entry SET status = %s WHERE id = %s", (outcome, entry_id)
        )
    return {"from_status": old[0], "patient_id": old[1]}


async def sweep_stale_entries() -> list[dict]:
    """Close walk-ins abandoned before Start on an earlier day.

    THE LOCKOUT THIS EXISTS TO PREVENT (entry 164, 2026-07-26): an
    `in_consultation` entry holds the single system-wide live-consultation slot,
    so while its date is current EVERY doctor is refused the slot — not just the
    one who opened it. The guard is global by design (see the capacity
    statement), which means one abandoned walk-in locks out the whole practice
    until midnight.

    Two conditions, both required, and the second is what keeps this safe:

    * `queue_date < CURRENT_DATE` — today's entries are never touched. A live
      consultation in progress right now looks exactly like a stale one, and the
      only thing separating them is the date.
    * no `consultation` row for that patient — if a consultation exists the
      session really started, and closing the entry as `cancelled` would file a
      real consultation under "no recording happened".

    Audits each closure itself, the same convention as
    `retention.sweep_expired_audio` — a sweep owns its own trail, so the record
    cannot go missing because a caller forgot. `queue.cancelled` with no acting
    user and a `via` saying what closed it and why: a future reader finding a
    cancelled walk-in needs the reason in the row, not in someone's memory.

    Returns what it closed. Called at startup beside the retention sweep; entry
    164 is closed by its first run.
    """
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "UPDATE queue_entry q SET status = 'cancelled'"
                " WHERE q.status = 'in_consultation'"
                "   AND q.queue_date < CURRENT_DATE"
                "   AND NOT EXISTS (SELECT 1 FROM consultation c"
                "                   WHERE c.patient_id = q.patient_id)"
                " RETURNING q.id, q.patient_id, q.queue_date"
            )
        ).fetchall()
    closed = [{"entry_id": r[0], "patient_id": r[1], "queue_date": str(r[2])}
              for r in rows]
    for entry in closed:
        await audit.log(None, "queue.cancelled", "queue_entry", entry["entry_id"],
                        {"outcome": "cancelled", "from_status": "in_consultation",
                         "patient_id": entry["patient_id"],
                         "queue_date": entry["queue_date"],
                         "via": "stale-entry sweep: abandoned before Start on an "
                                "earlier day, holding the live-consultation slot"})
        logger.warning("Stale-entry sweep closed queue entry %d (patient %d, %s)"
                       " — it was holding the live-consultation slot",
                       entry["entry_id"], entry["patient_id"], entry["queue_date"])
    return closed


async def finish_entry(entry_id: int) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE queue_entry SET status = 'done' WHERE id = %s", (entry_id,)
        )
