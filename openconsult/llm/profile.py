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
    job_tags: dict = field(default_factory=dict)   # a job done by another model of the same service, by the job's name

    def tag_for(self, job: str) -> str:
        """The model that does a job: the profile's own, unless the job is named here."""
        return self.job_tags.get(job, self.tag)

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

# The cloud model of v2.0 (15.13, rulings 15 and 21): Claude Haiku 5.5 for every job, and Claude Sonnet 5.5 for the
# drug-name call alone (15.10, ruling 36). The names are the service's own, read on its models page on 16 Nov 2026,
# and are typed here and nowhere else. Thinking off; the context as for the local model. The service takes no
# temperature and has no seed, so the sampling is not sent, and the stored request shows that (10.4).
CLAUDE = Profile(
    tag="claude-haiku-5-5",
    engine="claude",
    think=False,
    sampling=Sampling(temperature=0.0, seed=42),
    context=16384,
    tags={"claude": "claude-haiku-5-5"},
    job_tags={"drug_name": "claude-sonnet-5-5"},
)
