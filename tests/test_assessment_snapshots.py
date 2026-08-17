"""The assessment_snapshot table (Phase 7c slice 5, PHASE_7C_SPEC.md §7 —
the debt named in PHASE_7B_FACE_DRIVE_SPEC.md §6).

One row per CDS revision of a live session — version, the revision's own
moment, its audio position, whether it raised the alarm and with which
action texts — buffered in the session and persisted at completion like
the system utterances, written whether auto mode is on or off, read by
nothing yet (metric 7 and replay will). Pinned: the schema is in the one
ordering; a revision writes a row; urgent revisions carry their action
texts; the rows cascade on delete, through the #469 void-and-purge path
too; a live session with the gate DOWN writes them just the same.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import psycopg
import pytest

from app import assessment_snapshots, auth, consultations, schema
from app import main as appmain
from auto_harness import (ScriptedEngine, _assessment, _stop, gate, live,  # noqa: F401
                          needs_db)

pytestmark = needs_db


def _consultation() -> int:
    auth.ensure_schema()
    consultations.ensure_schema()
    assessment_snapshots.ensure_schema()
    return asyncio.run(consultations.create_consultation(None, None))


# --- the schema ------------------------------------------------------------

def test_the_table_is_in_the_one_schema_ordering_after_consultations():
    names = list(schema.MODULE_NAMES)
    assert "assessment_snapshots" in names
    assert names.index("assessment_snapshots") > names.index("consultations")
    schema.ensure_all()
    schema.ensure_all()          # idempotent, like every other module's DDL


# --- the row -----------------------------------------------------------------

def test_snapshot_of_carries_version_moment_position_and_the_alarm():
    at = datetime(2026, 8, 17, 9, 30, tzinfo=timezone.utc)
    quiet = assessment_snapshots.snapshot_of(_assessment(["Q?"]), 3, at, 41.26)
    assert quiet == {"version": 3, "created_at": at, "at_audio_s": 41.3,
                     "urgent": False, "urgent_actions": None}
    alarmed = _assessment(["Q?"])
    alarmed["urgent_actions"] = [{"action": "Bedside ECG now", "reason": "exclude ACS"},
                                 {"action": "Call 999", "reason": "possible STEMI"}]
    row = assessment_snapshots.snapshot_of(alarmed, 4, at, 60.0)
    assert row["urgent"] is True
    assert row["urgent_actions"] == [{"action": "Bedside ECG now", "reason": "exclude ACS"},
                                     {"action": "Call 999", "reason": "possible STEMI"}]


def test_save_and_read_back_in_version_order_with_the_texts():
    cid = _consultation()
    at = datetime(2026, 8, 17, 9, 30, tzinfo=timezone.utc)
    rows = [
        assessment_snapshots.snapshot_of(_assessment(["a"]), 2, at, 20.0),
        assessment_snapshots.snapshot_of(_assessment(["a"]), 1, at, 10.0),
    ]
    rows[0]["urgent"], rows[0]["urgent_actions"] = True, [{"action": "Call 999", "reason": "r"}]
    asyncio.run(assessment_snapshots.save(cid, rows))
    asyncio.run(assessment_snapshots.save(cid, rows))      # ON CONFLICT: once each
    got = asyncio.run(assessment_snapshots.for_consultation(cid))
    assert [g["version"] for g in got] == [1, 2]
    assert got[0]["urgent"] is False and got[0]["urgent_actions"] is None
    assert got[1]["urgent"] is True
    assert got[1]["urgent_actions"] == [{"action": "Call 999", "reason": "r"}]
    assert got[1]["created_at"] == at
    assert got[1]["at_audio_s"] == pytest.approx(20.0)


def test_rows_cascade_on_delete_and_through_the_void_and_purge_path():
    cid = _consultation()
    at = datetime.now(timezone.utc)
    asyncio.run(assessment_snapshots.save(
        cid, [assessment_snapshots.snapshot_of(_assessment([]), 1, at, 1.0)]))
    assert len(asyncio.run(assessment_snapshots.for_consultation(cid))) == 1
    # The #469 path: void, then purge — the rows must go with the record.
    admin = asyncio.run(auth.create_user(f"adm_{os.urandom(3).hex()}", "test-password-123",
                                         "Admin", "admin"))
    assert asyncio.run(consultations.void_consultation(cid, admin["id"], "test data")) is not None
    purged = asyncio.run(consultations.purge_voided(only_ids=[cid]))
    assert cid in purged["consultation_ids"]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        left = conn.execute("SELECT count(*) FROM assessment_snapshot WHERE consultation_id = %s",
                            (cid,)).fetchone()[0]
    assert left == 0
    # And a plain delete cascades too.
    cid2 = _consultation()
    asyncio.run(assessment_snapshots.save(
        cid2, [assessment_snapshots.snapshot_of(_assessment([]), 1, at, 1.0)]))
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("DELETE FROM consultation WHERE id = %s", (cid2,))
        conn.commit()
        assert conn.execute("SELECT count(*) FROM assessment_snapshot WHERE consultation_id = %s",
                            (cid2,)).fetchone()[0] == 0


# --- written on every revision of a live session ---------------------------

def _revise(s, *lines):
    """Commit transcript so that maybe_run_cds fires (the first-turn call),
    then tick until the pass lands."""
    def _inject():
        s.entry["transcript_parts"].extend(lines)
    s.ws.portal.call(_inject)
    for _ in range(40):
        s.probe()
        if s.entry["assessment"] is not None and s.entry["assessment_snapshots"]:
            return
    raise AssertionError("no CDS revision landed")


def test_a_live_revision_writes_a_row_and_an_urgent_one_carries_its_texts(gate):
    engine: ScriptedEngine = gate.cds_engine
    alarmed = _assessment(["Does it radiate?"], reasoning="cardiac")
    alarmed["urgent_actions"] = [{"action": "Bedside ECG now", "reason": "exclude ACS"}]

    async def update(transcript, previous=None):
        engine.updates.append(transcript)
        return dict(alarmed) if len(engine.updates) == 1 else _assessment(["Any nausea?"])
    engine.update = update
    with live(gate) as s:
        s.disclose()
        _revise(s, "I've got this crushing pain in my chest.")
        snaps = s.entry["assessment_snapshots"]
        assert len(snaps) == 1
        assert snaps[0]["version"] == 1 and snaps[0]["urgent"] is True
        assert snaps[0]["urgent_actions"] == [{"action": "Bedside ECG now",
                                               "reason": "exclude ACS"}]
        cid = _stop(s)
    rows = asyncio.run(assessment_snapshots.for_consultation(cid))
    assert [(r["version"], r["urgent"]) for r in rows] == [(1, True)]
    assert rows[0]["urgent_actions"][0]["action"] == "Bedside ECG now"
    assert rows[0]["at_audio_s"] is not None


def test_snapshots_are_written_with_the_gate_down_too(gate, monkeypatch):
    """Auto mode on or off: metric 7 and replay want every revision. This
    is the one 7c code path outside the flag — schema-level, one small
    insert per pass, no behaviour the doctor can see."""
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", False)
    with live(gate) as s:
        assert s.entry["auto"] is None
        s.disclose()
        _revise(s, "It started on Tuesday.")
        assert len(s.entry["assessment_snapshots"]) == 1
        cid = _stop(s)
    rows = asyncio.run(assessment_snapshots.for_consultation(cid))
    assert len(rows) == 1 and rows[0]["urgent"] is False
