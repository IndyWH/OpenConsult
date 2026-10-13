"""The four lines of ruling 23, as code judges them from the stored
results alone (spec 15.9, rulings 23 to 25, the details of 5d; 15.8
ruling 21). A setup works when it meets all four; misses one and it is
not working, with the first line it missed and the reason; where line
three or four cannot be judged and no other line is missed, the third
word, not judged. A way round is judged by the same lines, kept apart,
and never counted as a setup. Nothing here loads a model or asks an
engine: it reads what the run wrote."""

from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path

from openconsult.bench import score
from openconsult.bench.shared.embed import where_is
from openconsult.bench.speech.waits import live_lines
from openconsult.bench.writer import ResultWriter
from openconsult.db import open_database
from openconsult.llm.record import ModelCalls
from openconsult.speech.matching import normalise

WAYS = ("ollama-one", "ollama-together", "vllm-one", "vllm-together")
SPEECH = ("nemotron", "whisperx")
EMBEDDINGS = ("first", "second")
WHERE = ("card", "processor")
ARM_OF = {"nemotron": "nemotron", "whisperx": "whisperx_pyannote"}
# The worker's process on the card is told by its environment's folder in its name.
ENV_OF = {"nemotron": "speech/nemotron", "whisperx": "speech/whisperx_pyannote"}
SECOND_ENV = "embedding/embeddinggemma2"
FIRST_MODEL = "embeddinggemma"
DEVICE_OF = {"card": "cuda", "processor": "cpu"}
CHAINS = ("A1", "A2", "A3")
LINE_THREE_S = 0.5        # ruling 23, line three: less than half a second longer
STEADY_S = 0.25           # 15.8 ruling 21: the two base lines of a way within a quarter of a second
LINE_FOUR_S = 1.0         # ruling 23, line four: a second or more longer, or growing a second more
# The words a worker's own libraries use when the card is full: torch's
# OutOfMemoryError, and ctranslate2's "MemoryError: batch_size ... is
# probably too large" (seen at Stop in the proof of 13 Oct 2026).
MEMORY_WORDS = ("out of memory", "outofmemory", "memoryerror", "memory error")
WORDS = {True: "works", False: "not working", None: "not judged"}


def epoch_of(at: str) -> float:
    return dt.datetime.fromisoformat(at).timestamp()


def median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 3) if values else None


def says_memory(text) -> bool:
    low = (text or "").lower()
    return any(word in low for word in MEMORY_WORDS)


# ------------------------------------------------------------ what is read

def read_chains(folder: Path) -> dict | None:
    """A bench run folder: its chain results and its record of calls."""
    folder = Path(folder)
    if not (folder / "results").is_dir() or not (folder / "calls.db").is_file():
        return None
    results = {chain: r for (case, chain), r in ResultWriter(folder).read_all().items()}
    db = open_database(folder / "calls.db")
    try:
        rows = {row["id"]: row for row in ModelCalls(db).rows()}
    finally:
        db.close()
    return {"results": results, "calls": rows}


def read_json(path: Path) -> dict | None:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def read_speech(folder: Path) -> dict | None:
    folder = Path(folder)
    found = ResultWriter(folder).read_all() if (folder / "results").is_dir() else {}
    return next(iter(found.values()), None)


def passes_of(chains: dict | None) -> list[dict]:
    """Every pass with its wall time and, from the record, its start and
    end on the machine's clock: a pass ends at its last call's end and
    starts a wall time before that."""
    found = []
    for name, result in sorted((chains or {}).get("results", {}).items()):
        for p in result["passes"]:
            ends = [epoch_of(chains["calls"][p[job]["call_id"]]["at"]) for job in ("alarm", "assessment")
                    if p[job].get("call_id") in chains["calls"]]
            end = max(ends) if ends else None
            found.append({"chain": name, "point": p["point"], "wall_s": p["wall_ms"] / 1000,
                          "end_epoch": end, "start_epoch": end - p["wall_ms"] / 1000 if end else None,
                          "failures": [f for f in (p["alarm"].get("failure"), p["assessment"].get("failure")) if f],
                          "alarm_s": _call_s(chains, p["alarm"].get("call_id"))})
    return found


def _call_s(chains: dict, call_id) -> float | None:
    row = chains["calls"].get(call_id)
    return row["wall_ms"] / 1000 if row else None


def typical_pass(chains: dict | None) -> float | None:
    return median([p["wall_s"] for p in passes_of(chains)])


def stretch_of(chains: dict | None) -> tuple[float, float] | None:
    """From the start of the first pass to the end of the last, over the chains."""
    passes = [p for p in passes_of(chains) if p["start_epoch"] is not None]
    if not passes:
        return None
    return min(p["start_epoch"] for p in passes), max(p["end_epoch"] for p in passes)


# ----------------------------------------------------------- the base lines

def read_base(run: Path, which: str) -> dict:
    base = Path(run) / which
    return {"lm": {way: read_chains(base / f"lm-{way}" / "chains") for way in WAYS},
            "speech": {choice: read_speech(base / f"speech-{choice}" / "speech") for choice in SPEECH},
            "embed": {f"{m}-{w}": read_json(base / f"embed-{m}-{w}" / "searches.json") for m in EMBEDDINGS for w in WHERE},
            "index": {f"{m}-{w}": read_json(base / f"index-{m}-{w}" / "index.json") for m in EMBEDDINGS for w in WHERE}}


def steadiness(before: dict, after: dict) -> dict:
    """For each way: the two typical passes, their difference, and whether
    line three can be judged (15.8 ruling 21: within 0.25 s, both there)."""
    found = {}
    for way in WAYS:
        b, a = typical_pass(before["lm"].get(way)), typical_pass(after["lm"].get(way))
        diff = round(abs(a - b), 3) if a is not None and b is not None else None
        if b is None or a is None:
            reason = f"the base line {'before' if b is None else 'after'} is missing for {way}"
        elif diff > STEADY_S:
            reason = f"the two base lines of {way} differ by {diff:.2f} s, more than {STEADY_S} s: the day was not steady"
        else:
            reason = None
        found[way] = {"before": b, "after": a, "difference": diff, "mean": round((a + b) / 2, 3) if reason is None else None,
                      "judged": reason is None, "reason": reason}
    return found


# ------------------------------------------------------------------ line one

def fed_seconds(speech: dict | None) -> float | None:
    """When the sound ended: Stop's moment, or, when Stop gave nothing,
    the seconds of sound fed by the loudness windows the result keeps."""
    stop = (speech or {}).get("stop") or {}
    if stop.get("t") is not None:
        return stop["t"]
    loudness = (speech or {}).get("loudness") or {}
    windows = loudness.get("dbfs") or []
    if windows and loudness.get("window_s"):
        return len(windows) * loudness["window_s"]
    return max((p["fed_s"] for p in (speech or {}).get("pieces", [])), default=0.0)


def _readings_in(watch: dict | None, t0: float | None, stop: float | None) -> list[dict]:
    """The reading before the recording, every reading while it ran, and
    the first after Stop."""
    readings = sorted((watch or {}).get("readings", []), key=lambda r: r["at_epoch"])
    if t0 is None:
        return readings
    before = [r for r in readings if r["at_epoch"] <= t0]
    during = [r for r in readings if t0 < r["at_epoch"] <= (stop if stop is not None else float("inf"))]
    after = [r for r in readings if stop is not None and r["at_epoch"] > stop]
    return before[-1:] + during + after[:1]


def _at(reading: dict, t0: float | None) -> str:
    return f"{reading['at_epoch'] - t0:.0f} s" if t0 is not None else "a reading"


def _language_where(reading: dict, setup: dict) -> str:
    way, model = setup["way"], setup["engine"]["model"]
    if way.startswith("vllm"):
        engine = reading.get("vllm") or {}
        return "card" if engine.get("available") and model in (engine.get("models") or []) else "gone"
    source = reading.get("private" if way == "ollama-together" else "service") or {}
    if not source.get("available", False):
        return "unread"
    found = where_is(source.get("models"), model)
    return found["placement"] if found else "gone"


def _embedding_where(reading: dict, setup: dict) -> str:
    if setup["embedding"] == "first":
        source = reading.get("service") or {}
        if not source.get("available", False):
            return "unread"
        found = where_is(source.get("models"), FIRST_MODEL)
        return found["placement"] if found else "gone"
    programs = (reading.get("card") or {}).get("programs") or []
    on_card = any(SECOND_ENV in (p.get("name") or "") for p in programs)
    return "card" if on_card else "processor"


def _speech_on_card(reading: dict, speech: str) -> bool:
    programs = (reading.get("card") or {}).get("programs") or []
    return any(ENV_OF[speech] in (p.get("name") or "") for p in programs)


def line_one(setup: dict, watch: dict | None, speech: dict | None, searches: dict | None, chains: dict | None,
             after: dict | None, t0: float | None, stop_epoch: float | None) -> dict:
    """All on the card, and nothing moved; no program out of memory."""
    reasons = []
    allowed_off = setup.get("wayround") or {}
    if speech is None:
        reasons.append("the speech worker gave no result")
    elif speech.get("failure"):
        at, detail = speech["failure"].get("at"), speech["failure"].get("detail") or ""
        if says_memory(detail):
            reasons.append(f"the speech worker ran out of memory at {at}")
        elif at == "open":
            reasons.append(f"the speech worker would not start: {detail[:160]}")
    for item in (searches or {}).get("searches", []):
        for call in item["calls"]:
            if says_memory(call.get("error")):
                reasons.append(f"the embedding model ran out of memory at search {item['k']}")
                break
    for run in (chains, after):
        for row in (run or {}).get("calls", {}).values():
            if says_memory(row.get("detail")):
                reasons.append(f"the language model ran out of memory ({row['job']})")
                break
    if setup["embedding"] == "second" and searches is not None:
        device = (searches.get("info") or {}).get("device")
        if device != DEVICE_OF[setup["where"]]:
            reasons.append(f"the worker of EmbeddingGemma 2 ran on {device}, not where the setup asked ({setup['where']})")
    readings = _readings_in(watch, t0, stop_epoch)
    if not readings:
        reasons.append("no reading of the lists was made")
    for reading in readings:
        at = reading["at_epoch"]
        off_allowed = allowed_off and allowed_off.get("wanted_epoch", 0) <= at <= allowed_off.get("back_epoch", 0)
        where = _language_where(reading, setup)
        if where != "card" and not off_allowed:
            said = {"gone": "was unloaded", "split": "was split between the card and the processor",
                    "processor": "was on the processor", "unread": "could not be read on its list"}[where]
            reasons.append(f"the language model {said} at {_at(reading, t0)}")
            break
    for reading in readings:
        where = _embedding_where(reading, setup)
        if where != setup["where"]:
            reasons.append(f"the embedding model was {where if where != 'gone' else 'unloaded'} at {_at(reading, t0)}, "
                           f"not on the {setup['where']}")
            break
    during = [r for r in readings if t0 is not None and t0 <= r["at_epoch"] <= (stop_epoch or float("inf"))]
    if during and not all(_speech_on_card(r, setup["speech"]) for r in during):
        gone = next(r for r in during if not _speech_on_card(r, setup["speech"]))
        reasons.append(f"the speech worker was not on the card at {_at(gone, t0)}")
    return {"met": not reasons, "reason": "; ".join(reasons) or None}


# ------------------------------------------------------------------ line two

def line_two(chains: dict | None, after: dict | None, searches: dict | None, expected=CHAINS) -> dict:
    """No call fails, and the hard marks of 495 hold in each chain the
    setup ran (three in the test; the proof runs one)."""
    reasons = []
    for label, run in (("the chains", chains), ("the chain after Stop", after)):
        if run is None:
            reasons.append(f"{label} did not run")
            continue
        for name, result in sorted(run["results"].items()):
            if result.get("failed"):
                reasons.append(f"chain {name} failed: {result['failed']}")
            for p in result["passes"]:
                for job in ("alarm", "assessment"):
                    if p[job].get("failure"):
                        reasons.append(f"a call failed: {job} at point {p['point']} of chain {name} ({p[job]['failure']})")
    if chains is not None:
        for name in expected:
            result = chains["results"].get(name)
            if result is None:
                reasons.append(f"chain {name} is missing")
                continue
            marks = score.score_495(result)
            if marks["considered"] is None:
                reasons.append(f"the hard mark H1 was missed in chain {name}: ectopic pregnancy never on the list")
            if marks["tested"] is None:
                reasons.append(f"the hard mark H2 was missed in chain {name}: the alarm never named a pregnancy test or hCG")
    if searches is None:
        reasons.append("the searches did not run")
    for item in (searches or {}).get("searches", []):
        if not item["ok"]:
            bad = next((c for c in item["calls"] if not c["ok"]), None)
            reasons.append(f"search {item['k']} failed for {bad['name']}: {bad['error'] or bad['fault']}" if bad else f"search {item['k']} failed")
            break
    return {"met": not reasons, "reason": "; ".join(reasons) or None}


# ---------------------------------------------------------------- line three

def line_three(chains: dict | None, steady: dict) -> dict:
    typical = typical_pass(chains)
    if not steady["judged"]:
        return {"met": None, "reason": steady["reason"], "typical_s": typical, "base_s": None, "longer_s": None}
    if typical is None:
        return {"met": None, "reason": "no pass was timed", "typical_s": None, "base_s": steady["mean"], "longer_s": None}
    longer = round(typical - steady["mean"], 3)
    met = longer < LINE_THREE_S
    reason = None if met else f"the typical pass was {typical:.2f} s, {longer:.2f} s longer than {steady['mean']:.2f} s with the card to itself"
    return {"met": met, "reason": reason, "typical_s": typical, "base_s": steady["mean"], "longer_s": longer}


# ----------------------------------------------------------------- line four

def waits_in(result: dict | None, start_s: float, end_s: float) -> list[float]:
    """The waits, end of sound to final, of the live lines whose sound ends
    inside the stretch, in seconds of the recording: the field is the
    same for every choice (pieces[].lines[].end and the piece's t)."""
    if not result or result.get("stop") is None and not result.get("pieces"):
        return []
    return [round(line["t"] - line["end"], 3) for line in live_lines(result) if start_s <= line["end"] < end_s]


def wait_figures(result: dict | None, start_s: float, end_s: float) -> dict:
    middle = (start_s + end_s) / 2
    whole, first, second = (waits_in(result, start_s, end_s), waits_in(result, start_s, middle), waits_in(result, middle, end_s))
    growth = (median(second) - median(first)) if first and second else None
    return {"typical_s": median(whole), "lines": len(whole), "first_half_s": median(first), "first_half_lines": len(first),
            "second_half_s": median(second), "second_half_lines": len(second),
            "growth_s": round(growth, 3) if growth is not None else None}


def line_four(speech: dict | None, chains: dict | None, bases: list[dict | None]) -> dict:
    """The live transcript keeps up: judged on the lines whose sound ends
    while the language model is busy, against the same stretch of the
    speech choice alone (the mean of its two base lines)."""
    found = {"met": None, "reason": None, "setup": None, "base": None, "stretch_s": None}
    if speech is not None and speech.get("failure") and speech["failure"].get("at") == "stop" \
            and not says_memory(speech["failure"].get("detail")):
        return {**found, "met": False, "reason": f"Stop gave no transcript: {speech['failure'].get('detail', '')[:160]}"}
    if any(b is None or b.get("failure") for b in bases) or len(bases) != 2:
        return {**found, "reason": "the speech choice lacks one of its two base lines"}
    if speech is None or speech.get("t0_epoch") is None:
        return {**found, "reason": "the setup has no speech result"}
    stretch = stretch_of(chains)
    if stretch is None:
        return {**found, "reason": "the language model was never busy: no pass was timed"}
    start_s, end_s = (stretch[0] - speech["t0_epoch"], stretch[1] - speech["t0_epoch"])
    found["stretch_s"] = [round(start_s, 3), round(end_s, 3)]
    setup, base_figures = wait_figures(speech, start_s, end_s), [wait_figures(b, start_s, end_s) for b in bases]
    base = {key: (median([b[key] for b in base_figures]) if key.endswith("_s") else sum(b[key] for b in base_figures))
            for key in setup}
    base["typical_s"] = _mean([b["typical_s"] for b in base_figures])
    base["growth_s"] = _mean([b["growth_s"] for b in base_figures])
    found.update(setup=setup, base=base)
    if base["lines"] == 0:
        return {**found, "reason": "the speech choice alone gave no line in the stretch"}
    if setup["lines"] == 0:
        return {**found, "met": False, "reason": "no line reached the page while the language model was busy"}
    reasons = []
    longer = round(setup["typical_s"] - base["typical_s"], 3)
    if longer >= LINE_FOUR_S:
        reasons.append(f"the typical wait was {setup['typical_s']:.2f} s, {longer:.2f} s longer than {base['typical_s']:.2f} s alone")
    if setup["growth_s"] is not None and base["growth_s"] is not None and setup["growth_s"] - base["growth_s"] >= LINE_FOUR_S:
        reasons.append(f"the wait grew by {setup['growth_s']:.2f} s from the first half to the second, "
                       f"against {base['growth_s']:.2f} s alone")
    return {**found, "met": not reasons, "reason": "; ".join(reasons) or None, "longer_s": longer}


def _mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


# ---------------------------------------------------------------- one setup

def judge_setup(folder: Path, steady: dict, speech_bases: list, card=None) -> dict:
    """One setup or way round, from its folder, against the base lines."""
    folder = Path(folder)
    setup = read_json(folder / "setup.json") or {"name": folder.name, "way": "ollama-one", "speech": "nemotron",
                                                  "embedding": "first", "where": "card", "engine": {"model": ""}}
    chains, after = read_chains(folder / "chains"), read_chains(folder / "after-stop")
    speech, searches, watch = read_speech(folder / "speech"), read_json(folder / "searches.json"), read_json(folder / "watch.json")
    t0 = (speech or {}).get("t0_epoch")
    stop = (speech or {}).get("stop") or {}
    stop_epoch = t0 + fed_seconds(speech) if t0 is not None else None
    lines = {1: line_one(setup, watch, speech, searches, chains, after, t0, stop_epoch),
             2: line_two(chains, after, searches, tuple(setup.get("chains") or CHAINS)),
             3: line_three(chains, steady),
             4: line_four(speech, chains, speech_bases)}
    missed = [n for n in (1, 2, 3, 4) if lines[n]["met"] is False]
    not_judged = [n for n in (3, 4) if lines[n]["met"] is None]
    works = False if missed else (None if not_judged else True)
    return {"name": setup.get("name", folder.name), "kind": setup.get("kind", "setup"), "way": setup["way"],
            "speech": setup["speech"], "embedding": setup["embedding"], "where": setup["where"],
            "engine": setup.get("engine"), "vllm_kv_cache_bytes": setup.get("vllm_kv_cache_bytes"),
            "lines": {str(n): lines[n] for n in lines}, "first_missed": missed[0] if missed else None,
            "not_judged": not_judged, "works": works, "word": WORDS[works],
            "measured": measured(setup, chains, after, speech, searches, stop, t0, card)}


def measured(setup, chains, after, speech, searches, stop, t0, card) -> dict:
    """Written for every setup, and not lines."""
    passes = passes_of(chains)
    final = [normalise(line["text"]) for line in stop.get("lines", [])] if stop else []
    return {"typical_pass_s": typical_pass(chains), "slowest_pass_s": max((p["wall_s"] for p in passes), default=None),
            "alarm_answer_s": median([p["alarm_s"] for p in passes]),
            "stop_s": round(stop["t"] - stop["t_asked"], 3) if stop and stop.get("t_asked") is not None else None,
            "stop_seconds": dict(stop.get("seconds") or {}) if stop else None,
            "stop_pause": (speech or {}).get("stop_pause"),
            "after_stop_typical_s": typical_pass(after),
            "search_median_s": (searches or {}).get("median_s"), "searches": len((searches or {}).get("searches", [])),
            "late_starts": (searches or {}).get("late_starts"), "searches_failed": (searches or {}).get("failed"),
            "final_words": sum(len(w) for w in final), "speech_failure": (speech or {}).get("failure"),
            "card": card_steps(setup, card, t0, stop) if card else None}


def words_that_differ(final_a: list[dict], final_b: list[dict]) -> int:
    """The words of one page at Stop set against another's, both normalised
    (speech/matching.py): the count of words standing in one and not the other."""
    import difflib
    a = [w for line in final_a for w in normalise(line["text"])]
    b = [w for line in final_b for w in normalise(line["text"])]
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")


def card_steps(setup: dict, card: dict, t0, stop) -> dict:
    """The card's memory, in MiB, at each step of the setup: the highest
    reading of the sampler inside each step's window, in all and for each
    program. The sampler writes MiB and nothing here changes the unit."""
    windows = dict((setup.get("steps") or {}).items())
    if t0 is not None and stop and stop.get("t_asked") is not None:
        windows["recording"] = {"start_epoch": t0, "end_epoch": t0 + stop["t_asked"]}
        windows["stop"] = {"start_epoch": t0 + stop["t_asked"], "end_epoch": t0 + stop["t"]}
    found = {}
    for name, window in windows.items():
        start, end = window.get("start_epoch"), window.get("end_epoch")
        if start is None or end is None:
            continue
        used = [s["used"] for s in card.get("samples", []) if start <= s["epoch"] <= end]
        programs = {}
        for s in card.get("programs", []):
            if start <= s["epoch"] <= end and s.get("mib") is not None:
                programs[s["name"]] = max(programs.get(s["name"], 0), s["mib"])
        found[name] = {"used_mib_max": max(used) if used else None, "samples": len(used),
                       "programs_mib_max": dict(sorted(programs.items()))}
    return found


# ---------------------------------------------------------------- the run

def judge_run(run: Path, card: dict | None = None) -> dict:
    """Everything, from the run folder: the base lines, the steadiness of
    each way, every setup, every way round apart, and the counts."""
    run = Path(run)
    before, after = read_base(run, "base-before"), read_base(run, "base-after")
    steady = steadiness(before, after)
    speech_bases = {choice: [before["speech"][choice], after["speech"][choice]] for choice in SPEECH}
    setups, wayrounds = [], []
    for kind, folder, into in (("setups", run / "setups", setups), ("wayround", run / "wayround", wayrounds)):
        for child in sorted(p for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []:
            setup = read_json(child / "setup.json") or {}
            way = setup.get("way", "ollama-one")
            judged = judge_setup(child, steady[way], speech_bases[setup.get("speech", "nemotron")], card)
            if kind == "wayround":
                judged["kind"] = "way round"
            into.append(judged)
    for judged in setups:
        judged["measured"]["words_differ_from_alone"] = _differ(run, judged, speech_bases)
    counts = {engine: {"works": 0, "not working": 0, "not judged": 0} for engine in ("ollama", "vllm")}
    for judged in setups:
        counts[judged["way"].split("-")[0]][judged["word"]] += 1
    return {"base_before": summary_of(before), "base_after": summary_of(after), "steadiness": steady,
            "setups": setups, "wayrounds": wayrounds, "counts": counts, "pointers": pointers(setups)}


def _differ(run: Path, judged: dict, speech_bases: dict) -> int | None:
    speech = read_speech(run / "setups" / judged["name"] / "speech")
    base = speech_bases[judged["speech"]][0]
    if not speech or not speech.get("stop") or not base or not base.get("stop"):
        return None
    return words_that_differ(speech["stop"]["lines"], base["stop"]["lines"])


def summary_of(base: dict) -> dict:
    return {"lm": {way: typical_pass(chains) for way, chains in base["lm"].items()},
            "speech": {choice: (None if r is None else {"lines": len(live_lines(r)), "failure": r.get("failure"),
                                                        "stop_s": (r.get("stop") or {}).get("t")})
                       for choice, r in base["speech"].items()},
            "embed": {key: (None if s is None else {"median_s": s.get("median_s"), "searches": len(s.get("searches", [])),
                                                    "failed": s.get("failed"), "late_starts": s.get("late_starts"),
                                                    "info": s.get("info")})
                      for key, s in base["embed"].items()},
            "index": {key: (None if s is None else {"seconds": s.get("seconds"), "pieces": s.get("pieces"), "ok": s.get("ok")})
                      for key, s in base["index"].items()}}


def pointers(setups: list[dict]) -> dict:
    """For every setup with the embedding model on the card that does not
    work, the same setup with it on the processor and its word (ruling 24)."""
    by_name = {s["name"]: s for s in setups}
    found = {}
    for s in setups:
        if s["where"] == "card" and s["works"] is False:
            twin = by_name.get(s["name"].replace("-card", "-processor"))
            found[s["name"]] = {"twin": twin["name"], "word": twin["word"]} if twin else None
    return found
