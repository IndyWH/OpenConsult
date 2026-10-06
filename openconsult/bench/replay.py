"""The replay (spec 15.7; V1_LESSONS 9.1): 13 chains of every case
through the same pass and the same door as the app. Each chain starts
with no earlier answer and carries the stale list and the arranged
flag forward. A chain's result is written when it ends, complete or
failed, and a run that was stopped carries on from the chains that
have no result yet, on the same engine and model only (spec 15.8)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Callable

from openconsult.bench.cases import Case
from openconsult.bench.together import run_pass_together
from openconsult.bench.writer import ResultWriter
from openconsult.consult.cds_pass import Carried, run_pass
from openconsult.consult.messages import alarm_message, with_patient
from openconsult.llm.door import Door, Result
from openconsult.llm.profile import Sampling
from openconsult.prompts import loader


@dataclass(frozen=True)
class Chain:
    name: str
    temperature: float
    seed: int


CHAINS = ([Chain(f"A{i}", 0.0, 42) for i in (1, 2, 3)]
          + [Chain(f"B{s}", 0.5, s) for s in range(1, 11)])

UNREACHABLE_IN_A_ROW = 2


def stamp(door: Door) -> dict:
    """Every result carries the model's tag and digest, the engine's
    version and the prompt hashes (V1_LESSONS 9.6)."""
    version, digest = door.identity()
    return {"engine": door.profile.engine, "engine_version": version, "model_tag": door.profile.tag,
            "model_digest": digest,
            "prompts": {name: loader.sha256(loader.prompt(name)) for name in ("alarm", "assessment")}}


STEADY = Sampling(0.0, 42)


def answer_text(raw: str | None) -> tuple[str | None, str | None]:
    """The answer's text, and any thinking text, from a raw reply as the
    record holds it, whichever engine wrote it."""
    try:
        body = json.loads(raw or "")
        message = body["message"] if "message" in body else body["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None, None
    thinking = message.get("thinking") or message.get("reasoning_content") or message.get("reasoning")
    return message.get("content"), thinking or None


def first_call(door: Door, case: Case) -> Result:
    """The one call of an arm that is not measured (spec 15.8, the
    clock): the alarm call of the first case's first point. It is
    recorded, but no result names it, so it enters no time. After it the
    model is loaded and warm."""
    _, transcript = case.points()[0]
    return door.ask("alarm", with_patient(alarm_message(transcript), case.patient), STEADY)


def arm_differs(held: dict, door: Door, together: bool) -> str | None:
    """Why a folder's results cannot be carried on by this engine: an arm
    is never finished on another engine, another model, other prompts or
    another way of sending (stage 3b, rule 19)."""
    now = {**stamp(door), "together": together}
    then = {key: held.get(key, False if key == "together" else None) for key in now}
    if then == now:
        return None

    def said(s: dict) -> str:
        how = "sent together" if s["together"] else "one after another"
        prompts = ", ".join(f"{name} {str(sha)[:12]}" for name, sha in sorted((s["prompts"] or {}).items()))
        return (f"{s['engine']} {s['engine_version']}, model {s['model_tag']} {s['model_digest']}, "
                f"{how}, prompts {prompts}")

    return f"this folder holds results from {said(then)}; the engine now reports {said(now)}"


def run_chain(door: Door, case: Case, chain: Chain, log: Callable = print, together: bool = False) -> dict:
    """One chain of one case. For a script, any failed call fails the
    chain there (Task 5b's rule); for 495 and travel a failed pass is
    recorded and the chain goes on. The engine unreachable twice in a
    row fails any chain. Sent together, the pass's time runs from
    sending until both calls are back."""
    a_pass = run_pass_together if together else run_pass
    sampling = Sampling(chain.temperature, chain.seed)
    carried = Carried()
    passes, failed, unreachable = [], None, 0
    started = time.perf_counter()
    for point, transcript in case.points():
        t0 = time.perf_counter()
        result = a_pass(door, transcript, case.patient, carried, sampling)
        wall_ms = round(1000 * (time.perf_counter() - t0))
        carried = result.carried
        row = {"point": point, "wall_ms": wall_ms, "alarm": asdict(result.alarm),
               "assessment": asdict(result.assessment), "names": list(carried.names)}
        passes.append(row)
        failures = [f for f in (result.alarm.failure, result.assessment.failure) if f]
        log(f"  {case.name} {chain.name} point {point}: {wall_ms} ms"
            + (f" FAILED {failures}" if failures else ""))
        unreachable = unreachable + 1 if "unreachable" in failures else 0
        if unreachable >= UNREACHABLE_IN_A_ROW:
            failed = f"the engine was unreachable {unreachable} times in a row"
            break
        if failures and case.group == "script":
            failed = f"a call failed at point {point}: {', '.join(failures)}"
            break
    return {"case": case.name, "group": case.group, "chain": chain.name,
            "temperature": chain.temperature, "seed": chain.seed,
            "patient": asdict(case.patient), "case_sha256": case.sha256,
            "wall_s": round(time.perf_counter() - started, 1), "failed": failed,
            "passes": passes, "together": together, **stamp(door)}


def run(door: Door, cases: list[Case], writer: ResultWriter, chains: list[Chain] = CHAINS,
        log: Callable = print, together: bool = False) -> dict:
    """Every chain of every case that has no result yet, in order."""
    done, skipped, failed = 0, 0, []
    for case in cases:
        for chain in chains:
            if writer.exists(case.name, chain.name):
                skipped += 1
                continue
            log(f"=== {case.name} {chain.name} T={chain.temperature} seed={chain.seed}")
            result = run_chain(door, case, chain, log, together)
            writer.write(case.name, chain.name, result)
            done += 1
            if result["failed"]:
                failed.append((case.name, chain.name, result["failed"]))
                log(f"--- {case.name} {chain.name} FAILED CHAIN: {result['failed']}")
            else:
                log(f"--- {case.name} {chain.name} done in {result['wall_s']} s")
    return {"run": done, "kept": skipped, "failed": failed}
