"""Phase 7b: the impulse-mapping layer between consultation events and the
vendored kindalive engine — deterministic, hard-capped, GPU-free.

This module owns EVERYTHING between what happens in the room and what the
face renderer is sent. The vendored engine (vendor/kindalive/) is used
as-is; the [clinical] preset in its personalities.toml expresses the
intent, and the per-muscle policy below enforces it — belt and braces,
PHASE_7B_KINDALIVE.md decision 3. Nothing here calls a model, loads a
model, or draws randomness: the same event sequence always produces the
same face states (the clock is injectable; tests use ManualClock).

THE URGENCY ALARM IS DELIBERATELY NOT WIRED TO THE FACE. The face is a
listening presence for the patient; it must not signal clinical state to
them — an alarmed face would be the system communicating urgency to the
patient before the doctor has decided anything, which hard rule 1 exists
to prevent by voice and would be no better by eyebrow. Do not add it
later as an easy win.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tomllib
from pathlib import Path

from vendor.kindalive.engine.chemicals import Chemical
from vendor.kindalive.engine.clock import Clock, RealClock
from vendor.kindalive.engine.impulse import ChemicalImpulse
from vendor.kindalive.engine.neurochemical_engine import NeurochemicalEngine
from vendor.kindalive.engine.seed_chemistry import SeedChemistry
from vendor.kindalive.expression.face import project_face
from vendor.kindalive.expression.face_3d import DEFAULT_MOOD_COLOR

logger = logging.getLogger("consultation-ai.face")

CONFIG_DIR = Path(__file__).resolve().parents[1] / "vendor" / "kindalive" / "config"

PRESET = "clinical"

# Small positive range above neutral allowed for the banded muscles.
# Conservative default; env-tunable so the calibration pass can widen it
# from real use rather than from a guess.
FACE_BAND = float(os.environ.get("FACE_BAND", "0.15"))

# Face states are computed and sent at this rate while the face is on.
FACE_TICK_HZ = float(os.environ.get("FACE_TICK_HZ", "5"))

# Patient-audio impulses are injected at most this often while frames
# arrive — frames come 4×/s and per-frame injection would just saturate
# the engine's source dampening immediately.
AUDIO_INJECT_INTERVAL_S = 2.0

# ---------------------------------------------------------------------------
# The per-muscle policy — a classification, not a symmetric band.
#
# Owner's rule: negative emotions must be UNEXPRESSIBLE, not merely damped.
# Anger, frustration, disgust, fear and distress present as a neutral face.
#
# Classification of all twelve muscles, derived from the vendored
# face.toml / FACE_WEIGHTS (which chemicals drive each muscle) and the
# emotion projection (which emotions those chemicals mean — anger is
# testosterone+cortisol+adrenaline, anxiety adds low GABA, sadness is
# cortisol plus dopamine/serotonin deficits). Anything ambiguous is
# PINNED; loosening any row is the calibration pass, with the owner.
#
#   muscle               | AU   | reads as (upstream comment) | class  | why
#   ---------------------|------|-----------------------------|--------|----
#   brow_inner_raise     | AU1  | sadness, concern            | PINNED | empathic concern sits next to sadness — whether the face is allowed a little of it is the owner's clinical call, so it starts pinned
#   brow_outer_raise     | AU2  | surprise, fear              | PINNED | fear/distress
#   brow_lower           | AU4  | anger, focus                | PINNED | anger
#   eyelid_upper_raise   | AU5  | alertness, surprise         | BANDED | attention — the one arousal signal a listening presence needs
#   eyelid_lower_tighten | AU7  | anger, anxiety              | PINNED | anger/anxiety
#   cheek_raise          | AU6  | Duchenne joy                | BANDED | warmth
#   nose_wrinkle         | AU9  | disgust, anger              | PINNED | disgust
#   lip_corner_pull      | AU12 | smile                       | BANDED | warmth
#   lip_corner_depress   | AU15 | frown                       | PINNED | sadness/distress
#   jaw_open             | AU26 | surprise, laughter          | PINNED | ambiguous (laughter is not clinical); the TTS mouth flap is UNAFFECTED — face3d.js layers setSpeaking's flap on top of jaw_open client-side
#   lip_pucker           | AU18 | affection, concern          | PINNED | ambiguous (affection/concern both)
#   lip_press            | AU24 | restraint, anger            | PINNED | anger
#
# FREE class — purely mechanical liveliness: blink, breathing, eye
# saccades, and the mouth flap while speaking. None of these is a server
# muscle at all: face3d.js self-animates them and setSpeaking drives the
# flap, so they are untouched by construction — the server never sends
# them and cannot cap them.
# ---------------------------------------------------------------------------

BANDED_MUSCLES = frozenset({
    "eyelid_upper_raise",
    "cheek_raise",
    "lip_corner_pull",
})

PINNED_MUSCLES = frozenset({
    "brow_inner_raise",
    "brow_outer_raise",
    "brow_lower",
    "eyelid_lower_tighten",
    "nose_wrinkle",
    "lip_corner_depress",
    "jaw_open",
    "lip_pucker",
    "lip_press",
})


def load_preset(name: str = PRESET) -> tuple[SeedChemistry, float]:
    """(SeedChemistry, default_affinity) from the vendored personalities.toml.

    The vendored TOML is this project's config source of record — the
    upstream Python presets module was deliberately not vendored.
    """
    with open(CONFIG_DIR / "personalities.toml", "rb") as f:
        presets = tomllib.load(f)
    preset = presets[name]
    return SeedChemistry.from_dict(preset), float(preset.get("default_affinity", 1.0))


# Event → impulse mapping. Every number is a conservative first guess for
# the calibration pass — mild attention and engagement while the patient
# talks, calm baseline otherwise. Deltas are scaled by the preset's
# default_affinity before injection (0.4 under [clinical]).
EVENT_IMPULSES: dict[str, list[tuple[Chemical, float, float]]] = {
    # (chemical, delta, duration_seconds); duration 0 = instant spike
    "consultation_started": [
        (Chemical.DOPAMINE, 0.10, 0.0),   # settle into engagement
        (Chemical.OXYTOCIN, 0.08, 0.0),   # resting warmth
    ],
    "patient_audio": [
        (Chemical.DOPAMINE, 0.04, 2.0),   # attention while they talk
        (Chemical.OXYTOCIN, 0.02, 2.0),   # listening warmth
    ],
    "system_speech_started": [
        (Chemical.DOPAMINE, 0.02, 0.0),   # attentive while asking
    ],
    "system_speech_ended": [
        (Chemical.OXYTOCIN, 0.02, 0.0),   # a warm beat, handing back
    ],
}


class FaceDriver:
    """One engine instance for one live session, created only when the
    face is toggled on. Event methods are called from EXISTING code paths
    (the WS frame loop and the speak-window handlers) — this layer adds no
    detection of its own.
    """

    def __init__(self, clock: Clock | None = None,
                 band: float | None = None,
                 tick_hz: float | None = None) -> None:
        self._clock = clock or RealClock()
        seed, self._affinity = load_preset()
        self.engine = NeurochemicalEngine(clock=self._clock, seed=seed)
        self.band = FACE_BAND if band is None else band
        self.tick_hz = FACE_TICK_HZ if tick_hz is None else tick_hz
        # Neutral is the [clinical] preset's resting face: the muscle
        # values projected from baseline chemistry before any impulse.
        # Pinned muscles are held at exactly these values, so at rest the
        # policy changes nothing and under provocation they cannot move.
        self._neutral = project_face(self.engine.state).as_dict()
        self._last_advance = self._clock.now()
        self._last_audio_inject = float("-inf")
        self._stopped = False

    # ---- events (deterministic; no detection, no model calls) ----

    def _inject(self, event: str) -> None:
        for chemical, delta, duration in EVENT_IMPULSES[event]:
            self.engine.apply_impulse(ChemicalImpulse(
                chemical=chemical,
                delta=delta * self._affinity,
                duration_seconds=duration,
                source_id=f"face:{event}",
            ))

    def on_consultation_started(self) -> None:
        self._inject("consultation_started")

    def on_patient_audio(self) -> None:
        """Called as audio frames arrive on the live path (~4/s);
        rate-limited here so the engine sees a steady mild signal, not a
        firehose. The caller skips frames inside a speaking window — audio
        arriving while the system talks is mostly our own echo, not the
        patient."""
        now = self._clock.now()
        if now - self._last_audio_inject < AUDIO_INJECT_INTERVAL_S:
            return
        self._last_audio_inject = now
        self._inject("patient_audio")

    def on_system_speech_started(self) -> None:
        self._inject("system_speech_started")

    def on_system_speech_ended(self) -> None:
        self._inject("system_speech_ended")

    def stop(self) -> None:
        """Consultation stopped or face toggled off: the tick loop exits
        and this driver is discarded — no parting impulse, the face simply
        stops being computed."""
        self._stopped = True

    @property
    def stopped(self) -> bool:
        return self._stopped

    # ---- state ----

    def advance(self, dt: float | None = None) -> None:
        """Advance the chemistry. With dt=None, advances by the clock time
        elapsed since the last advance (the tick loop's mode); tests pass
        dt explicitly after moving a ManualClock."""
        now = self._clock.now()
        if dt is None:
            dt = max(0.0, now - self._last_advance)
        self._last_advance = now
        if dt > 0:
            self.engine.advance(dt)

    def payload(self) -> dict:
        """The setTargets payload with the per-muscle policy applied to the
        engine's output BEFORE anything is emitted. This is the only exit;
        there is no uncapped path to the client."""
        raw = project_face(self.engine.state).as_dict()
        muscles: dict[str, float] = {}
        for muscle, value in raw.items():
            neutral = self._neutral[muscle]
            if muscle in PINNED_MUSCLES:
                muscles[muscle] = neutral
            else:  # banded: warmth/attention may rise a little, never fall
                muscles[muscle] = min(max(value, neutral), neutral + self.band)
        # Same shape as the vendored face_payload (the setTargets
        # contract), built from the CAPPED values — the uncapped
        # projection never leaves this function. Mood accent: default
        # colour, low fixed intensity; recolouring to the app palette is
        # the styling pass (DESIGN_SPEC.md not yet available), and mood is
        # not allowed to carry emotional range regardless.
        return {
            "muscles": {k: round(v, 4) for k, v in muscles.items()},
            "mood": {"color": DEFAULT_MOOD_COLOR, "intensity": 0.2},
        }

    # ---- tick loop ----

    async def run(self, send) -> None:
        """Compute and hand a face_state payload to `send` at tick_hz until
        stopped. `send` is the WebSocket layer's coroutine; this loop owns
        timing only — it never touches the socket beyond calling it."""
        interval = 1.0 / self.tick_hz
        while not self._stopped:
            self.advance()
            await send({"type": "face_state", **self.payload()})
            await asyncio.sleep(interval)
