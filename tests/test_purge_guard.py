"""Purge must never destroy a clinical-safety void.

The live hazard this closes: consultation #70 is the transcript-quality
gate's regression fixture and the object of study in
`evals/2026-07-25_sinhala_confound_prereg.md`. `keep_for_research`
protects audio from the RETENTION SWEEP only — not from purge, which
hard-deletes the consultation, its turns and notes, and its WAV. With
#70 voided, one click on "Purge voided test data" would have destroyed
both the fixture and the audio.

Test-safety convention, unchanged and load-bearing: purge in tests is
ALWAYS scoped with `only_ids=`. An unscoped purge in a test would delete
voided data the owner is still holding.
"""

import asyncio
import os
import secrets
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from app import consultations

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _make_voided(reason_class: str, tmp_path: Path) -> tuple[int, Path]:
    """A voided consultation with turns, a note and a real audio file."""
    consultations.ensure_schema()
    wav = tmp_path / f"consultation_{secrets.token_hex(4)}.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")  # stand-in; purge only unlinks it

    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(cid, [
            {"role": "Doctor", "start": 0.0, "end": 2.0,
             "text": "Hello.", "confidence": 0.9}])
        await consultations.save_note(cid, {
            "subjective": [{"text": "x", "turns": [0], "uncited": False,
                            "flagged": False}],
            "objective": [], "assessment": [], "plan": []})
        await consultations.set_status(cid, "awaiting_review", audio_path=str(wav))
        await consultations.void_consultation(cid, None, f"{reason_class} fixture",
                                              reason_class)
        return cid

    return asyncio.run(build()), wav


def _exists(cid: int) -> bool:
    return asyncio.run(consultations.get_consultation(cid)) is not None


# ------------------------------------------------------------ the guard

def test_clinical_safety_void_survives_purge_with_its_audio(tmp_path):
    """The #70 case. It must still be there afterwards, audio included."""
    cid, wav = _make_voided(consultations.VOID_CLASS_CLINICAL_SAFETY, tmp_path)

    result = asyncio.run(consultations.purge_voided(only_ids=[cid]))

    assert result["consultations"] == 0
    assert result["protected"] == 1
    assert result["protected_ids"] == [cid]
    assert result["audio_paths"] == []          # never handed to the unlinker
    assert _exists(cid), "clinical-safety void was purged"
    assert wav.exists(), "clinical-safety audio was deleted"
    # Turns and notes intact too — the fixture is only useful whole.
    assert asyncio.run(consultations.get_turns(cid))
    assert asyncio.run(consultations.latest_note(cid)) is not None


def test_test_data_void_is_still_purged(tmp_path):
    """The guard must not break the feature it guards."""
    cid, wav = _make_voided(consultations.VOID_CLASS_TEST_DATA, tmp_path)

    result = asyncio.run(consultations.purge_voided(only_ids=[cid]))

    assert result["consultations"] == 1
    assert result["consultation_ids"] == [cid]
    assert result["protected"] == 0
    assert str(wav) in result["audio_paths"]
    assert not _exists(cid)


def test_mixed_purge_reports_both_counts(tmp_path):
    """Skipped rows are reported, never silently omitted."""
    safe_cid, safe_wav = _make_voided(consultations.VOID_CLASS_CLINICAL_SAFETY, tmp_path)
    junk_cid, _ = _make_voided(consultations.VOID_CLASS_TEST_DATA, tmp_path)

    result = asyncio.run(consultations.purge_voided(only_ids=[safe_cid, junk_cid]))

    assert result["consultations"] == 1 and result["consultation_ids"] == [junk_cid]
    assert result["protected"] == 1 and result["protected_ids"] == [safe_cid]
    assert _exists(safe_cid) and safe_wav.exists()
    assert not _exists(junk_cid)


def test_an_unclassified_legacy_void_is_still_purgeable(tmp_path):
    """A NULL class means a pre-2026-07-25 void, which the migration
    treats as test data. It must not become un-purgeable by accident."""
    cid, _ = _make_voided(consultations.VOID_CLASS_TEST_DATA, tmp_path)

    async def blank_the_class() -> None:
        async with await consultations._conn() as conn:
            await conn.execute(
                "UPDATE consultation SET void_reason_class = NULL WHERE id = %s",
                (cid,))

    asyncio.run(blank_the_class())
    result = asyncio.run(consultations.purge_voided(only_ids=[cid]))
    assert result["consultations"] == 1
    assert not _exists(cid)


# ---------------------------------------------------------------- preview

def test_purge_preview_counts_both_classes(tmp_path):
    safe_cid, _ = _make_voided(consultations.VOID_CLASS_CLINICAL_SAFETY, tmp_path)
    junk_cid, _ = _make_voided(consultations.VOID_CLASS_TEST_DATA, tmp_path)

    preview = asyncio.run(consultations.purge_preview(only_ids=[safe_cid, junk_cid]))
    assert preview == {"purgeable": 1, "protected": 1}

    asyncio.run(consultations.purge_voided(only_ids=[junk_cid]))


def test_ui_confirmation_states_both_numbers():
    page = (Path(__file__).parent.parent / "app" / "static" / "worklist.html").read_text()
    assert "purge-preview" in page
    assert "PROTECTED and will NOT" in page
    # The count must appear in the confirm text, not just the alert after.
    assert "${purgeable} voided consultation" in page


# ------------------------------------------------- test-safety convention

def test_purge_in_this_file_is_always_scoped():
    """Guard the convention itself: an unscoped purge_voided() in a test
    would delete real voided data."""
    source = Path(__file__).read_text()
    for line in source.splitlines():
        if "purge_voided(" in line and "def " not in line and "convention" not in line:
            assert "only_ids" in line, f"unscoped purge in a test: {line.strip()}"
