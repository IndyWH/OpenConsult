"""The three jobs of the speech bench (spec 15.9, rulings 17, 18 and 19;
15.8 ruling 1): the label check, the doubtful drug names and the note.
Each prompt is a file in the prompts folder beside this one, the owner's
approved text byte for byte, checked by its sha256 before it is read; each
has a form that code holds and a limit on its length and on its time. A
call goes through the one door to language models with the door's own
record, and never enters the app's table of jobs. The checks on a reply
that the details ask for are plain functions here: a label check that
misses, repeats or invents a line is refused whole; a doubtful name whose
heard words do not stand on its line is dropped and counted."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from openconsult.llm.door import Door, Result
from openconsult.llm.jobs import Job
from openconsult.speech.matching import normalise

PROMPTS = Path(__file__).resolve().parent / "prompts"
# The sha256 of each prompt file's bytes, with one line break after its last
# line, as the spec gives it under rulings 17, 18 and 19.
PROMPT_SHA256 = {
    "label_check": "262d1ef805d4b7a27a1823a71dd649b78d2cdb84da5ce570c8d7cd3d91de557a",
    "drug_name": "89fcdc35d7a6ea4ddf7cd9e1b7e96c3118fd7810013e857bd83f6bc7c3939963",
    "note": "adf0b5e73963ae198b1d4df55aedbfd92aec0c0f69117c459e78a9d3ec31f2e8",
}
LABELS = ("doctor", "patient", "unsure")

# The limits (the details of part two). The longest page of part one's
# rehearsal has 124 lines and a line of the label check's reply is about
# 13 tokens, so about 1,600; the longest of the 390 notes of Task 5d was
# 1,286 tokens and took 7.3 s. Both checked from the files in the plan.
LABEL_CHECK_MAX_TOKENS, LABEL_CHECK_TIMEOUT_S = 3000, 120.0
DRUG_NAME_MAX_TOKENS, DRUG_NAME_TIMEOUT_S = 1500, 90.0
NOTE_MAX_TOKENS, NOTE_TIMEOUT_S = 3000, 120.0
ON_FAILURE = "The call is kept as failed and counted; nothing is asked a second time."

JOBS = {
    "label_check": Job(name="bench_label_check", prompt="label_check", form="label_check", frames=(),
                       max_tokens=LABEL_CHECK_MAX_TOKENS, timeout_s=LABEL_CHECK_TIMEOUT_S, on_failure=ON_FAILURE),
    "drug_name": Job(name="bench_drug_name", prompt="drug_name", form="drug_name", frames=(),
                     max_tokens=DRUG_NAME_MAX_TOKENS, timeout_s=DRUG_NAME_TIMEOUT_S, on_failure=ON_FAILURE),
    "note": Job(name="bench_note", prompt="note", form="note", frames=(),
                max_tokens=NOTE_MAX_TOKENS, timeout_s=NOTE_TIMEOUT_S, on_failure=ON_FAILURE),
}


class PromptChanged(Exception):
    """A prompt file whose bytes are not the owner's approved text."""


def prompt_bytes(name: str) -> bytes:
    return (PROMPTS / f"{name}.prompt.txt").read_bytes()


def prompt_text(name: str) -> str:
    """The text a model reads: the file's bytes, checked against the
    approved hash, decoded, less the one line break after the last line
    (as the app's loader reads every prompt file)."""
    data = prompt_bytes(name)
    found = hashlib.sha256(data).hexdigest()
    if found != PROMPT_SHA256[name]:
        raise PromptChanged(f"{name}.prompt.txt has sha256 {found}, not {PROMPT_SHA256[name]}")
    text = data.decode("utf-8")
    return text[:-1] if text.endswith("\n") else text


def form_of(name: str) -> dict:
    return json.loads((PROMPTS / f"{name}.form.json").read_text(encoding="utf-8"))


def ask(door: Door, job_key: str, user: str) -> dict:
    """One call of a bench job through the door, as a plain dict for the
    result file: the answer or the failure, the call's id in the record,
    its tokens and its seconds."""
    job = JOBS[job_key]
    result: Result = door.ask_own(job, prompt_text(job_key), form_of(job_key), user)
    return {"job": job.name, "ok": result.ok, "answer": result.answer, "failure": result.failure,
            "detail": result.detail, "call_id": result.call_id, "wall_ms": result.wall_ms,
            "prompt_tokens": result.prompt_tokens, "output_tokens": result.output_tokens,
            "prompt_file_sha256": PROMPT_SHA256[job_key], "max_tokens": job.max_tokens, "timeout_s": job.timeout_s}


# ------------------------------------------------------- the label check

def check_labels(answer: dict | None, n_lines: int) -> tuple[dict[int, str] | None, dict | None]:
    """The labels by line number, or None with the reason the reply was
    refused: a line missed, repeated or not there (ruling 17). From a
    refused reply no label is taken."""
    if answer is None:
        return None, {"reason": "no answer"}
    seen: dict[int, str] = {}
    repeated, unknown = [], []
    for entry in answer.get("lines", []):
        number = entry["line"]
        if not isinstance(number, int) or number < 1 or number > n_lines:
            unknown.append(number)
        elif number in seen:
            repeated.append(number)
        else:
            seen[number] = str(entry["label"])
    missing = [n for n in range(1, n_lines + 1) if n not in seen]
    if missing or repeated or unknown:
        return None, {"reason": "refused", "missing": missing, "repeated": repeated, "unknown": unknown}
    return seen, None


# -------------------------------------------------- the doubtful names

def check_doubtful(answer: dict | None, lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """The entries whose heard words stand on their line, letter for letter
    (and, listed beside, whether they stand there after the matching's
    normalisation), and the entries dropped (ruling 18)."""
    kept, dropped = [], []
    by_number = {line["n"]: line for line in lines}
    for entry in (answer or {}).get("doubtful", []):
        number, heard, meant = entry.get("line"), str(entry.get("heard", "")), str(entry.get("meant", ""))
        line = by_number.get(number) if isinstance(number, int) else None
        record = {"line": number, "heard": heard, "meant": meant}
        if line is None or not heard.strip():
            dropped.append({**record, "why": "no such line" if line is None else "nothing heard"})
            continue
        exact = heard in line["text"]
        normalised = _holds(normalise(line["text"]), normalise(heard))
        if exact:
            kept.append({**record, "normalised_too": normalised})
        else:
            dropped.append({**record, "why": "not on its line", "normalised_only": normalised})
    return kept, dropped


def _holds(words: list[str], part: list[str]) -> bool:
    return bool(part) and any(words[i:i + len(part)] == part for i in range(len(words) - len(part) + 1))
