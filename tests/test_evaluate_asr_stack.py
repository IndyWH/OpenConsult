"""The ASR-stack harness's pure measures, on synthetic data.

The harness itself is REPORT ONLY and GPU-heavy; what is tested here is
the arithmetic the report rests on — WER, boundary drift, role
agreement, the confidence summary — plus the candidate selection's
honesty about what it skipped. Nothing here touches a model or the
database.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "evaluate_asr_stack.py"


def _load():
    spec = importlib.util.spec_from_file_location("evaluate_asr_stack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load()


# --- WER --------------------------------------------------------------------

def test_wer_is_zero_for_identical_text_modulo_case_and_punctuation():
    assert harness.wer("Chest pain, for two weeks.",
                       "chest pain for two weeks") == 0.0


def test_wer_counts_substitutions_insertions_and_deletions():
    # ref 4 words; one substitution -> 0.25
    assert harness.wer("the pain is sharp", "the pain is dull") == 0.25
    # one deletion -> 0.25
    assert harness.wer("the pain is sharp", "the pain sharp") == 0.25
    # one insertion -> 0.25
    assert harness.wer("the pain is sharp", "the pain is very sharp") == 0.25


def test_wer_handles_empty_reference():
    assert harness.wer("", "") == 0.0
    assert harness.wer("", "anything") == 1.0


# --- boundary drift and role agreement --------------------------------------

STORED = [
    {"idx": 0, "role": "Doctor", "start_s": 0.0, "end_s": 4.0, "text": "a"},
    {"idx": 1, "role": "Patient", "start_s": 5.0, "end_s": 9.0, "text": "b"},
]


def test_boundary_drift_is_the_median_nearest_distance():
    arm = [{"start": 0.5, "end": 4.0, "text": "a", "role": "Doctor"},
           {"start": 5.1, "end": 9.0, "text": "b", "role": "Patient"}]
    assert harness.boundary_drift_s(STORED, arm) == pytest.approx(0.3)
    assert harness.boundary_drift_s(STORED, []) is None


def test_role_agreement_is_time_weighted_against_the_stored_roles():
    perfect = [{"start": 0.0, "end": 4.0, "role": "Doctor"},
               {"start": 5.0, "end": 9.0, "role": "Patient"}]
    assert harness.role_agreement(STORED, perfect) == 1.0
    inverted = [{"start": 0.0, "end": 4.0, "role": "Patient"},
                {"start": 5.0, "end": 9.0, "role": "Doctor"}]
    assert harness.role_agreement(STORED, inverted) == 0.0
    # Half the audio attributed the other way: agreement in between.
    half = [{"start": 0.0, "end": 4.0, "role": "Doctor"},
            {"start": 5.0, "end": 9.0, "role": "Doctor"}]
    agreement = harness.role_agreement(STORED, half)
    assert 0.4 < agreement < 0.6


def test_confidence_summary_reports_the_s2_style_weighted_mean():
    turns = [{"start": 0, "end": 8, "confidence": 0.9},   # long, confident
             {"start": 8, "end": 9, "confidence": 0.1}]   # short, poor
    summary = harness.confidence_summary(turns)
    assert summary["n"] == 2
    assert summary["s2_weighted_mean"] == pytest.approx(0.811, abs=0.001)
    assert harness.confidence_summary([]) is None


# --- candidate selection honesty --------------------------------------------

def test_scripted_set_and_references_are_wired():
    """The cid->script mapping matches the recordings inventory, and the
    Sinhala reference is the frozen file, not a script parse."""
    assert set(harness.SCRIPTED) == {66, 67, 68, 69, 70}
    assert harness.SI_REFERENCE.name == "03_diabetes_review_si.txt"
    reference = harness.reference_for(66)
    assert reference and "chest" in reference.lower()
    assert harness.reference_for(999) is None


def test_candidate_selection_reports_skips_rather_than_silence():
    cids, notes = harness.candidate_cids(None)
    # Whatever exists on this machine, the FLAC-archived 7a consultations
    # must be named as skipped, never silently absent.
    flacs = list((REPO / "data" / "recordings").glob("consultation_*.flac"))
    named = [n for n in notes if "FLAC" in n]
    assert len(named) == len([f for f in flacs
                              if int(f.stem.split("_")[1]) >= 445])
