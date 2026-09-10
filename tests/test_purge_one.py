"""purge-one: the named, break-glass deletion of ONE voided consultation of
ANY class (scripts/manage_consultations.py, 2026-09-10).

Why it exists: consultation 469 was voided as clinical_safety on 14 Aug
and the web purge skips that class by design (tests/test_purge_guard.py
pins the guard). The project undertook to delete that one recording with
everything derived from it, so a shell path with a typed confirmation
was added. These tests are evidence that the path deletes what it says
and refuses what it should:

- refuses an un-voided consultation, and deletes nothing;
- purges a clinical_safety void: the row, its cascading rows, the
  orphaned patient, and the recording file;
- leaves the original `consultation.voided` audit row intact;
- writes one `data.purged` audit row naming the id, class, reason,
  operator and the file paths removed.

Test-safety convention: every purge here names ONE id this test created
against the disposable test database. Never a real row.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import secrets
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from app import audit, consultations, raw_segments

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

_SCRIPT = Path(__file__).parent.parent / "scripts" / "manage_consultations.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("manage_consultations", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manage = _load_script()


def _query(sql: str, params=()) -> list[tuple]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchall()


def _make(tmp_path: Path, *, void_class: str | None) -> dict:
    """A consultation with a patient of its own, turns, raw segments, a
    note, a real file in a scratch recordings directory, and — when
    void_class is given — a void plus its audit row, exactly as the app
    writes them."""
    consultations.ensure_schema()
    recordings = tmp_path / "recordings"
    recordings.mkdir()

    async def build() -> dict:
        patient_id = _query(
            "INSERT INTO patient (name) VALUES (%s) RETURNING id",
            (f"purge-one fixture {secrets.token_hex(3)}",))[0][0]
        cid = await consultations.create_consultation(patient_id=patient_id)
        wav = recordings / f"consultation_{cid}.wav"
        wav.write_bytes(b"RIFF....WAVEfmt ")
        await consultations.save_turns(cid, [
            {"role": "Doctor", "start": 0.0, "end": 2.0,
             "text": "Hello.", "confidence": 0.9},
            {"role": "Patient", "start": 2.0, "end": 4.0,
             "text": "Hi.", "confidence": 0.9}])
        await raw_segments.save(cid, [
            {"idx": 0, "start": 0.0, "end": 2.0, "text": "Hello."},
            {"idx": 1, "start": 2.0, "end": 4.0, "text": "Hi."},
            {"idx": 2, "start": 4.0, "end": 5.0, "text": "Yes."}])
        await consultations.save_note(cid, {
            "subjective": [{"text": "x", "turns": [0], "uncited": False,
                            "flagged": False}],
            "objective": [], "assessment": [], "plan": []})
        await consultations.set_status(cid, "unreliable_transcript",
                                       audio_path=str(wav))
        void_audit_id = None
        if void_class:
            await consultations.void_consultation(
                cid, None, "Not meeting project criteria", void_class)
            await audit.log(None, "consultation.voided", "consultation", cid,
                            {"reason": "Not meeting project criteria",
                             "reason_class": void_class})
            void_audit_id = _query(
                "SELECT max(id) FROM audit_event WHERE action ="
                " 'consultation.voided' AND subject_id = %s", (cid,))[0][0]
        return {"cid": cid, "patient_id": patient_id, "wav": wav,
                "recordings": recordings, "void_audit_id": void_audit_id}

    return asyncio.run(build())


def _run(fx: dict, typed: str | None = None) -> int:
    typed = str(fx["cid"]) if typed is None else typed
    return asyncio.run(manage.cmd_purge_one(
        fx["cid"], confirm=lambda prompt: typed, operator="test-operator",
        recordings_dir=fx["recordings"]))


def _rows(cid: int) -> dict[str, int]:
    return {t: _query(f"SELECT count(*) FROM {t} WHERE consultation_id = %s",
                      (cid,))[0][0]
            for t in ("transcript_turn", "raw_segment", "note")}


# ------------------------------------------------------------- refusals

def test_refuses_an_unvoided_consultation_and_deletes_nothing(tmp_path):
    fx = _make(tmp_path, void_class=None)

    assert _run(fx) == 1

    assert asyncio.run(consultations.get_consultation(fx["cid"])) is not None
    assert _rows(fx["cid"]) == {"transcript_turn": 2, "raw_segment": 3, "note": 1}
    assert fx["wav"].exists()
    assert _query("SELECT count(*) FROM audit_event WHERE action = 'data.purged'"
                  " AND subject_id = %s", (fx["cid"],))[0][0] == 0
    # The library guard holds on its own too: not voided, not deletable.
    assert asyncio.run(consultations.purge_one(fx["cid"])) is None
    assert asyncio.run(consultations.get_consultation(fx["cid"])) is not None


def test_refuses_when_the_typed_confirmation_does_not_match(tmp_path):
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_CLINICAL_SAFETY)

    assert _run(fx, typed=str(fx["cid"] + 1)) == 1

    assert asyncio.run(consultations.get_consultation(fx["cid"])) is not None
    assert fx["wav"].exists()


def test_a_missing_consultation_is_reported_not_purged():
    missing = _query("SELECT COALESCE(max(id), 0) + 100000 FROM consultation")[0][0]
    fx = {"cid": missing, "recordings": Path("/nonexistent")}
    assert _run(fx) == 1


# ---------------------------------------------------- the 469 case, whole

def test_purges_a_clinical_safety_void_with_everything_derived_from_it(tmp_path):
    """The class the web purge protects by design: this path deletes it,
    and every row and file the consultation owned goes with it."""
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_CLINICAL_SAFETY)
    cid = fx["cid"]
    # Sanity: the fixture really was the protected class and had content.
    assert asyncio.run(consultations.purge_voided(only_ids=[cid]))["protected"] == 1
    assert _rows(cid) == {"transcript_turn": 2, "raw_segment": 3, "note": 1}

    assert _run(fx) == 0

    assert asyncio.run(consultations.get_consultation(cid)) is None
    assert _rows(cid) == {"transcript_turn": 0, "raw_segment": 0, "note": 0}
    assert _query("SELECT count(*) FROM patient WHERE id = %s",
                  (fx["patient_id"],))[0][0] == 0, "orphaned patient row survived"
    assert not fx["wav"].exists(), "the recording file survived"


def test_purges_a_test_data_void_too(tmp_path):
    """'Any class' means any class."""
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_TEST_DATA)
    assert _run(fx) == 0
    assert asyncio.run(consultations.get_consultation(fx["cid"])) is None
    assert not fx["wav"].exists()


def test_the_void_audit_row_is_left_intact(tmp_path):
    """Audit 2620 for 469 must outlive the purge: the record that the
    consultation was voided, and why, is the history the purge completes."""
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_CLINICAL_SAFETY)

    assert _run(fx) == 0

    rows = _query("SELECT action, subject_id, detail FROM audit_event WHERE id = %s",
                  (fx["void_audit_id"],))
    assert rows and rows[0][0] == "consultation.voided"
    assert rows[0][1] == fx["cid"]
    assert rows[0][2]["reason_class"] == consultations.VOID_CLASS_CLINICAL_SAFETY


def test_writes_one_data_purged_audit_row_naming_everything(tmp_path):
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_CLINICAL_SAFETY)

    assert _run(fx) == 0

    rows = _query("SELECT user_id, detail FROM audit_event WHERE action ="
                  " 'data.purged' AND subject_type = 'consultation'"
                  " AND subject_id = %s", (fx["cid"],))
    assert len(rows) == 1
    user_id, detail = rows[0]
    assert user_id is None  # a shell operator, not an app account
    assert detail["consultation_id"] == fx["cid"]
    assert detail["void_reason_class"] == consultations.VOID_CLASS_CLINICAL_SAFETY
    assert detail["void_reason"] == "Not meeting project criteria"
    assert detail["operator"] == "test-operator"
    assert detail["files_removed"] == [str(fx["wav"])]
    assert detail["files_failed"] == []
    assert detail["patient_id"] == fx["patient_id"]
    assert detail["patient_purged"] is True
    assert detail["cascaded_rows"]["transcript_turn"] == 2
    assert detail["cascaded_rows"]["raw_segment"] == 3
    assert detail["cascaded_rows"]["note"] == 1
    assert detail["via"] == "break-glass CLI purge-one"


def test_a_shared_patient_is_kept(tmp_path):
    """The patient row goes only when no other consultation references it."""
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_TEST_DATA)
    other = asyncio.run(consultations.create_consultation(patient_id=fx["patient_id"]))

    assert _run(fx) == 0

    assert _query("SELECT count(*) FROM patient WHERE id = %s",
                  (fx["patient_id"],))[0][0] == 1
    assert asyncio.run(consultations.get_consultation(other)) is not None
    detail = _query("SELECT detail FROM audit_event WHERE action = 'data.purged'"
                    " AND subject_id = %s", (fx["cid"],))[0][0]
    assert detail["patient_purged"] is False


def test_files_named_for_the_id_go_even_if_the_row_lost_the_path(tmp_path):
    """A flac beside the wav (retention compresses on approval), or a file
    the row no longer names — anything under the recordings directory
    for this id is removed and listed."""
    fx = _make(tmp_path, void_class=consultations.VOID_CLASS_TEST_DATA)
    flac = fx["recordings"] / f"consultation_{fx['cid']}.flac"
    flac.write_bytes(b"fLaC")
    stranger = fx["recordings"] / f"consultation_{fx['cid'] + 1}.wav"
    stranger.write_bytes(b"RIFF")

    assert _run(fx) == 0

    assert not fx["wav"].exists() and not flac.exists()
    assert stranger.exists(), "a neighbouring id's file was touched"
    detail = _query("SELECT detail FROM audit_event WHERE action = 'data.purged'"
                    " AND subject_id = %s", (fx["cid"],))[0][0]
    assert sorted(detail["files_removed"]) == sorted([str(fx["wav"]), str(flac)])


def test_the_cli_has_the_command_and_it_is_break_glass():
    source = _SCRIPT.read_text()
    assert '"purge-one"' in source
    assert "Type the consultation id" in source
    assert json.loads('"data.purged"') in source
