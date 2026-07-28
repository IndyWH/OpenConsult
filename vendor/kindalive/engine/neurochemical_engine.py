"""NeurochemicalEngine — core simulation loop.

Manages chemical state, applies impulses, runs decay + interactions
with sub-stepping for numerical stability.
"""

from __future__ import annotations

import time as _time
from collections import defaultdict

from vendor.kindalive.engine.chemicals import Chemical, ChemicalState
from vendor.kindalive.engine.clock import Clock, ManualClock
from vendor.kindalive.engine.impulse import ActiveSustainedImpulse, ChemicalImpulse
from vendor.kindalive.engine.interactions import apply_interactions
from vendor.kindalive.engine.seed_chemistry import SeedChemistry

# Sub-step ceiling for numerical stability
MAX_SUB_STEP = 0.5  # seconds

# Saturation sliding window
SATURATION_WINDOW = 300.0  # 5 minutes
SATURATION_DAMPENING = 0.3


class NeurochemicalEngine:
    """The core simulation engine.

    Maintains ChemicalState, applies impulses (instant + sustained),
    runs decay and cross-chemical interactions with sub-stepping.
    """

    def __init__(
        self,
        clock: Clock | None = None,
        seed: SeedChemistry | None = None,
    ) -> None:
        self._clock = clock or ManualClock()
        self._seed = seed or SeedChemistry.from_species_defaults()

        # Build half-lives dict from seed
        half_lives = {
            chem: self._seed.effective_half_life(chem)
            for chem in Chemical
        }

        self.state = ChemicalState(
            baselines=dict(self._seed.baselines),
            half_lives=half_lives,
        )

        self._sustained: list[ActiveSustainedImpulse] = []
        self._saturation: dict[str, list[float]] = defaultdict(list)
        self._last_tick: float = self._clock.now()

    @property
    def seed(self) -> SeedChemistry:
        return self._seed

    @property
    def clock(self) -> Clock:
        return self._clock

    # --- Impulse application ---

    def apply_impulse(self, impulse: ChemicalImpulse) -> None:
        """Apply a single impulse to the engine."""
        effective_delta = self._apply_saturation(impulse)
        if impulse.duration_seconds > 0:
            # Create sustained impulse with saturation-adjusted delta
            adjusted = ChemicalImpulse(
                chemical=impulse.chemical,
                delta=effective_delta,
                duration_seconds=impulse.duration_seconds,
                source_id=impulse.source_id,
                source_label=impulse.source_label,
            )
            self._sustained.append(ActiveSustainedImpulse.from_impulse(adjusted))
        else:
            level = self.state.get(impulse.chemical)
            self.state.set(impulse.chemical, level + effective_delta)

    def apply_impulses(self, impulses: list[ChemicalImpulse]) -> None:
        """Apply multiple impulses."""
        for imp in impulses:
            self.apply_impulse(imp)

    def _apply_saturation(self, impulse: ChemicalImpulse) -> float:
        """Apply saturation dampening and return effective delta."""
        if not impulse.source_id:
            return impulse.delta

        now = self._clock.now()
        key = impulse.source_id

        # Prune old entries outside the sliding window
        self._saturation[key] = [
            t for t in self._saturation[key]
            if now - t < SATURATION_WINDOW
        ]

        count = len(self._saturation[key])
        factor = 1.0 / (1.0 + count * SATURATION_DAMPENING)
        self._saturation[key].append(now)

        return impulse.delta * factor

    # --- Simulation advancement ---

    def advance(self, dt: float) -> None:
        """Advance the simulation by dt seconds.

        Internally sub-steps at MAX_SUB_STEP for stability.
        Each sub-step: apply sustained drips → decay → interactions → clamp.

        Args:
            dt: Time in seconds. Must be >= 0.
        """
        if dt < 0:
            raise ValueError(f"dt must be >= 0, got {dt}")
        remaining = dt
        while remaining > 1e-9:
            step = min(remaining, MAX_SUB_STEP)
            self._sub_step(step)
            remaining -= step

    def _sub_step(self, dt: float) -> None:
        """Execute one sub-step of the simulation."""
        # 1. Apply sustained impulse drips
        still_active: list[ActiveSustainedImpulse] = []
        for active in self._sustained:
            drip_dt = min(dt, active.remaining_seconds)
            if drip_dt > 0:
                drip_amount = active.rate_per_second * drip_dt
                # Apply saturation to sustained drips too
                effective = drip_amount  # sustained impulses don't re-saturate per tick
                level = self.state.get(active.impulse.chemical)
                self.state.set(active.impulse.chemical, level + effective)
                active.remaining_seconds -= drip_dt
                if active.remaining_seconds > 1e-9:
                    still_active.append(active)
        self._sustained = still_active

        # 2. Decay all chemicals toward baseline
        self.state.decay_all(dt)

        # 3. Cross-chemical interactions
        apply_interactions(self.state, dt, scale=self._seed.interaction_scale)

        # 4. Clamp everything to [0, 1]
        self.state.clamp_all()
