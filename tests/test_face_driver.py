"""app/face.py — the drive layer's per-muscle policy holds under attack.

Updated 2026-08-01 for the rewritten drive (PHASE_7B_FACE_DRIVE_SPEC.md).
The acceptance criteria for the new drive live in test_face_drive.py;
this file keeps the questions that were always asked here — what may
leave payload() under the worst chemistry the engine can hold, whether
the two modes differ where they claim to, and determinism.

The adversarial test drives the chemistry as hard as the engine allows
toward anger and disgust (testosterone, cortisol, adrenaline up; GABA,
serotonin, dopamine and oxytocin crushed), deliberately bypassing the
polite event API, because the policy must hold against the engine's worst
output and not only against the impulses we choose. In clinical mode
pinned muscles must sit at exactly neutral in every emitted payload and
banded muscles must stay inside their band — which is TWO-SIDED since
2026-08-01, so a muscle may fall below neutral as well as rise above it.
"""

import asyncio

import pytest

from vendor.kindalive.engine.chemicals import Chemical
from vendor.kindalive.engine.clock import ManualClock
from vendor.kindalive.expression.face import project_face

from app import face as face_mod
from app.face import (AFFECT_TARGETS, BANDED_MUSCLES, JAW_REST_CAP,
                      PINNED_MUSCLES, FaceDriver)

ALL_MUSCLES = PINNED_MUSCLES | BANDED_MUSCLES

# The worst face the projection can be asked for: anger and disgust at
# their maxima, with the deficit terms that drive the frown fully open.
ANGER_DISGUST_ATTACK = {
    Chemical.TESTOSTERONE: 1.0,
    Chemical.CORTISOL: 1.0,
    Chemical.ADRENALINE: 1.0,
    Chemical.GABA: 0.0,
    Chemical.SEROTONIN: 0.0,
    Chemical.DOPAMINE: 0.0,
    Chemical.OXYTOCIN: 0.0,
    Chemical.ENDORPHINS: 0.0,
}


def attack(driver: FaceDriver) -> None:
    """Write that chemistry straight into the state the projection reads.

    Impulses would be the wrong instrument now: since 2026-08-01 nothing
    in the drive integrates — the driver holds a target chemistry and
    rewrites the engine's state on every advance — so an injected impulse
    is overwritten by the next tick and the policy would be tested
    against nothing. Writing the state and projecting from it asks the
    same adversarial question of the layer that still answers it: whatever
    the chemistry, what is allowed to leave payload()?
    """
    for chemical, value in ANGER_DISGUST_ATTACK.items():
        driver.engine.state.set(chemical, value)


def hold(affect, seconds: float = 30.0, mode: str = "full") -> dict:
    """Settle a driver on one affect, room quiet, and return its payload."""
    clock = ManualClock()
    driver = FaceDriver(clock=clock, mode=mode)
    driver.on_affect(affect)
    t = 0.0
    while t < seconds:
        clock.advance(seconds=0.2)
        driver.advance()
        t += 0.2
    return driver.payload()


def test_classification_covers_all_twelve_muscles_exactly_once():
    assert len(ALL_MUSCLES) == 12
    assert not (PINNED_MUSCLES & BANDED_MUSCLES)


def test_pinned_muscles_stay_at_neutral_under_maximum_anger_and_disgust():
    """HALF OF THE GUARANTEE — this one holds the PAYLOAD POLICY: whatever
    chemistry the engine is holding, including anger and disgust forced
    straight into the state, nothing angry leaves payload() in the
    clinical arm.

    The other half is test_face_drive.py::test_c6_the_face_is_never_angry
    _or_disgusted, which holds the DRIVE: no affect this project can
    select ever asks the projection for anger or disgust in the first
    place. Together they cover it; separately each is half. Do not remove
    either believing the other covers it.
    """
    # Keyed to clinical mode: since 2026-07-28 the caps are one arm of the
    # owner's evaluation-first comparison, not the default behaviour.
    driver = FaceDriver(clock=ManualClock(), mode="clinical")
    neutral = dict(driver._neutral)
    attack(driver)
    payload = driver.payload()

    # The attack genuinely reaches the projection — the policy did the
    # work, not a quiet engine. Without this the test could pass vacuously.
    raw = project_face(driver.engine.state).as_dict()
    assert raw["brow_lower"] > 0.5
    assert raw["nose_wrinkle"] > 0.5

    for muscle in PINNED_MUSCLES:
        # jaw_open is pinned AND then capped at rest: the clinical
        # neutral jaw is 0.12, above the renderer's 0.10 "draw an open
        # mouth" threshold, so the cap is what closes the resting mouth.
        expected = round(neutral[muscle], 4)
        if muscle == "jaw_open":
            expected = min(expected, JAW_REST_CAP)
        assert payload["muscles"][muscle] == expected, (
            f"pinned muscle {muscle} moved under attack")
    for muscle in BANDED_MUSCLES:
        value = payload["muscles"][muscle]
        # The band is two-sided since 2026-08-01: a banded muscle may fall
        # below neutral as well as rise above it, which is what lets the
        # clinical arm show concern instead of only warmth.
        assert round(neutral[muscle] - driver.band, 4) <= value, (
            f"banded muscle {muscle} escaped its band downward")
        assert value <= round(neutral[muscle] + driver.band, 4), (
            f"banded muscle {muscle} escaped its band upward")

    # The spirit of this test, restated because the PINNED set changed:
    # anger and disgust must be UNEXPRESSIBLE, not damped. These four are
    # the anger/disgust muscles and none of them may move at all.
    for muscle in ("brow_lower", "nose_wrinkle", "eyelid_lower_tighten",
                   "lip_press"):
        assert muscle in PINNED_MUSCLES, (
            f"{muscle} carries anger or disgust and must stay pinned")
        assert payload["muscles"][muscle] == round(neutral[muscle], 4)

    # ...while the two muscles the owner moved PINNED → BANDED on
    # 2026-08-01 are now allowed to move, inside the band. Concern is
    # expressible in the clinical arm; rage is not.
    assert payload["muscles"]["brow_inner_raise"] > round(
        neutral["brow_inner_raise"], 4)


@pytest.mark.parametrize("mode", ["full", "clinical"])
def test_same_event_sequence_produces_identical_states(mode):
    def run() -> list[dict]:
        clock = ManualClock()
        driver = FaceDriver(clock=clock, mode=mode)
        states = []
        driver.on_consultation_started()
        for i in range(20):
            clock.advance(seconds=0.25)
            driver.on_speech_activity()
            if i == 8:
                driver.on_system_speech_started()
            if i == 12:
                driver.on_system_speech_ended()
            driver.advance(0.25)
            states.append(driver.payload())
        return states

    assert run() == run()


def test_stopped_driver_emits_nothing():
    driver = FaceDriver(clock=ManualClock())
    driver.stop()
    sent = []

    async def send(msg):
        sent.append(msg)

    asyncio.run(driver.run(send))
    assert sent == []


def test_tick_loop_emits_face_state_payloads_then_stops():
    driver = FaceDriver(clock=ManualClock(), tick_hz=200.0)
    sent = []

    async def send(msg):
        sent.append(msg)
        if len(sent) >= 3:
            driver.stop()

    asyncio.run(driver.run(send))
    assert len(sent) == 3
    for msg in sent:
        assert msg["type"] == "face_state"
        assert set(msg["muscles"]) == ALL_MUSCLES


def test_full_mode_clamps_nothing_except_the_jaw():
    """Mirror of the clinical adversarial test: in full mode the same
    anger/disgust drive REACHES the payload un-neutralised — the owner's
    evaluation-first decision, superseding the caps for this phase — with
    ONE exception since 2026-08-01. jaw_open is capped at JAW_REST_CAP in
    BOTH modes: the mouth belongs to speech. face3d.js draws an open mouth
    above 0.10 and layers the assistant's speaking flap on top, so a
    resting jaw above the cap makes the face look about to talk.
    """
    driver = FaceDriver(clock=ManualClock(), mode="full")
    attack(driver)
    muscles = driver.payload()["muscles"]
    # brow_lower is the anger brow; nose_wrinkle is disgust. Both pinned
    # in clinical mode; both must move freely here.
    assert muscles["brow_lower"] > 0.5
    assert muscles["nose_wrinkle"] > 0.5
    # The jaw would hang open on this chemistry if nothing capped it...
    assert project_face(driver.engine.state).jaw_open > JAW_REST_CAP
    assert muscles["jaw_open"] == JAW_REST_CAP

    clinical = FaceDriver(clock=ManualClock(), mode="clinical")
    attack(clinical)
    assert clinical.payload()["muscles"]["jaw_open"] <= JAW_REST_CAP


def test_the_modes_differ_in_per_muscle_policy_not_in_baselines():
    """Rewritten 2026-08-01. The modes used to differ in their baselines
    too — full ran kindalive's upstream default personality, clinical the
    [clinical] preset. The baselines are OURS in both modes now, because
    three muscles read the DEFICIT below baseline (brow_inner_raise,
    lip_corner_depress, and the frown terms generally), so the resting
    levels are part of the AFFECT_TARGETS calibration rather than a
    personality choice. What still separates the arms is the per-muscle
    policy: full emits the projection, clinical pins and bands it.
    """
    full = FaceDriver(clock=ManualClock(), mode="full")
    clinical = FaceDriver(clock=ManualClock(), mode="clinical")
    for name, value in face_mod.PRESET_BASELINES.items():
        chemical = Chemical.from_string(name)
        assert full.engine.state.baseline(chemical) == pytest.approx(value)
        assert clinical.engine.state.baseline(chemical) == pytest.approx(value)

    attack(full)
    attack(clinical)
    assert full.payload()["muscles"]["brow_lower"] > 0.5
    assert clinical.payload()["muscles"]["brow_lower"] == round(
        clinical._neutral["brow_lower"], 4)


def test_default_mode_is_full_and_unknown_falls_back_loudly():
    assert FaceDriver(clock=ManualClock()).mode == face_mod.FACE_EXPRESSION_MODE
    assert face_mod.FACE_EXPRESSION_MODE in face_mod.EXPRESSION_MODES
    assert FaceDriver(clock=ManualClock(), mode="typo").mode == "full"


def test_urgency_is_deliberately_not_an_event():
    """The face must not signal clinical state to the patient. If someone
    wires the urgency alarm in, this fails and points at the reasoning.
    Unchanged in spirit through the 2026-08-01 rewrite; it now guards the
    whole module surface rather than the two impulse maps it replaced.
    """
    for name in dir(face_mod):
        assert "urgen" not in name.lower() and "alarm" not in name.lower(), (
            "the urgency alarm must not drive the face — see the module "
            "docstring in app/face.py")
    for name in dir(face_mod.FaceDriver):
        assert "urgen" not in name.lower() and "alarm" not in name.lower()
    for affect in list(AFFECT_TARGETS) + list(face_mod.AFFECT_VALUES):
        assert "urgen" not in affect and "alarm" not in affect


def test_absent_or_unknown_affect_is_neutral_and_repeats_change_nothing():
    """Replaces test_affect_injects_on_change_only_..., which described a
    mechanism that no longer exists: affect is a STATE now, so on_affect
    sets the target the driver ramps toward rather than injecting an
    impulse, and "only on change" is not a property of anything. What must
    still hold is that an absent or unrecognised hint means neutral, and
    that repeating one is the same one state.
    """
    neutral = hold("neutral")
    assert hold(None) == neutral
    assert hold("") == neutral
    assert hold("cheerful") == neutral       # unrecognised
    assert hold("distressed") != neutral     # non-vacuous

    clock = ManualClock()
    driver = FaceDriver(clock=clock, mode="full")
    driver.on_affect("distressed")
    for _ in range(150):
        clock.advance(seconds=0.2)
        driver.advance()
    settled = driver.payload()
    for _ in range(10):
        driver.on_affect("distressed")
    assert driver.payload() == settled


def test_affect_response_is_a_listener_not_a_mirror():
    """The important one, kept. A distressed patient gets warm concern,
    not a distressed face reflected back: warmth (oxytocin, which drives
    lip_pucker — AU18, affection and concern) must RISE as the patient's
    state worsens, and must rise at least as far as any stress chemical
    does. Asserted against AFFECT_TARGETS, which is where the response now
    lives — the impulse deltas it used to read are gone.
    """
    warmth = {a: t[Chemical.OXYTOCIN] for a, t in AFFECT_TARGETS.items()}
    for affect in ("anxious", "low", "distressed"):
        assert warmth[affect] > warmth["neutral"], affect
    assert warmth["distressed"] == max(warmth.values())

    baseline = AFFECT_TARGETS["neutral"]
    for affect, target in AFFECT_TARGETS.items():
        warmer = target[Chemical.OXYTOCIN] - baseline[Chemical.OXYTOCIN]
        for stress in (Chemical.CORTISOL, Chemical.ADRENALINE):
            assert warmer >= target[stress] - baseline[stress], (
                f"{affect}: the face must lean in, not fall apart")


def test_same_affect_sequence_produces_identical_states():
    def run() -> list[dict]:
        clock = ManualClock()
        driver = FaceDriver(clock=clock, mode="full")
        states = []
        for affect in ["neutral", "anxious", "anxious", "distressed",
                       "neutral", "positive", None, "low"]:
            driver.on_affect(affect)
            clock.advance(seconds=1.0)
            driver.advance(1.0)
            states.append(driver.payload())
        return states

    assert run() == run()
