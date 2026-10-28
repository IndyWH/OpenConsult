"""The letters bench (spec 15.12, ruling 10 and the detail The bench):
the list call and the letter calls on the four approved notes, 13 chains
a case, through the same door, the same numbering, the same frames and
the same check as the app, so what is benched is what the app sends. A
case with a stated referral drafts to each expected specialty; a case
with none drafts to the specialty the command names for it. Results go
to the writer's folder, never over an existing one; no word of a note
or a reply enters the repo."""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict
from typing import Callable

from openconsult.bench.cases import Case
from openconsult.bench.replay import CHAINS, Chain
from openconsult.bench.writer import ResultWriter
from openconsult.consult import letter_check, referral_note, referrals
from openconsult.llm.door import Door, Result
from openconsult.llm.profile import Sampling
from openconsult.prompts import loader

FILES = ("letter", "referrals")
FIXED = ("letter.frame", "referrals.frame", "letter.withheld")
KIND = "letters"


def specialties_for(case: Case, named: dict[str, str]) -> list[str]:
    """The specialties a chain drafts to: the case's expected stated
    referrals, or the one named for a case that states none."""
    expected = [s for s in (case.expected.get("stated_referrals") or []) if s]
    if expected:
        return expected
    if case.name in named:
        return [named[case.name]]
    raise ValueError(f"{case.name} states no referral and no --letter names a specialty for it")


def stamp(door: Door) -> dict:
    """Every result carries the engine, the model and the hashes of the
    two prompts and the three fixed-words files (V1_LESSONS 9.6)."""
    version, digest = door.identity()
    prompts = {name: hashlib.sha256(loader.prompt_bytes(name)).hexdigest() for name in FILES}
    prompts.update({name: hashlib.sha256(loader.file_bytes(name)).hexdigest() for name in FIXED})
    return {"kind": KIND, "engine": door.profile.engine, "engine_version": version, "model_tag": door.profile.tag,
            "model_digest": digest, "prompts": prompts}


def arm_differs(held: dict, door: Door) -> str | None:
    """Why a folder's results cannot be carried on: another engine,
    model, prompt words, or another bench's results."""
    now = stamp(door)
    then = {key: held.get(key) for key in now}
    if then == now:
        return None
    return f"this folder holds results from {then}; the engine now reports {now}"


def first_call(door: Door, case: Case) -> Result:
    """The one unmeasured call of the arm: the list call of the first case."""
    text = case.path.read_text(encoding="utf-8")
    return door.ask("referrals", referral_note.list_message(text, case.patient), Sampling(0.0, 42))


def _call_row(result: Result) -> dict:
    return {"call_id": result.call_id, "wall_ms": result.wall_ms, "failure": f"{result.failure}: {result.detail}" if not result.ok else None,
            "prompt_tokens": result.prompt_tokens, "output_tokens": result.output_tokens}


def run_chain(door: Door, case: Case, chain: Chain, named: dict[str, str], log: Callable = print) -> dict:
    """One chain of one case: the list call, sorted by code; then one
    letter call for each specialty, checked as the app checks."""
    text = case.path.read_text(encoding="utf-8")
    lines = referral_note.numbered_lines(text)
    sampling = Sampling(chain.temperature, chain.seed)
    started = time.perf_counter()
    listed = door.ask("referrals", referral_note.list_message(text, case.patient), sampling)
    items = referrals.sort_items(listed.answer, lines) if listed.ok else []
    log(f"  {case.name} {chain.name} list: {listed.wall_ms} ms, {sum(i.kind == 'stated' for i in items)} stated, "
        f"{sum(i.kind == 'suggested' for i in items)} suggested" + (f" FAILED {listed.failure}" if not listed.ok else ""))
    letters = []
    for specialty in specialties_for(case, named):
        drafted = door.ask("letter", referral_note.letter_message(text, specialty, case.patient), sampling)
        row = {"specialty": specialty, **_call_row(drafted), "reasoning": None, "model_body": None, "body": None,
               "check_detail": None, "total": 0, "grounded": 0, "placeholders": 0, "dropped": 0, "refused": None}
        if drafted.ok:
            paragraphs = [{"text": str(p.get("text", "")), "note_lines": list(p.get("note_lines") or [])}
                          for p in drafted.answer.get("paragraphs") or [] if isinstance(p, dict)]
            checked = letter_check.check(paragraphs, lines, {str(case.patient.age)})
            row.update(reasoning=str(drafted.answer.get("reasoning") or ""), model_body=paragraphs, body=checked.paragraphs,
                       check_detail=checked.detail, total=checked.total, grounded=checked.grounded,
                       placeholders=checked.placeholders, dropped=checked.dropped, refused=checked.refused)
        letters.append(row)
        log(f"  {case.name} {chain.name} letter to {specialty}: {drafted.wall_ms} ms, {row['grounded']} of {row['total']} grounded, "
            f"{row['placeholders']} placeholders" + (" REFUSED" if row["refused"] else "") + (f" FAILED {drafted.failure}" if not drafted.ok else ""))
    return {"case": case.name, "group": case.group, "chain": chain.name, "temperature": chain.temperature, "seed": chain.seed,
            "patient": asdict(case.patient), "case_sha256": case.sha256, "expected": dict(case.expected),
            "wall_s": round(time.perf_counter() - started, 1),
            "lines": [asdict(line) for line in lines],
            "list": {**_call_row(listed), "answer": listed.answer, "reasoning": str(listed.answer.get("reasoning") or "") if listed.ok else None,
                     "items": [asdict(i) for i in items]},
            "letters": letters, **stamp(door)}


def run(door: Door, cases: list[Case], writer: ResultWriter, named: dict[str, str], chains: list[Chain] = CHAINS,
        log: Callable = print) -> dict:
    """Every chain of every case that has no result yet, in order; a case
    with nothing to draft to stops before any call."""
    for case in cases:
        specialties_for(case, named)
    done, skipped = 0, 0
    for case in cases:
        for chain in chains:
            if writer.exists(case.name, chain.name):
                skipped += 1
                continue
            log(f"=== {case.name} {chain.name} T={chain.temperature} seed={chain.seed}")
            result = run_chain(door, case, chain, named, log)
            writer.write(case.name, chain.name, result)
            done += 1
            log(f"--- {case.name} {chain.name} done in {result['wall_s']} s")
    return {"run": done, "kept": skipped}
