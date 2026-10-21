"""Retention (spec 15.11 ruling 7; 7.3; 8.8; R15; V1_LESSONS 10.3, 10.5):
the clock deletes the recording file only, after the days of the
setting, default 90; 0 keeps it until the consultation is deleted by
hand. The transcript and the approved note stay. The sweep runs at
start-up and then every 24 hours in the app's own loop, never while a
consultation is stopping; each sweep that deletes anything writes the
date to each row, one audio_deletion row and one audit line with the
consultations and the bytes freed; the player then shows the line of
stage 6 with the date. The start-up sweep of orphans reports a
recording file with no consultation row and deletes nothing."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Callable

from openconsult.consult.recording import folder_of

SWEEP_EVERY_S = 24 * 3600      # once a day while the app runs (ruling 7)
RETRY_S = 60                   # a sweep put off by a Stop is tried again after this
DEFERRED, DONE = "deferred", "done"


def due(rows: list[dict], days: int, now: datetime) -> list[dict]:
    """The final consultations whose recording is older than the setting
    and still here. At 0 nothing is ever due."""
    if days <= 0:
        return []
    limit = now - timedelta(days=days)
    found = []
    for row in rows:
        if row["state"] != "final" or not row["recording_file"] or row["audio_deleted_at"] or not row["stopped_at"]:
            continue
        if datetime.fromisoformat(row["stopped_at"]) < limit:
            found.append(row)
    return found


def sweep(p, now: datetime | None = None) -> str:
    """One sweep. Deferred while any consultation is stopping (never
    during a Stop); otherwise done, with the rows, the audio_deletion row
    and the audit line written only when something was deleted."""
    if p.consultations.in_state("stopping"):
        return DEFERRED
    now = now or p.clock()
    rows = due(p.consultations.all_rows(), p.stored.audio_retention_days, now)
    deleted, freed = [], 0
    for row in rows:
        path = folder_of(p.settings.data_folder) / row["recording_file"]
        if path.is_file():
            freed += path.stat().st_size
            path.unlink()
        p.consultations.set(row["id"], audio_deleted_at=now.isoformat(timespec="seconds"))
        deleted.append(row["id"])
    if deleted:
        p.db.execute("INSERT INTO audio_deletion (at, consultation_ids, files, bytes) VALUES (?, ?, ?, ?)",
                     (now.isoformat(timespec="seconds"), json.dumps(deleted), len(deleted), freed))
        p.audit.record("audio.deleted", f"{len(deleted)} recordings of consultations {', '.join(map(str, deleted))}, "
                                        f"{freed} bytes freed, after {p.stored.audio_retention_days} days")
    return DONE


def next_wait_s(outcome: str) -> int:
    return RETRY_S if outcome == DEFERRED else SWEEP_EVERY_S


async def loop(p, sleep: Callable = asyncio.sleep, run: Callable = sweep) -> None:
    """The app's own loop: wait, sweep on a thread, wait again; the first
    sweep was made at start-up, so the first wait is a whole day."""
    wait = SWEEP_EVERY_S
    while True:
        await sleep(wait)
        outcome = await asyncio.to_thread(run, p)
        wait = next_wait_s(outcome)


def orphans(p) -> list[str]:
    """The start-up sweep of orphans (ruling 8; V1_LESSONS 10.3): every
    recording file whose number names no consultation row, reported with
    one audit line and never deleted. The names hold only numbers."""
    folder = folder_of(p.settings.data_folder)
    if not folder.is_dir():
        return []
    known = {row["id"] for row in p.consultations.all_rows()}
    found = []
    for path in sorted(folder.iterdir()):
        if path.suffix not in (".wav", ".ogg") or not path.stem.startswith("consultation_"):
            continue
        number = path.stem.removeprefix("consultation_")
        if not number.isdigit() or int(number) not in known:
            found.append(path.name)
    if found:
        p.audit.record("recording.orphan", ", ".join(found))
    return found
