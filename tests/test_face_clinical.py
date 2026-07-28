"""The [clinical] preset damps arousal harder than [default].

The owner's requirement (PHASE_7B_KINDALIVE.md decision 3): under
[clinical] a large adrenaline impulse must produce a smaller peak
deflection and return to baseline faster than the same impulse under the
default preset. Peak is sampled after the first advance step — at t=0 an
instant impulse adds the same delta to both engines by construction, so
the preset can only show up once decay and interactions have run.
"""

import tomllib
from pathlib import Path

from vendor.kindalive.engine.chemicals import Chemical
from vendor.kindalive.engine.clock import ManualClock
from vendor.kindalive.engine.impulse import ChemicalImpulse
from vendor.kindalive.engine.neurochemical_engine import NeurochemicalEngine
from vendor.kindalive.engine.seed_chemistry import SeedChemistry

CONFIG_DIR = Path(__file__).resolve().parents[1] / "vendor" / "kindalive" / "config"


def load_preset(name: str) -> SeedChemistry:
    """Build a SeedChemistry from the vendored personalities.toml."""
    with open(CONFIG_DIR / "personalities.toml", "rb") as f:
        return SeedChemistry.from_dict(tomllib.load(f)[name])

SETTLED = 0.02  # deflection below this counts as back at baseline
STEP_S = 5.0
HORIZON_S = 1800.0


def _adrenaline_response(preset: str) -> tuple[float, float]:
    """(peak deflection, seconds until settled) for a 0.5 adrenaline spike."""
    clock = ManualClock()
    engine = NeurochemicalEngine(clock=clock, seed=load_preset(preset))
    baseline = engine.state.baseline(Chemical.ADRENALINE)

    engine.apply_impulse(ChemicalImpulse(Chemical.ADRENALINE, 0.5))

    peak = 0.0
    settled_at = HORIZON_S
    t = 0.0
    while t < HORIZON_S:
        clock.advance(seconds=STEP_S)
        engine.advance(STEP_S)
        t += STEP_S
        deflection = engine.state.get(Chemical.ADRENALINE) - baseline
        peak = max(peak, deflection)
        if deflection < SETTLED:
            settled_at = t
            break
    return peak, settled_at


def test_clinical_damps_adrenaline_harder_than_default():
    clinical_peak, clinical_settled = _adrenaline_response("clinical")
    default_peak, default_settled = _adrenaline_response("default")

    assert clinical_peak < default_peak, (
        f"clinical peak {clinical_peak:.3f} not below default {default_peak:.3f}"
    )
    assert clinical_settled < default_settled, (
        f"clinical settled at {clinical_settled:.0f}s, "
        f"default at {default_settled:.0f}s"
    )
    assert clinical_settled < HORIZON_S, "clinical never returned to baseline"
