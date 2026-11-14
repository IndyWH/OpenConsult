"""The three jobs of the speech bench (spec 15.9, rulings 17, 18 and 19;
15.8 ruling 1): the label check, the doubtful drug names and the note.
Each prompt is a file, the owner's approved text byte for byte, checked by
its sha256 before it is read, in the app's prompts folder, where the app
reads the same files (spec 5.1; stages 6a and 6b, step 6c); each has a
form that code holds and a limit on its length and on its time, the
app's own for the note and the drug names. A
call goes through the one door to language models with the door's own
record, and never enters the app's table of jobs. The checks on a reply
that the details ask for are the app's own functions: a label check
that misses a line is refused whole (15.10 ruling 24); a doubtful name
whose heard words do not stand on its line is dropped and counted."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from openconsult.consult.drug_marks import check_doubtful  # noqa: F401 - the app's check, kept under its bench name
from openconsult.consult.labels import check_labels  # noqa: F401 - the app's check, kept under its bench name
from openconsult.llm import jobs as app_jobs
from openconsult.llm.door import Door, Result
from openconsult.llm.jobs import NOTE_MAX_TOKENS, NOTE_TIMEOUT_S, Job
from openconsult.prompts import loader

# The one file of each prompt is the app's (spec 5.1): the bench has no prompts folder of its own since 6c.
FOLDER_OF = {"label_check": loader.FOLDER, "drug_name": loader.FOLDER, "note": loader.FOLDER}
# The sha256 of each prompt file's bytes, with one line break after its last
# line, as the spec gives it under 15.9 rulings 17 and 18 and 15.10 ruling 3
# (the note prompt of v2; v1's of ruling 19 was the bench's until 6b).
PROMPT_SHA256 = {
    "label_check": "262d1ef805d4b7a27a1823a71dd649b78d2cdb84da5ce570c8d7cd3d91de557a",
    "drug_name": loader.APPROVED_BYTES["drug_name"],
    "note": loader.APPROVED_BYTES["note"],
}
LABELS = ("doctor", "patient", "unsure")

# The limits (the details of part two). The longest page of part one's
# rehearsal has 124 lines and a line of the label check's reply is about
# 13 tokens, so about 1,600; the longest of the 390 notes of Task 5d was
# 1,286 tokens and took 7.3 s. Both checked from the files in the plan.
# The note's two are the app's own since 6b (llm/jobs.py), and the drug
# name's since 6c: 3,000 tokens where the bench of 5e had 1,500.
LABEL_CHECK_MAX_TOKENS, LABEL_CHECK_TIMEOUT_S = 3000, 120.0
DRUG_NAME_MAX_TOKENS, DRUG_NAME_TIMEOUT_S = app_jobs.JOBS["drug_name"].max_tokens, app_jobs.JOBS["drug_name"].timeout_s
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
    return (FOLDER_OF[name] / f"{name}.prompt.txt").read_bytes()


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
    return json.loads((FOLDER_OF[name] / f"{name}.form.json").read_text(encoding="utf-8"))


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


# The replies are checked by the app's own functions, check_labels
# (consult/labels.py) and check_doubtful (consult/drug_marks.py),
# imported above under the names the bench has used.
