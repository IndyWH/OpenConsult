"""ChemicalImpulse — the unit of change applied to the engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from vendor.kindalive.engine.chemicals import Chemical


@dataclass
class ChemicalImpulse:
    """A discrete change to a chemical level.

    - delta: signed magnitude [-0.5, +0.5]
    - duration_seconds: 0 = instant spike, >0 = sustained drip over time
    - source_id: for saturation tracking (e.g., "sports:goal:BOS_vs_MTL")
    - source_label: human-readable (e.g., "Bruins goal — leads 3-2")
    """

    chemical: Chemical
    delta: float
    duration_seconds: float = 0.0
    source_id: str = ""
    source_label: str = ""


# Convenience alias
Impulse = ChemicalImpulse


@dataclass
class ActiveSustainedImpulse:
    """Tracks a sustained impulse that is currently dripping."""

    impulse: ChemicalImpulse
    remaining_seconds: float = 0.0
    rate_per_second: float = 0.0

    @classmethod
    def from_impulse(cls, imp: ChemicalImpulse) -> ActiveSustainedImpulse:
        return cls(
            impulse=imp,
            remaining_seconds=imp.duration_seconds,
            rate_per_second=imp.delta / imp.duration_seconds,
        )
