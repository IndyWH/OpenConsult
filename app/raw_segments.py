"""The raw-transcript view's storage: pre-merge ASR segments, from disk.

Spec: `RAW_TRANSCRIPT_VIEW_SPEC.md`. The diarised transcript is a
processed artifact — WhisperX transcribes, pyannote clusters, a merge
joins, a rule assigns roles — and three of the defects of 21–28 July
lived in those steps, not in the recognition. This table lets the doctor
see the layer their signed note rests on.

**Read from storage, never rebuilt (spec §3).** WhisperX is not
deterministic across runs (turn counts moved ±2‥+5 on identical audio,
measured 2026-07-28), so a view rebuilt on demand would show a
consultation that never existed, presented as the record of what was
heard. These rows are written once, at finalisation, and only ever read
after that. There is no code path from this module to a transcriber.

**Persisted BEFORE the silence invariant, dropped segments FLAGGED**
(owner decision 2026-07-30, banked in HANDOVER; it supersedes spec §2's
"out of scope" for invariant-dropped segments): the invariant is itself
a layer that has eaten transcript — 445 lost six minutes to it — and the
view exists to make such layers visible. A view showing only what
survived the invariant would be blind to the one failure mode it was
commissioned after.

**Display only (spec §4).** Raw segments carry no turn number and are
not citation targets: `for_consultation` deliberately emits no `idx`
(order is the array order), matching the system-utterance convention —
there is nothing here a citation chip could resolve to. The diarised
view stays the record; every correction happens there.

Rows cascade on consultation delete, so the admin purge stays one step.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_segment (
    id serial PRIMARY KEY,
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    seq int NOT NULL,                -- order within the recording
    cluster text,                    -- pyannote majority label (SPEAKER_xx)
    start_s real NOT NULL,
    end_s real NOT NULL,
    text text NOT NULL,
    confidence real,
    -- Removed by the silence invariant (stored anyway, flagged — the
    -- owner's 2026-07-30 decision: the view must show what layers ate).
    dropped boolean NOT NULL DEFAULT false,
    UNIQUE (consultation_id, seq)
);
CREATE INDEX IF NOT EXISTS raw_segment_consultation_idx
    ON raw_segment (consultation_id, seq);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


async def save(consultation_id: int, segments: list[dict]) -> None:
    """Persist one finalisation's raw segments. Written once; a re-run of
    finalisation for the same consultation must not duplicate rows, so
    conflicts are ignored rather than updated — the FIRST write is the
    record of what that finalisation heard."""
    if not segments:
        return
    async with await _conn() as conn:
        for seg in segments:
            await conn.execute(
                "INSERT INTO raw_segment"
                " (consultation_id, seq, cluster, start_s, end_s, text,"
                "  confidence, dropped)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (consultation_id, seq) DO NOTHING",
                (consultation_id, seg["idx"], seg.get("cluster"),
                 seg["start"], seg["end"], seg["text"],
                 seg.get("confidence"), bool(seg.get("dropped"))),
            )
        await conn.commit()


async def for_consultation(consultation_id: int) -> list[dict]:
    """The stored raw view, oldest first. NO `idx` in the payload — a raw
    segment must never look like a citation target (spec §4)."""
    async with await _conn() as conn:
        rows = await (await conn.execute(
            "SELECT cluster, start_s, end_s, text, confidence, dropped"
            " FROM raw_segment WHERE consultation_id = %s ORDER BY seq",
            (consultation_id,))).fetchall()
    return [{"cluster": r[0], "start_s": r[1], "end_s": r[2], "text": r[3],
             "confidence": r[4], "dropped": r[5]} for r in rows]
