"""Consultation persistence (Phase 2).

Statuses: live → processing → awaiting_review → approved
(→ failed if the finalisation pipeline dies; the audio is kept so it can
be retried — raw audio is retained until finalisation succeeds, per plan).
"""

from __future__ import annotations

import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS consultation (
    id serial PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'live',
    audio_path text,
    error text
);
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS urgent_actions jsonb;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS urgent_ack_at timestamptz;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS patient_id int;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS doctor_id int;
-- Governance (admin): voiding hides a consultation from working views but
-- keeps its content in the database; only the separate purge step deletes.
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS voided_at timestamptz;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS voided_by int;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS void_reason text;
-- Void reason class (2026-07-25). 'test_data' voids stay freely
-- reversible; 'clinical_safety' voids CANNOT be unvoided over HTTP at
-- all — reversal is break-glass only (scripts/manage_consultations.py).
-- Added because a written "don't unvoid real rows" lesson failed twice:
-- #70 was unvoided 2026-07-22 and again 2026-07-24, six minutes after
-- the commit documenting the first recurrence. See HANDOVER docket 5.
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS void_reason_class text;
-- Backfill: anything already voided was test data (the pre-2026-07-25
-- voids were all governance/test rows), EXCEPT #70, the Sinhala
-- hallucination that is the transcript-quality gate's regression
-- fixture. Guarded on voided_at so an unvoided row never carries a
-- stale class.
UPDATE consultation SET void_reason_class = 'test_data'
 WHERE voided_at IS NOT NULL AND void_reason_class IS NULL AND id <> 70;
UPDATE consultation SET void_reason_class = 'clinical_safety'
 WHERE voided_at IS NOT NULL AND id = 70;
-- Audio retention (plan §8): research flag exempts a recording from the
-- retention sweep; audio_deleted_at records that the sweep removed it
-- (audio only — transcripts and notes are never deleted by retention).
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS keep_for_research boolean NOT NULL DEFAULT false;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS audio_deleted_at timestamptz;
-- Connection resilience: set when a live session's WebSocket dropped and
-- never reconnected — the audio tail may be missing; review shows a
-- warning banner so the doctor knows what they are signing.
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS connection_lost boolean NOT NULL DEFAULT false;
-- Transcript-quality gate (2026-07-25, TRANSCRIPT_QUALITY_GATE_SPEC.md §7).
-- quality_signals holds all four measured signals on EVERY consultation,
-- whether or not anything fired — that is how calibration data for the
-- S1/S3 redesign accumulates for free. quality_outcome is 'pass' or
-- 'refused' ('flagged' is reserved for the follow-up flag tier).
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS quality_signals jsonb;
ALTER TABLE consultation ADD COLUMN IF NOT EXISTS quality_outcome text;
CREATE TABLE IF NOT EXISTS transcript_turn (
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    idx int NOT NULL,
    role text NOT NULL,          -- 'Doctor' | 'Patient'
    start_s real NOT NULL,
    end_s real NOT NULL,
    text text NOT NULL,
    confidence real NOT NULL,    -- mean ASR word confidence, 0..1
    PRIMARY KEY (consultation_id, idx)
);
CREATE TABLE IF NOT EXISTS note (
    id serial PRIMARY KEY,
    consultation_id int NOT NULL REFERENCES consultation(id) ON DELETE CASCADE,
    version int NOT NULL,
    content jsonb NOT NULL,      -- SOAP structure with per-claim turn citations
    status text NOT NULL DEFAULT 'draft',   -- 'draft' | 'approved'
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    approved_text text           -- the doctor-edited plain text, on approval
);
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


async def create_consultation(
    patient_id: int | None = None, doctor_id: int | None = None
) -> int:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO consultation (patient_id, doctor_id)"
                " VALUES (%s, %s) RETURNING id",
                (patient_id, doctor_id),
            )
        ).fetchone()
        return row[0]


async def latest_for_patient_today(patient_id: int) -> int | None:
    """Newest of today's consultations for this patient — the Resume
    target when a queue entry's live session was stopped but the entry
    outlived it (or crashed between create and finish)."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id FROM consultation WHERE patient_id = %s"
                " AND started_at::date = CURRENT_DATE AND voided_at IS NULL"
                " ORDER BY id DESC LIMIT 1",
                (patient_id,),
            )
        ).fetchone()
    return row[0] if row else None


async def list_consultations(
    include_voided: bool = False, doctor_id: int | None = None
) -> list[dict]:
    """Worklist rows: no clinical content — safe for all logged-in roles.
    Voided consultations appear only in the admin view (include_voided).
    doctor_id applies the strict own-consultations scoping (owner decision
    2026-07-24): only that doctor's rows, plus unowned legacy/test rows
    (doctor_id IS NULL — real consultations always carry their doctor)."""
    conditions, params = [], []
    if not include_voided:
        conditions.append("c.voided_at IS NULL")
    if doctor_id is not None:
        conditions.append("(c.doctor_id = %s OR c.doctor_id IS NULL)")
        params.append(doctor_id)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT c.id, c.started_at, c.status, p.name, u.display_name,"
                " c.voided_at, c.void_reason, v.display_name,"
                " c.audio_path, c.keep_for_research, c.audio_deleted_at,"
                " c.void_reason_class"
                " FROM consultation c"
                " LEFT JOIN patient p ON p.id = c.patient_id"
                " LEFT JOIN app_user u ON u.id = c.doctor_id"
                " LEFT JOIN app_user v ON v.id = c.voided_by"
                + where
                + " ORDER BY c.id DESC",
                params,
            )
        ).fetchall()
    return [
        {"id": r[0], "started_at": str(r[1])[:16], "status": r[2],
         "patient_name": r[3] or "—", "doctor_name": r[4] or "—",
         "voided_at": str(r[5])[:16] if r[5] else None,
         "void_reason": r[6], "voided_by": r[7],
         "audio_path": r[8], "keep_for_research": r[9],
         "audio_deleted_at": str(r[10])[:16] if r[10] else None,
         "void_reason_class": r[11]}
        for r in rows
    ]


async def queued_finalisations() -> list[tuple[int, str]]:
    """Consultations enqueued for finalisation when the app last stopped
    (status 'queued', audio on disk) — re-enqueued at startup so a crash
    or restart never strands a recording."""
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT id, audio_path FROM consultation"
                " WHERE status = 'queued' AND audio_path IS NOT NULL"
                " ORDER BY id"
            )
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


async def set_connection_lost(cid: int) -> None:
    """The live stream dropped and never reconnected: the recording ends
    where the connection did, not where the consultation did."""
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET connection_lost = true WHERE id = %s", (cid,)
        )


async def set_audio_path(cid: int, path: str) -> None:
    """Post-approval FLAC compression updates the stored location."""
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET audio_path = %s WHERE id = %s", (path, cid)
        )


async def set_keep_for_research(cid: int, value: bool) -> bool:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE consultation SET keep_for_research = %s WHERE id = %s"
                " RETURNING id", (value, cid),
            )
        ).fetchone()
    return row is not None


async def set_status(cid: int, status: str, *, audio_path: str | None = None,
                     error: str | None = None) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET status = %s,"
            " audio_path = COALESCE(%s, audio_path), error = %s WHERE id = %s",
            (status, audio_path, error, cid),
        )


async def save_quality(cid: int, signals: dict, outcome: str) -> None:
    """Store the transcript-quality signals and verdict. Called on EVERY
    finalisation, refused or not — the stored signals are the calibration
    data for the S1/S3 redesign (spec §7)."""
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET quality_signals = %s, quality_outcome = %s"
            " WHERE id = %s",
            (json.dumps(signals), outcome, cid),
        )


async def get_consultation(cid: int) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT c.id, c.started_at, c.status, c.audio_path, c.error,"
                " c.urgent_actions, c.urgent_ack_at, c.patient_id, p.name,"
                " c.voided_at, c.void_reason, c.doctor_id, c.connection_lost,"
                " c.quality_signals, c.quality_outcome"
                " FROM consultation c LEFT JOIN patient p ON p.id = c.patient_id"
                " WHERE c.id = %s", (cid,),
            )
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "started_at": str(row[1]),
        "status": row[2],
        "audio_path": row[3],
        "error": row[4],
        "urgent_actions": row[5] or [],
        "urgent_ack_at": str(row[6]) if row[6] else None,
        "patient_id": row[7],
        "patient_name": row[8],
        "voided_at": str(row[9]) if row[9] else None,
        "void_reason": row[10],
        "doctor_id": row[11],
        "connection_lost": row[12],
        "quality_signals": row[13],
        "quality_outcome": row[14],
    }


async def save_urgent_actions(cid: int, actions: list[dict]) -> None:
    """Persist the live session's final unresolved urgent actions."""
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE consultation SET urgent_actions = %s WHERE id = %s",
            (json.dumps(actions), cid),
        )


async def acknowledge_urgent(cid: int) -> str:
    """Record the doctor's acknowledgement of the urgency banner."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE consultation SET urgent_ack_at = now()"
                " WHERE id = %s AND urgent_ack_at IS NULL"
                " RETURNING urgent_ack_at", (cid,),
            )
        ).fetchone()
        if row is None:  # already acknowledged: keep the original timestamp
            row = await (
                await conn.execute(
                    "SELECT urgent_ack_at FROM consultation WHERE id = %s", (cid,)
                )
            ).fetchone()
    return str(row[0])


async def save_turns(cid: int, turns: list[dict]) -> None:
    async with await _conn() as conn:
        await conn.execute("DELETE FROM transcript_turn WHERE consultation_id = %s", (cid,))
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO transcript_turn"
                " (consultation_id, idx, role, start_s, end_s, text, confidence)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    (cid, i, t["role"], t["start"], t["end"], t["text"], t["confidence"])
                    for i, t in enumerate(turns)
                ],
            )


async def get_turns(cid: int) -> list[dict]:
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT idx, role, start_s, end_s, text, confidence"
                " FROM transcript_turn WHERE consultation_id = %s ORDER BY idx", (cid,),
            )
        ).fetchall()
    return [
        {"idx": r[0], "role": r[1], "start": r[2], "end": r[3], "text": r[4],
         "confidence": r[5]}
        for r in rows
    ]


async def update_turn_text(cid: int, idx: int, text: str) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE transcript_turn SET text = %s, confidence = 1.0"
            " WHERE consultation_id = %s AND idx = %s",
            (text, cid, idx),  # a doctor-corrected turn is fully trusted
        )


async def swap_roles(cid: int) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE transcript_turn SET role ="
            " CASE role WHEN 'Doctor' THEN 'Patient' ELSE 'Doctor' END"
            " WHERE consultation_id = %s", (cid,),
        )


async def save_note(cid: int, content: dict) -> int:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO note (consultation_id, version, content)"
                " VALUES (%s, COALESCE((SELECT max(version) FROM note"
                "   WHERE consultation_id = %s), 0) + 1, %s) RETURNING version",
                (cid, cid, json.dumps(content)),
            )
        ).fetchone()
        return row[0]


async def latest_note(cid: int) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT version, content, status, approved_text FROM note"
                " WHERE consultation_id = %s ORDER BY version DESC LIMIT 1", (cid,),
            )
        ).fetchone()
    if row is None:
        return None
    return {"version": row[0], "content": row[1], "status": row[2],
            "approved_text": row[3]}


# A void is one of two kinds, and the kind decides whether it can ever be
# reversed over HTTP. test_data is the common case and stays freely
# reversible; clinical_safety is irreversible except by break-glass.
VOID_CLASS_TEST_DATA = "test_data"
VOID_CLASS_CLINICAL_SAFETY = "clinical_safety"
VOID_CLASSES = (VOID_CLASS_TEST_DATA, VOID_CLASS_CLINICAL_SAFETY)


async def void_consultation(cid: int, admin_id: int, reason: str,
                            reason_class: str = VOID_CLASS_TEST_DATA) -> dict | None:
    """Admin error-correction: mark voided (any status, including approved
    — that is the point). Content stays in the database; working views
    filter on voided_at. Returns the prior status, or None when the
    consultation doesn't exist or is already voided."""
    if reason_class not in VOID_CLASSES:
        raise ValueError(f"unknown void reason class: {reason_class!r}")
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE consultation SET voided_at = now(), voided_by = %s,"
                " void_reason = %s, void_reason_class = %s"
                " WHERE id = %s AND voided_at IS NULL"
                " RETURNING status, patient_id",
                (admin_id, reason, reason_class, cid),
            )
        ).fetchone()
    return {"from_status": row[0], "patient_id": row[1]} if row else None


async def void_state(cid: int) -> dict | None:
    """The void columns alone, for guard checks before attempting a
    reversal. None when the consultation doesn't exist."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT voided_at IS NOT NULL, void_reason, void_reason_class"
                " FROM consultation WHERE id = %s", (cid,),
            )
        ).fetchone()
    if row is None:
        return None
    return {"voided": row[0], "reason": row[1], "reason_class": row[2]}


async def unvoid_consultation(cid: int, *, allow_clinical_safety: bool = False
                              ) -> dict | None:
    """Reverse a mistaken void: clear the flags, restoring the consultation
    to working views exactly as it was (voiding only ever set these three
    columns). Returns the reverted reason for the audit trail, or None if
    the consultation doesn't exist or isn't voided.

    A `clinical_safety` void is refused unless the caller explicitly opts
    in — the HTTP layer never does, so that class is reversible only from
    the server shell (scripts/manage_consultations.py). The guard lives
    in the UPDATE's WHERE clause rather than in a prior read, so two
    concurrent callers cannot race past it.
    """
    async with await _conn() as conn:
        # Self-join to hand back the PRE-update reason (RETURNING alone
        # would give the freshly-NULLed column).
        row = await (
            await conn.execute(
                "UPDATE consultation c SET voided_at = NULL, voided_by = NULL,"
                " void_reason = NULL, void_reason_class = NULL"
                " FROM consultation old"
                " WHERE c.id = %s AND old.id = c.id AND c.voided_at IS NOT NULL"
                + ("" if allow_clinical_safety else
                   " AND COALESCE(c.void_reason_class, %s) <> %s")
                + " RETURNING c.status, old.void_reason, old.void_reason_class",
                (cid,) if allow_clinical_safety
                else (cid, VOID_CLASS_TEST_DATA, VOID_CLASS_CLINICAL_SAFETY),
            )
        ).fetchone()
    if row is None:
        return None
    return {"status": row[0], "reverted_reason": row[1],
            "reverted_class": row[2]}


async def purge_voided(only_ids: list[int] | None = None) -> dict:
    """The second, explicit deletion step: hard-delete already-voided
    consultations (turns and notes cascade) and any synthetic patients
    left with no remaining consultations. Never touches un-voided rows.
    only_ids narrows the purge (tests use it to stay surgical); the admin
    endpoint purges all voided. Returns counts + audio paths for the
    caller to unlink after commit."""
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT id, audio_path, patient_id FROM consultation"
                " WHERE voided_at IS NOT NULL"
                + (" AND id = ANY(%s)" if only_ids is not None else ""),
                ((only_ids,) if only_ids is not None else ()),
            )
        ).fetchall()
        cids = [r[0] for r in rows]
        patient_ids = sorted({r[2] for r in rows if r[2] is not None})
        await conn.execute("DELETE FROM consultation WHERE id = ANY(%s)", (cids,))
        purged_patients = await (
            await conn.execute(
                "DELETE FROM patient p WHERE p.id = ANY(%s) AND NOT EXISTS"
                " (SELECT 1 FROM consultation c WHERE c.patient_id = p.id)"
                " RETURNING p.id",
                (patient_ids,),
            )
        ).fetchall()
    return {
        "consultations": len(cids),
        "consultation_ids": cids,
        "patients": len(purged_patients),
        "audio_paths": [r[1] for r in rows if r[1]],
    }


async def approve_note(cid: int, approved_text: str) -> None:
    async with await _conn() as conn:
        await conn.execute(
            "UPDATE note SET status = 'approved', approved_at = now(),"
            " approved_text = %s WHERE consultation_id = %s AND version ="
            " (SELECT max(version) FROM note WHERE consultation_id = %s)",
            (approved_text, cid, cid),
        )
        await conn.execute(
            "UPDATE consultation SET status = 'approved' WHERE id = %s", (cid,)
        )
