"""app/face.py — the impulse-mapping layer's hard caps hold under attack.

The adversarial test drives the chemistry as hard as the engine allows
toward anger and disgust (testosterone, cortisol, adrenaline up; GABA and
serotonin crushed) — deliberately bypassing the polite event API, because
the caps must hold against the engine's worst output, not only against
the impulses we choose to inject. Pinned muscles must sit at exactly
neutral in every emitted payload; banded muscles must stay inside their
band. Plus: the same event sequence always produces the same states, and
a stopped driver's tick loop emits nothing.
"""

import asyncio

import pytest

from vendor.kindalive.engine.chemicals import Chemical
from vendor.kindalive.engine.clock import ManualClock
from vendor.kindalive.engine.impulse import ChemicalImpulse

from app import face as face_mod
from app.face import BANDED_MUSCLES, PINNED_MUSCLES, FaceDriver

ALL_MUSCLES = PINNED_MUSCLES | BANDED_MUSCLES

ANGER_DISGUST_ATTACK = [
    (Chemical.TESTOSTERONE, 0.5),
    (Chemical.CORTISOL, 0.5),
    (Chemical.ADRENALINE, 0.5),
    (Chemical.GABA, -0.5),
    (Chemical.SEROTONIN, -0.5),
    (Chemical.DOPAMINE, -0.5),   # dopamine deficit drives the frown terms
    (Chemical.OXYTOCIN, -0.5),
]


def test_classification_covers_all_twelve_muscles_exactly_once():
    assert len(ALL_MUSCLES) == 12
    assert not (PINNED_MUSCLES & BANDED_MUSCLES)


def test_pinned_muscles_stay_at_neutral_under_maximum_anger_and_disgust():
    # Keyed to clinical mode: since 2026-07-28 the caps are one arm of the
    # owner's evaluation-first comparison, not the default behaviour.
    clock = ManualClock()
    driver = FaceDriver(clock=clock, mode="clinical")
    neutral = dict(driver._neutral)

    for _ in range(30):  # repeated max-delta spikes, then a tick's advance
        for chemical, delta in ANGER_DISGUST_ATTACK:
            driver.engine.apply_impulse(ChemicalImpulse(chemical, delta))
        clock.advance(seconds=0.2)
        driver.advance(0.2)
        payload = driver.payload()

        for muscle in PINNED_MUSCLES:
            assert payload["muscles"][muscle] == round(neutral[muscle], 4), (
                f"pinned muscle {muscle} moved under attack")
        for muscle in BANDED_MUSCLES:
            value = payload["muscles"][muscle]
            assert round(neutral[muscle], 4) <= value, (
                f"banded muscle {muscle} fell below neutral")
            assert value <= round(neutral[muscle] + driver.band, 4), (
                f"banded muscle {muscle} escaped its band")

    # The attack genuinely moved the chemistry — the caps did the work,
    # not a quiet engine. Without this the test could pass vacuously.
    state = driver.engine.state
    assert state.get(Chemical.CORTISOL) > state.baseline(Chemical.CORTISOL) + 0.2


@pytest.mark.parametrize("mode", ["full", "clinical"])
def test_same_event_sequence_produces_identical_states(mode):
    def run() -> list[dict]:
        clock = ManualClock()
        driver = FaceDriver(clock=clock, mode=mode)
        states = []
        driver.on_consultation_started()
        for i in range(20):
            clock.advance(seconds=0.25)
            driver.on_patient_audio()          # rate-limited internally
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


def test_full_mode_does_not_clamp():
    """Mirror of the clinical adversarial test: in full mode the same
    anger/disgust drive REACHES the payload un-neutralised — the owner's
    evaluation-first decision, superseding the caps for this phase."""
    clock = ManualClock()
    driver = FaceDriver(clock=clock, mode="full")
    for _ in range(30):
        for chemical, delta in ANGER_DISGUST_ATTACK:
            driver.engine.apply_impulse(ChemicalImpulse(chemical, delta))
        clock.advance(seconds=0.2)
        driver.advance(0.2)
    muscles = driver.payload()["muscles"]
    # brow_lower is the anger brow; nose_wrinkle is disgust. Both pinned
    # in clinical mode; both must move freely here.
    assert muscles["brow_lower"] > 0.5
    assert muscles["nose_wrinkle"] > 0.5


def test_full_mode_runs_the_upstream_default_not_clinical():
    full = FaceDriver(clock=ManualClock(), mode="full")
    clinical = FaceDriver(clock=ManualClock(), mode="clinical")
    # Species-default adrenaline baseline is 0.1; [clinical] lowers it to
    # 0.02. Full mode must show the upstream default.
    assert full.engine.state.baseline(Chemical.ADRENALINE) == pytest.approx(0.1)
    assert clinical.engine.state.baseline(Chemical.ADRENALINE) == pytest.approx(0.02)


def test_default_mode_is_full_and_unknown_falls_back_loudly():
    assert FaceDriver(clock=ManualClock()).mode == face_mod.FACE_EXPRESSION_MODE
    assert face_mod.FACE_EXPRESSION_MODE in face_mod.EXPRESSION_MODES
    assert FaceDriver(clock=ManualClock(), mode="typo").mode == "full"


def test_urgency_is_deliberately_not_an_event():
    """The face must not signal clinical state to the patient. If someone
    wires the urgency alarm in, this fails and points at the reasoning."""
    assert not any("urgen" in event for event in face_mod.EVENT_IMPULSES), (
        "the urgency alarm must not drive the face — see the module "
        "docstring in app/face.py")
