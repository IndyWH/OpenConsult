"""The test of a connection to a cloud service (spec 7.2; 15.13, the
details of run 9b): small, real, and able to find a key with no credit
before a consultation does.

Claude: one very small message to each of the two models the app asks,
by the app's own engine, side by side. An answer of 200 from both is a
pass; the words of a reply are never read. Each request is written to
the record of model calls, as every call to a model is (R20; 15.8,
ruling 1).

Speechmatics: the app's own speech door opens a live session at the EU
address with the settings a consultation opens it with, and ends it
after the service's first answer. No sound is sent. It runs in the
worker's own code, as a process of its own, so nothing is written twice.

Each test has a limit of time, and each way of failing has one name,
the names the speech door already has: the key refused, no credit, no
internet, the service down, a limit reached; and too slow. The key
goes where a call's key goes and nowhere else: never into a reason, a
row or a log."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.llm import claude
from openconsult.llm.engine import EngineTimeout, EngineUnreachable
from openconsult.llm.profile import CLAUDE as CLAUDE_PROFILE
from openconsult.llm.record import CallRow, ModelCalls
from openconsult.prompts import loader
from openconsult.settings.path import CLAUDE, SPEECHMATICS
from openconsult.speech import environment
from openconsult.speech.choices import SPEECHMATICS as SPEECHMATICS_CHOICE
from openconsult.speech.door import Door
from openconsult.speech.worker import Worker

# No answer within this is too slow. A design choice: a Start screen must not wait longer on a dead line.
LIMIT_S = 10.0
# The session is opened as a consultation opens it (15.9, rulings 9 and 32): 48,000 samples a second, two speakers.
TEST_RATE, TEST_SPEAKERS = 48000, 2
KEY_REFUSED, NO_CREDIT, NO_INTERNET, SERVICE_DOWN, LIMIT_REACHED, TOO_SLOW = (
    "key_refused", "no_credit", "no_internet", "service_down", "limit_reached", "too_slow")
SENTENCES = {KEY_REFUSED: words.KEY_REFUSED, NO_CREDIT: words.NO_CREDIT, NO_INTERNET: words.NO_INTERNET,
             SERVICE_DOWN: words.SERVICE_DOWN, LIMIT_REACHED: words.LIMIT_REACHED, TOO_SLOW: words.TOO_SLOW}
CREDIT_WORD = "credit"          # the service's billing answer is a 400 that names the credit balance


@dataclass(frozen=True)
class Tested:
    service: str
    ok: bool
    reason: str | None           # a key of SENTENCES when not ok
    detail: str                  # the service's own status or code, for the audit log; never a key
    seconds: float
    call_ids: tuple = ()         # the rows of the record this test wrote

    @property
    def sentence(self) -> str | None:
        """The exact reason, in one sentence, for the control pressed (R15)."""
        if self.ok:
            return None
        return SENTENCES[self.reason].format(service=words.SERVICE_TITLES[self.service], seconds=f"{LIMIT_S:.0f}", detail=self.detail)


# ------------------------------------------------------------------ Claude

def claude_reason(status: int, text: str) -> str | None:
    """What an answer of the service means for the connection."""
    if status == 200:
        return None
    if status in (401, 403):
        return KEY_REFUSED
    if status == 402 or (status == 400 and CREDIT_WORD in text.lower()):
        return NO_CREDIT
    if status == 429:
        return LIMIT_REACHED
    return SERVICE_DOWN


def _one_model(engine, tag: str, limit_s: float, record: ModelCalls | None, timer: Callable) -> tuple[str | None, str, int | None]:
    started = timer()
    sent, text, status = json.dumps(claude.test_request(tag)), None, None
    try:
        status, text, sent = engine.test(tag, limit_s)
        reason, detail = claude_reason(status, text), f"HTTP {status}"
    except EngineTimeout:
        reason, detail = TOO_SLOW, f"no answer within {limit_s:.0f} s"
    except EngineUnreachable as gone:
        reason, detail = NO_INTERNET, str(gone)[:200]
    wall_ms = round(1000 * (timer() - started))
    call_id = None
    if record is not None:
        try:
            body = json.loads(text or "")
        except ValueError:
            body = {}
        usage = body.get("usage") if isinstance(body, dict) and isinstance(body.get("usage"), dict) else {}
        named = body.get("model") if isinstance(body, dict) and isinstance(body.get("model"), str) else tag
        call_id = record.add(CallRow(
            job=claude.TEST_JOB, engine=engine.name, engine_version=claude.ENGINE_VERSION, model_tag=named,
            model_digest=claude.NO_DIGEST, prompt_sha256=loader.sha256(claude.TEST_WORDS), request=sent, reply=text,
            prompt_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"), wall_ms=wall_ms, total_ms=wall_ms,
            load_ms=None, read_ms=None, write_ms=None,
            outcome="ok" if reason is None else "too_slow" if reason == TOO_SLOW else "unreachable",
            detail=None if reason is None else f"{reason}: {detail}"))
    return reason, detail, call_id


def test_claude(key: str, record: ModelCalls | None = None, engine=None, limit_s: float = LIMIT_S,
                timer: Callable = time.perf_counter) -> Tested:
    """Both models, side by side; the first that fails, in the profile's
    order, gives the reason."""
    engine = engine or claude.ClaudeEngine(key=key)
    tags = list(dict.fromkeys([CLAUDE_PROFILE.tag, *CLAUDE_PROFILE.job_tags.values()]))
    found: dict[str, tuple] = {}
    started = timer()
    threads = [threading.Thread(target=lambda t=tag: found.__setitem__(t, _one_model(engine, t, limit_s, record, timer)),
                                name=f"connection-test-{tag}", daemon=True) for tag in tags]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    seconds = round(timer() - started, 2)
    ids = tuple(found[tag][2] for tag in tags if found[tag][2] is not None)
    for tag in tags:
        reason, detail, _ = found[tag]
        if reason is not None:
            return Tested(CLAUDE, False, reason, f"{tag}: {detail}", seconds, ids)
    return Tested(CLAUDE, True, None, "HTTP 200 from each model", seconds, ids)


# ------------------------------------------------------------ Speechmatics

def test_speechmatics(key: str, data_folder: Path, make_worker: Callable | None = None, limit_s: float = LIMIT_S,
                      environ=os.environ, timer: Callable = time.perf_counter) -> Tested:
    """The live session opened with the app's own settings and ended after
    the service's first answer. No sound is sent."""
    choice = SPEECHMATICS_CHOICE
    if make_worker is None:
        def make_worker():
            return Worker(environment.worker_command(data_folder, choice), log_path=environment.log_path(data_folder, choice),
                          env=environment.worker_env(environ, choice.key, key))
    door = Door(choice, make_worker=make_worker, installed=lambda: True)
    found = {}

    def run() -> None:
        found["live"] = door.open(TEST_RATE, speakers=TEST_SPEAKERS)
        if found["live"].ok:
            door.end()

    started = timer()
    thread = threading.Thread(target=run, name="connection-test-speechmatics", daemon=True)
    thread.start()
    thread.join(limit_s)
    slow = thread.is_alive()
    door.close()                       # the worker ends either way: nothing of the test stays open
    seconds = round(timer() - started, 2)
    live = found.get("live")
    if slow or live is None:
        return Tested(SPEECHMATICS, False, TOO_SLOW, f"no answer within {limit_s:.0f} s", seconds)
    if live.ok:
        return Tested(SPEECHMATICS, True, None, "the session started", seconds)
    reason = live.failure if live.failure in (KEY_REFUSED, NO_CREDIT, NO_INTERNET, LIMIT_REACHED) else SERVICE_DOWN
    return Tested(SPEECHMATICS, False, reason, f"{live.failure}: {live.detail or ''}"[:300], seconds)
