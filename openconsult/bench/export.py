"""The public form of the engine bench (spec 15.8, rulings 2 and 11):
the cases, and for each arm every reply with its case, chain, point,
job, how it ended, the tokens and the seconds, as compressed text, with
the marks and the times as data.

The requests are never written: anyone can rebuild them from the cases,
the prompts and the code. From a file of recorded passes only the rows
of the listed consultation are taken. No path of the machine is written.
Nothing published is ever written over, and the marks can be worked out
again from the published replies alone.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from openconsult.bench import score
from openconsult.bench.cases import load_cases
from openconsult.bench.replay import answer_text, pass_row, why_failed
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult.cds_pass import Carried, settle
from openconsult.db import open_database
from openconsult.llm.door import Result
from openconsult.llm.record import ModelCalls

LIMIT = 30_000_000   # the whole public folder stays under 30 MB (spec 15.8)
NOTE = "The cases of the engine bench. Each is acted or scripted. None is a real patient."
JOBS = ("alarm", "assessment")
NUMBERS = ("prompt_tokens", "output_tokens", "wall_ms", "read_ms", "write_ms")


def as_json(found) -> bytes:
    return (json.dumps(found, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def publish(public: Path, files: dict[str, bytes]) -> int:
    """Write the files, all or none: never over a published file, and
    never past the limit. Gives the folder's size afterwards."""
    public = Path(public)
    held = sum(f.stat().st_size for f in public.rglob("*") if f.is_file()) if public.exists() else 0
    total = held + sum(len(data) for data in files.values())
    for name in files:
        if (public / name).exists():
            raise Refused(f"{public / name} is published and is never written over")
    if total > LIMIT:
        raise Refused(f"the public folder would be over 30 MB ({total} bytes)")
    for name, data in files.items():
        target = public / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return total


# ---------------------------------------------------------------- the cases

def case_files(private: Path) -> dict[str, bytes]:
    """The cases as they are published, with a list of their own. A
    script is copied byte for byte. Of a file of recorded passes, only
    the rows of the listed consultation are taken, each as it stands."""
    private = Path(private)
    load_cases(private)   # every private file is the one on the list
    files, listed = {}, []
    for entry in json.loads((private / "cases.json").read_text(encoding="utf-8"))["cases"]:
        source = private / entry["file"]
        entry = dict(entry)
        if entry["kind"] == "passes":
            rows = [line for line in source.read_text(encoding="utf-8").splitlines()
                    if line.strip() and json.loads(line).get("consultation") == entry["consultation"]]
            data = ("\n".join(rows) + "\n").encode("utf-8")
            entry["file"] = f"{entry['name']}.jsonl"
            entry["cut"] = f"the {len(rows)} recorded live transcripts, one pass each"
        else:
            data = source.read_bytes()
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        files[f"cases/{entry['file']}"] = data
        listed.append(entry)
    files["cases/cases.json"] = as_json({"note": NOTE, "cases": listed})
    return files


# ------------------------------------------------------------------ an arm

def reply_lines(results: dict, rows: dict) -> list[dict]:
    """One line for each call a result names, in the order they were
    made. Never the request."""

    def line(r: dict, point: int, job: str, call_id: int, **more) -> dict:
        row = rows[call_id]
        text, thinking = answer_text(row["reply"])
        return {"case": r["case"], "group": r["group"], "chain": r["chain"], "point": point, "job": job,
                **more, "outcome": row["outcome"], "detail": row["detail"],
                **{key: row[key] for key in NUMBERS}, "text": text, "thinking": thinking}

    lines = []
    for _, r in sorted(results.items()):
        if r.get("kind") == "repeat":
            lines += [line(r, r["point"], s["job"], s["call_id"], n=s["n"], role=s["role"], same=s.get("same"))
                      for s in r["sends"]]
            continue
        for p in r["passes"]:
            for job in JOBS:
                lines.append(line(r, p["point"], job, p[job]["call_id"], temperature=r["temperature"],
                                  seed=r["seed"], pass_ms=p["wall_ms"],
                                  kept=bool(p["assessment"].get("kept")) if job == "assessment" else None))
    return lines


def card_memory(csv: Path, windows: list[tuple[str, str]]) -> dict | None:
    """The sampler's readings inside the given windows, pooled: MiB in use.
    The windows are an arm's own steps, because the arms took turns
    through the day; or its first and last call, when no steps are given."""
    spans = [tuple(dt.datetime.fromisoformat(at).replace(tzinfo=None) for at in window) for window in windows]
    used = []
    for row in Path(csv).read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in row.split(",")]
        try:
            when = dt.datetime.strptime(parts[0], "%Y/%m/%d %H:%M:%S.%f")
            if any(start <= when <= end for start, end in spans):
                used.append(int(parts[1].split()[0]))
        except (ValueError, IndexError):
            continue
    if not used:
        return None
    return {"samples": len(used), "windows": len(spans), "lowest_mib": min(used), "median_mib": score.med(used),
            "highest_mib": max(used)}


def steps_of(steps_file: Path, arm: str) -> list[tuple[str, str]]:
    """The windows of an arm's own steps, from the published steps file."""
    steps = json.loads(Path(steps_file).read_text(encoding="utf-8"))["steps"]
    found = [(step["start"], step["end"]) for step in steps if step["arm"] == arm]
    if not found:
        raise Refused(f"{steps_file} names no step of the arm {arm}")
    return found


def pass_times(results: dict) -> dict:
    by_group = {}
    for r in results.values():
        for p in r["passes"]:
            by_group.setdefault(r["group"], []).append(p["wall_ms"])
            by_group.setdefault("all", []).append(p["wall_ms"])
    return {group: {"passes": len(ms), "median_ms": score.med(ms), "slowest_ms": max(ms)}
            for group, ms in sorted(by_group.items())}


def arm_files(name: str, out: Path, card: Path | None = None, facts: dict | None = None,
              steps: list[tuple[str, str]] | None = None) -> dict[str, bytes]:
    """An arm's public files, from its result files and its record of
    calls. The card's memory is taken over the arm's own steps when they
    are given, else between its first and last call."""
    results = ResultWriter(out).read_all()
    if not results:
        raise Refused(f"{out} holds no result")
    rows = {row["id"]: row for row in ModelCalls(open_database(Path(out) / "calls.db")).rows()}
    lines = reply_lines(results, rows)
    repeat = any(r.get("kind") == "repeat" for r in results.values())
    named = [rows[i] for r in results.values()
             for i in ([s["call_id"] for s in r["sends"]] if r.get("kind") == "repeat"
                       else [p[job]["call_id"] for p in r["passes"] for job in JOBS])]
    first, last = min(row["at"] for row in named), max(row["at"] for row in named)
    stamp = next(iter(results.values()))
    memory = card_memory(card, steps or [(first, last)]) if card else None
    arm = {"arm": name, "kind": "repeat" if repeat else "chains",
           "together": any(r.get("together") for r in results.values()),
           **{key: stamp.get(key) for key in ("engine", "engine_version", "model_tag", "model_digest", "prompts")},
           "cases": sorted({r["case"] for r in results.values()}),
           "chains": sorted({r["chain"] for r in results.values()}),
           "results": len(results), "calls": len(lines),
           "outcomes": dict(Counter(line["outcome"] for line in lines)),
           "first_call_at": first, "last_call_at": last,
           "card": {"over": "the arm's own steps" if steps else "first call to last call", **memory} if memory else None,
           "facts": facts or {}}
    packed = gzip.compress("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode("utf-8"),
                           mtime=0)   # no time stamp inside: the same run always gives the same file
    files = {f"arms/{name}/arm.json": as_json(arm), f"arms/{name}/replies.jsonl.gz": packed}
    if repeat:
        files[f"arms/{name}/repeat.json"] = as_json([
            {key: r[key] for key in ("case", "point", "job", "way", "times", "same_as_first")}
            for _, r in sorted(results.items())])
    else:
        files[f"arms/{name}/marks.json"] = as_json(score.summary(results))
        files[f"arms/{name}/times.json"] = as_json({"calls": score.call_times(named), "passes": pass_times(results)})
    return files


# ------------------------------------------------- back from what is published

def read_replies(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


def results_from_replies(lines: list[dict]) -> dict:
    """Each chain rebuilt from its published replies, by the same
    settling and the same rule for a failed chain as the run itself."""
    chains: dict[tuple, list] = {}
    for line in lines:
        if "n" not in line:   # not a line of the repeat test
            chains.setdefault((line["case"], line["chain"]), []).append(line)

    def as_result(line: dict) -> Result:
        ok = line["outcome"] == "ok"
        return Result(line["job"], ok, json.loads(line["text"]) if ok else None, None if ok else line["outcome"],
                      line["detail"], 0, line["wall_ms"], line["prompt_tokens"], line["output_tokens"])

    results = {}
    for key, mine in chains.items():
        carried, passes, failed, unreachable = Carried(), [], None, 0
        for alarm, assessment in zip(mine[0::2], mine[1::2]):
            result = settle(as_result(alarm), as_result(assessment), carried)
            carried = result.carried
            passes.append(pass_row(alarm["point"], alarm["pass_ms"], result))
            failures = [f for f in (result.alarm.failure, result.assessment.failure) if f]
            unreachable = unreachable + 1 if "unreachable" in failures else 0
            failed = why_failed(alarm["group"], alarm["point"], failures, unreachable)
            if failed:
                break
        first = mine[0]
        results[key] = {"case": first["case"], "group": first["group"], "chain": first["chain"],
                        "temperature": first["temperature"], "seed": first["seed"], "failed": failed,
                        "passes": passes}
    return results
