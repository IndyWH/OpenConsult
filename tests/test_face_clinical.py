"""The clinical arm narrows the range; it does not change the reading.

Rewritten 2026-08-01 (PHASE_7B_FACE_DRIVE_SPEC.md § 2.3). This file used
to assert that the [clinical] preset damped a large adrenaline impulse
harder and settled faster than [default] — a statement about the vendored
engine's decay and interaction dynamics. Those dynamics are deliberately
no longer used: their time constants (20 min to 4 h) are an order of
magnitude too slow for a consultation, which is what produced the
consultation-463 defect, so the drive holds a target chemistry instead of
integrating impulses. The old assertion described something that no
longer happens.

What the clinical arm still means, and what is asserted here instead: it
is the narrow-range arm of the owner's comparison. Every muscle's range
across the seven affects (the 2026-08-01 enum: happy and angry joined
the original five) must be no wider than the same muscle's range in
full mode, the total must be strictly narrower, and the face must still
READ the same — the smile ordered by how the patient seems, in the same
order, and the concern brow still raised for a patient who is low or
distressed. A narrower arm is the point; a differently-ordered one would
be a different face, not a damped one.
"""

import pytest

from app.face import FACE_BAND, FaceDriver
from test_face_drive import RENDER_BROW_THRESHOLD, curve
from vendor.kindalive.engine.clock import ManualClock

# The valence ladder, ordered. ANGRY IS DELIBERATELY NOT IN IT — anger is
# a different axis, not a darker sadness (test_face_drive.py, C2/C13). It
# joins the range and cap assertions below, never the ordering.
AFFECTS = ["happy", "positive", "neutral", "anxious", "low", "distressed"]
ALL_AFFECTS = AFFECTS + ["angry"]
TICK = 0.2


def settle(affect: str, mode: str) -> dict[str, float]:
    """Run one driver to steady state on a manual clock, room active."""
    clock = ManualClock()
    driver = FaceDriver(clock=clock, mode=mode)
    driver.on_affect(affect)
    t = 0.0
    while t < 90.0:
        driver.on_speech_activity()
        clock.advance(TICK)
        driver.advance()
        t += TICK
    return driver.payload()["muscles"]


@pytest.fixture(scope="module")
def arms() -> dict[str, dict[str, dict[str, float]]]:
    return {mode: {a: settle(a, mode) for a in ALL_AFFECTS}
            for mode in ("full", "clinical")}


def _spread(arm: dict[str, dict[str, float]], muscle: str) -> float:
    """Range across ALL seven affects — angry included: the band must
    hold for every state the enum can select, not just the ladder."""
    values = [arm[a][muscle] for a in ALL_AFFECTS]
    return max(values) - min(values)


def test_clinical_narrows_every_muscle_and_the_face_as_a_whole(arms):
    full, clinical = arms["full"], arms["clinical"]
    for muscle in full["neutral"]:
        assert _spread(clinical, muscle) <= _spread(full, muscle) + 1e-9, (
            f"{muscle} has a wider range in the clinical arm than in full")
    total_full = sum(_spread(full, m) for m in full["neutral"])
    total_clinical = sum(_spread(clinical, m) for m in clinical["neutral"])
    assert total_clinical < total_full


def test_both_arms_order_the_smile_the_same_way(arms):
    """Narrower, not different: the smile must still fall from a happy
    patient to a distressed one, in the same order. One tolerated tie: in
    the clinical arm the band SATURATES the top of the ladder — happy and
    positive both clip to the neutral+band cap, and a saturated smile is
    a damped one, where a reordered smile would be a different face. A
    tie is therefore accepted only in the clinical arm and only when both
    values sit exactly at the band cap."""
    for mode in ("full", "clinical"):
        smiles = [arms[mode][a]["lip_corner_pull"] for a in AFFECTS]
        cap = arms[mode]["neutral"]["lip_corner_pull"] + FACE_BAND
        for higher, lower in zip(smiles, smiles[1:]):
            assert higher >= lower, mode
            if higher == lower:
                assert mode == "clinical", "the full-mode ladder is strict"
                assert higher == pytest.approx(cap), (
                    "a clinical tie is only ever the band binding")


def test_both_arms_still_raise_the_concern_brow(arms):
    """The 2026-08-01 owner decision that moved brow_inner_raise from
    PINNED to BANDED: before it, the clinical arm could express warmth but
    not concern, which is the original defect in miniature. Happy joins
    the fine states: delight must not read as concern."""
    for mode in ("full", "clinical"):
        brow = arms[mode]
        for worse in ("low", "distressed"):
            for fine in ("neutral", "positive", "happy"):
                assert (brow[worse]["brow_inner_raise"]
                        > brow[fine]["brow_inner_raise"]), f"{mode}/{worse}"


def test_both_arms_answer_the_angry_patient_the_c13_way(arms):
    """Angry's own rule, as test_face_drive.py::test_c13 frames it for the
    full drive, asserted here for BOTH arms: neutral's steadiness, smile
    removed, no brow furrow, no concern brow (anger is not a darker
    sadness) — and warmth raised where the arm CAN raise it. lip_pucker
    is PINNED in the clinical arm (app/face.py PINNED_MUSCLES; the
    payload-policy test in test_face_driver.py holds that pin), so the
    clinical face answers anger with steadiness alone: its warmth stays
    exactly at neutral, asserted as the pin rather than skipped.
    Referenced rather than duplicated: curve() and the render threshold
    come from test_face_drive."""
    for mode in ("full", "clinical"):
        ang, neu = arms[mode]["angry"], arms[mode]["neutral"]
        assert curve(ang) < curve(neu), mode                      # smile removed
        if mode == "full":
            assert ang["lip_pucker"] > neu["lip_pucker"]          # warmth raised
            assert ang["brow_lower"] <= 0.05                      # no furrow
        else:
            # Both muscles are PINNED in the clinical arm: warmth and
            # furrow sit exactly at the resting face, whatever the affect.
            assert ang["lip_pucker"] == pytest.approx(neu["lip_pucker"])
            assert ang["brow_lower"] == pytest.approx(neu["brow_lower"])
        assert (ang["eyelid_lower_tighten"]
                <= neu["eyelid_lower_tighten"] + 0.02), mode      # steadiness
        assert ang["brow_inner_raise"] <= RENDER_BROW_THRESHOLD, mode
