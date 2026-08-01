"""The acceptance criteria for the corrected face drive, as tests.

Written before the numbers in AFFECT_TARGETS were tuned. Every one of
these is a property the face must have, not a snapshot of what it
happens to do — if a future calibration changes the numbers, these should
still pass, and if they cannot, the calibration is wrong.

See PHASE_7B_FACE_DRIVE_SPEC.md § 4.
"""
import pytest

from app.face import FaceDriver
from vendor.kindalive.engine.clock import ManualClock

TICK = 0.2
AFFECTS = ["positive", "neutral", "anxious", "low", "distressed"]

# face3d.js drawMask() only draws the brow bar above this value, so a
# concern face below it is computed, sent, and invisible.
RENDER_BROW_THRESHOLD = 0.28
# ...and draws an open mouth above this one.
RENDER_JAW_THRESHOLD = 0.10


def curve(muscles):
    """What face3d.js actually draws the mouth from. The smile muscle on
    its own is not what a person sees."""
    return muscles["lip_corner_pull"] - muscles["lip_corner_depress"]


def settle(affect, seconds=90.0, active=True, mode="full"):
    """Run the driver to steady state on a manual clock."""
    clock = ManualClock()
    d = FaceDriver(clock=clock, mode=mode)
    d.on_affect(affect)
    t = 0.0
    while t < seconds:
        if active:
            d.on_speech_activity()
        clock.advance(TICK)
        d.advance()
        t += TICK
    return d.payload()["muscles"]


@pytest.fixture(scope="module")
def steady():
    return {a: settle(a) for a in AFFECTS}


def test_c1_the_face_does_not_drift_with_time():
    """The defect in consultation 463: the face smiled harder the longer
    the consultation ran. Nothing in the drive integrates, so this holds
    by construction — which is why it is worth pinning."""
    clock = ManualClock()
    d = FaceDriver(clock=clock, mode="full")
    d.on_affect("neutral")
    at2 = at15 = None
    t = 0.0
    while t < 960:
        d.on_speech_activity()
        clock.advance(TICK)
        d.advance()
        t += TICK
        if abs(t - 120) < 1e-9:
            at2 = d.payload()["muscles"]
        if abs(t - 900) < 1e-9:
            at15 = d.payload()["muscles"]
    assert max(abs(at15[m] - at2[m]) for m in at2) <= 0.01


def test_c2_the_mouth_curve_is_ordered_by_how_the_patient_seems(steady):
    curves = [curve(steady[a]) for a in AFFECTS]
    for higher, lower in zip(curves, curves[1:]):
        assert higher - lower >= 0.05


def test_c3_distress_turns_the_mouth_down(steady):
    """Inverted, this is the 463 defect: distress used to turn it up."""
    assert curve(steady["neutral"]) - curve(steady["distressed"]) >= 0.20


@pytest.mark.parametrize("affect", ["distressed", "low"])
def test_c4_the_concern_brow_actually_renders(steady, affect):
    assert steady[affect]["brow_inner_raise"] > RENDER_BROW_THRESHOLD


@pytest.mark.parametrize("affect", ["neutral", "positive"])
def test_c4b_no_concern_brow_when_the_patient_is_fine(steady, affect):
    assert steady[affect]["brow_inner_raise"] <= 0.10


def test_c5_warmth_is_greatest_where_it_is_most_needed(steady):
    """A listener's response, not a mirror: the face leans in."""
    warm = {a: steady[a]["lip_pucker"] for a in AFFECTS}
    assert warm["distressed"] >= warm["low"] >= warm["anxious"] >= warm["neutral"]
    # NEUTRAL IS EXEMPT from the floor by owner decision 2026-08-01: it is
    # kindalive's own untouched resting chemistry, so its warmth is
    # whatever that rests at. The floor applies to the four states we
    # author. Relaxed because the requirement changed, not because the
    # code failed to meet it.
    assert min(warm[a] for a in AFFECTS if a != "neutral") >= 0.18


@pytest.mark.parametrize("muscle,cap", [
    ("brow_lower", 0.15), ("nose_wrinkle", 0.15),
    ("lip_press", 0.25), ("eyelid_lower_tighten", 0.20)])
def test_c6_the_face_is_never_angry_or_disgusted(steady, muscle, cap):
    for affect in AFFECTS:
        assert steady[affect][muscle] <= cap, affect


def test_c7_the_face_keeps_up_with_the_room(steady):
    clock = ManualClock()
    d = FaceDriver(clock=clock, mode="full")
    d.on_affect("neutral")
    for _ in range(600):
        d.on_speech_activity()
        clock.advance(TICK)
        d.advance()
    start = curve(d.payload()["muscles"])
    end = curve(steady["distressed"])
    d.on_affect("distressed")
    t = 0.0
    while t < 20.0:
        d.on_speech_activity()
        clock.advance(TICK)
        d.advance()
        t += TICK
    now = curve(d.payload()["muscles"])
    assert abs(now - start) / abs(end - start) >= 0.90


def test_c8_attention_is_visible_but_modest(steady):
    quiet = settle("neutral", active=False)
    lift = (steady["neutral"]["eyelid_upper_raise"]
            - quiet["eyelid_upper_raise"])
    assert 0.03 <= lift <= 0.15


def test_c9_the_drive_is_deterministic():
    assert settle("distressed") == settle("distressed")


def test_c10_concern_not_grief(steady):
    assert -curve(steady["distressed"]) <= 0.25


def test_c11_the_clinical_arm_can_still_express_concern():
    """The arm exists to limit range, not to reintroduce the defect: it
    must still lower the smile and raise the concern brow under distress."""
    cl = {a: settle(a, mode="clinical") for a in AFFECTS}
    assert (cl["neutral"]["lip_corner_pull"]
            > cl["distressed"]["lip_corner_pull"])
    assert (cl["distressed"]["brow_inner_raise"]
            > cl["neutral"]["brow_inner_raise"])


@pytest.mark.parametrize("affect", AFFECTS)
@pytest.mark.parametrize("mode", ["full", "clinical"])
def test_c12_the_resting_mouth_stays_closed(affect, mode):
    """An open mouth must mean the assistant is speaking. face3d.js
    layers the speaking flap on top of whatever jaw_open we send."""
    assert settle(affect, mode=mode)["jaw_open"] <= RENDER_JAW_THRESHOLD


def test_urgency_is_still_not_an_event():
    """Unchanged and deliberate: an alarmed face would tell the patient
    something the doctor has not decided yet."""
    import app.face as face
    surface = {n for n in dir(face.FaceDriver) if n.startswith("on_")}
    assert not any("urgen" in n or "alarm" in n for n in surface)
    assert not any("urgen" in k or "alarm" in k for k in face.AFFECT_TARGETS)


def test_activity_floor_ignores_digital_silence():
    from app.face import frame_is_active
    assert not frame_is_active(b"\x00\x00" * 400)
    loud = b"".join(int(8000).to_bytes(2, "little", signed=True)
                    for _ in range(400))
    assert frame_is_active(loud)
