"""A made-up run of the test of 5d for the suite: base lines, setups and
ways round written in the shape the real commands write, from made-up
figures. Nothing here is what a model, an engine or a speech worker
said. Every builder takes the figures a test wants to move."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from openconsult.bench.writer import ResultWriter
from openconsult.db import open_database
from openconsult.llm.record import CallRow, ModelCalls

T0 = 1_800_000_000.0                     # the made-up moment the feed began
LM = "made-up-gemma:q4"
VLLM_MODEL = "made-up/repack"
ENV = {"nemotron": "/made-up/data/speech/nemotron/.venv/bin/python",
       "whisperx": "/made-up/data/speech/whisperx_pyannote/.venv/bin/python"}
ARM = {"nemotron": "nemotron", "whisperx": "whisperx_pyannote"}
SECOND = "/made-up/data/embedding/embeddinggemma2/.venv/bin/python"
ZONE = dt.timezone(dt.timedelta(hours=1))


def at(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, ZONE).isoformat(timespec="milliseconds")


def a_pass(point, call_ids, wall_ms, ectopic=True, test=True, failure=None, alarm_s=1.2):
    diffs = [{"condition": "Ectopic pregnancy" if ectopic else "Made-up thing", "likelihood": "high"}]
    raw = [{"action": "Urgent pregnancy test" if test else "Made-up step", "reason": "made up"}]
    return {"point": point, "wall_ms": wall_ms, "names": [d["condition"] for d in diffs],
            "alarm": {"judged": failure is None, "actions": raw, "raw_actions": raw, "flag_without_action": False,
                      "failure": failure, "call_id": call_ids[0]},
            "assessment": {"ok": True, "differentials": diffs, "questions": ["Last period?"], "failure": None,
                           "call_id": call_ids[1]}}


def write_chains(folder: Path, start_epoch: float, chains=("A1", "A2", "A3"), passes=11, wall_ms=4000,
                 ectopic=True, test=True, fail_at=None, chain_failed=None, alarm_ms=1200) -> tuple[float, float]:
    """Chains one after another from start_epoch, each pass wall_ms long;
    the record of calls beside them. Gives the stretch (first start, last end)."""
    folder = Path(folder)
    writer = ResultWriter(folder)
    db = open_database(folder / "calls.db")
    moment = {"epoch": start_epoch}
    record = ModelCalls(db, clock=lambda: dt.datetime.fromtimestamp(moment["epoch"], ZONE))
    first = start_epoch
    try:
        for chain in chains:
            rows = []
            for point in range(1, passes + 1):
                moment["epoch"] += wall_ms / 1000
                failure = "too_slow" if fail_at == (chain, point) else None
                ids = []
                for job, ms in (("alarm", alarm_ms), ("assessment", wall_ms - alarm_ms)):
                    ids.append(record.add(CallRow(job=job, engine="made-up", engine_version="0", model_tag=LM,
                                                  model_digest="d", prompt_sha256="p", request="{}", reply="{}",
                                                  prompt_tokens=10, output_tokens=5, wall_ms=ms, total_ms=ms,
                                                  load_ms=0, read_ms=1, write_ms=ms - 1,
                                                  outcome="too_slow" if failure and job == "alarm" else "ok",
                                                  detail="made-up: CUDA out of memory" if failure == "oom" else None)))
                rows.append(a_pass(point, ids, wall_ms, ectopic and not (chain == "A3" and point > 0 and ectopic == "A3-missing"),
                                   test, failure, alarm_ms / 1000))
            writer.write("495", chain, {"case": "495", "group": "495", "chain": chain, "temperature": 0.0, "seed": 42,
                                        "failed": chain_failed if chain == "A1" else None, "passes": rows,
                                        "engine": "made-up", "model_tag": LM})
    finally:
        db.close()
    return first, moment["epoch"]


def speech_result(t0: float, arm: str, lines, stop_t=315.0, failure=None, pause=None) -> dict:
    """A made-up speech result: lines as (end_s, wait_s) pairs, each final
    wait_s after its sound ended; the page at Stop holds their words."""
    pieces = []
    for n, (end, wait) in enumerate(lines, start=1):
        pieces.append({"n": n, "fed_s": end + wait, "t": round(end + wait, 3), "partial": "",
                       "lines": [{"speaker": "S0", "start": end - 1.0, "end": end, "text": f"made up line {n}",
                                  "confidence": None, "id": n}], "refused": [], "revisions": []})
    result = {"arm": arm, "recording": "473", "t0_epoch": t0, "pieces": pieces, "failure": failure,
              "stop": None if failure and failure["at"] == "stop" else
              {"t": stop_t, "t_asked": stop_t - 0.5, "lines": [p["lines"][0] for p in pieces], "last_live": [],
               "refused": [], "raw": [], "seconds": {"stop": 0.5}, "revisions": [], "speakers": {}, "notes": {}},
              "loudness": {"window_s": 0.1, "dbfs": [None] * int(stop_t * 10)}, "stamp": {"choice": arm}}
    if pause:
        result["stop_pause"] = pause
    return result


def write_speech(folder: Path, arm: str, result: dict) -> None:
    ResultWriter(Path(folder)).write(arm, "473", result)


def searches(n=33, device="cuda", fail_at=None, median_s=0.3, error="made-up: refused") -> dict:
    items = []
    for k in range(n):
        name = "Made-up condition"
        ok = k != fail_at
        items.append({"k": k, "names": [name], "due": 5.0 * k, "started": 5.0 * k, "started_epoch": T0 + 15 + 5.0 * k,
                      "late_s": 0.0, "late": False, "empty": False, "ok": ok, "error": None if ok else error,
                      "calls": [{"name": name, "wall_s": 0.3, "ok": ok, "error": None if ok else error, "fault": None, "own": {}}],
                      "ended": 5.0 * k + 0.3, "seconds": 0.3})
    return {"embedding": "made-up", "where": "card", "info": {"device": device, "dtype": "made-up"}, "every_s": 5.0,
            "t0_epoch": T0 + 15, "searches": items, "stopped_by": "limit", "late_starts": 0, "empty": 0,
            "failed": sum(1 for i in items if not i["ok"]), "median_s": median_s}


def reading(epoch: float, way: str, speech: str, embedding: str, where: str, lm_where="card", emb_where=None,
            speech_on=True, vllm_up=True, second_on_card=None) -> dict:
    emb_where = where if emb_where is None else emb_where
    size = 15_000
    vram_of = {"card": size, "processor": 0, "split": size // 2}
    first = {"name": "embeddinggemma:latest", "size": 600, "size_vram": {"card": 600, "processor": 0, "split": 300}[emb_where]}
    lm = {"name": LM, "size": size, "size_vram": vram_of.get(lm_where, size)}
    service_models = [first] if embedding == "first" else []
    private_models = []
    if way == "ollama-one" and lm_where != "gone":
        service_models.append(lm)
    if way == "ollama-together" and lm_where != "gone":
        private_models.append(lm)
    programs = [{"pid": 1, "name": ENV[speech], "mib": 4000}] if speech_on else []
    on_card = where == "card" if second_on_card is None else second_on_card
    if embedding == "second" and on_card:
        programs.append({"pid": 2, "name": SECOND, "mib": 1300})
    found = {"at_epoch": epoch, "service": {"available": True, "models": service_models},
             "card": {"available": True, "error": None, "programs": programs}}
    if way == "ollama-together":
        found["private"] = {"available": True, "models": private_models}
    if way.startswith("vllm"):
        found["vllm"] = {"available": vllm_up and lm_where != "gone", "health": 200 if vllm_up else 0,
                         "models": [VLLM_MODEL] if vllm_up and lm_where != "gone" else []}
    return found


def watch(t0: float, stop_t: float, way, speech, embedding, where, odd: dict | None = None, **kwargs) -> dict:
    """Readings every 5 s from 5 s before the feed to 5 s after Stop; odd
    maps an offset in seconds to keyword changes for that one reading."""
    readings = []
    offset = -5.0
    while offset <= stop_t + 5.0:
        over = {**kwargs, **(odd or {}).get(offset, {})}
        readings.append(reading(t0 + offset, way, speech, embedding, where, **over))
        offset += 5.0
    return {"every_s": 5.0, "sources": ["card", "service"], "readings": readings}


def setup_json(name, way, speech, embedding, where, kind="setup", **extra) -> dict:
    model = VLLM_MODEL if way.startswith("vllm") else LM
    return {"name": name, "kind": kind, "way": way, "speech": speech, "embedding": embedding, "where": where,
            "chains": list(extra.pop("chains", ("A1", "A2", "A3"))),
            "engine": {"kind": way.split("-")[0], "address": "http://127.0.0.1:1", "model": model, "digest": "d", "version": "0"},
            "vllm_kv_cache_bytes": 1_400_000_000 if way.startswith("vllm") else None, "recording": "473",
            "steps": {"load_language": {"start_epoch": T0 - 60, "end_epoch": T0 - 50},
                      "load_embedding": {"start_epoch": T0 - 50, "end_epoch": T0 - 40}}, **extra}


def write_setup(run: Path, name, way="ollama-one", speech="nemotron", embedding="first", where="card",
                wall_ms=4000, lines=None, watch_kwargs=None, search_kwargs=None, chain_kwargs=None,
                after_kwargs=None, speech_failure=None, kind="setups", setup_extra=None, pause=None) -> Path:
    """One setup folder with every file a run writes, from made-up figures.
    The chains start 15 s into the feed."""
    folder = Path(run) / kind / name
    folder.mkdir(parents=True)
    extra = dict(setup_extra or {})
    kind_word = "wayround" if kind == "wayround" else "setup"
    (folder / "setup.json").write_text(json.dumps(setup_json(name, way, speech, embedding, where, kind_word, **extra)),
                                       encoding="utf-8")
    start, end = write_chains(folder / "chains", T0 + 15, wall_ms=wall_ms, **(chain_kwargs or {}))
    write_chains(folder / "after-stop", T0 + 330, chains=("A1",), wall_ms=wall_ms, **(after_kwargs or {}))
    stop_t = 315.0
    write_speech(folder / "speech", ARM[speech], speech_result(T0, ARM[speech], lines if lines is not None else default_lines(),
                                                                stop_t, speech_failure, pause))
    (folder / "searches.json").write_text(json.dumps(searches(**(search_kwargs or {}))), encoding="utf-8")
    (folder / "watch.json").write_text(json.dumps(watch(T0, stop_t, way, speech, embedding, where, **(watch_kwargs or {}))),
                                       encoding="utf-8")
    return folder


def default_lines(wait=2.0, growth=0.0, every=3.0, until=312.0):
    """A line every few seconds through the recording, each final `wait`
    after its sound, the wait growing by `growth` over the recording."""
    lines, end = [], 3.0
    while end < until:
        lines.append((end, round(wait + growth * end / until, 3)))
        end += every
    return lines


def write_base(run: Path, which: str, lm_ms=None, speech_lines=None, speech_missing=(), lm_missing=()) -> None:
    """Base lines before or after: the four ways, the two speech choices,
    the four embedding setups, and (before) the side reading."""
    base = Path(run) / which
    for way in ("ollama-one", "ollama-together", "vllm-one", "vllm-together"):
        if way in lm_missing:
            continue
        write_chains(base / f"lm-{way}" / "chains", T0 - 10_000, wall_ms=(lm_ms or {}).get(way, 4000))
    for choice in ("nemotron", "whisperx"):
        if choice in speech_missing:
            continue
        lines = (speech_lines or {}).get(choice, default_lines())
        write_speech(base / f"speech-{choice}" / "speech", ARM[choice], speech_result(T0 - 5_000, ARM[choice], lines))
    for m in ("first", "second"):
        for w in ("card", "processor"):
            folder = base / f"embed-{m}-{w}"
            folder.mkdir(parents=True)
            (folder / "searches.json").write_text(json.dumps(searches(device="cuda" if w == "card" else "cpu")), encoding="utf-8")
            if which == "base-before":
                index = base / f"index-{m}-{w}"
                index.mkdir(parents=True)
                (index / "index.json").write_text(json.dumps({"seconds": 12.5, "pieces": 250, "ok": True, "batches": []}),
                                                  encoding="utf-8")


def card_samples(t0: float, used=18_000, programs=None) -> dict:
    """The sampler's samples, every 2 s around the feed, as the judge reads them."""
    samples, progs = [], []
    epoch = t0 - 70
    while epoch < t0 + 400:
        samples.append({"epoch": epoch, "used": used, "total": 24_564})
        for name, mib in (programs or {"made-up-engine": 17_000, ENV["nemotron"]: 4_000}).items():
            progs.append({"epoch": epoch, "name": name, "mib": mib})
        epoch += 2
    return {"samples": samples, "programs": progs}
