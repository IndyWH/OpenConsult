"""Cross-chemical interaction rules.

These run after decay each sub-step. They model how chemicals affect
each other (cortisol erodes serotonin, GABA dampens adrenaline, etc.).

**Equilibrium principle.** Every interaction term is written so that it
*vanishes when the relevant chemical is at its baseline*. That makes the
all-baseline resting state a true fixed point: at rest nothing drifts.
Interactions are couplings between *perturbations*, not constant pushes
toward 0 or 1.

This matters because the chemicals have very different decay timescales
(adrenaline ~3 min, cortisol ~1 h, serotonin ~4 h). An older version
used constant per-second pushes toward zero (e.g. ``cortisol -= oxytocin
* 0.08``); those overwhelmed the slow decay-toward-baseline and *pinned*
chemicals at their extremes — cortisol and GABA collapsed to 0, which in
turn removed adrenaline's damping and let testosterone ratchet adrenaline
to 1.0. Gating each rule on the deviation-from-baseline removes that
failure mode while preserving the intended directional effects.

Important: clamping to [0, 1] happens AFTER all rules run in a sub-step,
not between individual rules.
"""

from __future__ import annotations

from vendor.kindalive.engine.chemicals import Chemical, ChemicalState

# Baseline drift bounds
BASELINE_DRIFT_MIN = 0.1
BASELINE_DRIFT_MAX = 0.5

# Interaction coefficients (per second, before the seed's interaction_scale)
K_CORTISOL_SEROTONIN = 0.03    # excess cortisol erodes serotonin
K_GABA_ADRENALINE = 0.15       # GABA damps adrenaline's excess
K_TESTOSTERONE_ADRENALINE = 0.015  # excess testosterone amplifies adrenaline
K_ADRENALINE_GABA = 0.30       # adrenaline's excess inhibits GABA toward a floor
K_OXYTOCIN_CORTISOL = 0.30     # oxytocin relieves cortisol's excess

# Adrenaline keeps inhibiting GABA only until GABA reaches this fraction of
# its baseline. The remaining GABA preserves adrenaline's damping, so a
# burst of arousal can't fully strip the brake and run away.
GABA_INHIBITION_FLOOR_FRAC = 0.5

# Baseline drift thresholds. The "recovery lowers baseline" threshold sits
# *below* the resting cortisol baseline (0.2) so it only fires during a
# genuinely sustained low-cortisol stretch, not at normal rest.
CORTISOL_DRIFT_UP_THRESHOLD = 0.7
CORTISOL_DRIFT_DOWN_THRESHOLD = 0.15


def apply_interactions(state: ChemicalState, dt: float, scale: float = 1.0) -> None:
    """Apply all cross-chemical interaction rules for one sub-step.

    Args:
        state: The mutable chemical state to modify in-place.
        dt: Time step in seconds (should be <= 0.5 for stability).
        scale: Global interaction coefficient multiplier (from SeedChemistry).
    """
    # Snapshot all levels before any mutations. All rules read from this
    # snapshot so results are order-independent within a sub-step.
    cortisol = state.get(Chemical.CORTISOL)
    serotonin = state.get(Chemical.SEROTONIN)
    gaba = state.get(Chemical.GABA)
    adrenaline = state.get(Chemical.ADRENALINE)
    testosterone = state.get(Chemical.TESTOSTERONE)
    oxytocin = state.get(Chemical.OXYTOCIN)

    # Excess of a chemical above its own baseline (0 when at/below rest).
    cortisol_excess = max(0.0, cortisol - state.baseline(Chemical.CORTISOL))
    adrenaline_excess = max(0.0, adrenaline - state.baseline(Chemical.ADRENALINE))
    testosterone_excess = max(
        0.0, testosterone - state.baseline(Chemical.TESTOSTERONE)
    )
    gaba_floor = GABA_INHIBITION_FLOOR_FRAC * state.baseline(Chemical.GABA)

    # Compute deltas from the snapshot (all independent; order doesn't matter).

    # Rule 1: excess cortisol erodes serotonin (stress wears down wellbeing).
    d_serotonin = -cortisol_excess * K_CORTISOL_SEROTONIN * scale * dt

    # Rule 2: GABA dampens adrenaline's excess (calm counteracts arousal),
    # restoring it toward baseline rather than toward zero.
    # Rule 4: excess testosterone amplifies adrenaline (drive fuels arousal).
    d_adrenaline = (
        -gaba * K_GABA_ADRENALINE * adrenaline_excess * scale * dt
        + testosterone_excess * K_TESTOSTERONE_ADRENALINE * scale * dt
    )

    # Rule 3: adrenaline's excess inhibits GABA, but only the portion above
    # the floor — so the brake on adrenaline is never fully removed.
    d_gaba = (
        -adrenaline_excess
        * K_ADRENALINE_GABA
        * max(0.0, gaba - gaba_floor)
        * scale
        * dt
    )

    # Rule 5: oxytocin relieves cortisol's excess (bonding eases stress),
    # but cannot drive cortisol below its resting baseline.
    d_cortisol = -oxytocin * K_OXYTOCIN_CORTISOL * cortisol_excess * scale * dt

    # Apply all deltas
    state.set(Chemical.SEROTONIN, serotonin + d_serotonin)
    state.set(Chemical.ADRENALINE, adrenaline + d_adrenaline)
    state.set(Chemical.GABA, gaba + d_gaba)
    state.set(Chemical.CORTISOL, cortisol + d_cortisol)

    # Rule 6: Sustained high cortisol raises cortisol baseline (chronic stress).
    if cortisol > CORTISOL_DRIFT_UP_THRESHOLD:
        new_bl = state.baseline(Chemical.CORTISOL) + 0.001 * dt
        state.set_baseline(Chemical.CORTISOL, new_bl)  # auto-clamped to [0.1, 0.5]

    # Rule 7: Sustained low cortisol lowers cortisol baseline (recovery).
    if cortisol < CORTISOL_DRIFT_DOWN_THRESHOLD:
        new_bl = state.baseline(Chemical.CORTISOL) - 0.0005 * dt
        state.set_baseline(Chemical.CORTISOL, new_bl)  # auto-clamped to [0.1, 0.5]
