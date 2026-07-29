"""The barge-in calibration report's logic, on synthetic rows.

The verdict functions are pure and run everywhere (the
test_calibrate_transcript_quality convention); the one end-to-end smoke
test needs Postgres and self-skips without it. Nothing here asserts what
the owner's room will measure — the report reports, the owner decides.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg
import pytest

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "calibrate_barge_in.py"


def _load():
    spec = importlib.util.spec_from_file_location("calibrate_bi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calib = _load()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


def reading(peak=0.01, floor=0.004, answer="yes", ratio=None,
            discrepancy=None, device="Speakers") -> dict:
    return {"at": "2026-07-29", "username": "doctor", "peak_rms": peak,
            "noise_floor_rms": floor, "answer": answer,
            "ratio": ratio if ratio is not None else peak / floor,
            "discrepancy": discrepancy, "device_label": device}


# --- the D5 target is the spec's, verbatim ----------------------------------

def test_the_d5_target_matches_the_spec():
    assert calib.D5_FALSE_STOP_MAX == 0.01
    assert calib.D5_CATCH_MIN == 0.90
    assert calib.D5_CATCH_WITHIN_MS == 300


# --- grouping and filtering -------------------------------------------------

def test_readings_group_by_device_and_unlabelled_rows_are_quarantined():
    """A level without its path is not a measurement: rows with no device
    label land in their own named group and never mix with real ones."""
    groups = calib.group_by_device([
        reading(device="Speakers"), reading(device="Monitor"),
        reading(device=None)])
    assert set(groups) == {"Speakers", "Monitor", calib.NO_DEVICE}
    assert "not comparable" in calib.NO_DEVICE


def test_headphone_and_silent_readings_carry_no_loopback():
    rows = [reading(),
            reading(discrepancy="no_acoustic_path_headphones_likely"),
            reading(peak=0.0)]
    assert len(calib.acoustic_readings(rows)) == 1


# --- the two predicted sides ------------------------------------------------

def _assess(rows, **kw):
    defaults = {"margin": 2.0, "abs_floor": 0.02, "min_ms": 150}
    return calib.assess_device(rows, **{**defaults, **kw})


def test_fewer_than_five_readings_is_insufficient_data_not_a_verdict():
    verdicts = _assess([reading()] * 4)
    assert verdicts["side_a"] is None and verdicts["side_b"] is None
    assert any("5 needed" in why for why in verdicts["side_a_why"])


def test_consistent_quiet_loopback_predicts_both_sides_met():
    """Loopback ~0.01, noise floor 0.004: the threshold clears room noise
    and quiet speech clears the threshold — both sides predicted met."""
    verdicts = _assess([reading(peak=0.010), reading(peak=0.011),
                        reading(peak=0.009), reading(peak=0.012),
                        reading(peak=0.010)])
    assert verdicts["side_a"] is True
    assert verdicts["side_b"] is True
    assert verdicts["numbers"]["predicted_latency_ms"] == 200


def test_inconsistent_loopback_fails_the_false_stop_side():
    verdicts = _assess([reading(peak=0.005), reading(peak=0.030),
                        reading(peak=0.008), reading(peak=0.010),
                        reading(peak=0.020)])
    assert verdicts["side_a"] is False
    assert any("spread" in why for why in verdicts["side_a_why"])


def test_a_floor_close_to_room_noise_fails_the_false_stop_side():
    verdicts = _assess([reading(floor=0.015) for _ in range(5)])
    assert verdicts["side_a"] is False
    assert any("noise floor" in why for why in verdicts["side_a_why"])


def test_a_loud_loopback_fails_the_catch_side_for_quiet_speech():
    """Echo at 0.05 RMS pushes the worst-case threshold to 0.1 — above
    the quietest real speech this system has measured (0.056, 445)."""
    verdicts = _assess([reading(peak=0.05) for _ in range(5)])
    assert verdicts["side_b"] is False
    assert any("445" in why for why in verdicts["side_b_why"])


def test_a_sustain_requirement_over_the_budget_fails_the_catch_side():
    verdicts = _assess([reading() for _ in range(5)], min_ms=300)
    assert verdicts["side_b"] is False
    assert verdicts["numbers"]["predicted_latency_ms"] == 350


# --- sound-check ratio recommendations --------------------------------------

def test_no_recommendation_from_too_few_confirmed_readings():
    assert calib.recommend_ratios([reading()] * 4) is None


def test_no_recommendation_from_inconsistent_ratios():
    rows = [reading(ratio=2.0), reading(ratio=30.0), reading(ratio=10.0),
            reading(ratio=12.0), reading(ratio=9.0)]
    assert calib.recommend_ratios(rows) is None


def test_recommendation_carries_its_supporting_numbers():
    """Six confirmed-heard readings clustered around ratio 10: good at
    half the median, faint at a fifth — a proposal, never a setting."""
    rows = [reading(ratio=r) for r in (8.0, 9.0, 10.0, 10.0, 11.0, 12.0)]
    rec = calib.recommend_ratios(rows)
    assert rec["n"] == 6 and rec["median"] == 10.0
    assert rec["good"] == 5.0
    assert rec["faint"] == 2.0
    assert rec["min"] == 8.0 and rec["max"] == 12.0


def test_answers_other_than_yes_never_support_a_recommendation():
    rows = [reading(answer="no")] * 6
    assert calib.recommend_ratios(rows) is None


# --- end-to-end smoke -------------------------------------------------------

@pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")
def test_the_report_runs_and_changes_nothing(capsys):
    """REPORT ONLY, even when the audit log is empty: it prints the
    next-steps footer and exits 0. The reads are inside a READ ONLY
    transaction, so a write would be a Postgres error, not a review find."""
    assert calib.main() == 0
    out = capsys.readouterr().out
    assert "REPORT ONLY, nothing changed" in out
    assert "BARGE_IN_ENABLED stays FALSE until BOTH sides" in out
    assert "NORMAL ROOM VOLUME" in out or "Readings are sufficient" in out
