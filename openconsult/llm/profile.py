"""The model's profile (spec 15.7; V1_LESSONS 3.8): everything one model
needs, in one place. The model's name is typed here and nowhere else."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sampling:
    temperature: float
    seed: int


@dataclass(frozen=True)
class Profile:
    tag: str
    engine: str
    think: bool
    sampling: Sampling
    context: int


# A local model keeps the settings that make it answer as steadily as it
# can (spec 10.4). One context size for every call, so the model never
# reloads between calls (R19). Thinking off: with it on, no pass landed
# (V1_LESSONS 3.8).
GEMMA_4_QAT = Profile(
    tag="gemma4:26b-a4b-it-qat",
    engine="ollama",
    think=False,
    sampling=Sampling(temperature=0.0, seed=42),
    context=16384,
)
