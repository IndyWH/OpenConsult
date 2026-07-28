"""The abandoned-walk-in lockout, and the sweep that clears it.

QUEUE ENTRY 164 IS THE SPECIMEN: herath, 2026-07-26, patient 253, still
`in_consultation`, no consultation row — a walk-in opened for a demo and
abandoned before Start.

The defect has two halves, and the first is the one that takes the practice
down. An `in_consultation` entry holds the SINGLE SYSTEM-WIDE live-consultation
slot, so while its date is current every doctor is refused — the guard is global
by design (the capacity statement), which means one abandoned walk-in locks out
everybody until midnight. Then, once the date rolls over, BOTH recovery paths
refused the entry as well, because every queue query was scoped to
`queue_date = CURRENT_DATE`: Resume answered 404 and Close answered 409. Nothing
was left that could close it, so it was permanent.

Two changes are tested here: the close path can now reach into the past, and a
startup sweep closes entries abandoned before Start on an earlier day.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from datetime import date, timedelta

import psycopg
import pytest
from dotenv import load_dotenv

from app import audit, consultations, frontdesk

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _schema() -> None:
    frontdesk.ensure_schema()
    consultations.ensure_schema()
    audit.ensure_schema()


def _entry_on(day: date, *, status: str = "in_consultation",
              with_consultation: bool = False) -> dict:
    """A queue entry dated `day`, inserted directly.

    The normal paths always write CURRENT_DATE, which is exactly why the stale
    case could not be reproduced through them.
    """
    _schema()

    async def build() -> dict:
        async with await psycopg.AsyncConnection.connect(
                os.environ["DATABASE_URL"]) as conn:
            patient = await (await conn.execute(
                "INSERT INTO patient (name, age, sex) VALUES (%s, 40, 'F')"
                " RETURNING id", (f"Stale {secrets.token_hex(3)}",))).fetchone()
            entry = await (await conn.execute(
                "INSERT INTO queue_entry (patient_id, queue_date, position, status)"
                " VALUES (%s, %s, 99, %s) RETURNING id",
                (patient[0], day, status))).fetchone()
        cid = None
        if with_consultation:
            cid = await consultations.create_consultation(patient_id=patient[0])
        return {"entry_id": entry[0], "patient_id": patient[0],
                "consultation_id": cid}

    return asyncio.run(build())


def _status(entry_id: int) -> str:
    async def read() -> str:
        async with await psycopg.AsyncConnection.connect(
                os.environ["DATABASE_URL"]) as conn:
            row = await (await conn.execute(
                "SELECT status FROM queue_entry WHERE id = %s",
                (entry_id,))).fetchone()
        return row[0]

    return asyncio.run(read())


def _sweep() -> list[dict]:
    return asyncio.run(frontdesk.sweep_stale_entries())


YESTERDAY = date.today() - timedelta(days=1)
TWO_DAYS_AGO = date.today() - timedelta(days=2)


# ------------------------------------------------- the close path reaches back

def test_an_entry_from_a_past_date_can_be_closed():
    """The escape hatch must not itself be day-scoped. Before this, Close
    answered 409 on entry 164 because `close_entry` filtered on CURRENT_DATE —
    an escape hatch scoped to today cannot let anybody out of yesterday."""
    entry = _entry_on(TWO_DAYS_AGO)
    closed = asyncio.run(frontdesk.close_entry(entry["entry_id"], "cancelled"))
    assert closed is not None, "a past-dated entry must be closable"
    assert closed["from_status"] == "in_consultation"
    assert _status(entry["entry_id"]) == "cancelled"


def test_todays_entries_are_still_closable_and_the_display_stays_day_scoped():
    """Widening the close path must not widen the queue. Today's queue is still
    today's queue: `_ENTRY_SELECT` keeps its CURRENT_DATE filter, so a
    past-dated entry stays invisible to `get_entry` even though it can be
    closed."""
    old = _entry_on(YESTERDAY)
    assert asyncio.run(frontdesk.get_entry(old["entry_id"])) is None, (
        "a past-dated entry must not appear in today's queue")

    today = _entry_on(date.today(), status="waiting")
    assert asyncio.run(frontdesk.close_entry(today["entry_id"], "done")) is not None
    assert _status(today["entry_id"]) == "done"

    from pathlib import Path
    source = Path("app/frontdesk.py").read_text()
    select = source[source.index("_ENTRY_SELECT = ("):]
    select = select[:select.index(")\n")]
    assert "q.queue_date = CURRENT_DATE" in select, (
        "the display queries must stay day-scoped")


# --------------------------------------------------------------- the sweep

def test_the_sweep_closes_a_stale_entry():
    entry = _entry_on(YESTERDAY)
    closed = _sweep()
    assert entry["entry_id"] in [c["entry_id"] for c in closed]
    assert _status(entry["entry_id"]) == "cancelled"


def test_the_sweep_audits_what_it_closed():
    """A system action with no acting user, the retention sweep's convention.
    The sweep writes its own trail rather than relying on a caller, and the
    detail has to say WHY — a future reader finding a cancelled walk-in needs
    the reason in the row, not in someone's memory."""
    entry = _entry_on(YESTERDAY)
    _sweep()

    async def read() -> dict | None:
        async with await psycopg.AsyncConnection.connect(
                os.environ["DATABASE_URL"]) as conn:
            row = await (await conn.execute(
                "SELECT user_id, detail FROM audit_event"
                " WHERE action = 'queue.cancelled' AND subject_id = %s"
                " ORDER BY id DESC LIMIT 1", (entry["entry_id"],))).fetchone()
        return row

    row = asyncio.run(read())
    assert row is not None, "the sweep's closure must be audited"
    user_id, detail = row
    assert user_id is None, "a sweep has no acting user"
    assert detail["from_status"] == "in_consultation"
    assert "stale-entry sweep" in detail["via"]


def test_the_sweep_does_not_touch_an_entry_with_a_consultation_row():
    """If a consultation exists the session really started, and closing the
    entry as `cancelled` would file a real consultation under "no recording
    happened"."""
    entry = _entry_on(YESTERDAY, with_consultation=True)
    assert entry["entry_id"] not in [c["entry_id"] for c in _sweep()]
    assert _status(entry["entry_id"]) == "in_consultation"


def test_the_sweep_does_not_touch_todays_entries():
    """THE dangerous case: a live consultation in progress right now looks
    exactly like a stale one, and the only thing separating them is the date. A
    sweep that got this wrong would cancel the consultation being recorded."""
    live = _entry_on(date.today())
    waiting = _entry_on(date.today(), status="waiting")
    closed = [c["entry_id"] for c in _sweep()]
    assert live["entry_id"] not in closed
    assert waiting["entry_id"] not in closed
    assert _status(live["entry_id"]) == "in_consultation"
    assert _status(waiting["entry_id"]) == "waiting"


def test_the_sweep_leaves_already_closed_entries_alone():
    """Idempotent: it runs at every startup, and a restart loop must not
    re-audit the same closure over and over."""
    entry = _entry_on(YESTERDAY)
    assert entry["entry_id"] in [c["entry_id"] for c in _sweep()]
    assert entry["entry_id"] not in [c["entry_id"] for c in _sweep()]


def test_the_sweep_runs_at_startup_beside_the_retention_sweep():
    from pathlib import Path

    main = Path("app/main.py").read_text()
    lifespan = main[main.index("app.state.retention_task = asyncio.create_task"):]
    lifespan = lifespan[:lifespan.index("\n    yield")]
    assert "frontdesk.sweep_stale_entries()" in lifespan
    assert "except Exception" in lifespan, (
        "startup must survive a sweep failure")
