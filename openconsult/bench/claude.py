"""The Claude kind of the bench (spec 15.13, rulings 14 to 17 and 22, the
details for runs 9d, 9d2 and 9b). The engine itself, with the request
the benches sent, is the app's own (llm/claude.py) since run 9b, and
nothing of it is written twice. What stays here is the bench's alone
(R31), a class on top of that engine:

The kind keeps under the account's limits by waiting before a call, by
the figures of the service's own reply headers, and never sends a call a
second time; a call refused for rate is a failed call, three in a row
stop the run. A refused key or used-up credit stops the run too, and
nothing more is sent.

The effort (15.13, ruling 22): the service's own control of speed and
cost, low, medium or high, sent in output_config when the bench names
it and not sent otherwise, so the service's default stands. The record
holds it in engine_version beside the API version on every call, so a
later reader knows what was benched.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
import urllib.request
from typing import Callable

from openconsult.bench.cloud import Stops, own_address, stop_line  # noqa: F401  (own_address: the shared rule, read here by the tests)
from openconsult.llm import claude as engine
from openconsult.llm.claude import (ADDRESS, ENGINE_VERSION, KEY_NAME, NO_DIGEST, STATUS_TIMEOUT_S, TAKEN_OFF,  # noqa: F401
                                    THINKING_OFF, THINKING_OFF_FOR, VERSION, engine_version, sent_form)
from openconsult.llm.engine import Call, Reply

EFFORTS = ("low", "medium", "high")           # the service's own setting; None sends nothing and the service's default stands
# The key refused or forbidden: nothing more is sent. A 400 naming the credit balance is the service's billing answer.
STOP_STATUSES = (401, 403)
CREDIT_WORD = "credit"
RATE_STATUS, RATE_IN_A_ROW = 429, 3
MARGIN_S = 0.2


def moment(value: str | None) -> float | None:
    """A reset header's moment as seconds since the epoch, or None."""
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


class ClaudeEngine(Stops, engine.ClaudeEngine):
    def __init__(self, address: str = ADDRESS, key: str = "", expected: str | None = None,
                 urlopen: Callable = urllib.request.urlopen, sleep: Callable = time.sleep, effort: str | None = None):
        # The expected address is read at the call, so a test may stand a made service in its place.
        super().__init__(address, key, expected or ADDRESS, urlopen)
        if effort is not None and effort not in EFFORTS:
            raise ValueError(f"not an effort the service names: {effort}; one of {', '.join(EFFORTS)}, or none")
        self.effort = effort
        self._sleep = sleep
        self._lock = threading.Lock()
        self._remaining: dict[str, tuple[int, float | None]] = {}   # limit name: (remaining, reset moment)
        self._retry_until: float | None = None
        self._last_input: int | None = None
        self._rate_in_a_row = 0

    # ------------------------------------------------------------ the rate

    def _note_limits(self, status: int, headers: dict) -> None:
        """The service's own figures for the account's limits, kept for the next call."""
        with self._lock:
            for name in ("requests", "input-tokens", "output-tokens", "tokens"):
                remaining = headers.get(f"anthropic-ratelimit-{name}-remaining")
                if remaining is not None and str(remaining).lstrip("-").isdigit():
                    self._remaining[name] = (int(remaining), moment(headers.get(f"anthropic-ratelimit-{name}-reset")))
            if status == RATE_STATUS:
                after = headers.get("retry-after")
                self._retry_until = time.time() + float(after) if after and str(after).replace(".", "", 1).isdigit() else (
                    max((reset for _, reset in self._remaining.values() if reset), default=time.time() + 1.0))

    def before_send(self, call: Call, body_length: int) -> int:
        """Sleep until the limits allow the two calls of a pass; the ms waited.
        Under the lock, so the two threads of a pass check in turn and the
        second passes without sleeping once the first has waited."""
        with self._lock:
            needed = {"requests": 2, "input-tokens": 2 * (self._last_input or body_length // 3), "output-tokens": 2 * call.max_tokens}
            needed["tokens"] = needed["input-tokens"] + needed["output-tokens"]
            until = self._retry_until or 0.0
            for name, want in needed.items():
                remaining, reset = self._remaining.get(name, (None, None))
                if remaining is not None and remaining < want and reset:
                    until = max(until, reset)
            now = time.time()
            if until <= now:
                return 0
            waited = until + MARGIN_S - now
            self._sleep(waited)
            self._remaining, self._retry_until = {}, None
            return round(1000 * waited)

    def after_exchange(self, status: int, text: str, headers: dict) -> None:
        self._note_limits(status, headers)
        self._rate_in_a_row = self._rate_in_a_row + 1 if status == RATE_STATUS else 0
        if status in STOP_STATUSES or (status == 400 and CREDIT_WORD in text.lower()):
            self.stop(stop_line(status))
        elif self._rate_in_a_row >= RATE_IN_A_ROW:
            self.stop(f"the service refused the rate (HTTP {RATE_STATUS}) {RATE_IN_A_ROW} times in a row; nothing more is sent")

    # ------------------------------------------------------------ the call

    def build_request(self, call: Call) -> dict:
        body = super().build_request(call)
        if self.effort:
            body["output_config"]["effort"] = self.effort
        return body

    def chat(self, call: Call) -> Reply:
        self.refuse_if_stopped()
        return super().chat(call)

    def _read(self, status: int, text: str, wall_ms: int, waited_ms: int, request: str) -> Reply:
        reply = super()._read(status, text, wall_ms, waited_ms, request)
        if isinstance(reply.prompt_tokens, int):
            self._last_input = reply.prompt_tokens     # the size of a call, for the next wait
        return reply

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return engine_version(self.effort)
