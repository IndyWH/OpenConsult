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
from openconsult.settings import keys
from openconsult.settings.path import CLAUDE, SPEECHMATICS
from openconsult.settings.secure import NoStore
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


# ---------------------------------------------- the connections of the app

@dataclass(frozen=True)
class Service:
    name: str
    key_name: str
    key_page: str          # the service's own page where a key is made, read on the service's own page on 16 Nov 2026


SERVICES = {
    CLAUDE: Service(CLAUDE, claude.KEY_NAME, "https://platform.claude.com/settings/keys"),
    SPEECHMATICS: Service(SPEECHMATICS, SPEECHMATICS_CHOICE.key, "https://portal.speechmatics.com/settings/api-keys/"),
}
NOT_CONNECTED, NO_STORE = "not_connected", "no_store"


@dataclass(frozen=True)
class State:
    """What the page says of one service, and nothing of the key."""
    service: str
    has_key: bool
    where: str | None            # keys.STORE, keys.ENVIRONMENT or keys.FILE
    last: Tested | None          # the last test in this run of the app
    last_at: object | None
    connected: bool


class KeyNotSaved(Exception):
    """The key passed its test and the secure store did not keep it."""


class Connections:
    """The keys in use and the last test of each service, for one run of
    the app. A key is written to the secure store here alone, and only
    after it has passed its test (7.2); nothing here holds a key longer
    than a call. A key that came from the store passed its test when it
    was saved; one from the environment or the file counts as connected
    only after it has passed a test in this run."""

    def __init__(self, data_folder: Path, store, audit, record: ModelCalls | None, clock, environ=os.environ,
                 testers: dict | None = None):
        self._data_folder, self._store, self._audit, self._clock, self._environ = Path(data_folder), store, audit, clock, environ
        self._testers = {CLAUDE: lambda key: test_claude(key, record),
                         SPEECHMATICS: lambda key: test_speechmatics(key, self._data_folder, environ=environ), **(testers or {})}
        self._last: dict[str, tuple[Tested, object]] = {}
        self._lock = threading.Lock()

    def key(self, service: str) -> str | None:
        return keys.find_key(SERVICES[service].key_name, self._data_folder, self._environ, self._store)[0]

    def state(self, service: str) -> State:
        value, where = keys.find_key(SERVICES[service].key_name, self._data_folder, self._environ, self._store)
        last, at = self._last.get(service, (None, None))
        connected = value is not None and (last.ok if last is not None else where == keys.STORE)
        return State(service, value is not None, where, last, at, connected)

    def connected(self, service: str) -> bool:
        return self.state(service).connected

    def store_reason(self) -> str | None:
        """Why no secure store answers on this computer, or None when one does."""
        return self._store.why_not()

    def _keep(self, service: str, tested: Tested) -> Tested:
        with self._lock:
            self._last[service] = (tested, self._clock())
        outcome = "answered" if tested.ok else f"{tested.reason} ({tested.detail})"
        self._audit.record("connection.tested", f"{words.SERVICE_TITLES[service]}: {outcome}")
        return tested

    def test(self, service: str) -> Tested | None:
        """The key in use, tested now; None when there is no key to test."""
        key = self.key(service)
        if key is None:
            return None
        return self._keep(service, self._run(service, key))

    def _run(self, service: str, key: str) -> Tested:
        """A test never raises into a page or a start: whatever broke in it
        is a service that did not answer, said plainly (R30)."""
        try:
            return self._testers[service](key)
        except Exception as broke:  # noqa: BLE001 - the name of what broke, never its words, which could hold anything
            return Tested(service, False, SERVICE_DOWN, f"the test itself failed: {type(broke).__name__}", 0.0)

    def test_all(self, services) -> dict[str, Tested | None]:
        """Several services side by side, so a view waits for the slowest
        one and not for their sum."""
        found: dict[str, Tested | None] = {}
        threads = [threading.Thread(target=lambda s=service: found.__setitem__(s, self.test(s)), name=f"connection-{service}",
                                    daemon=True) for service in services]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return found

    def connect(self, service: str, pasted: str) -> Tested:
        """A pasted key: tested, and kept in the secure store only if it
        passed (7.2). The key that was in use stays in use when the pasted
        one fails. Raises KeyNotSaved when the store did not keep a key
        that passed."""
        tested = self._run(service, pasted)
        if not tested.ok:
            # Said on the screen and written to the log, and not kept as the service's state: the key in use was not tested.
            self._audit.record("connection.tested", f"{words.SERVICE_TITLES[service]}: a pasted key: {tested.reason} ({tested.detail})")
            return tested
        try:
            self._store.put(SERVICES[service].key_name, pasted)
        except NoStore as none:
            raise KeyNotSaved(str(none)) from None
        self._audit.record("key.saved", f"{words.SERVICE_TITLES[service]}: kept in the secure store after it passed its test")
        return self._keep(service, tested)

    def remove(self, service: str) -> bool:
        """Take the key out of the secure store. False when the key in use
        is not there: the app removes nothing from the environment or a file."""
        if self.state(service).where != keys.STORE:
            return False
        try:
            self._store.take_out(SERVICES[service].key_name)
        except NoStore:
            return False
        with self._lock:
            self._last.pop(service, None)
        self._audit.record("key.removed", f"{words.SERVICE_TITLES[service]}: taken out of the secure store")
        return True
