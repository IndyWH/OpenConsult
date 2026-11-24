"""The teaching bench (spec 15.14, rulings 7 and 14, the details of run
10a): the actor, the examination, the feedback and the writer of fresh
cases, through the same door, the same frames and the same forms as the
app will use. Its material is Cowork's and private: six scenarios with
fixed learner lines, and the list of the writer's runs; the README
beside them says how each part is run, and this module runs it so.

Every call stands alone: the consultation a call is given is made of the
material's own reference replies, never of a model's earlier reply, so
every arm faces the same words. One file a call, with the request and
the reply as they crossed the wire; a file is never written over, so a
bench that was stopped is carried on by the same command and no call is
sent a second time. No word of the material or of a reply enters the
repo."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from openconsult.bench.writer import Refused, ResultWriter
from openconsult.llm.door import Door
from openconsult.llm.jobs import job as job_named
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from openconsult.teaching import frames

KIND = "teaching"
PARTS = ("actor", "examination", "feedback", "writer")
JOB_OF = {"actor": "teaching_patient", "examination": "teaching_examination",
          "feedback": "teaching_feedback", "writer": "teaching_case"}
FRESH = "fresh"          # where a stored file names its case, for a case the writer makes
TRIAL = "trial"          # the folder of the four calls sent before any bench
ARM_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
# US dollars for a million tokens read and written by Claude Haiku 5.5, as the spec holds them: 15.13, ruling 14
# (read on the service's pages on 6 Nov 2026) and 15.10 (14 Nov 2026). The cost stop and the report count by them.
PRICE_READ, PRICE_WRITTEN, PRICES_OF = 0.10, 0.50, "6 and 14 Nov 2026"
RATE_REFUSED = "HTTP 429"


class MaterialRefused(Exception):
    pass


@dataclass(frozen=True)
class Item:
    """One call of the bench: where it belongs, the words it sends and what the material expects of the reply."""
    part: str
    case: str
    item: str
    user: str
    expected: dict
    source_sha256: str


@dataclass(frozen=True)
class Material:
    cases: tuple[dict, ...]
    runs: tuple[dict, ...]
    sha256: dict            # each file's name and the sha256 of its bytes


def read_material(folder: Path) -> Material:
    """The case files and the writer's runs, read and never changed."""
    folder = Path(folder)
    paths = sorted(folder.glob("case_*.json"))
    runs_path = folder / "writer_runs.json"
    if not paths or not runs_path.is_file():
        raise MaterialRefused(f"{folder} holds no case_*.json or no writer_runs.json")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in [*paths, runs_path]}
    cases = tuple(json.loads(path.read_text(encoding="utf-8")) for path in paths)
    for case, path in zip(cases, paths):
        case["file"] = path.name
    runs = tuple(json.loads(runs_path.read_text(encoding="utf-8"))["runs"])
    return Material(cases, runs, hashes)


def conversation(case: dict, numbers: list[int]) -> list[tuple[str, str]]:
    """The lines named, each followed by its reference reply (the README: How each part is run)."""
    lines = {line["n"]: line for line in case["bench"]["lines"]}
    spoken = []
    for n in numbers:
        spoken += [("doctor", lines[n]["doctor"]), ("patient", lines[n]["reference_reply"])]
    return spoken


def actor_item(case: dict, line: dict, sha: str) -> Item:
    before = [other["n"] for other in case["bench"]["lines"] if other["n"] < line["n"]]
    expected = {key: value for key, value in line.items() if key not in ("doctor", "reference_reply")}
    return Item("actor", case["id"], f"line{line['n']:02d}",
                frames.patient_message(case["scenario"], conversation(case, before), line["doctor"]), expected, sha)


def examination_item(case: dict, number: int, sha: str) -> Item:
    request = case["bench"]["examination_requests"][number - 1]
    expected = {key: value for key, value in request.items() if key != "doctor"}
    return Item("examination", case["id"], f"request{number}",
                frames.examination_message(case["scenario"], request["doctor"]), expected, sha)


def feedback_item(case: dict, transcript: dict, sha: str) -> Item:
    bench = case["bench"]
    answers = next(found for found in bench["answers"] if found["name"] == transcript["answers"])
    examined = [bench["examination_requests"][n - 1]["doctor"] for n in transcript["examined"]]
    expected = {**{key: value for key, value in transcript.items() if key != "name"},
                **{key: value for key, value in answers.items() if key.startswith("expects_")},
                "red_flag_points": bench.get("red_flag_points", []), "points_not_asserted": bench.get("points_not_asserted", [])}
    return Item("feedback", case["id"], transcript["name"],
                frames.feedback_message(case["scenario"], conversation(case, transcript["lines"]), examined, answers), expected, sha)


def writer_item(run: dict, sha: str) -> Item:
    return Item("writer", FRESH, f"run{run['n']:02d}", frames.case_message(run["topic"], run["level"]), dict(run), sha)


def items(material: Material, parts: tuple[str, ...] = PARTS, only: list[str] | None = None) -> list[Item]:
    """Every call of one round, in the order of the parts, the cases and the material's own lists."""
    cases = [case for case in material.cases if not only or case["id"] in only]
    found = []
    for part in parts:
        if part == "writer":
            found += [writer_item(run, material.sha256["writer_runs.json"]) for run in material.runs]
            continue
        for case in cases:
            sha, bench = material.sha256[case["file"]], case["bench"]
            if part == "actor":
                found += [actor_item(case, line, sha) for line in bench["lines"]]
            elif part == "examination":
                found += [examination_item(case, n, sha) for n in range(1, len(bench["examination_requests"]) + 1)]
            elif part == "feedback":
                found += [feedback_item(case, transcript, sha) for transcript in bench["transcripts"]]
    return found


def trial_items(material: Material, parts: tuple[str, ...] = PARTS) -> list[Item]:
    """The calls sent before any bench, one of each job asked for: the writer's first run; and, of the first
    case, the patient at line 3, the first examination request and the first transcript."""
    case = material.cases[0]
    sha = material.sha256[case["file"]]
    line = next(found for found in case["bench"]["lines"] if found["n"] == 3)
    four = [writer_item(material.runs[0], material.sha256["writer_runs.json"]), actor_item(case, line, sha),
            examination_item(case, 1, sha), feedback_item(case, case["bench"]["transcripts"][0], sha)]
    return [item for item in four if item.part in parts]


def name_of(item: Item, round_: int, arm: str) -> str:
    """A stored file's name, read at the double underscores: the part, the case, the item, the round and the arm."""
    return f"{item.part}__{item.case}__{item.item}__r{round_}__{arm}"


def files_of(job_name: str) -> dict:
    """The sha256 of the bytes of every file a call of the job reads its words from."""
    job = job_named(job_name)
    return {f"{job.prompt}.prompt.txt": hashlib.sha256(loader.prompt_bytes(job.prompt)).hexdigest(),
            f"{job.form}.form.json": hashlib.sha256(loader.form_bytes(job.form)).hexdigest(),
            **{f"{frame}.frame.txt": hashlib.sha256(loader.file_bytes(f"{frame}.frame")).hexdigest() for frame in job.frames},
            f"{frames.LAYOUT}.layout.json": hashlib.sha256(loader.layout_bytes(frames.LAYOUT)).hexdigest()}


def stamp(door: Door, arm: str) -> dict:
    """What every stored call carries of its arm (V1_LESSONS 9.6)."""
    version, digest = door.identity()
    return {"kind": KIND, "arm": arm, "engine": door.profile.engine, "engine_version": version,
            "model_tag": door.profile.tag, "model_digest": digest}


def arm_differs(held: dict, door: Door, arm: str) -> str | None:
    """Why a folder's results cannot be carried on: another arm, engine, model or bench."""
    now = stamp(door, arm)
    then = {key: held.get(key) for key in now}
    return None if then == now else f"this folder holds results from {then}; the engine now reports {now}"


def wire_parts(request: str | None) -> tuple[str | None, str | None]:
    """The system and the user words of a stored request, read in each engine's own wire shape."""
    try:
        body = json.loads(request or "")
        if "system" in body:                                        # the Messages API of the Claude kind
            return body["system"], body["messages"][0]["content"]
        return body["messages"][0]["content"], body["messages"][1]["content"]     # Ollama and the chat engines
    except (ValueError, KeyError, IndexError, TypeError):
        return None, None


def reply_parts(raw: str | None) -> tuple[str | None, bool | None]:
    """The text of a stored reply and whether it held thinking, in each engine's own wire shape; None where
    the reply cannot be read."""
    try:
        body = json.loads(raw or "")
        if isinstance(body.get("content"), list):                   # the Claude kind
            blocks = [block for block in body["content"] if isinstance(block, dict)]
            text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
            return text, any(block.get("type") in ("thinking", "redacted_thinking") for block in blocks)
        message = body["choices"][0]["message"] if "choices" in body else body["message"]
        text = message.get("content") or ""
        thought = any(message.get(key) for key in ("reasoning_content", "reasoning", "thinking"))
        return text, bool(thought) or "<think>" in text
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None, None


def dollars(read: int, written: int) -> float:
    return (read * PRICE_READ + written * PRICE_WRITTEN) / 1_000_000


def run_call(door: Door, record: ModelCalls, item: Item, round_: int, arm: str, trial: bool = False) -> dict:
    """One call through the door, and everything of it that is stored. The case alone carries its own sampling,
    with a seed drawn afresh; the other three go by the profile (the details: Sampling)."""
    job_name = JOB_OF[item.part]
    sampling = frames.case_sampling() if item.part == "writer" else None
    result = door.ask(job_name, item.user, sampling)
    row = record.get(result.call_id) or {}
    text, thinking = reply_parts(row.get("reply"))
    sent = sampling or door.profile.sampling
    job = job_named(job_name)
    return {**stamp(door, arm), "part": item.part, "case": item.case, "item": item.item, "round": round_, "trial": trial,
            "job": job_name, "max_tokens": job.max_tokens, "timeout_s": job.timeout_s, "files": files_of(job_name),
            "material_sha256": item.source_sha256, "expected": item.expected,
            "sampling": {"temperature": sent.temperature, "seed": sent.seed, "sent": door.engine_name != "claude"},
            "system": loader.prompt(job.prompt), "user": item.user, "form": loader.form(job.form),
            "request": row.get("request"), "reply": row.get("reply"), "text": text, "thinking": thinking,
            "ok": result.ok, "failure": result.failure, "detail": result.detail, "answer": result.answer,
            "model_replied": row.get("model_tag"), "at": row.get("at"), "wall_ms": result.wall_ms,
            "prompt_tokens": result.prompt_tokens, "output_tokens": result.output_tokens,
            "total_ms": row.get("total_ms"), "load_ms": row.get("load_ms"), "read_ms": row.get("read_ms"), "write_ms": row.get("write_ms")}


def spent(writer: ResultWriter) -> float:
    """The cost of every call the folder holds, the trial's with them, at the prices above."""
    held = writer.read_all().values()
    return dollars(sum(row.get("prompt_tokens") or 0 for row in held), sum(row.get("output_tokens") or 0 for row in held))


def line_of(stored: dict) -> str:
    how = "ok" if stored["ok"] else f"FAILED {stored['failure']}: {str(stored['detail'])[:160]}"
    return (f"{stored['wall_ms']} ms, read {stored['prompt_tokens']}, written {stored['output_tokens']}, {how}"
            + (", HELD THINKING" if stored["thinking"] else ""))


def run(door: Door, record: ModelCalls, writer: ResultWriter, material: Material, arm: str, parts: tuple[str, ...] = PARTS,
        rounds: int = 2, only: list[str] | None = None, trial: bool = False, max_dollars: float | None = None,
        log: Callable = print) -> dict:
    """Every call that has no file yet: round 1 whole, then the next; the writer once. With trial, the four
    calls of the trial alone. A call the service refused for the key or the credit never reached a model: it is
    written apart, to be sent when the bench is carried on. Every other failed call is stored and stands."""
    plan = [(0, item) for item in trial_items(material, parts)] if trial else [
        (round_, item) for round_ in range(1, rounds + 1) for item in items(material, parts, only)
        if item.part != "writer" or round_ == 1]
    done = kept = failed = 0
    cost = spent(writer) if max_dollars is not None else 0.0
    for round_, item in plan:
        folder, name = (TRIAL if trial else item.part), name_of(item, round_, arm)
        if writer.exists(folder, name):
            kept += 1
            continue
        if door.stopped:
            return {"run": done, "kept": kept, "failed": failed, "dollars": cost, "stopped": door.stopped}
        if max_dollars is not None and cost > max_dollars:
            why = (f"the cost of the arm, {cost:.2f} US dollars at {PRICE_READ} a million tokens read and {PRICE_WRITTEN} "
                   f"written, passed {max_dollars:.2f}; nothing more is sent")
            return {"run": done, "kept": kept, "failed": failed, "dollars": cost, "stopped": why}
        stored = run_call(door, record, item, round_, arm, trial)
        log(f"  {name}: {line_of(stored)}")
        if door.stopped and not str(stored["detail"] or "").startswith(RATE_REFUSED):
            try:
                writer.write_apart(folder, name, stored)
            except Refused:
                pass    # an earlier stop already left this call apart
            continue
        writer.write(folder, name, stored)
        done += 1
        failed += not stored["ok"]
        if max_dollars is not None:
            cost += dollars(stored["prompt_tokens"] or 0, stored["output_tokens"] or 0)
    summary = {"run": done, "kept": kept, "failed": failed, "dollars": cost}
    return {**summary, "stopped": door.stopped} if door.stopped else summary


def trial_holds(writer: ResultWriter, parts: tuple[str, ...] = PARTS) -> list[str]:
    """Why the bench of these parts may not start after the trial: a call that was not the form, a reply that
    held thinking, a reply cut at its limit, a part with no trial call. Empty when the trial of each part holds."""
    held = [row for (folder, _), row in sorted(writer.read_all().items()) if folder == TRIAL and row["part"] in parts]
    why = [f"{row['job']}: {row['failure']}: {str(row['detail'])[:200]}" for row in held if not row["ok"]]
    why += [f"{row['job']}: the reply held thinking" for row in held if row["thinking"]]
    return why + ([] if len(held) == len(parts) else [f"the trial holds {len(held)} calls, not {len(parts)}"])
