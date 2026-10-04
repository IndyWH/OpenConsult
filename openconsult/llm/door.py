"""The one door to language models (spec 5.1, 15.7). Every call goes
through ask(): it has a limit on its length and on its time, is checked
against its form, is written to the record whatever happened, and gives
back one Result. It never raises into a consultation (R30): a failure
comes back with its reason, and nothing else is tried (spec 10.4).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Callable

from openconsult.llm import forms
from openconsult.llm.engine import Call, Engine, EngineFailure, EngineTimeout, EngineUnreachable, Reply
from openconsult.llm.jobs import Job, job as job_named
from openconsult.llm.profile import GEMMA_4_QAT, Profile, Sampling
from openconsult.llm.record import CallRow, ModelCalls
from openconsult.prompts import loader

FAILURES = ("too_slow", "too_long", "unreachable", "bad_form", "did_not_fit")


@dataclass(frozen=True)
class Result:
    job: str
    ok: bool
    answer: dict | None
    failure: str | None      # one of FAILURES when not ok
    detail: str | None
    call_id: int
    wall_ms: int
    prompt_tokens: int | None
    output_tokens: int | None


class Door:
    def __init__(self, engine: Engine, record: ModelCalls, profile: Profile = GEMMA_4_QAT,
                 timer: Callable[[], float] = time.perf_counter):
        self._engine = engine
        self._record = record
        self.profile = profile
        self._timer = timer
        self._identity: tuple[str | None, str | None] | None = None

    def call_for(self, job_name: str, user: str, sampling: Sampling | None = None) -> Call:
        """The parts of a call, as the engine will see them. The sampling
        override is for the bench's chains only; the app takes the
        profile's steady values (spec 10.4)."""
        job = job_named(job_name)
        sampling = sampling or self.profile.sampling
        return Call(job=job.name, tag=self.profile.tag, system=loader.prompt(job.prompt),
                    user=user, form=loader.form(job.form), temperature=sampling.temperature,
                    seed=sampling.seed, context=self.profile.context, max_tokens=job.max_tokens,
                    think=self.profile.think, timeout_s=job.timeout_s)

    def ask(self, job_name: str, user: str, sampling: Sampling | None = None) -> Result:
        job = job_named(job_name)
        call = self.call_for(job_name, user, sampling)
        started = self._timer()
        try:
            reply = self._engine.chat(call)
        except EngineTimeout as slow:
            return self._failed(call, job, started, slow, "too_slow",
                                f"no answer within {job.timeout_s:.0f} s: {slow}")
        except EngineUnreachable as gone:
            self._identity = None  # read it again when the engine is back
            return self._failed(call, job, started, gone, "unreachable", str(gone))
        wall_ms = round(1000 * (self._timer() - started))
        outcome, detail, answer = self._judge(reply, call, job, wall_ms)
        call_id = self._write(call, reply.request, reply.raw, reply, wall_ms, outcome, detail)
        return Result(job.name, outcome == "ok", answer, None if outcome == "ok" else outcome,
                      detail, call_id, wall_ms, reply.prompt_tokens, reply.output_tokens)

    def _judge(self, reply: Reply, call: Call, job: Job, wall_ms: int):
        """How the call ended, in the door's terms."""
        if reply.ended == "did_not_fit":
            return "did_not_fit", f"the input did not fit the context of {call.context}: {reply.error}", None
        if reply.ended == "error":
            return "unreachable", f"HTTP {reply.status}: {reply.error}", None
        if reply.ended == "cut":
            return "too_long", f"the reply was cut at the limit of {job.max_tokens} tokens", None
        if wall_ms > job.timeout_s * 1000:
            return "too_slow", f"the reply came after {wall_ms} ms, over the limit of {job.timeout_s:.0f} s", None
        try:
            answer = json.loads(reply.text or "")
        except ValueError:
            return "bad_form", "the reply is not JSON", None
        reason = forms.misfit(answer, call.form)
        if reason:
            return "bad_form", reason, None
        return "ok", None, answer

    def _failed(self, call: Call, job: Job, started: float, failure: EngineFailure,
                outcome: str, detail: str) -> Result:
        """A call the engine could not complete still leaves its row: the
        request as the engine tried to send it, or the parts if it never
        got that far."""
        wall_ms = round(1000 * (self._timer() - started))
        sent = failure.request or json.dumps(asdict(call), ensure_ascii=False)
        call_id = self._write(call, sent, None, None, wall_ms, outcome, detail)
        return Result(job.name, False, None, outcome, detail, call_id, wall_ms, None, None)

    def identity(self) -> tuple[str | None, str | None]:
        """The engine's version and the model's digest, read once and kept
        until the engine is lost (V1_LESSONS 9.6)."""
        if self._identity is None:
            self._identity = (self._engine.version(), self._engine.model_digest(self.profile.tag))
        return self._identity

    def _write(self, call: Call, request: str, raw: str | None, reply: Reply | None,
               wall_ms: int, outcome: str, detail: str | None) -> int:
        version, digest = self.identity()
        return self._record.add(CallRow(
            job=call.job, engine=self._engine.name, engine_version=version, model_tag=call.tag,
            model_digest=digest, prompt_sha256=loader.sha256(call.system), request=request,
            reply=raw, prompt_tokens=reply.prompt_tokens if reply else None,
            output_tokens=reply.output_tokens if reply else None, wall_ms=wall_ms,
            total_ms=reply.total_ms if reply else None, load_ms=reply.load_ms if reply else None,
            read_ms=reply.read_ms if reply else None, write_ms=reply.write_ms if reply else None,
            outcome=outcome, detail=detail))
