"""Audio retention (plan §8: "audio deleted after finalisation unless
flagged for research").

Two mechanisms, audio-only — transcripts and notes are NEVER touched:

1. On approval the consultation's WAV is compressed to FLAC (lossless,
   same sample rate — the audit trail keeps its evidential value at
   roughly half the disk cost).
2. A retention sweep (on startup, then daily) deletes audio older than
   AUDIO_RETENTION_DAYS (env, default 90) unless the consultation is
   flagged keep_for_research (admin-settable). One audit event per
   sweep that deleted anything: data.audio_purged {consultation_ids,
   bytes_freed}.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from app import audit

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")
AUDIO_RETENTION_DAYS = int(os.getenv("AUDIO_RETENTION_DAYS", "90"))
SWEEP_INTERVAL_S = 24 * 3600

logger = logging.getLogger(__name__)


def compress_to_flac(wav_path: str) -> tuple[str, int, int] | None:
    """WAV → FLAC beside it, delete the WAV. Lossless: 16-bit PCM in,
    16-bit FLAC out, sample rate untouched. Returns (flac_path,
    wav_bytes, flac_bytes), or None if there was nothing to do.
    Blocking (file I/O + encode) — call via asyncio.to_thread."""
    import soundfile

    path = Path(wav_path)
    if path.suffix.lower() != ".wav" or not path.exists():
        return None
    data, sample_rate = soundfile.read(path, dtype="int16")
    flac_path = path.with_suffix(".flac")
    soundfile.write(flac_path, data, sample_rate, format="FLAC", subtype="PCM_16")
    wav_bytes = path.stat().st_size
    flac_bytes = flac_path.stat().st_size
    path.unlink()
    logger.info("Compressed %s: %d → %d bytes (%.0f%%)",
                path.name, wav_bytes, flac_bytes, 100 * flac_bytes / wav_bytes)
    return str(flac_path), wav_bytes, flac_bytes


async def compress_on_approval(cid: int, audio_path: str | None) -> None:
    """Best-effort: approval must never fail because compression did."""
    from app import consultations

    if not audio_path:
        return
    try:
        result = await asyncio.to_thread(compress_to_flac, audio_path)
    except Exception:
        logger.exception("FLAC compression failed for consultation %d "
                         "(WAV left in place)", cid)
        return
    if result is not None:
        await consultations.set_audio_path(cid, result[0])


async def sweep_expired_audio(only_ids: list[int] | None = None) -> dict:
    """Delete audio files past retention; audio only. Rows keep their
    transcripts/notes; audio_path is nulled and audio_deleted_at stamped
    so the UI can say "audio purged (retention)" rather than showing a
    broken file. keep_for_research exempts a row indefinitely.

    only_ids narrows the sweep — tests MUST pass it (same convention as
    consultations.purge_voided): the suite runs against the real dev
    database, and an unscoped sweep in a test would delete the owner's
    real recordings the day they age past the retention window."""
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        rows = await (
            await conn.execute(
                "SELECT id, audio_path FROM consultation"
                " WHERE audio_path IS NOT NULL AND NOT keep_for_research"
                " AND started_at < now() - make_interval(days => %s)"
                + (" AND id = ANY(%s)" if only_ids is not None else ""),
                ((AUDIO_RETENTION_DAYS, only_ids) if only_ids is not None
                 else (AUDIO_RETENTION_DAYS,)),
            )
        ).fetchall()
        purged_ids: list[int] = []
        bytes_freed = 0
        for cid, path in rows:
            with contextlib.suppress(OSError):
                bytes_freed += os.path.getsize(path)
                os.unlink(path)
            # Stamp the row even if the file was already gone — the audio
            # is equally unavailable either way.
            await conn.execute(
                "UPDATE consultation SET audio_path = NULL,"
                " audio_deleted_at = now() WHERE id = %s", (cid,),
            )
            purged_ids.append(cid)
    if purged_ids:
        await audit.log(None, "data.audio_purged", "consultation", None,
                        {"consultation_ids": purged_ids,
                         "bytes_freed": bytes_freed,
                         "retention_days": AUDIO_RETENTION_DAYS})
        logger.info("Retention sweep: %d recording(s) deleted, %d bytes freed",
                    len(purged_ids), bytes_freed)
    return {"consultations": len(purged_ids), "bytes_freed": bytes_freed}


async def retention_loop() -> None:
    """On-startup sweep, then daily. Run as a lifespan background task."""
    while True:
        try:
            await sweep_expired_audio()
        except Exception:
            logger.exception("Retention sweep failed; retrying next cycle")
        await asyncio.sleep(SWEEP_INTERVAL_S)
