"""The self-test (spec 11.5 rule 6; D46; 15.9): a short clip that comes
with the app is fed through the door in the pieces the live page will
send, at real time, then the transcript at Stop is asked for, and the
words of both are checked. A broken install is found at once. The
result is stored; This machine reads it. The pass rule is a draft for
the owner."""

from __future__ import annotations

import hashlib
import json
import re
import time
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local
from openconsult.speech.door import Door

CLIP = Path(__file__).parent / "clip" / "jfk.wav"
CLIP_SHA256 = "59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e"
EXPECTED = ("and so my fellow americans ask not what your country can do for you "
            "ask what you can do for your country").split()
# The pass rule: of the 22 expected words, at least this many in order,
# live and at Stop. A broken install gives nothing or rubbish; a working
# one gives all 22 on this clip. The allowance is the owner's to change.
NEEDED = 20
SPEAKERS = 1          # the clip has one speaker
PIECE_S = 0.25        # the size the live page sends (v1's page)


class ClipChanged(Exception):
    """The clip is not the one that came with the app."""


@dataclass
class Outcome:
    passed: bool
    reason: str | None
    live_words: list[str]
    stop_words: list[str]
    detail: dict = field(default_factory=dict)


def read_clip(path: Path = CLIP) -> tuple[int, bytes]:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != CLIP_SHA256:
        raise ClipChanged(path.name)
    with wave.open(str(path), "rb") as clip:
        if clip.getnchannels() != 1 or clip.getsampwidth() != 2:
            raise ClipChanged(path.name)
        return clip.getframerate(), clip.readframes(clip.getnframes())


def pieces(pcm: bytes, rate: int, piece_s: float = PIECE_S) -> list[bytes]:
    size = int(rate * piece_s) * 2
    return [pcm[i:i + size] for i in range(0, len(pcm), size)]


def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def in_order(expected: list[str], heard: list[str]) -> int:
    """How many of the expected words appear in the heard words, in order:
    the longest common subsequence, so a missing word early on does not
    cost the words after it."""
    previous = [0] * (len(heard) + 1)
    for word in expected:
        current = [0]
        for j, other in enumerate(heard, start=1):
            current.append(previous[j - 1] + 1 if word == other else max(previous[j], current[j - 1]))
        previous = current
    return previous[-1]


def judge(live_words: list[str], stop_words: list[str]) -> tuple[bool, str | None]:
    live, stop = in_order(EXPECTED, live_words), in_order(EXPECTED, stop_words)
    if live < NEEDED:
        return False, words.SELF_TEST_TOO_FEW_LIVE.format(heard=live, total=len(EXPECTED), needed=NEEDED)
    if stop < NEEDED:
        return False, words.SELF_TEST_TOO_FEW_STOP.format(heard=stop, total=len(EXPECTED), needed=NEEDED)
    return True, None


def run(door: Door, sleep: Callable = time.sleep, clip: Path = CLIP) -> Outcome:
    """The clip through the door at real time, then Stop with one speaker."""
    rate, pcm = read_clip(clip)
    detail = {"clip": clip.name, "sha256": CLIP_SHA256, "rate": rate, "piece_s": PIECE_S,
              "speakers": SPEAKERS, "expected": EXPECTED, "needed": NEEDED}
    # A choice whose labels are live is told the number at open (15.9, the details of 5b).
    opened = door.open(rate, speakers=SPEAKERS) if door.declares.speakers == "live" else door.open(rate)
    if not opened.ok:
        return _failed(opened.failure, opened.detail, detail, door)
    live, refused, delays, revisions = [], [], [], []
    started = time.monotonic()
    for number, piece in enumerate(pieces(pcm, rate), start=1):
        result = door.feed(piece)
        if not result.ok:
            return _failed(result.failure, result.detail, detail, door)
        delays += [round(result.fed_s - line.end, 2) for line in result.lines]
        live += result.lines
        refused += result.refused
        revisions += result.revisions
        sleep(max(0.0, started + number * PIECE_S - time.monotonic()))
    final = door.stop(SPEAKERS)
    if not final.ok:
        return _failed(final.failure, final.detail, detail, door)
    live += final.last_live
    refused += final.refused
    revisions += final.revisions
    live_words = words_of(" ".join(line.text for line in live))
    stop_words = words_of(" ".join(line.text for line in final.lines))
    passed, reason = judge(live_words, stop_words)
    detail.update(
        live_lines=[asdict(line) for line in live], last_live=[asdict(line) for line in final.last_live],
        stop_lines=[asdict(line) for line in final.lines], refused=[asdict(r) for r in refused],
        raw=list(final.raw), delays_s=delays, seconds=dict(final.seconds), stamp=_stamp(door),
        worker=_worker(door), failure=None, revisions=[asdict(r) for r in revisions],
        same_lines=door.one_transcript, speakers_given=dict(final.speakers),
    )
    return Outcome(passed, reason, live_words, stop_words, detail)


def _failed(failure: str, reason: str, detail: dict, door: Door) -> Outcome:
    return Outcome(False, reason, [], [], {**detail, "failure": failure, "stamp": _stamp(door), "worker": _worker(door)})


def _stamp(door: Door) -> dict | None:
    return asdict(door.stamp) if door.stamp else None


def _worker(door: Door) -> dict:
    info = door.ready_info
    return {key: info.get(key) for key in ("load_s", "device") if key in info}


class SelfTests:
    """The stored results: one row per run. The page reads the last."""

    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock

    def add(self, choice: str, outcome: Outcome) -> int:
        detail = {"reason": outcome.reason, "live_words": outcome.live_words,
                  "stop_words": outcome.stop_words, **outcome.detail}
        cursor = self._db.execute(
            "INSERT INTO speech_self_test (at, choice, passed, detail) VALUES (?, ?, ?, ?)",
            (self._clock().isoformat(timespec="seconds"), choice, int(outcome.passed),
             json.dumps(detail, ensure_ascii=False)))
        return int(cursor.lastrowid)

    def last(self, choice: str) -> dict | None:
        row = self._db.query_one(
            "SELECT at, passed, detail FROM speech_self_test WHERE choice = ? ORDER BY id DESC LIMIT 1",
            (choice,))
        if row is None:
            return None
        return {"at": row["at"], "passed": bool(row["passed"]), "detail": json.loads(row["detail"])}
