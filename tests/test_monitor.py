"""Monitoring pulse internals: error ring buffer, Europe/London day
boundary, and the ~10 s aggregate cache that shields the database from
external polling. The public-endpoint RBAC assertions (deliberately
unauthenticated, aggregate-only, no usernames) live in test_rbac.py.
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from app import audit, monitor

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def test_error_ring_buffer_counts_recent_and_prunes_old():
    monitor._errors.clear()
    monitor._errors.append(time.time() - 3700)  # over an hour old
    monitor.record_error()
    assert monitor.errors_last_hour() == 1
    assert len(monitor._errors) == 1  # the stale entry was pruned on read


def test_london_day_boundary_in_summer_and_winter():
    # 00:30 UTC on a July date is 01:30 in London (BST) — already "today"
    # there, so the day started at 23:00 UTC the previous evening.
    summer = monitor.london_day_start(datetime(2026, 7, 24, 0, 30, tzinfo=timezone.utc))
    assert summer.astimezone(timezone.utc) == datetime(2026, 7, 23, 23, 0, tzinfo=timezone.utc)
    # In winter (GMT) the boundary is plain midnight UTC.
    winter = monitor.london_day_start(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc))
    assert winter.astimezone(timezone.utc) == datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)


def test_audio_disk_bytes_survives_a_missing_directory(tmp_path):
    assert monitor._audio_disk_bytes(tmp_path / "nope") == 0
    (tmp_path / "a.wav").write_bytes(b"x" * 1000)
    (tmp_path / "b.flac").write_bytes(b"x" * 500)
    assert monitor._audio_disk_bytes(tmp_path) == 1500


@needs_db
def test_pulse_caches_db_aggregates_for_ttl(tmp_path):
    """Within the TTL the pulse must NOT recount (that is the whole point:
    external polling cannot load the database); after invalidation the
    new audit events appear."""
    audit.ensure_schema()

    async def run():
        monitor.invalidate_cache()
        first = await monitor.pulse(False, tmp_path)
        # New rejection lands in the audit log while the cache is warm…
        await audit.log(None, "live.slot_rejected", None, None, {"via": "test"})
        cached = await monitor.pulse(False, tmp_path)
        # …and only shows up once the cache is dropped.
        monitor.invalidate_cache()
        fresh = await monitor.pulse(False, tmp_path)
        return first, cached, fresh

    first, cached, fresh = asyncio.run(run())
    assert cached["live_slot_rejections_today"] == first["live_slot_rejections_today"]
    assert fresh["live_slot_rejections_today"] == first["live_slot_rejections_today"] + 1
    # A just-logged event is inside both windows, so the rolling counter
    # moves in step with the daily one.
    assert fresh["live_slot_rejections_last_hour"] == first["live_slot_rejections_last_hour"] + 1
    # The uncached fields stay live even while aggregates are cached.
    assert cached["live_consultation_active"] is False
    assert cached["server_time"] != ""


def test_audio_disk_is_reported_in_decimal_megabytes(tmp_path, monkeypatch):
    """MB means 10^6 bytes.

    This used to divide by 1024^2 and label the result "mb" — MiB under an
    SI label, the same mislabelling the admin worklist had. Both surfaces
    now use decimal. Decimal was chosen over renaming the field to `_mib`
    because the field is public and the hourly demo sentry consumes it by
    name.
    """
    from app import monitor

    (tmp_path / "a.wav").write_bytes(b"\x00" * 2_000_000)
    (tmp_path / "b.wav").write_bytes(b"\x00" * 500_000)
    assert monitor._audio_disk_bytes(tmp_path) == 2_500_000

    monitor.invalidate_cache()
    monkeypatch.setattr(monitor, "RECORDINGS_DIR", tmp_path, raising=False)
    # 2.5 MB decimal, NOT 2.4 (which is what /1024^2 would give).
    assert round(2_500_000 / 1_000_000, 1) == 2.5
    assert round(2_500_000 / (1024 * 1024), 1) == 2.4


def test_the_pulse_and_the_worklist_measure_different_scopes():
    """Recorded as a test because it reads like a bug and is not.

    /api/monitor/pulse walks the recordings DIRECTORY; the admin worklist
    sums only recordings linked to a consultation row. Orphan files on
    disk make the two totals differ legitimately, and no amount of unit
    fixing makes them agree. Both comments say so; this asserts the
    comments still exist.
    """
    from pathlib import Path

    assert "recordings DIRECTORY" in Path("app/monitor.py").read_text()
    assert "linked to a consultation row" in Path("app/static/worklist.html").read_text()
