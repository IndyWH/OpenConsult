"""SeedChemistry — configurable baseline neurochemistry for a robot.

Three-layer model: Species Defaults → Seed Chemistry → Runtime Drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vendor.kindalive.engine.chemicals import Chemical, SPECIES_DEFAULTS


@dataclass
class SeedChemistry:
    """Full baseline configuration for a robot's resting neurochemistry."""

    baselines: dict[Chemical, float] = field(default_factory=dict)
    half_life_multipliers: dict[Chemical, float] = field(default_factory=dict)
    interaction_scale: float = 1.0

    @classmethod
    def from_species_defaults(cls) -> SeedChemistry:
        """All 8 chemicals at species default baselines."""
        return cls(
            baselines={
                chem: info["baseline"]
                for chem, info in SPECIES_DEFAULTS.items()
            },
        )

    @classmethod
    def from_dict(cls, overrides: dict[str, Any]) -> SeedChemistry:
        """Start from species defaults, apply overrides.

        Accepts:
            baselines: {chemical_name: float}
            half_life_multipliers: {chemical_name: float}
            interaction_scale: float
        """
        seed = cls.from_species_defaults()

        for name, value in (overrides.get("baselines") or {}).items():
            chem = Chemical.from_string(str(name))
            seed.baselines[chem] = float(value)

        for name, mult in (overrides.get("half_life_multipliers") or {}).items():
            chem = Chemical.from_string(str(name))
            seed.half_life_multipliers[chem] = float(mult)

        seed.interaction_scale = float(
            overrides.get("interaction_scale", 1.0)
        )
        return seed

    def effective_half_life(self, chem: Chemical) -> float:
        """Return the half-life for a chemical, applying any multiplier."""
        base_hl = SPECIES_DEFAULTS[chem]["half_life"]
        mult = self.half_life_multipliers.get(chem, 1.0)
        return base_hl * mult

    def to_dict(self) -> dict[str, object]:
        """Serialize for persistence."""
        result: dict[str, object] = {
            "baselines": {chem.value: val for chem, val in self.baselines.items()},
            "interaction_scale": self.interaction_scale,
        }
        if self.half_life_multipliers:
            result["half_life_multipliers"] = {
                chem.value: val
                for chem, val in self.half_life_multipliers.items()
            }
        return result
