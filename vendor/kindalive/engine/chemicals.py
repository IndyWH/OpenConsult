"""Chemical enum and ChemicalState — the core data model.

All concentrations are clamped to [0.0, 1.0].
"""

from __future__ import annotations

from enum import Enum


class Chemical(Enum):
    """The 8 neurochemicals in the simulation.

    Enum names are UPPERCASE. Values are lowercase strings used in
    LLM-facing interfaces, config files, and JSON serialization.
    """

    DOPAMINE = "dopamine"
    SEROTONIN = "serotonin"
    OXYTOCIN = "oxytocin"
    TESTOSTERONE = "testosterone"
    CORTISOL = "cortisol"
    ADRENALINE = "adrenaline"
    ENDORPHINS = "endorphins"
    GABA = "gaba"

    @classmethod
    def from_string(cls, name: str) -> Chemical:
        """Case-insensitive lookup by name or value."""
        lower = name.lower()
        for member in cls:
            if member.value == lower or member.name.lower() == lower:
                return member
        raise ValueError(f"Unknown chemical: {name!r}")


# Species-default baselines and half-lives (seconds).
# These are the "generic robot" values.
SPECIES_DEFAULTS: dict[Chemical, dict[str, float]] = {
    Chemical.DOPAMINE:     {"baseline": 0.3, "half_life": 1200.0},    # 20 min
    Chemical.SEROTONIN:    {"baseline": 0.5, "half_life": 14400.0},   # 4 hrs
    Chemical.OXYTOCIN:     {"baseline": 0.2, "half_life": 1800.0},    # 30 min
    Chemical.TESTOSTERONE:  {"baseline": 0.3, "half_life": 7200.0},   # 2 hrs
    Chemical.CORTISOL:     {"baseline": 0.2, "half_life": 3600.0},    # 1 hr
    Chemical.ADRENALINE:   {"baseline": 0.1, "half_life": 180.0},     # 3 min
    Chemical.ENDORPHINS:   {"baseline": 0.2, "half_life": 1800.0},    # 30 min
    Chemical.GABA:         {"baseline": 0.4, "half_life": 3600.0},    # 1 hr
}


class ChemicalState:
    """Mutable vector of 8 chemical concentrations with baselines and half-lives."""

    def __init__(
        self,
        baselines: dict[Chemical, float] | None = None,
        half_lives: dict[Chemical, float] | None = None,
    ) -> None:
        # Resolve baselines: explicit > species default
        self._baselines: dict[Chemical, float] = {}
        self._half_lives: dict[Chemical, float] = {}
        self._levels: dict[Chemical, float] = {}

        for chem in Chemical:
            defaults = SPECIES_DEFAULTS[chem]
            bl = (baselines or {}).get(chem, defaults["baseline"])
            hl = (half_lives or {}).get(chem, defaults["half_life"])
            self._baselines[chem] = bl
            self._half_lives[chem] = hl
            self._levels[chem] = bl  # start at baseline

    def get(self, chem: Chemical) -> float:
        return self._levels[chem]

    def set(self, chem: Chemical, value: float) -> None:
        self._levels[chem] = max(0.0, min(1.0, value))

    def baseline(self, chem: Chemical) -> float:
        return self._baselines[chem]

    def set_baseline(self, chem: Chemical, value: float) -> None:
        self._baselines[chem] = max(0.1, min(0.5, value))

    def half_life(self, chem: Chemical) -> float:
        return self._half_lives[chem]

    def clamp_all(self) -> None:
        """Clamp all levels to [0.0, 1.0]."""
        for chem in Chemical:
            self._levels[chem] = max(0.0, min(1.0, self._levels[chem]))

    def apply_decay(self, chem: Chemical, dt: float) -> None:
        """Decay a single chemical toward its baseline using true half-life.

        Formula: level += (baseline - level) * (1 - 2^(-dt / half_life))
        """
        hl = self._half_lives[chem]
        level = self._levels[chem]
        bl = self._baselines[chem]
        factor = 1.0 - (2.0 ** (-dt / hl))
        self._levels[chem] = level + (bl - level) * factor

    def decay_all(self, dt: float) -> None:
        """Apply decay to all chemicals."""
        for chem in Chemical:
            self.apply_decay(chem, dt)

    def as_dict(self) -> dict[str, float]:
        """Return levels as {lowercase_name: value} dict."""
        return {chem.value: self._levels[chem] for chem in Chemical}

    def baselines_as_dict(self) -> dict[str, float]:
        return {chem.value: self._baselines[chem] for chem in Chemical}

    def copy(self) -> ChemicalState:
        """Create a deep copy of this state."""
        state = ChemicalState.__new__(ChemicalState)
        state._baselines = dict(self._baselines)
        state._half_lives = dict(self._half_lives)
        state._levels = dict(self._levels)
        return state
