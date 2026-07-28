"""EmotionProjection — derive emotions from chemical state.

Emotions are computed, never stored. Each is a weighted linear
combination of chemical levels, clamped to [0.0, 1.0].

The weights are exposed as `EMOTION_WEIGHTS` so UIs can build
"why do I feel this way?" breakdowns without duplicating the formulas.
"""

from __future__ import annotations

from dataclasses import dataclass

from vendor.kindalive.engine.chemicals import Chemical, ChemicalState
from vendor.kindalive.emotions.emotion_vector import EmotionVector


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class EmotionTerm:
    """One weighted term in an emotion's linear combination.

    If ``inverted`` is True, the term contributes the *deficit* relative to
    the chemical's baseline: ``max(0, baseline - level)``. This is used for
    sadness, which activates on the absence of positive chemicals — a robot
    is only sad when dopamine/serotonin/oxytocin fall BELOW their typical
    level, not whenever they are less than 1.0.
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


# Single source of truth for emotion weights. UIs read this to show
# the formula breakdown; EmotionProjection.compute() evaluates it.
EMOTION_WEIGHTS: dict[str, list[EmotionTerm]] = {
    "happiness": [
        EmotionTerm(Chemical.DOPAMINE, 0.35),
        EmotionTerm(Chemical.SEROTONIN, 0.35),
        EmotionTerm(Chemical.ENDORPHINS, 0.15),
        EmotionTerm(Chemical.OXYTOCIN, 0.15),
        EmotionTerm(Chemical.CORTISOL, -0.20),
    ],
    "excitement": [
        EmotionTerm(Chemical.ADRENALINE, 0.45),
        EmotionTerm(Chemical.DOPAMINE, 0.35),
        EmotionTerm(Chemical.TESTOSTERONE, 0.20),
    ],
    "anger": [
        EmotionTerm(Chemical.TESTOSTERONE, 0.35),
        EmotionTerm(Chemical.CORTISOL, 0.35),
        EmotionTerm(Chemical.ADRENALINE, 0.30),
        EmotionTerm(Chemical.GABA, -0.30),
    ],
    "calm": [
        EmotionTerm(Chemical.GABA, 0.45),
        EmotionTerm(Chemical.SEROTONIN, 0.35),
        EmotionTerm(Chemical.OXYTOCIN, 0.20),
        EmotionTerm(Chemical.ADRENALINE, -0.25),
        EmotionTerm(Chemical.CORTISOL, -0.15),
    ],
    "bonding": [
        EmotionTerm(Chemical.OXYTOCIN, 0.50),
        EmotionTerm(Chemical.SEROTONIN, 0.30),
        EmotionTerm(Chemical.ENDORPHINS, 0.20),
    ],
    "anxiety": [
        EmotionTerm(Chemical.CORTISOL, 0.40),
        EmotionTerm(Chemical.ADRENALINE, 0.35),
        EmotionTerm(Chemical.TESTOSTERONE, 0.25),
        EmotionTerm(Chemical.GABA, -0.35),
        EmotionTerm(Chemical.SEROTONIN, -0.15),
    ],
    "sadness": [
        EmotionTerm(Chemical.CORTISOL, 0.60),
        EmotionTerm(Chemical.DOPAMINE, 0.50, inverted=True),
        EmotionTerm(Chemical.SEROTONIN, 0.40, inverted=True),
        EmotionTerm(Chemical.OXYTOCIN, 0.40, inverted=True),
    ],
    "euphoria": [
        EmotionTerm(Chemical.DOPAMINE, 0.30),
        EmotionTerm(Chemical.ENDORPHINS, 0.30),
        EmotionTerm(Chemical.ADRENALINE, 0.20),
        EmotionTerm(Chemical.OXYTOCIN, 0.20),
    ],
}


class EmotionProjection:
    """Stateless projection from ChemicalState to EmotionVector."""

    @staticmethod
    def compute(state: ChemicalState) -> EmotionVector:
        values: dict[str, float] = {}
        for emotion, terms in EMOTION_WEIGHTS.items():
            raw = sum(term.evaluate(state) for term in terms)
            values[emotion] = _clamp(raw)
        return EmotionVector(**values)
