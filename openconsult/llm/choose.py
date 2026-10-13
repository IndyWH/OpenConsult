"""The engine chosen at start (spec 15.8, rulings 30, 37, 40; 10.4). On
Linux with a suitable card the app asks vLLM once, with the joint's
short wait, whether it answers, holds the model and reports room enough;
if not, it asks Ollama the same way. On Windows, on a Mac and where the
card is not suitable vLLM is not asked; Ollama is asked on a suitable
card only, as since stage 3. The choice is made once and held for the
run: a call that fails later fails and says so, and nothing is tried in
its place. The app starts no engine (ruling 37).
"""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.llm.engine import Call, Engine, EngineStatus, EngineUnreachable, Reply
from openconsult.llm.profile import Profile
from openconsult.settings.machine import Machine

# The joint's short wait, as This machine has used since stage 3.
SHORT_WAIT_S = 2.0
# vLLM runs natively on Linux only (ruling 30: its own pages, 13 Oct 2026).
VLLM_SYSTEM = "Linux"
ORDER = ("vllm", "ollama")
# Why an engine that was asked is not fit; each is a key into the file of words.
NO_ANSWER, NO_MODEL, SMALL_CONTEXT = "no_answer", "no_model", "small_context"
NO_ENGINE = "no local language model is running"


@dataclass(frozen=True)
class Tried:
    name: str
    address: str | None
    status: EngineStatus
    unfit: str | None     # None when fit


@dataclass(frozen=True)
class Choice:
    name: str | None      # the chosen engine, or None when none is fit
    tried: tuple[Tried, ...]

    @property
    def chosen(self) -> Tried | None:
        return next((t for t in self.tried if t.name == self.name), None)

    @property
    def passed_over(self) -> tuple[Tried, ...]:
        return tuple(t for t in self.tried if t.unfit is not None)


def order_for(machine: Machine) -> tuple[str, ...]:
    """Which engines are asked, in order, on this machine."""
    if machine.case != "suitable":
        return ()
    return ORDER if machine.os == VLLM_SYSTEM else ("ollama",)


def unfit(status: EngineStatus, context: int) -> str | None:
    """Fit means: answers, holds the model, and reports a context of at
    least the profile's, where it reports one (the details of 3c)."""
    if not status.running:
        return NO_ANSWER
    if not status.model_present:
        return NO_MODEL
    if status.context is not None and status.context < context:
        return SMALL_CONTEXT
    return None


def choose(machine: Machine, engines: dict[str, Engine], profile: Profile,
           timeout_s: float = SHORT_WAIT_S) -> Choice:
    tried = []
    for name in order_for(machine):
        engine = engines[name]
        status = engine.status(profile.for_engine(name).tag, timeout_s)
        why = unfit(status, profile.context)
        tried.append(Tried(name, getattr(engine, "address", None), status, why))
        if why is None:
            return Choice(name, tuple(tried))
    return Choice(None, tuple(tried))


class NoEngine:
    """Stands behind the door when no engine is fit (ruling 37): every
    call fails plainly and is recorded, the app runs, and Start is not
    offered. Nothing is tried in its place."""

    name = "none"
    address = None

    def chat(self, call: Call) -> Reply:
        raise EngineUnreachable(NO_ENGINE)

    def version(self, timeout_s: float = SHORT_WAIT_S) -> str | None:
        return None

    def model_digest(self, tag: str, timeout_s: float = SHORT_WAIT_S) -> str | None:
        return None

    def status(self, tag: str, timeout_s: float = SHORT_WAIT_S) -> EngineStatus:
        return EngineStatus(False, None, None, None)
