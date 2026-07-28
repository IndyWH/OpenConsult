"""The vendored kindalive core works as plain files on our import path.

Constructs the engine from the vendored config (personalities.toml parsed
with stdlib tomllib — the vendored TOML is this project's config source;
upstream's Python presets module was deliberately not vendored), injects
an impulse, advances the injectable clock, projects to a face state, and
asserts every muscle stays inside its declared range.

FaceState declares every muscle as a value in [0.0, 1.0] (clamped in
FaceProjection.compute); that documented range is what the range test
asserts, not an implementation detail.
"""

import tomllib
from pathlib import Path

from vendor.kindalive.engine.chemicals import Chemical
from vendor.kindalive.engine.clock import ManualClock
from vendor.kindalive.engine.impulse import ChemicalImpulse
from vendor.kindalive.engine.neurochemical_engine import NeurochemicalEngine
from vendor.kindalive.engine.seed_chemistry import SeedChemistry
from vendor.kindalive.expression.face import FaceState, project_face
from vendor.kindalive.expression.face_3d import face_payload

CONFIG_DIR = Path(__file__).resolve().parents[1] / "vendor" / "kindalive" / "config"

MUSCLES = [
    "brow_inner_raise",
    "brow_outer_raise",
    "brow_lower",
    "eyelid_upper_raise",
    "eyelid_lower_tighten",
    "cheek_raise",
    "nose_wrinkle",
    "lip_corner_pull",
    "lip_corner_depress",
    "jaw_open",
    "lip_pucker",
    "lip_press",
]


def load_preset(name: str) -> SeedChemistry:
    """Build a SeedChemistry from the vendored personalities.toml."""
    with open(CONFIG_DIR / "personalities.toml", "rb") as f:
        presets = tomllib.load(f)
    return SeedChemistry.from_dict(presets[name])


def test_engine_from_vendored_config_stays_in_declared_range():
    clock = ManualClock()
    engine = NeurochemicalEngine(clock=clock, seed=load_preset("stoic"))

    engine.apply_impulse(ChemicalImpulse(Chemical.DOPAMINE, 0.4))
    clock.advance(seconds=5)
    engine.advance(5.0)

    face = project_face(engine.state)
    assert isinstance(face, FaceState)
    values = face.as_dict()
    assert sorted(values) == sorted(MUSCLES)
    for muscle, value in values.items():
        assert 0.0 <= value <= 1.0, f"{muscle} out of declared range: {value}"


def test_face_payload_shape_matches_settargets_contract():
    engine = NeurochemicalEngine(clock=ManualClock(), seed=load_preset("default"))
    payload = face_payload(project_face(engine.state))
    assert sorted(payload["muscles"]) == sorted(MUSCLES)
    assert set(payload["mood"]) == {"color", "intensity"}


def test_all_named_presets_load_from_vendored_toml():
    with open(CONFIG_DIR / "personalities.toml", "rb") as f:
        presets = tomllib.load(f)
    for name in presets:
        seed = load_preset(name)
        assert isinstance(seed, SeedChemistry)
