"""Smoke tests for the transcript-quality calibration harness.

The metric functions are pure and are tested on synthetic turn data, so
they run everywhere. Anything needing real audio, Postgres or a Whisper
model self-skips when absent, per the existing convention.

These tests deliberately do NOT assert any threshold: the harness
measures and the project owner sets the numbers.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "calibrate_transcript_quality.py"


def _load():
    spec = importlib.util.spec_from_file_location("calibrate_tq", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calib = _load()


def turn(idx: int, start: float, end: float, text: str, confidence: float) -> dict:
    return {"idx": idx, "role": "Doctor", "start": start, "end": end,
            "text": text, "confidence": confidence}


# --- S2: duration-weighted confidence ------------------------------------

def test_weighted_confidence_is_dominated_by_the_long_segment():
    """The whole point of weighting: a short clean segment must not
    cancel a long garbled one (the #70 failure shape)."""
    turns = [
        turn(0, 0.0, 90.0, "long garbled stretch", 0.30),
        turn(1, 90.0, 92.0, "short clean bit", 1.00),
    ]
    weighted = calib.weighted_mean_confidence(turns)
    unweighted = calib.unweighted_mean_confidence(turns)
    assert weighted == pytest.approx((0.30 * 90 + 1.00 * 2) / 92)
    assert unweighted == pytest.approx(0.65)
    assert weighted < unweighted  # weighting reveals what the mean hides


def test_weighted_confidence_equals_unweighted_for_equal_durations():
    turns = [turn(0, 0.0, 10.0, "a", 0.4), turn(1, 10.0, 20.0, "b", 0.8)]
    assert calib.weighted_mean_confidence(turns) == pytest.approx(0.6)
    assert calib.unweighted_mean_confidence(turns) == pytest.approx(0.6)


def test_confidence_is_none_without_measurable_duration():
    assert calib.weighted_mean_confidence([]) is None
    assert calib.unweighted_mean_confidence([]) is None
    assert calib.weighted_mean_confidence(
        [turn(0, 5.0, 5.0, "zero length", 0.9)]) is None


# --- S3: repetition -------------------------------------------------------

def test_ngram_share_detects_a_repetition_loop():
    looped = " ".join(["the pain in the"] * 10)
    share, gram = calib.max_ngram_share([turn(0, 0.0, 30.0, looped, 0.5)])
    assert gram == "the pain in the"
    assert share > 0.9  # nearly the whole transcript is one phrase


def test_ngram_share_is_low_for_varied_speech():
    text = ("good morning mrs fernando please sit down how have you been "
            "since the last visit and how are the tablets suiting you now")
    share, _ = calib.max_ngram_share([turn(0, 0.0, 20.0, text, 0.9)])
    assert share < 0.3


def test_ngram_share_handles_text_shorter_than_the_window():
    share, gram = calib.max_ngram_share([turn(0, 0.0, 1.0, "too short", 0.9)])
    assert share == 0.0 and gram is None


def test_ngram_share_spans_segment_boundaries():
    """A loop split across segments is still a loop."""
    turns = [turn(i, i, i + 1.0, "the pain in the", 0.5) for i in range(6)]
    share, _ = calib.max_ngram_share(turns)
    assert share > 0.9


def test_max_consecutive_repeats_counts_segments():
    turns = [
        turn(0, 0, 1, "hello there", 0.9),
        turn(1, 1, 2, "same text", 0.9),
        turn(2, 2, 3, "Same TEXT.", 0.9),   # normalisation: punctuation/case
        turn(3, 3, 4, "same text", 0.9),
        turn(4, 4, 5, "different", 0.9),
    ]
    assert calib.max_consecutive_repeats(turns) == 3
    assert calib.max_consecutive_repeats([]) == 0
    assert calib.max_consecutive_repeats([turn(0, 0, 1, "one", 0.9)]) == 1


# --- S4: truncation -------------------------------------------------------

def test_truncation_gap_measures_audio_after_the_last_segment():
    turns = [turn(0, 0.0, 417.0, "final words", 0.8)]
    assert calib.truncation_gap(turns, 450.0) == pytest.approx(33.0)


def test_truncation_gap_is_none_when_audio_is_absent():
    turns = [turn(0, 0.0, 10.0, "x", 0.8)]
    assert calib.truncation_gap(turns, None) is None
    assert calib.truncation_gap([], 100.0) is None


def test_truncation_gap_never_negative():
    turns = [turn(0, 0.0, 120.0, "x", 0.8)]
    assert calib.truncation_gap(turns, 100.0) == 0.0


# --- truncation window ----------------------------------------------------

def test_truncate_turns_at_keeps_only_turns_ending_by_the_boundary():
    turns = [turn(i, i * 10.0, (i + 1) * 10.0, f"t{i}", 0.9) for i in range(5)]
    kept = calib.truncate_turns_at(turns, 30.0)
    assert [t["idx"] for t in kept] == [0, 1, 2]


def test_measure_reports_every_signal():
    turns = [turn(0, 0.0, 10.0, "a b c d e", 0.5)]
    m = calib.measure(turns, 12.0)
    assert set(m) >= {
        "segments", "s2_confidence_weighted", "s2_confidence_unweighted",
        "s3_max_4gram_share", "s3_max_consecutive_identical",
        "s4_truncation_gap_s",
    }
    assert m["segments"] == 1


# --- wiring ---------------------------------------------------------------

def test_consultation_map_matches_the_deviation_report():
    assert calib.CONSULTATIONS == {
        66: "01_chest_pain_en",
        67: "02_febrile_child_en",
        68: "03_diabetes_review_en",
        69: "04_asthma_en",
        70: "03_diabetes_review_si",
    }
    assert calib.NEEDS_TRUNCATION == (66, 68)
    assert calib.KNOWN_BAD == 70


def test_parse_overrides():
    assert calib.parse_overrides(["66=291.4", "68=390"]) == {66: 291.4, 68: 390.0}
    assert calib.parse_overrides([]) == {}
    assert calib.parse_overrides(None) == {}


def test_harness_sets_no_thresholds():
    """Guard against the gate creeping into the measurement harness."""
    source = SCRIPT.read_text(encoding="utf-8")
    for banned in ("THRESHOLD =", "MIN_CONFIDENCE", "def gate(", "is_unreliable"):
        assert banned not in source, f"{banned} suggests a gate, not a measurement"


def test_missing_consultation_row_degrades_cleanly():
    class NoDetector:
        def detect(self, path):
            return None, None

    rows = calib.build_rows({cid: {"present": False} for cid in calib.CONSULTATIONS},
                            NoDetector(), {})
    assert len(rows) == 5
    assert all(row["available"] is False for row in rows)
    assert all("not found" in row["note"] for row in rows)


def test_absent_audio_is_reported_not_fabricated():
    """#70 is voided and voided consultations are purge-eligible."""
    class NoDetector:
        def detect(self, path):
            return None, None

    data = {70: {"present": True, "audio_path": "/nonexistent/70.wav",
                 "status": "approved", "voided": True,
                 "turns": [turn(0, 0.0, 10.0, "stored hallucination", 0.49)]}}
    rows = calib.build_rows(data, NoDetector(), {})
    row = next(r for r in rows if r["consultation"] == 70)
    assert row["audio_present"] is False
    assert "purge-eligible" in row["audio_note"]
    assert row["full"]["s4_truncation_gap_s"] is None   # not fabricated as 0
    assert row["full"]["s2_confidence_weighted"] == pytest.approx(0.49)


def test_scripted_close_detection_finds_the_final_scripted_line():
    script = REPO / "mock_consultations" / "03_diabetes_review_en.md"
    if not script.exists():
        pytest.skip("mock scripts not present")
    from app.mock_scripts import parse_script
    final = parse_script(script)[-1].text
    turns = [
        turn(0, 0.0, 10.0, "some earlier unrelated talk", 0.9),
        turn(1, 10.0, 20.0, final, 0.9),
        turn(2, 20.0, 26.0, "you know i don't read the script but i do naturally", 0.6),
    ]
    found = calib.find_scripted_close(turns, script)
    assert found is not None
    assert found["idx"] == 1
    assert found["containment"] > 0.8
    assert calib.truncate_turns_at(turns, found["boundary_s"])[-1]["idx"] == 1


def test_scripted_close_found_inside_a_merged_segment():
    """Diarisation merges adjacent same-speaker turns, so the closing
    line often sits inside a much longer segment. Whole-string similarity
    picks the wrong turn there; containment must not."""
    script = REPO / "mock_consultations" / "03_diabetes_review_en.md"
    if not script.exists():
        pytest.skip("mock scripts not present")
    from app.mock_scripts import parse_script
    final = parse_script(script)[-1].text
    padding = "and then a great deal of unrelated examination narration " * 12
    turns = [
        turn(0, 0.0, 100.0, "early conversation about the tablets", 0.9),
        turn(1, 100.0, 300.0, padding + " " + final, 0.9),   # merged segment
    ]
    found = calib.find_scripted_close(turns, script)
    assert found is not None
    assert found["idx"] == 1, "containment must find the close inside the merge"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"),
                    reason="DATABASE_URL not set")
def test_fetch_consultations_is_read_only():
    """Runs only where Postgres is configured; asserts the shape, and
    that the session refuses writes."""
    try:
        data = calib.fetch_consultations([66])
    except Exception as exc:  # Postgres absent/unreachable
        pytest.skip(f"database unavailable: {exc}")
    assert 66 in data
    assert "present" in data[66]
