"""Public monitoring pulse (external-demo observation).

GET /api/monitor/pulse is deliberately unauthenticated: it exposes
aggregate counts ONLY — never a username, patient name, or any clinical
content. Every value is a number or boolean plus one ISO timestamp, so
there is structurally nothing to leak. "Today" means Europe/London.

The database counts and the recordings-directory scan are cached for
PULSE_CACHE_TTL_S, so external polling — however aggressive — costs at
most one indexed query every ~10 s. server_time, the live-consultation
boolean, and the error counter are in-memory reads and stay fresh on
every call.

All per-day counters — and their rolling last-hour equivalents — come
from the audit log (one grouped query over the (action, at) index, two
filtered counts per action): registrations and logins were already
audited; finalisation failures and live-slot rejections write their own
audit events precisely so this endpoint can count them after a restart.
"""

from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

LONDON = ZoneInfo("Europe/London")
PULSE_CACHE_TTL_S = 10.0

# audit action → pulse field. Adding a counter is one audit.log call at
# the event site plus one row here; each field automatically gets a
# rolling *_last_hour twin computed from the same query.
_DAY_COUNTERS = {
    # Both registration events feed one field (counts ACCUMULATE per
    # field): user.registered is the pre-approval-era event, kept so the
    # day's totals stay correct across the cutover.
    "user.registered": "registrations_today",
    "user.registered_pending": "registrations_today",
    "user.login": "logins_today",
    "consultation.created": "consultations_started_today",
    "finalisation.failed": "finalisations_failed_today",
    "live.slot_rejected": "live_slot_rejections_today",
}


def _last_hour_field(day_field: str) -> str:
    return day_field.replace("_today", "_last_hour")

# Unhandled exceptions / 5xx responses, as timestamps in a ring buffer —
# maxlen bounds memory if something errors in a tight loop; entries older
# than an hour are pruned on read. In-process by design: errors before
# the last restart are gone, which is the right semantics for "is the
# demo healthy right now".
_errors: deque[float] = deque(maxlen=1000)

_cache: dict = {}


def record_error() -> None:
    _errors.append(time.time())


def errors_last_hour(now: float | None = None) -> int:
    cutoff = (now if now is not None else time.time()) - 3600
    while _errors and _errors[0] < cutoff:
        _errors.popleft()
    return len(_errors)


def london_day_start(now: datetime | None = None) -> datetime:
    """Midnight today in Europe/London as an aware datetime — Postgres
    timestamptz comparison then lands the day boundary correctly in both
    GMT and BST."""
    now = now.astimezone(LONDON) if now else datetime.now(LONDON)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def invalidate_cache() -> None:
    """Tests only: force the next pulse to recount."""
    _cache.clear()


def _audio_disk_bytes(recordings_dir: Path) -> int:
    total = 0
    try:
        entries = list(recordings_dir.iterdir())
    except OSError:
        return 0
    for entry in entries:
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


async def _aggregates(recordings_dir: Path) -> dict:
    counts = dict.fromkeys(_DAY_COUNTERS.values(), 0)
    counts.update(dict.fromkeys(map(_last_hour_field, _DAY_COUNTERS.values()), 0))
    day_start = london_day_start()
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        rows = await (
            await conn.execute(
                "SELECT action,"
                " count(*) FILTER (WHERE at >= %s),"
                " count(*) FILTER (WHERE at >= %s)"
                " FROM audit_event"
                " WHERE at >= %s AND action = ANY(%s) GROUP BY action",
                # Just after a London midnight the last hour reaches back
                # into yesterday, so the scan starts at the earlier cutoff.
                (day_start, hour_ago, min(day_start, hour_ago), list(_DAY_COUNTERS)),
            )
        ).fetchall()
        # Accounts still waiting for the admin's approval (approve-to-
        # activate, 2026-07-24), windowed by registration time so the
        # hourly sentry can say "someone new is waiting". Live state, not
        # an event count: an approved account drops out immediately.
        pending_row = await (
            await conn.execute(
                "SELECT count(*) FILTER (WHERE created_at >= %s),"
                " count(*) FILTER (WHERE created_at >= %s)"
                " FROM app_user WHERE pending_approval AND NOT active",
                (day_start, hour_ago),
            )
        ).fetchone()
    for action, day_n, hour_n in rows:
        counts[_DAY_COUNTERS[action]] += day_n
        counts[_last_hour_field(_DAY_COUNTERS[action])] += hour_n
    counts["registrations_pending_activation_today"] = pending_row[0]
    counts["registrations_pending_activation_last_hour"] = pending_row[1]
    counts["audio_disk_used_mb"] = round(
        _audio_disk_bytes(recordings_dir) / (1024 * 1024), 1
    )
    return counts


async def pulse(live_active: bool, recordings_dir: Path) -> dict:
    now = time.monotonic()
    if not _cache or now - _cache["at"] >= PULSE_CACHE_TTL_S:
        _cache.update(at=now, data=await _aggregates(recordings_dir))
    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        **_cache["data"],
        "live_consultation_active": live_active,
        "errors_last_hour": errors_last_hour(),
    }
