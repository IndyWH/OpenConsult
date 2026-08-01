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
across the five affects must be no wider than the same muscle's range in
full mode, the total must be strictly narrower, and the face must still
READ the same — the smile ordered by how the patient seems, in the same
order, and the concern brow still raised for a patient who is low or
distressed. A narrower arm is the point; a differently-ordered one would
be a different face, not a damped one.
"""

import pytest

from app.face import FaceDriver
from vendor.kindalive.engine.clock import ManualClock

AFFECTS = ["positive", "neutral", "anxious", "low", "distressed"]
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
    return {mode: {a: settle(a, mode) for a in AFFECTS}
            for mode in ("full", "clinical")}


def _spread(arm: dict[str, dict[str, float]], muscle: str) -> float:
    values = [arm[a][muscle] for a in AFFECTS]
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
    """Narrower, not different: the clinical arm must still fall from a
    positive patient to a distressed one, in the same order."""
    for mode in ("full", "clinical"):
        smiles = [arms[mode][a]["lip_corner_pull"] for a in AFFECTS]
        for higher, lower in zip(smiles, smiles[1:]):
            assert higher > lower, mode


def test_both_arms_still_raise_the_concern_brow(arms):
    """The 2026-08-01 owner decision that moved brow_inner_raise from
    PINNED to BANDED: before it, the clinical arm could express warmth but
    not concern, which is the original defect in miniature."""
    for mode in ("full", "clinical"):
        brow = arms[mode]
        for worse in ("low", "distressed"):
            for fine in ("neutral", "positive"):
                assert (brow[worse]["brow_inner_raise"]
                        > brow[fine]["brow_inner_raise"]), f"{mode}/{worse}"
