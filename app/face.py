"""Phase 7b: the drive layer between consultation events and the
vendored kindalive engine — deterministic, GPU-free.

Rewritten 2026-08-01 after consultation 463, where the face smiled
throughout a chest-pain history. See PHASE_7B_FACE_DRIVE_SPEC.md.

WHAT CHANGED AND WHY
--------------------
The old layer injected dopamine every two seconds for as long as audio
frames arrived. Audio frames arrive whenever the microphone is on, so the
signal was a metronome, and dopamine is the largest term in the smile
muscle (0.40) — the face therefore smiled harder the longer a
consultation ran, regardless of what was said. Chemical half-lives run
20 min to 4 h, so nothing came back down inside a consultation.

Two structural changes:

1. NOTHING INTEGRATES. Affect is a STATE, not an event, so it sets a
   TARGET chemistry that the driver ramps toward and then holds. Attention
   is a bounded level with attack and release, not an accumulating
   impulse. No repeating stimulus can push any chemical upward without
   limit, so the face cannot drift with time. This is a structural
   guarantee, not a tuning choice: there is no accumulator to overflow.

2. ATTENTION RIDES ADRENALINE, NOT DOPAMINE. In the vendored FACE_WEIGHTS
   alertness lives in adrenaline (eyelid_upper_raise 0.55, brow_outer_raise
   0.50); dopamine is reward, and drives the smile. Using dopamine for
   "someone is talking" was the original category error.

The engine's decay, cross-interactions and saturation are deliberately
NOT used: their time constants are an order of magnitude too slow for a
15-minute consultation. What is used is the vendored FACE_WEIGHTS
projection (chemistry to 12 FACS muscles) and the vendored config. The
vendored files remain untouched at their pinned commit.

Speech activity counts BOTH speakers (owner decision 2026-08-01): the
face is a listening presence for the patient, and it is at least as
relevant while the doctor — or Alba — is the one talking.

The urgency alarm is still NOT wired to the face. Unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import tomllib
from pathlib import Path

from vendor.kindalive.engine.chemicals import Chemical
from vendor.kindalive.engine.clock import Clock, RealClock
from vendor.kindalive.engine.neurochemical_engine import NeurochemicalEngine
from vendor.kindalive.engine.seed_chemistry import SeedChemistry
from vendor.kindalive.expression.face import project_face
from vendor.kindalive.expression.face_3d import DEFAULT_MOOD_COLOR, face_payload

logger = logging.getLogger("consultation-ai.face")

CONFIG_DIR = Path(__file__).resolve().parents[1] / "vendor" / "kindalive" / "config"

FACE_EXPRESSION_MODE = os.environ.get("FACE_EXPRESSION_MODE", "full")
EXPRESSION_MODES = ("full", "clinical")
FACE_BAND = float(os.environ.get("FACE_BAND", "0.15"))
FACE_TICK_HZ = float(os.environ.get("FACE_TICK_HZ", "5"))

# How fast the face moves to a new affect. 6 s reaches ~96% in 20 s, which
# is inside one CDS revision interval — the face keeps up with the room
# without twitching on every revision.
AFFECT_RAMP_S = float(os.environ.get("FACE_AFFECT_RAMP_S", "6"))

# Attention: rises quickly when the room is active, falls back over a few
# seconds of quiet. Bounded in [0, 1] by construction.
ATTENTION_ATTACK_S = float(os.environ.get("FACE_ATTENTION_ATTACK_S", "0.8"))
ATTENTION_RELEASE_S = float(os.environ.get("FACE_ATTENTION_RELEASE_S", "5.0"))
ATTENTION_GAIN = float(os.environ.get("FACE_ATTENTION_GAIN", "0.15"))
# Room audio counts as activity for this long after the last frame above
# the floor, so ordinary gaps between words do not read as silence.
ACTIVITY_HOLD_S = 1.2

# THE MOUTH BELONGS TO SPEECH. face3d.js layers its syllable-rate flap on
# top of jaw_open while the assistant talks. Kindalive also opens the jaw
# for excitement, which is right for a companion robot and wrong here: a
# resting face with an open mouth looks like it is about to speak, and at
# any real dopamine level the emotional term alone crosses the renderer's
# jaw > 0.10 "draw an open mouth" threshold. Capped in BOTH modes, so the
# resting mouth is always the drawn curve and opening it always means the
# assistant is speaking. Not an expression cap: jaw_open carries no
# emotional information the smile and brow do not already carry.
JAW_REST_CAP = 0.08

AFFECT_VALUES = ("positive", "neutral", "low", "anxious", "distressed")

# Stamped into every face.toggled audit row alongside the mode, so a
# mock-patient session can always be tied to the drive it ran.
FACE_DRIVE_VERSION = "2026-08-01"

# Room audio above this RMS, as a fraction of full scale, counts as
# activity. Same floor the silence-nudge activity detector uses in
# live.html, so the two surfaces cannot disagree about when the room is
# quiet. A wrong value here is cosmetic, not dangerous: attention is a
# bounded level, so a floor set too low leaves the eyes slightly open and
# CANNOT make the face drift.
ACTIVITY_RMS_FLOOR = float(os.environ.get("FACE_ACTIVITY_RMS", "1e-4"))


def frame_is_active(pcm16: bytes) -> bool:
    """True when a mono 16-bit PCM frame carries room audio above the
    floor. Speech from ANYONE counts - patient, doctor, or the assistant
    itself (owner decision 2026-08-01). Pure Python, no numpy import on
    the live path; a frame is a few hundred samples."""
    if len(pcm16) < 2:
        return False
    total = 0
    count = len(pcm16) // 2
    for i in range(0, count * 2, 2):
        sample = int.from_bytes(pcm16[i:i + 2], "little", signed=True)
        total += sample * sample
    rms = math.sqrt(total / count) / 32768.0
    return rms >= ACTIVITY_RMS_FLOOR

# Calibrated 2026-08-01 by least-squares fit against the vendored
# FACE_WEIGHTS, to a written clinical brief for each affect, with hard
# caps on the anger and disgust muscles. See PHASE_7B_FACE_DRIVE_SPEC.md.
#
#   affect     | the face it is asked to make
#   -----------|--------------------------------------------------------
#   positive   | warm open smile, relaxed brow
#   neutral    | attentive, faint pleasantness — a listening face
#   anxious    | alert and steady: eyes a little wider, smile mostly gone
#   low        | gentle concern: inner brows up, mouth soft, warmth high
#   distressed | clear concern: brows up over the render threshold, mouth
#              | gently down, warmth highest of all
#
# Warmth (oxytocin, which drives lip_pucker — FACS AU18, "affection,
# concern") RISES as the patient's state worsens. That is the listener's
# response, not a mirror: the face leans in, it does not fall apart.
AFFECT_TARGETS: dict[str, dict[Chemical, float]] = {
    "positive": {
        Chemical.DOPAMINE: 0.65, Chemical.SEROTONIN: 0.85,
        Chemical.OXYTOCIN: 0.35, Chemical.TESTOSTERONE: 0.05,
        Chemical.CORTISOL: 0.21, Chemical.ADRENALINE: 0.20,
        Chemical.ENDORPHINS: 0.47, Chemical.GABA: 0.53},
    "neutral": {
        Chemical.DOPAMINE: 0.30, Chemical.SEROTONIN: 0.55,
        Chemical.OXYTOCIN: 0.34, Chemical.TESTOSTERONE: 0.05,
        Chemical.CORTISOL: 0.25, Chemical.ADRENALINE: 0.20,
        Chemical.ENDORPHINS: 0.28, Chemical.GABA: 0.35},
    "anxious": {
        Chemical.DOPAMINE: 0.38, Chemical.SEROTONIN: 0.55,
        Chemical.OXYTOCIN: 0.56, Chemical.TESTOSTERONE: 0.05,
        Chemical.CORTISOL: 0.44, Chemical.ADRENALINE: 0.20,
        Chemical.ENDORPHINS: 0.05, Chemical.GABA: 0.35},
    "low": {
        Chemical.DOPAMINE: 0.04, Chemical.SEROTONIN: 0.30,
        Chemical.OXYTOCIN: 0.54, Chemical.TESTOSTERONE: 0.05,
        Chemical.CORTISOL: 0.45, Chemical.ADRENALINE: 0.20,
        Chemical.ENDORPHINS: 0.46, Chemical.GABA: 0.35},
    "distressed": {
        Chemical.DOPAMINE: 0.11, Chemical.SEROTONIN: 0.30,
        Chemical.OXYTOCIN: 0.72, Chemical.TESTOSTERONE: 0.05,
        Chemical.CORTISOL: 0.54, Chemical.ADRENALINE: 0.20,
        Chemical.ENDORPHINS: 0.21, Chemical.GABA: 0.50},
}

# Resting baselines. These matter for more than decay: three muscles read
# the DEFICIT below baseline (sadness only appears when dopamine and
# serotonin fall below the resting level), so the baselines are part of
# the calibration and must match what the fit assumed.
PRESET_BASELINES = {
    "dopamine": 0.30, "serotonin": 0.55, "oxytocin": 0.30,
    "testosterone": 0.05, "cortisol": 0.15, "adrenaline": 0.10,
    "endorphins": 0.25, "gaba": 0.55,
}

BANDED_MUSCLES = frozenset({
    "eyelid_upper_raise",
    "cheek_raise",
    "lip_corner_pull",
    # Added 2026-08-01: with the drive corrected, pinning these two left
    # the clinical arm able to express warmth but not concern — which is
    # the original defect in miniature. Banded, not free: the arm still
    # limits how much sadness a clinical face may show. OWNER DECISION,
    # one line to revert.
    "brow_inner_raise",
    "lip_corner_depress",
})

PINNED_MUSCLES = frozenset({
    "brow_outer_raise",
    "brow_lower",
    "eyelid_lower_tighten",
    "nose_wrinkle",
    "jaw_open",
    "lip_pucker",
    "lip_press",
})


def load_preset(name: str = "clinical") -> tuple[SeedChemistry, float]:
    with open(CONFIG_DIR / "personalities.toml", "rb") as f:
        presets = tomllib.load(f)
    preset = dict(presets[name])
    preset["baselines"] = {**PRESET_BASELINES, **(preset.get("baselines") or {})}
    return SeedChemistry.from_dict(preset), float(preset.get("default_affinity", 1.0))


class FaceDriver:
    def __init__(self, clock: Clock | None = None,
                 band: float | None = None,
                 tick_hz: float | None = None,
                 mode: str | None = None) -> None:
        self._clock = clock or RealClock()
        mode = mode or FACE_EXPRESSION_MODE
        if mode not in EXPRESSION_MODES:
            logger.warning("Unknown FACE_EXPRESSION_MODE %r - running full", mode)
            mode = "full"
        self.mode = mode
        seed, self._affinity = load_preset("clinical" if mode == "clinical"
                                           else "default")
        # Baselines are ours in both modes: the deficit-driven muscles are
        # measured against them, so they are calibration, not personality.
        for name, value in PRESET_BASELINES.items():
            seed.baselines[Chemical.from_string(name)] = value
        self.engine = NeurochemicalEngine(clock=self._clock, seed=seed)
        self.band = FACE_BAND if band is None else band
        self.tick_hz = FACE_TICK_HZ if tick_hz is None else tick_hz

        self._affect = "neutral"
        # The ramped chemistry actually being held, starting at neutral.
        self._held = dict(AFFECT_TARGETS["neutral"])
        self._attention = 0.0
        self._last_activity = float("-inf")
        self._last_tick = self._clock.now()
        self._stopped = False
        self._apply()
        self._neutral = project_face(self.engine.state).as_dict()

    # ---- events -------------------------------------------------------

    def on_consultation_started(self) -> None:
        """Kept for the call site. There is nothing to inject: the face
        opens at the neutral target, which is already its resting state."""

    def on_speech_activity(self) -> None:
        """The room is audible — either speaker, and the assistant's own
        voice too. Called from the live path when a frame's RMS clears the
        silence floor. Idempotent within a frame; the attention level does
        the smoothing, so there is no rate limit to get wrong."""
        self._last_activity = self._clock.now()

    # Kept so existing call sites keep working; speech from the assistant
    # is room activity like any other.
    def on_system_speech_started(self) -> None:
        self.on_speech_activity()

    def on_system_speech_ended(self) -> None:
        self.on_speech_activity()

    def on_affect(self, affect: str | None) -> None:
        self._affect = affect if affect in AFFECT_VALUES else "neutral"

    def stop(self) -> None:
        self._stopped = True

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def attention(self) -> float:
        return self._attention

    # ---- state --------------------------------------------------------

    def advance(self, dt: float | None = None) -> None:
        now = self._clock.now()
        if dt is None:
            dt = max(0.0, now - self._last_tick)
        self._last_tick = now
        if dt <= 0:
            return

        active = (now - self._last_activity) <= ACTIVITY_HOLD_S
        tau = ATTENTION_ATTACK_S if active else ATTENTION_RELEASE_S
        k = 1.0 - math.exp(-dt / tau)
        self._attention += ((1.0 if active else 0.0) - self._attention) * k

        target = AFFECT_TARGETS[self._affect]
        kr = 1.0 - math.exp(-dt / AFFECT_RAMP_S)
        for chem, want in target.items():
            self._held[chem] += (want - self._held[chem]) * kr
        self._apply()

    def _apply(self) -> None:
        """Write the held chemistry into the engine's state. The engine is
        the state holder and the projection's input; its decay and
        interaction dynamics are deliberately unused (see module docstring)."""
        for chem, value in self._held.items():
            if chem is Chemical.ADRENALINE:
                value = value + ATTENTION_GAIN * self._attention
            self.engine.state.set(chem, value)

    def payload(self) -> dict:
        if self.mode == "full":
            p = face_payload(project_face(self.engine.state))
            p["muscles"]["jaw_open"] = min(p["muscles"]["jaw_open"], JAW_REST_CAP)
            return p
        raw = project_face(self.engine.state).as_dict()
        muscles: dict[str, float] = {}
        for muscle, value in raw.items():
            neutral = self._neutral[muscle]
            if muscle in PINNED_MUSCLES:
                muscles[muscle] = neutral
            else:
                muscles[muscle] = min(max(value, neutral - self.band),
                                      neutral + self.band)
        muscles["jaw_open"] = min(muscles["jaw_open"], JAW_REST_CAP)
        return {
            "muscles": {k: round(v, 4) for k, v in muscles.items()},
            "mood": {"color": DEFAULT_MOOD_COLOR, "intensity": 0.2},
        }

    async def run(self, send) -> None:
        interval = 1.0 / self.tick_hz
        while not self._stopped:
            self.advance()
            await send({"type": "face_state", **self.payload()})
            await asyncio.sleep(interval)
