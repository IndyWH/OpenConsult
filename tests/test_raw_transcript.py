"""The raw-transcript view (RAW_TRANSCRIPT_VIEW_SPEC.md).

The two load-bearing rules, asserted rather than assumed:

- **Read from storage, never rebuilt.** WhisperX is not deterministic;
  a rebuilt view would show a consultation that never existed. The
  endpoint works with no transcriber installed at all, and a structural
  test pins that the storage module has no path to one.
- **Opening the view is audited** — the point is to measure whether
  checking happens, not to be able to say checking was possible.

Plus the owner's 2026-07-30 persistence decision: segments are stored
BEFORE the silence invariant, with the invariant's removals FLAGGED in
the stored set — the invariant has eaten transcript before (445), and
the view exists to make such layers visible.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import audit, auth, consultations, raw_segments
from app import finalize
from app import main as appmain


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

NODE = shutil.which("node")


# --- building the stored set (pure) -----------------------------------------

def seg(start, end, text, speaker="SPEAKER_00", score=0.8):
    return {"start": start, "end": end, "text": text,
            "words": [{"word": w, "speaker": speaker, "score": score}
                      for w in text.split()]}


def test_records_mirror_the_merges_own_derivations():
    """Cluster and confidence are derived exactly as merge_into_turns
    derives them, so the raw view and the diarised transcript describe
    the same measurements — only the merge and the role rule differ."""
    records = finalize.raw_segment_records(
        [seg(0.0, 2.0, "hello there", score=0.9),
         seg(2.5, 4.0, "yes doctor", speaker="SPEAKER_01", score=0.6)], [])
    assert records == [
        {"idx": 0, "cluster": "SPEAKER_00", "start": 0.0, "end": 2.0,
         "text": "hello there", "confidence": 0.9, "dropped": False},
        {"idx": 1, "cluster": "SPEAKER_01", "start": 2.5, "end": 4.0,
         "text": "yes doctor", "confidence": 0.6, "dropped": False},
    ]


def test_invariant_dropped_segments_are_flagged_not_absent():
    """The owner's 2026-07-30 decision, and the identity test is the
    honest one: the invariant returns the SAME dicts it dropped."""
    kept = seg(0.0, 2.0, "real speech")
    eaten = seg(3.0, 4.0, "Thank you.")
    records = finalize.raw_segment_records([kept, eaten], [eaten])
    assert [r["dropped"] for r in records] == [False, True]
    assert records[1]["text"] == "Thank you."


def test_a_segment_with_the_same_text_as_a_dropped_one_is_not_flagged():
    """Identity, not equality: two segments can say the same words, and
    only the one the invariant actually removed is flagged."""
    first = seg(0.0, 1.0, "Thank you.")
    second = seg(5.0, 6.0, "Thank you.")
    records = finalize.raw_segment_records([first, second], [second])
    assert [r["dropped"] for r in records] == [False, True]


def test_empty_text_segments_are_skipped_like_the_merge_skips_them():
    records = finalize.raw_segment_records(
        [seg(0.0, 1.0, "words"), {"start": 1.0, "end": 2.0, "text": "  "}], [])
    assert len(records) == 1 and records[0]["idx"] == 0


# --- storage round-trip -----------------------------------------------------

def _make_user(role: str = "doctor") -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _consultation_for(doctor: dict) -> int:
    consultations.ensure_schema()
    raw_segments.ensure_schema()
    audit.ensure_schema()
    return asyncio.run(consultations.create_consultation(None, doctor["id"]))


ROWS = [
    {"idx": 0, "cluster": "SPEAKER_00", "start": 0.0, "end": 2.0,
     "text": "hello there", "confidence": 0.9, "dropped": False},
    {"idx": 1, "cluster": "SPEAKER_01", "start": 2.5, "end": 4.0,
     "text": "I have chest pain", "confidence": 0.7, "dropped": False},
    {"idx": 2, "cluster": None, "start": 5.0, "end": 6.0,
     "text": "Thank you.", "confidence": None, "dropped": True},
]


@needs_db
def test_round_trip_keeps_order_flags_and_emits_no_idx():
    """The payload carries NO idx — a raw segment must never look like a
    citation target (spec §4); order is the array order."""
    doctor = _make_user()
    cid = _consultation_for(doctor)
    asyncio.run(raw_segments.save(cid, ROWS))
    stored = asyncio.run(raw_segments.for_consultation(cid))
    assert [s["text"] for s in stored] == [r["text"] for r in ROWS]
    assert [s["dropped"] for s in stored] == [False, False, True]
    for s in stored:
        assert "idx" not in s and "id" not in s
    assert stored[1]["cluster"] == "SPEAKER_01"
    assert stored[2]["confidence"] is None


@needs_db
def test_a_second_finalisation_cannot_overwrite_the_first_record():
    """Written once: the FIRST write is the record of what that
    finalisation heard. A re-run must not silently replace it."""
    doctor = _make_user()
    cid = _consultation_for(doctor)
    asyncio.run(raw_segments.save(cid, ROWS))
    rewritten = [dict(ROWS[0], text="something else entirely")]
    asyncio.run(raw_segments.save(cid, rewritten))
    stored = asyncio.run(raw_segments.for_consultation(cid))
    assert stored[0]["text"] == "hello there"


# --- the endpoint -----------------------------------------------------------

@needs_db
def test_the_view_is_read_from_storage_with_no_transcriber_anywhere():
    """Spec §8 test 3, behaviourally: app.state carries NO transcriber
    when this endpoint serves — reading storage is all it can do."""
    state = appmain.app.state
    missing = object()
    had = getattr(state, "transcriber", missing)
    if had is not missing:
        delattr(state, "transcriber")
    try:
        doctor = _make_user()
        cid = _consultation_for(doctor)
        asyncio.run(raw_segments.save(cid, ROWS))
        response = _client_for(doctor).get(f"/api/consultations/{cid}/raw-transcript")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert [s["text"] for s in body["segments"]] == \
            [r["text"] for r in ROWS]
    finally:
        if had is not missing:
            state.transcriber = had


@needs_db
def test_history_is_handled_honestly_never_rebuilt():
    """A consultation finalised before the feature has no stored segments:
    the payload SAYS so, and nothing re-runs the pipeline."""
    doctor = _make_user()
    cid = _consultation_for(doctor)
    response = _client_for(doctor).get(f"/api/consultations/{cid}/raw-transcript")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False and body["segments"] == []
    assert "never rebuilt" in body["reason"]


@needs_db
def test_opening_the_view_is_audited_once_per_open():
    """Spec §8 test 5 — including an open that finds nothing stored: an
    attempt to check is the behaviour being measured."""
    doctor = _make_user()
    cid = _consultation_for(doctor)
    client = _client_for(doctor)
    client.get(f"/api/consultations/{cid}/raw-transcript")
    client.get(f"/api/consultations/{cid}/raw-transcript")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT user_id, detail FROM audit_event"
            " WHERE action = 'transcript.raw_viewed' AND subject_id = %s"
            " ORDER BY id", (cid,)).fetchall()
    assert len(rows) == 2, "one audit row per open, every open"
    assert rows[0][0] == doctor["id"]
    assert rows[0][1]["available"] is False


@needs_db
def test_rbac_receptionist_403_foreign_doctor_403_voided_410():
    doctor, intruder = _make_user(), _make_user()
    receptionist = _make_user("receptionist")
    cid = _consultation_for(doctor)

    assert _client_for(receptionist).get(
        f"/api/consultations/{cid}/raw-transcript").status_code == 403
    assert _client_for(intruder).get(
        f"/api/consultations/{cid}/raw-transcript").status_code == 403

    asyncio.run(consultations.void_consultation(cid, doctor["id"], "test data"))
    assert _client_for(doctor).get(
        f"/api/consultations/{cid}/raw-transcript").status_code == 410


# --- display-only, structurally ---------------------------------------------

REVIEW = Path("app/static/review.html").read_text()


def test_no_citation_can_resolve_to_a_raw_segment():
    """Spec §8 test 1. Citations highlight `turn-N` ids; the raw renderer
    never mints one, and the payload rows carry no idx to mint one from
    (asserted in the round-trip test above)."""
    raw_block = REVIEW[REVIEW.index("function rawNode"):
                       REVIEW.index("function renderRawTranscript")]
    assert "turn-" not in raw_block
    assert "'n'" not in raw_block, "no turn-number column on a raw segment"


def test_the_raw_view_exposes_no_edit_path():
    """Spec §8 test 2: no contentEditable, no PATCH, no role button
    anywhere in the raw-view code."""
    raw_ui = REVIEW[REVIEW.index("function groupRawSegments"):
                    REVIEW.index("async function toggleRawView")]
    assert "contentEditable" not in raw_ui
    assert "PATCH" not in raw_ui
    assert "rolebtn" not in raw_ui


def test_the_finalisation_pipeline_persists_beside_the_turns():
    """The write sits with save_turns — BEFORE the quality gate, so a
    refused consultation's raw layer is stored too (it is exactly the
    kind that needs seeing)."""
    source = Path("app/finalize.py").read_text()
    save_turns_at = source.index("await consultations.save_turns(cid, turns)")
    raw_save_at = source.index("raw_segments_store.save")
    gate_at = source.index("transcript_quality.compute_signals")
    assert save_turns_at < raw_save_at < gate_at


def test_the_storage_module_has_no_path_to_a_transcriber():
    source = Path("app/raw_segments.py").read_text()
    for needle in ("whisper", "transcribe(", "import torch", "faster_whisper"):
        assert needle not in source, needle


# --- the join, made visible (Node) ------------------------------------------

def _extract_group_fn() -> str:
    start = REVIEW.index("function groupRawSegments")
    return REVIEW[start:REVIEW.index("\n}", start) + 2]


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_merge_join_is_visible_as_one_group():
    """Spec §8 test 4, executed: several raw segments whose midpoints fall
    inside one merged turn come back as ONE group — the 445/66 shape at a
    glance — while a dropped segment stands alone, attached to no turn."""
    harness = _extract_group_fn() + """
const turns = [
  {idx: 0, role: 'Doctor',  start_s: 0,  end_s: 4},
  {idx: 1, role: 'Patient', start_s: 4.5, end_s: 210},   // the 445 shape
];
const segments = [
  {start_s: 0,   end_s: 2,   text: 'a', dropped: false},
  {start_s: 5,   end_s: 60,  text: 'b', dropped: false},
  {start_s: 61,  end_s: 130, text: 'c', dropped: false},
  {start_s: 131, end_s: 209, text: 'd', dropped: false},
  {start_s: 300, end_s: 301, text: 'eaten', dropped: true},
];
console.log(JSON.stringify(groupRawSegments(segments, turns)));
"""
    result = subprocess.run([NODE, "-e", harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    groups = json.loads(result.stdout)
    assert len(groups) == 3
    assert groups[0]["turnIdx"] == 0 and len(groups[0]["segments"]) == 1
    assert groups[1]["turnIdx"] == 1 and len(groups[1]["segments"]) == 3, (
        "the merged turn must show its several source segments as one group")
    assert groups[1]["turnLabel"] == "1 (Patient)"
    assert groups[2]["turnIdx"] is None, "a dropped segment belongs to no turn"
