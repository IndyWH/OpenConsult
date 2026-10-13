"""The replay (spec 13.4; 15.9, the details of 5c). A banked recording goes
through the door in pieces of a quarter of a second, at the speed it was
spoken: a piece is fed when its sound has ended, as a live page can only
send it then. Everything the door gives is kept, with the moment it
arrived, and the loudness of the sound in the door's own windows, so the
scoring can be made again from the stored results alone. A failure is
kept as failed and counted; nothing is tried again in silence."""

from __future__ import annotations

import datetime as dt
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.bench.speech import sound
from openconsult.bench.speech.arms import Arm
from openconsult.bench.speech.banked import Recording, check_file
from openconsult.bench.writer import ResultWriter
from openconsult.speech.door import Door
from openconsult.speech.loudness import QUIET_DBFS, WINDOW_S

PIECE_S = sound.PIECE_S
# Two switches of the replay for the test of 5d (spec 15.9, the details of
# 5d): a file written when the feed begins, so a driver can start the
# language model's chains 15 s into the sound; and a pause before Stop, so
# the way round can take the language model off the card first. Given by
# nobody, the replay does what it does today.
STARTED_NAME = "feeding.json"
STOP_WANTED, STOP_GO = "stop.wanted", "stop.go"
PAUSE_LIMIT_S = 600.0


def _lines(items) -> list[dict]:
    return [asdict(item) for item in items]


def _piece_record(n: int, fed_s: float, t: float, live) -> dict:
    return {"n": n, "fed_s": round(fed_s, 3), "t": t, "lines": _lines(live.lines), "refused": _lines(live.refused),
            "partial": live.partial, "revisions": _lines(live.revisions)}


def _windows(door: Door) -> list[float | None]:
    return [None if w == -math.inf else round(w, 1) for w in door.loudness_windows]


def run(door: Door, arm: Arm, recording: Recording, pcm: bytes, sleep: Callable = time.sleep,
        clock: Callable = time.monotonic, now: Callable = dt.datetime.now, wall: Callable = time.time,
        started_file: Path | None = None, pause_at_stop: Path | None = None) -> dict:
    """One recording through one door, as if live. The result, complete or
    failed, as a plain dict for the result file. t0_epoch is the machine's
    own clock at the moment the feed began, so other results of the same
    moment can be set beside this one."""
    live_labels = door.declares.speakers == "live"
    result = {"arm": arm.name, "recording": recording.name, "recording_sha256": recording.sha256,
              "script": recording.script, "script_key": recording.script_key, "script_sha256": recording.script_sha256,
              "rate": recording.rate, "speakers": recording.speakers, "piece_s": PIECE_S, "window_s": WINDOW_S,
              "quiet_dbfs": QUIET_DBFS, "time_slack_s": door.declares.time_slack_s,
              "machine_voices": recording.machine_voices, "consent": dict(recording.consent),
              "started_at": now().isoformat(timespec="seconds"), "stamp": None, "pieces": [], "stop": None,
              "loudness": None, "failure": None}

    def failed(at: str, piece: int | None, outcome) -> dict:
        result["failure"] = {"at": at, "piece": piece, "failure": outcome.failure, "detail": outcome.detail}
        result["stamp"] = asdict(door.stamp) if door.stamp else None
        result["loudness"] = {"window_s": WINDOW_S, "dbfs": _windows(door)}
        return result

    opened = door.open(recording.rate, speakers=recording.speakers) if live_labels else door.open(recording.rate)
    if not opened.ok:
        return failed("open", None, opened)
    result["stamp"] = asdict(door.stamp) if door.stamp else None
    started = clock()
    result["t0_epoch"] = wall()
    if started_file is not None:
        Path(started_file).write_text(json.dumps({"arm": arm.name, "recording": recording.name,
                                                  "t0_epoch": result["t0_epoch"]}), encoding="utf-8")
    last_partial = ""
    for n, piece in enumerate(sound.pieces(pcm, recording.rate), start=1):
        # A live page sends a piece only after it was spoken: wait, then feed.
        sleep(max(0.0, started + n * PIECE_S - clock()))
        live = door.feed(piece)
        t = round(clock() - started, 3)
        if not live.ok:
            return failed("feed", n, live)
        if live.lines or live.refused or live.revisions or live.partial != last_partial:
            result["pieces"].append(_piece_record(n, live.fed_s, t, live))
        last_partial = live.partial
    if pause_at_stop is not None:
        result["stop_pause"] = _pause(Path(pause_at_stop), sleep, clock, wall)
    t_asked = round(clock() - started, 3)
    final = door.stop(recording.speakers)
    t = round(clock() - started, 3)
    if not final.ok:
        return failed("stop", None, final)
    result["stop"] = {"t": t, "t_asked": t_asked, "lines": _lines(final.lines), "last_live": _lines(final.last_live),
                      "refused": _lines(final.refused), "raw": list(final.raw), "seconds": dict(final.seconds),
                      "revisions": _lines(final.revisions), "speakers": dict(final.speakers),
                      "notes": dict(final.notes)}
    result["loudness"] = {"window_s": WINDOW_S, "dbfs": _windows(door)}
    return result


def _pause(folder: Path, sleep: Callable, clock: Callable, wall: Callable) -> dict:
    """Before Stop: say that Stop is wanted, and wait for the go file, at
    most PAUSE_LIMIT_S; then Stop goes ahead either way, and the result
    says which."""
    folder.mkdir(parents=True, exist_ok=True)
    wanted, go = folder / STOP_WANTED, folder / STOP_GO
    wanted.write_text(json.dumps({"wanted_epoch": wall()}), encoding="utf-8")
    t0 = clock()
    while not go.exists() and clock() - t0 < PAUSE_LIMIT_S:
        sleep(0.5)
    return {"wanted_epoch": wall(), "waited_s": round(clock() - t0, 3), "went_ahead": not go.exists()}


def run_many(arm: Arm, recordings: list[Recording], make_door: Callable[[], Door], writer: ResultWriter,
             say: Callable = print, sleep: Callable = time.sleep, clock: Callable = time.monotonic,
             now: Callable = dt.datetime.now, started_file: Path | None = None, pause_at_stop: Path | None = None) -> dict:
    """Every recording that has no result yet, through the arm, in order.
    Consent is asked before the door is built (ruling 14). A failure is
    written as failed and the next recording runs."""
    done, kept, failed, refused = [], [], [], []
    for recording in recordings:
        if writer.exists(arm.name, recording.name):
            say(words.BENCH_RESULT_EXISTS.format(arm=arm.name, name=recording.name))
            kept.append(recording.name)
            continue
        if arm.cloud and not recording.cloud_allowed(arm.cloud_service):
            say(words.BENCH_NO_CLOUD_CONSENT.format(name=recording.name, service=arm.choice.title))
            refused.append(recording.name)
            continue
        check_file(recording)
        pcm = sound.read_wav(recording.path, recording.rate)
        say(words.BENCH_FEEDING.format(name=recording.name, seconds=sound.seconds_of(pcm, recording.rate),
                                       rate=recording.rate, arm=arm.name))
        door = make_door()
        try:
            result = run(door, arm, recording, pcm, sleep=sleep, clock=clock, now=now,
                         started_file=started_file, pause_at_stop=pause_at_stop)
        finally:
            door.close()
        path = writer.write(arm.name, recording.name, result)
        say(words.BENCH_RESULT_WRITTEN.format(path=path))
        if result["failure"]:
            failed.append(recording.name)
            say(words.BENCH_FAILED.format(arm=arm.name, name=recording.name, at=result["failure"]["at"],
                                          detail=result["failure"]["detail"]))
        else:
            done.append(recording.name)
    return {"run": done, "kept": kept, "failed": failed, "refused": refused}
