"""The model's profile (spec 15.7; V1_LESSONS 3.8): everything one model
needs, in one place. The model's name for each engine is typed here and
nowhere else (15.8, the details of 3c)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace


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
    tags: dict = field(default_factory=dict)   # the model's name on each engine

    def for_engine(self, engine: str) -> "Profile":
        """The same profile as that engine knows the model."""
        try:
            return replace(self, tag=self.tags[engine], engine=engine)
        except KeyError:
            raise KeyError(f"no model named for the engine {engine}") from None


# A local model keeps the settings that make it answer as steadily as it
# can (spec 10.4). One context size for every call, so the model never
# reloads between calls (R19). Thinking off: with it on, no pass landed
# (V1_LESSONS 3.8). On vLLM the model is the repack of 15.8, ruling 7;
# Ollama's own tag is the default, the fallback everywhere (ruling 30).
GEMMA_4_QAT = Profile(
    tag="gemma4:26b-a4b-it-qat",
    engine="ollama",
    think=False,
    sampling=Sampling(temperature=0.0, seed=42),
    context=16384,
    tags={"ollama": "gemma4:26b-a4b-it-qat", "vllm": "xbill9/gemma-4-26B-A4B-it-qat-q4_0-w4a16-ct"},
)
