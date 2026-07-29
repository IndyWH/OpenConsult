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
            discrepancy=None, device="Speakers", at="2026-07-29",
            chain=None, residual_peak=None, residual_series=None) -> dict:
    row = {"at": at, "username": "doctor", "peak_rms": peak,
           "noise_floor_rms": floor, "answer": answer,
           "ratio": ratio if ratio is not None else peak / floor,
           "discrepancy": discrepancy, "device_label": device,
           **({"chain": chain} if chain is not None else {})}
    if residual_peak is not None:
        row["residual"] = {"peak_rms": residual_peak,
                           "mean_rms": residual_peak * 0.6,
                           "series": residual_series or [residual_peak],
                           "window_ms": 250}
    return row


def dual(residual_peak, raw=0.40, **kw) -> dict:
    """A residual-bearing (dual-measurement) reading — the only kind
    verdicts come from since the Part 10 amendment. Raw defaults loud
    (0.40, the measured room) to keep the raw-vs-residual gap honest."""
    return reading(peak=raw, residual_peak=residual_peak, **kw)


# --- the D5 target is the spec's, verbatim ----------------------------------

def test_the_d5_target_matches_the_spec():
    assert calib.D5_FALSE_STOP_MAX == 0.01
    assert calib.D5_CATCH_MIN == 0.90
    assert calib.D5_CATCH_WITHIN_MS == 300


# --- grouping and filtering -------------------------------------------------

def test_readings_group_by_device_and_unlabelled_rows_are_quarantined():
    """A level without its path is not a measurement: rows with no device
    label land in their own named group and never mix with real ones.
    (Amended for the chain field: grouping keys are now (device, chain).)"""
    groups = calib.group_readings([
        reading(device="Speakers"), reading(device="Monitor"),
        reading(device=None)])
    assert set(groups) == {("Speakers", None, "raw-only"),
                           ("Monitor", None, "raw-only"),
                           (calib.NO_DEVICE, None, "raw-only")}
    assert "not comparable" in calib.NO_DEVICE


def test_readings_across_two_chains_never_pool():
    """The device-label lesson applied to the processing chain: the same
    device under two capture chains is two instruments, and their
    readings must never share a spread, an average or a recommendation.
    Pre-chain rows (no record at all) form a third, incomparable group."""
    old_chain = {"ec": True, "ns": True, "agc": True}
    new_chain = {"ec": False, "ns": True, "agc": True}
    rows = ([reading(chain=old_chain) for _ in range(5)]
            + [reading(chain=new_chain) for _ in range(5)]
            + [reading()])                        # pre-chain row
    groups = calib.group_readings(rows)
    assert len(groups) == 3
    assert all(len(g) in (1, 5) for g in groups.values())
    labels = set(groups)
    assert ("Speakers", "ec=on ns=on agc=on", "raw-only") in labels
    assert ("Speakers", "ec=off ns=on agc=on", "raw-only") in labels
    assert ("Speakers", None, "raw-only") in labels
    # And the labels are honest about what None means.
    assert "not comparable" in calib.NO_CHAIN


def test_residual_and_no_residual_readings_never_pool():
    """Same device, same chain, but one set carries the detector-stream
    residual and the other predates the dual measurement: two groups,
    never one — a raw-only row must not lend its raw peak to a residual
    spread or vice versa."""
    chain = {"ec": False, "ns": True, "agc": True}
    rows = ([dual(0.010, chain=chain) for _ in range(5)]
            + [reading(chain=chain) for _ in range(5)])
    groups = calib.group_readings(rows)
    assert set(groups) == {("Speakers", "ec=off ns=on agc=on", "dual"),
                           ("Speakers", "ec=off ns=on agc=on", "raw-only")}
    assert all(len(g) == 5 for g in groups.values())
    assert "predates the dual measurement" in calib.NO_RESIDUAL


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


# AMENDED for the Part 10 amendment (2026-07-30): verdicts now come from
# residual-bearing readings — the threshold operates on the detector
# stream, so stability and headroom are judged on the residual there,
# with the loud raw loopback (0.40 in these fixtures, per the measured
# room) reported only as the sanity upper bound.

def test_consistent_quiet_residual_predicts_both_sides_met():
    """Residual ~0.01 under a 0.40 raw loopback, noise floor 0.004: the
    threshold clears room noise and quiet speech clears the
    residual-derived threshold — exactly the case the raw-derived
    threshold could never pass (its bound here would be 0.8)."""
    verdicts = _assess([dual(0.010), dual(0.011), dual(0.009),
                        dual(0.012), dual(0.010)])
    assert verdicts["side_a"] is True
    assert verdicts["side_b"] is True
    assert verdicts["numbers"]["predicted_latency_ms"] == 200
    assert verdicts["numbers"]["raw_bound_worst"] == pytest.approx(0.8)


def test_inconsistent_residual_fails_the_false_stop_side():
    verdicts = _assess([dual(0.005), dual(0.030), dual(0.008),
                        dual(0.010), dual(0.020)])
    assert verdicts["side_a"] is False
    assert any("spread" in why for why in verdicts["side_a_why"])


def test_a_floor_close_to_room_noise_fails_the_false_stop_side():
    verdicts = _assess([dual(0.010, floor=0.015) for _ in range(5)])
    assert verdicts["side_a"] is False
    assert any("noise floor" in why for why in verdicts["side_a_why"])


def test_a_loud_residual_fails_the_catch_side_for_quiet_speech():
    """Residual at 0.05 RMS pushes the worst-case threshold to 0.1 —
    above the quietest real speech this system has measured (0.056, 445).
    A canceller that leaves that much behind is not helping."""
    verdicts = _assess([dual(0.05) for _ in range(5)])
    assert verdicts["side_b"] is False
    assert any("445" in why for why in verdicts["side_b_why"])


def test_a_sustain_requirement_over_the_budget_fails_the_catch_side():
    verdicts = _assess([dual(0.010) for _ in range(5)], min_ms=300)
    assert verdicts["side_b"] is False
    assert verdicts["numbers"]["predicted_latency_ms"] == 350


def test_convergence_summary_flags_a_first_window_that_would_fire():
    """The unconverged first window is the false-stop risk: the summary
    says per reading whether it alone would have crossed the threshold."""
    hot_start = dual(0.010, residual_series=[0.045, 0.012, 0.006, 0.005])
    curve = calib.convergence_summary(hot_start, threshold_loud=0.020)
    assert curve["first"] == pytest.approx(0.045)
    assert curve["settled"] == pytest.approx(0.005)
    assert curve["would_fire"] is True

    calm = dual(0.010, residual_series=[0.012, 0.008, 0.006])
    assert calib.convergence_summary(calm, threshold_loud=0.020)["would_fire"] is False
    assert calib.convergence_summary(reading(), 0.02) is None


# --- the --since window -----------------------------------------------------

def test_split_since_partitions_by_date_and_none_keeps_everything():
    import datetime
    rows = [reading(at="2026-07-20"), reading(at="2026-07-29"),
            # datetime objects (what the database actually returns) work too
            reading(at=datetime.datetime(2026, 7, 30, 22, 42, 49))]
    kept, excluded = calib.split_since(rows, None)
    assert kept == rows and excluded == []
    kept, excluded = calib.split_since(rows, datetime.date(2026, 7, 29))
    assert [str(calib._reading_date(r)) for r in kept] == \
        ["2026-07-29", "2026-07-30"]
    assert [str(calib._reading_date(r)) for r in excluded] == ["2026-07-20"]


def test_a_recent_consistent_cluster_passes_under_since_and_fails_without():
    """The flag's whole purpose: the current room configuration evaluated
    without the device's history polluting the spread. Old scattered
    readings (x30 spread) drown a recent consistent cluster; --since cuts
    to the cluster and the spread check passes."""
    import datetime
    old = [dual(p, at="2026-07-20")
           for p in (0.005, 0.060, 0.150, 0.010, 0.090)]
    recent = [dual(p, at="2026-07-30")
              for p in (0.010, 0.011, 0.009, 0.012, 0.010)]
    rows = old + recent

    without = calib.assess_device(calib.acoustic_readings(rows),
                                  margin=2.0, abs_floor=0.02, min_ms=150)
    assert without["side_a"] is False
    assert any("spread" in why for why in without["side_a_why"])

    kept, excluded = calib.split_since(rows, datetime.date(2026, 7, 30))
    assert len(excluded) == 5
    narrowed = calib.assess_device(calib.acoustic_readings(kept),
                                   margin=2.0, abs_floor=0.02, min_ms=150)
    assert narrowed["side_a"] is True
    assert narrowed["side_b"] is True


@pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")
def test_excluded_readings_are_announced_never_silent(capsys):
    """A narrowed window must be visible in the output: the report names
    how many readings --since excluded and from when."""
    from app import schema
    schema.ensure_all()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "INSERT INTO audit_event (at, action, detail) VALUES"
            " ('2026-06-01T10:00:00Z', 'speech.sound_check',"
            "  '{\"peak_rms\": 0.02, \"noise_floor_rms\": 0.004,"
            "    \"answer\": \"yes\", \"ratio\": 5.0,"
            "    \"device_label\": \"Since-flag test device\"}')")
    assert calib.main(["--since", "2026-06-15"]) == 0
    out = capsys.readouterr().out
    assert "readings from 2026-06-15 onward only" in out
    assert "EXCLUDED by --since 2026-06-15: 1 reading(s) from 2026-06-01" in out


def test_an_invalid_since_date_is_an_argparse_error_not_a_guess():
    with pytest.raises(SystemExit):
        calib.main(["--since", "yesterday"])


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
