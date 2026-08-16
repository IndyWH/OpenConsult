"""What the system said out loud, and exactly where in the recording.

Spec: `PHASE_7A_SPEC.md` §3.1. Two jobs, and the first one is structural:

**1. A separate table, on purpose.** System utterances are NOT rows in
`transcript_turn` with a `role` of `system`. The note generator receives
turns; system utterances are not turns. That is the by-construction
version of "the note can never cite our voice" — there is no enum value
for a future contributor to forget to filter, and no query that
accidentally includes us by omitting a WHERE clause. Every path that
reads the transcript (note generation, citation resolution, plain-text
export, referral letters) reads `transcript_turn` and therefore cannot
see this table even by mistake.

**2. The durable record of the exclusion spans.** Live exclusion happens
in `app/live.py` while the session is in memory; finalisation happens
minutes later, possibly after a crash and restart, on a WAV file. These
rows are what carries the spans across that gap — which is why spec §2.3
can say that a `connection_lost` finalisation still excludes correctly:
the spans live in the database, not in the live session object.

**Bytes are authoritative, milliseconds are for humans.** Both are
stored. `start_byte`/`end_byte` are exact offsets into the WAV's PCM data
and are what `app/finalize.py` mutes; the `*_offset_ms` columns spec §3.1
names by that name are derived from them (32 bytes per millisecond at
16 kHz mono 16-bit) and rounded, so they must never be the thing arithmetic
is done on.

Rows cascade on consultation delete, so the admin purge stays one step.
"""

from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

# end_reason values. 'complete' and 'barge_in' come from the client;
# 'doctor_stop' is the manual cut; 'cancelled' is a reconnect (playback is
# never resumed across one); 'failed_to_play' means speak_started never
# arrived, so there was no window and no exclusion; 'window_ceiling' means
# speak_ended never arrived and the window closed at
# start + duration + tail. Phase 7c (PHASE_7C_SPEC.md §5, §7, §11):
# 'politeness_abort' — the client found speech had resumed immediately
# before playback and declined to play (no window, no span; the utterance
# is requeued by the controller, not lost); 'urgency_pause' — an auto
# utterance cut because an urgent alarm paused auto mode.
END_REASONS = ("complete", "barge_in", "doctor_stop", "cancelled",
               "failed_to_play", "window_ceiling",
               "politeness_abort", "urgency_pause")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS system_utterance (
    id serial PRIMARY KEY,
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    utterance_id text NOT NULL,
    text text NOT NULL,
    ref_kind text NOT NULL,          -- 'phrase' | 'cds_question' | 'template' (7c)
    ref_detail jsonb,                -- phrase id, or assessment version + index,
                                     -- or template id + topic; auto utterances
                                     -- (7c) add via/phase/trigger
    cds_rationale text,              -- the agenda's reasoning as it stood
    requested_at timestamptz NOT NULL DEFAULT now(),
    -- Authoritative exclusion span: byte offsets into the WAV's PCM data.
    start_byte bigint,
    end_byte bigint,
    -- The same span in milliseconds, per spec 3.1's column names. Derived
    -- and rounded — never the input to arithmetic.
    started_offset_ms int,
    ended_offset_ms int,
    end_reason text,
    cut_latency_ms int,              -- barge-in: speech onset to playback stop
    voice text,
    synth_ms int,
    stale boolean NOT NULL DEFAULT false,  -- question had left the agenda
    UNIQUE (consultation_id, utterance_id)
);
CREATE INDEX IF NOT EXISTS system_utterance_consultation_idx
    ON system_utterance (consultation_id, start_byte);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


async def save(consultation_id: int, rows: list[dict]) -> None:
    """Persist a session's utterances. Called once, at session completion."""
    if not rows:
        return
    async with await _conn() as conn:
        for row in rows:
            await conn.execute(
                "INSERT INTO system_utterance"
                " (consultation_id, utterance_id, text, ref_kind, ref_detail,"
                "  cds_rationale, start_byte, end_byte, started_offset_ms,"
                "  ended_offset_ms, end_reason, cut_latency_ms, voice, synth_ms,"
                "  stale)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (consultation_id, utterance_id) DO NOTHING",
                (consultation_id, row["utterance_id"], row["text"], row["ref_kind"],
                 json.dumps(row.get("ref_detail") or {}), row.get("cds_rationale"),
                 row.get("start_byte"), row.get("end_byte"),
                 row.get("started_offset_ms"), row.get("ended_offset_ms"),
                 row.get("end_reason"), row.get("cut_latency_ms"),
                 row.get("voice"), row.get("synth_ms"), bool(row.get("stale"))),
            )
        await conn.commit()


async def exclusion_spans(consultation_id: int) -> list[tuple[int, int]]:
    """(start_byte, end_byte) for every utterance that actually played.

    This is what `app/finalize.py` mutes. Rows with no span — a
    `failed_to_play` utterance, where `speak_started` never arrived — are
    excluded here rather than filtered downstream: no window means no
    exclusion, and there is nothing to mute because nothing was heard.
    """
    async with await _conn() as conn:
        rows = await (await conn.execute(
            "SELECT start_byte, end_byte FROM system_utterance"
            " WHERE consultation_id = %s AND start_byte IS NOT NULL"
            "   AND end_byte IS NOT NULL AND end_byte > start_byte"
            " ORDER BY start_byte",
            (consultation_id,))).fetchall()
    return [(int(a), int(b)) for a, b in rows]


async def for_consultation(consultation_id: int) -> list[dict]:
    """Full rows, for the review page's grey channel (session 2's UI).

    Deliberately a separate call from anything the note path uses.
    """
    async with await _conn() as conn:
        cursor = await conn.execute(
            "SELECT utterance_id, text, ref_kind, ref_detail, cds_rationale,"
            "       started_offset_ms, ended_offset_ms, end_reason, stale"
            " FROM system_utterance WHERE consultation_id = %s"
            " ORDER BY start_byte NULLS LAST, id",
            (consultation_id,))
        columns = [c.name for c in cursor.description]
        return [dict(zip(columns, row)) for row in await cursor.fetchall()]
