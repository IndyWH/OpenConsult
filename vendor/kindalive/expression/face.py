"""FaceProjection — derive a 12-muscle facial expression from chemical state.

This is a second projection from `ChemicalState`, parallel to
`EmotionProjection`. Where the emotion vector quantizes the chemistry
through 8 high-level moods, the face vector keeps everything continuous
and animatable: each muscle is a weighted linear combination of
chemicals, clamped to [0.0, 1.0]. The names map roughly to FACS Action
Units so a future driver for physical actuators can hand them straight
through.

The weights are tuned for *expressive robot behavior*, not biological
accuracy. They are exposed as `FACE_WEIGHTS` so UIs can build "why
does the face look this way?" breakdowns without duplicating formulas
(mirroring the `EMOTION_WEIGHTS` pattern).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from vendor.kindalive.engine.chemicals import Chemical, ChemicalState


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class FaceTerm:
    """One weighted term contributing to a facial muscle.

    If ``inverted`` is True, the term contributes the *deficit* relative
    to the chemical's baseline: ``max(0, baseline - level)``. Mirrors
    `EmotionTerm` semantics — a face only "frowns from sadness" when
    dopamine/serotonin fall below the robot's resting level.
    """

    chemical: Chemical
    weight: float
    inverted: bool = False

    def evaluate(self, state: ChemicalState) -> float:
        level = state.get(self.chemical)
        if self.inverted:
            deficit = max(0.0, state.baseline(self.chemical) - level)
            return self.weight * deficit
        return self.weight * level


@dataclass(frozen=True)
class FaceState:
    """A 12-parameter snapshot of facial muscle activations in [0.0, 1.0].

    Parameter names are derived from FACS Action Units so the same vector
    can drive an SVG, a physical robot face, or a blendshape model later.
    """

    brow_inner_raise: float       # AU1  — sadness, concern
    brow_outer_raise: float       # AU2  — surprise, fear
    brow_lower: float             # AU4  — anger, focus
    eyelid_upper_raise: float     # AU5  — alertness, surprise
    eyelid_lower_tighten: float   # AU7  — anger, anxiety
    cheek_raise: float            # AU6  — Duchenne joy
    nose_wrinkle: float           # AU9  — disgust, anger
    lip_corner_pull: float        # AU12 — smile
    lip_corner_depress: float     # AU15 — frown
    jaw_open: float               # AU26 — surprise, laughter
    lip_pucker: float             # AU18 — affection, concern
    lip_press: float              # AU24 — restraint, anger

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    def top_n(self, n: int = 3) -> list[tuple[str, float]]:
        """Return the top-n most-activated muscles, sorted descending."""
        items = sorted(self.as_dict().items(), key=lambda kv: kv[1], reverse=True)
        return items[:n]


# Single source of truth for facial muscle weights. The `face.toml`
# config file mirrors these values for documentation; the Python module
# is authoritative (the same convention `EMOTION_WEIGHTS` uses).
FACE_WEIGHTS: dict[str, list[FaceTerm]] = {
    "brow_inner_raise": [
        FaceTerm(Chemical.CORTISOL, 0.40),
        FaceTerm(Chemical.DOPAMINE, 0.35, inverted=True),
        FaceTerm(Chemical.SEROTONIN, 0.25, inverted=True),
        FaceTerm(Chemical.GABA, -0.10),
    ],
    "brow_outer_raise": [
        FaceTerm(Chemical.ADRENALINE, 0.50),
        FaceTerm(Chemical.DOPAMINE, 0.20),
        FaceTerm(Chemical.GABA, -0.10),
    ],
    "brow_lower": [
        FaceTerm(Chemical.TESTOSTERONE, 0.35),
        FaceTerm(Chemical.CORTISOL, 0.30),
        FaceTerm(Chemical.ADRENALINE, 0.20),
        FaceTerm(Chemical.GABA, -0.20),
        FaceTerm(Chemical.SEROTONIN, -0.10),
    ],
    "eyelid_upper_raise": [
        FaceTerm(Chemical.ADRENALINE, 0.55),
        FaceTerm(Chemical.CORTISOL, 0.25),
        FaceTerm(Chemical.DOPAMINE, 0.15),
        FaceTerm(Chemical.GABA, -0.20),
    ],
    "eyelid_lower_tighten": [
        FaceTerm(Chemical.CORTISOL, 0.35),
        FaceTerm(Chemical.TESTOSTERONE, 0.25),
        FaceTerm(Chemical.ADRENALINE, 0.20),
        FaceTerm(Chemical.GABA, -0.15),
    ],
    "cheek_raise": [
        FaceTerm(Chemical.DOPAMINE, 0.45),
        FaceTerm(Chemical.ENDORPHINS, 0.30),
        FaceTerm(Chemical.OXYTOCIN, 0.20),
        FaceTerm(Chemical.CORTISOL, -0.20),
    ],
    "nose_wrinkle": [
        FaceTerm(Chemical.TESTOSTERONE, 0.30),
        FaceTerm(Chemical.CORTISOL, 0.30),
        FaceTerm(Chemical.ADRENALINE, 0.15),
        FaceTerm(Chemical.GABA, -0.20),
    ],
    "lip_corner_pull": [
        FaceTerm(Chemical.DOPAMINE, 0.40),
        FaceTerm(Chemical.ENDORPHINS, 0.30),
        FaceTerm(Chemical.SEROTONIN, 0.20),
        FaceTerm(Chemical.OXYTOCIN, 0.15),
        FaceTerm(Chemical.CORTISOL, -0.25),
    ],
    "lip_corner_depress": [
        FaceTerm(Chemical.CORTISOL, 0.45),
        FaceTerm(Chemical.DOPAMINE, 0.35, inverted=True),
        FaceTerm(Chemical.SEROTONIN, 0.25, inverted=True),
        FaceTerm(Chemical.ENDORPHINS, -0.15),
    ],
    "jaw_open": [
        FaceTerm(Chemical.ADRENALINE, 0.40),
        FaceTerm(Chemical.DOPAMINE, 0.25),
        FaceTerm(Chemical.ENDORPHINS, 0.15),
        FaceTerm(Chemical.GABA, -0.15),
        FaceTerm(Chemical.CORTISOL, -0.10),
    ],
    "lip_pucker": [
        FaceTerm(Chemical.OXYTOCIN, 0.50),
        FaceTerm(Chemical.ENDORPHINS, 0.20),
        FaceTerm(Chemical.CORTISOL, -0.10),
    ],
    "lip_press": [
        FaceTerm(Chemical.TESTOSTERONE, 0.35),
        FaceTerm(Chemical.CORTISOL, 0.25),
        FaceTerm(Chemical.GABA, 0.15),
        FaceTerm(Chemical.ENDORPHINS, -0.10),
    ],
}


class FaceProjection:
    """Stateless projection from ChemicalState to FaceState."""

    @staticmethod
    def compute(state: ChemicalState) -> FaceState:
        values: dict[str, float] = {}
        for muscle, terms in FACE_WEIGHTS.items():
            raw = sum(term.evaluate(state) for term in terms)
            values[muscle] = _clamp(raw)
        return FaceState(**values)


def project_face(state: ChemicalState) -> FaceState:
    """Convenience function — `FaceProjection.compute(state)`."""
    return FaceProjection.compute(state)
