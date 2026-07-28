"""EmotionVector — the 8-emotion output of the projection layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmotionVector:
    """Immutable snapshot of 8 computed emotions, all in [0.0, 1.0]."""

    happiness: float
    excitement: float
    anger: float
    calm: float
    bonding: float
    anxiety: float
    sadness: float
    euphoria: float

    def as_dict(self) -> dict[str, float]:
        return {
            "happiness": self.happiness,
            "excitement": self.excitement,
            "anger": self.anger,
            "calm": self.calm,
            "bonding": self.bonding,
            "anxiety": self.anxiety,
            "sadness": self.sadness,
            "euphoria": self.euphoria,
        }

    def dominant(self) -> tuple[str, float]:
        """Return (name, value) of the highest emotion."""
        d = self.as_dict()
        name = max(d, key=d.get)  # type: ignore[arg-type]
        return name, d[name]

    def top_n(self, n: int = 3) -> list[tuple[str, float]]:
        """Return the top N emotions sorted by value descending."""
        d = self.as_dict()
        return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]
