"""The word check (spec 15.7, ruling 3; 15.8, ruling 43). It needs no
model. For every assessment and alarm call v1 recorded with the patient
line, v2 builds its own request from the same case, the same point in it
and the same earlier answer, and compares: the message, the model, the
thinking switch and the options one by one; the prompt sent against the
spec's approved hash (ruling 43: the prompts are the spec's words now,
not v1's); and then the whole body with v1's key order and v1's own
prompt put back in its slot, which carries the form and every other
part. v1's prompt texts are given in a folder and are proven first
against the hashes v1's own arm-start records carry. The Ollama engine's
own builder makes the body; truncate, the one key v1 did not send, is
removed before the whole-body hash (HANDOVER, stage 3: the door sends truncate false).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from openconsult.bench.cases import Case
from openconsult.consult.messages import alarm_message, assessment_message, names_of, with_patient
from openconsult.llm.door import Door
from openconsult.llm.ollama import build_request, encode
from openconsult.llm.profile import Sampling
from openconsult.prompts import loader

V1_JOB = {"assessment": "assessment", "urgency": "alarm"}
V1_RECORDED = {"assessment": "assessment_prompt_sha256", "alarm": "urgency_prompt_sha256"}


def v1_prompts_as_recorded(path: Path, folder: Path, arm: str = "D") -> dict[str, str]:
    """v1's two prompt texts from the folder, read as the loader reads a
    prompt, each proven against the hash the v1 file's arm-start records
    carry. A text that differs is refused with both hashes named."""
    recorded: dict[str, set[str]] = {job: set() for job in V1_RECORDED}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") == arm and r.get("call") == "arm_start":
            for job, key in V1_RECORDED.items():
                recorded[job].add(r[key])
    texts = {}
    for job in V1_RECORDED:
        text = Path(folder, f"{job}.prompt.txt").read_text(encoding="utf-8")
        text = text[:-1] if text.endswith("\n") else text
        found = loader.sha256(text)
        if recorded[job] != {found}:
            raise ValueError(f"v1's {job} prompt in {folder} hashes to {found}; "
                             f"{path} recorded {', '.join(sorted(recorded[job])) or 'nothing'}")
        texts[job] = text
    return texts


def load_records(path: Path, arm: str = "D") -> list[dict]:
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") == arm and r.get("call") in V1_JOB and not r.get("error"):
            records.append(r)
    return records


def where(r: dict) -> tuple[str, str, int]:
    """(case key, chain key, point) of one v1 record. v1 wrote the case
    key on every record: the consultation, the travel case or the script's
    file name."""
    key = r["case_key"]
    if r["workload"] == "495":
        return key, r["chain"], r["pass"]
    if r["workload"] == "travel":
        return key, r["chain"], r["end_turn"]
    return key, f"{r['workload']}:{r.get('chain', 'single')}", r["update"]


def _case_for(cases: list[Case], key: str) -> Case:
    for case in cases:
        if case.name == key or case.path.name == key:
            return case
    raise KeyError(f"no case on the list for {key}")


def earlier_names(by_chain: dict, chain: str, point: int) -> tuple[str, ...]:
    """The stale list as v1 held it: the latest earlier assessment of the
    same chain whose reply parsed (a failed one kept the one before)."""
    for earlier_point in sorted((p for p in by_chain.get(chain, {}) if p < point), reverse=True):
        content = by_chain[chain][earlier_point]
        try:
            parsed = json.loads(content) if content else None
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return names_of(parsed.get("differentials"))
    return ()


def check(records: list[dict], cases: list[Case], door: Door, v1_prompts: dict[str, str],
          approved: dict[str, str] = loader.APPROVED) -> dict:
    """The count of v1 calls v2 rebuilds exactly, and every mismatch."""
    transcripts: dict[str, list[tuple[int, str]]] = {}
    by_chain: dict[tuple[str, str], dict[int, str]] = {}
    for r in records:
        if r["call"] == "assessment":
            key, chain, point = where(r)
            by_chain.setdefault((key, chain), {})[point] = r.get("reply_content")
    matched, mismatches = Counter(), []
    for r in records:
        key, chain, point = where(r)
        case = _case_for(cases, key)
        if case.name not in transcripts:
            transcripts[case.name] = case.points()
        points = transcripts[case.name]
        # v1 numbered a script's points by update (1, 2, ...), the rest by pass or turn.
        transcript = points[point - 1][1] if r["workload"] in ("urgency", "restraint") else dict(points)[point]
        job = V1_JOB[r["call"]]
        if job == "alarm":
            plain = alarm_message(transcript)
        else:
            plain = assessment_message(transcript, earlier_names({chain: by_chain.get((key, chain), {})}, chain, point))
        user = with_patient(plain, case.patient)
        options = r["options_sent"]
        call = door.call_for(job, user, Sampling(options["temperature"], options["seed"]))
        body = build_request(call)
        wrong = []
        if hashlib.sha256(user.encode("utf-8")).hexdigest() != r["user_sha256"]:
            wrong.append("message")
        if loader.sha256(body["messages"][0]["content"]) != approved[job]:
            wrong.append("prompt")
        if body["model"] != r["model"]:
            wrong.append("model")
        if body["think"] is not r["think_sent"]:
            wrong.append("think")
        if list(body["options"].items()) != list(options.items()):
            wrong.append("options")
        as_v1 = {k: v for k, v in body.items() if k != "truncate"}
        as_v1["messages"] = [{**body["messages"][0], "content": v1_prompts[job]}, *body["messages"][1:]]
        if hashlib.sha256(encode(as_v1)).hexdigest() != r["request_sha256"]:
            wrong.append("whole request with v1's prompt in place (form or any part)")
        label = (r["workload"], job)
        if wrong:
            mismatches.append({"where": [key, chain, point], "job": job, "differs_in": wrong})
        else:
            matched[label] += 1
    total = len(records)
    return {"total": total, "matched": sum(matched.values()),
            "by_workload_and_job": {f"{w}/{j}": n for (w, j), n in sorted(matched.items())},
            "mismatches": mismatches}
