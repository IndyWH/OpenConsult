"""The calls of the speech bench to the language model (spec 15.9, rulings
17 to 20 and 22; the details of part two of 5c): the label check and the
doubtful drug names for each page, the notes in two rounds, and the notes
from the scripts. Each page's lines are those of model_lines; each call
goes through the door's own record; each result is one file that holds
what was sent, what came back, and how the call ended. A result that
exists is never asked for again, and a call that fails is kept as failed.
The pages are those at Stop of every arm but WhisperX with v1's line,
which shares its pass at Stop (ruling 3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import banked, jobs, marks, model_lines, pages, tables, who
from openconsult.bench.speech.reference import Reference, build
from openconsult.bench.writer import ResultWriter
from openconsult.llm.door import Door

JOB_KINDS = ("label_check", "drug_name", "note", "script_note")
SHARES_STOP = ("whisperx_v1_line",)
SCRIPT_ARM = "script"


def chain_name(arm: str, name: str, round_n: int | None) -> str:
    return f"{arm}--{name}" + (f"--r{round_n}" if round_n else "")


def pages_for_calls(results: dict, names: list[str] | None, arms: list[str] | None) -> list[tuple[str, str, dict]]:
    found = []
    for (arm, name), result in sorted(results.items()):
        if arm in SHARES_STOP or result.get("failure") or (names and name not in names) or (arms and arm not in arms):
            continue
        found.append((arm, name, result))
    return found


def prepare(job: str, result: dict | None, reference: Reference) -> dict:
    """The lines or the turns, the roles, and the user text of one call."""
    if job == "script_note":
        turns = model_lines.script_turns(reference)
        return {"turns": turns, "roles": {}, "user": model_lines.turns_text(turns, {})}
    lines = model_lines.lines_of(pages.stop_pieces(result))
    if job in ("label_check", "drug_name"):
        return {"lines": lines, "user": model_lines.lines_text(lines)}
    page = who.line_page(lines, reference)
    roles = marks.who_spoke(page, reference)["mapping"]
    turns = model_lines.turns_of(lines)
    return {"lines": lines, "turns": turns, "roles": roles, "user": model_lines.turns_text(turns, roles)}


def one_call(door: Door, job: str, prepared: dict) -> dict:
    """The call, and the checks on its reply that the details ask for."""
    asked = jobs.ask(door, "note" if job == "script_note" else job, prepared["user"])
    record: dict = {"call": asked}
    # A call that failed is failed, not refused: its checks are not run.
    if job == "label_check":
        labels, refusal = jobs.check_labels(asked["answer"], len(prepared["lines"])) if asked["ok"] else (None, None)
        record.update(labels={str(n): label for n, label in labels.items()} if labels else None, refusal=refusal)
    elif job == "drug_name":
        kept, dropped = jobs.check_doubtful(asked["answer"], prepared["lines"]) if asked["ok"] else ([], [])
        record.update(kept=kept, dropped=dropped)
    else:
        record.update(note=asked["answer"] if asked["ok"] else None)
    return record


def run_calls(door: Door, job: str, round_n: int | None, listed: list[banked.Recording], results: dict,
              script_folders: list[Path], writer: ResultWriter, names: list[str] | None, arms: list[str] | None,
              say: Callable = print, now: Callable = dt.datetime.now) -> dict:
    """Every page (or every script as cut, for script_note) that has no
    result yet for this job and round."""
    version, digest = door.identity()
    done, kept, failed = [], [], []
    if job == "script_note":
        chosen = [(SCRIPT_ARM, r.name, None) for r in listed if not r.voice_only and (not names or r.name in names)
                  and r.name in {name for (_, name) in results}]
    else:
        chosen = pages_for_calls(results, names, arms)
    for arm, name, result in chosen:
        chain = chain_name(arm, name, round_n)
        if writer.exists(job, chain):
            say(words.BENCH_RESULT_EXISTS.format(arm=f"{job} on {arm}", name=name))
            kept.append(chain)
            continue
        recording = banked.named(listed, name)
        reference = build(tables.find_script(recording, script_folders), recording.last_speech, recording.read_differently)
        prepared = prepare(job, result, reference)
        say(words.BENCH_CALL_ASKING.format(job=job, arm=arm, name=name, round=f", round {round_n}" if round_n else ""))
        record = one_call(door, job, prepared)
        record.update(job=job, arm=arm, recording=name, recording_sha256=recording.sha256, round=round_n,
                      lines=prepared.get("lines"), turns=prepared.get("turns"), roles=prepared.get("roles"),
                      user=prepared["user"], engine={"version": version, "digest": digest, "tag": door.profile.tag},
                      started_at=now().isoformat(timespec="seconds"))
        path = writer.write(job, chain, record)
        say(words.BENCH_RESULT_WRITTEN.format(path=path))
        if not record["call"]["ok"]:
            failed.append(chain)
            say(words.BENCH_CALL_FAILED.format(job=job, arm=arm, name=name, failure=record["call"]["failure"],
                                               detail=record["call"]["detail"]))
        elif record.get("refusal"):
            say(words.BENCH_CALL_REFUSED.format(job=job, arm=arm, name=name, reason=record["refusal"]))
            done.append(chain)
        else:
            done.append(chain)
    return {"run": done, "kept": kept, "failed": failed}
