"""Speaker-tagged lines from the Nemotron live pipeline, stored as they arrive.

Task 13 (v1.1). With SPEECH_PIPELINE=nemotron, the live process commits
each line once, with its speaker (an anonymous index, not a person) and
its times on the session clock. `NemotronLiveSession` writes the line
here at that moment, before it orders lines for the page and the CDS. So
what was heard survives a crash of the app or of the worker.

The consultation row does not exist until Stop, so lines are keyed by the
live session id. At Stop they are linked to the consultation
(`link`), and finalisation builds the final transcript from them
(`for_consultation`). WhisperX and pyannote are not used on this path.

A **revision** updates the text and end of a line already stored. The
worker sends one when NeMo extends a line after committing it (in Task 13
Part 1, two lines each gained a final full stop). So the stored line ends
as NeMo's own final text.

Rows cascade on consultation delete. Rows never linked, because their
session never reached Stop or the grace expiry (the app itself died),
hold consultation text with no consultation. `purge_unlinked` deletes them
after a day.

Research and education prototype; synthetic consultations only.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS live_speech_segment (
    session_id text NOT NULL,
    line_id int NOT NULL,            -- the worker's id, in commit order
    speaker int NOT NULL,            -- anonymous diariser index (0, 1, ...)
    start_s real NOT NULL,           -- session clock (= recording clock)
    end_s real NOT NULL,
    text text NOT NULL,
    consultation_id int REFERENCES consultation(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    revised_at timestamptz,
    PRIMARY KEY (session_id, line_id)
);
CREATE INDEX IF NOT EXISTS live_speech_segment_consultation_idx
    ON live_speech_segment (consultation_id, start_s);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


async def save(session_id: str, lines: list[dict]) -> None:
    """Store newly committed lines. A line id is stored once; a repeat is
    ignored (the first write is the record of what was heard)."""
    if not lines:
        return
    async with await _conn() as conn:
        for line in lines:
            await conn.execute(
                "INSERT INTO live_speech_segment"
                " (session_id, line_id, speaker, start_s, end_s, text)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (session_id, line_id) DO NOTHING",
                (session_id, int(line["id"]), int(line["speaker"]),
                 float(line["start"]), float(line["end"]), line["text"]))
        await conn.commit()


async def revise(session_id: str, revisions: list[dict]) -> None:
    """NeMo extended a line after it was committed: store its final text."""
    if not revisions:
        return
    async with await _conn() as conn:
        for rev in revisions:
            await conn.execute(
                "UPDATE live_speech_segment SET text = %s, end_s = %s, revised_at = now()"
                " WHERE session_id = %s AND line_id = %s",
                (rev["text"], float(rev["end"]), session_id, int(rev["id"])))
        await conn.commit()


async def link(session_id: str, consultation_id: int) -> int:
    """At Stop: the session's lines belong to this consultation."""
    async with await _conn() as conn:
        cur = await conn.execute(
            "UPDATE live_speech_segment SET consultation_id = %s"
            " WHERE session_id = %s AND consultation_id IS NULL",
            (consultation_id, session_id))
        await conn.commit()
        return cur.rowcount


def _rows_to_lines(rows) -> list[dict]:
    return [{"id": r[0], "speaker": r[1], "start": r[2], "end": r[3], "text": r[4]}
            for r in rows]


async def for_consultation(consultation_id: int) -> list[dict]:
    """Every stored line of the consultation, in spoken (start) order."""
    async with await _conn() as conn:
        rows = await (await conn.execute(
            "SELECT line_id, speaker, start_s, end_s, text FROM live_speech_segment"
            " WHERE consultation_id = %s ORDER BY start_s, line_id",
            (consultation_id,))).fetchall()
    return _rows_to_lines(rows)


async def for_session(session_id: str) -> list[dict]:
    async with await _conn() as conn:
        rows = await (await conn.execute(
            "SELECT line_id, speaker, start_s, end_s, text FROM live_speech_segment"
            " WHERE session_id = %s ORDER BY start_s, line_id",
            (session_id,))).fetchall()
    return _rows_to_lines(rows)


async def purge_unlinked(older_than_hours: float = 24.0) -> int:
    async with await _conn() as conn:
        cur = await conn.execute(
            "DELETE FROM live_speech_segment WHERE consultation_id IS NULL"
            " AND created_at < now() - make_interval(secs => %s)",
            (older_than_hours * 3600.0,))
        await conn.commit()
        return cur.rowcount
