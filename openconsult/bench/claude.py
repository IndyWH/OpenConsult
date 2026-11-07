"""The Claude kind of the bench (spec 15.13, rulings 14 to 17 and the
details for run 9d): Claude Haiku 5.5 through the door, in the service's
own Messages API. A class of its own on the door's joint beside the
DeepInfra kind: the app's system message in the system field, its user
message in the messages field, the form in output_config.format,
thinking switched off by the service's own field, the job's limit on
tokens written; no temperature (the service refuses it), no seed (the
API has none), none of the local arm's sampling values. The key goes in
the x-api-key header and nowhere else, to the service's own address over
https. The bench's alone (R31).

The form as sent is a copy for the wire (sent_form): every object marked
as taking no other property, which the service demands, and maxItems
taken off, which it does not hold. The door still judges every reply
against the whole form, so a reply over a list's limit is a failed call.

The kind keeps under the account's limits by waiting before a call, by
the figures of the service's own reply headers, and never sends a call a
second time; a call refused for rate is a failed call, three in a row
stop the run. Standard library only.
"""

from __future__ import annotations

import copy
import datetime as dt
import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

from openconsult.bench.cloud import Stops, own_address, stop_line
from openconsult.llm.engine import Call, EngineStatus, EngineTimeout, EngineUnreachable, Reply
from openconsult.llm.ollama import encode

ADDRESS = "https://api.anthropic.com"
KEY_NAME = "ANTHROPIC_API_KEY"
VERSION = "2026-10-21"                        # the API version the service's reference gives (7 Nov 2026)
ENGINE_VERSION = f"anthropic-version {VERSION}"   # the one thing the request can pin; the service gives no build version
NO_DIGEST = "no digest given by the service"
STATUS_TIMEOUT_S = 2.0
# The key refused or forbidden: nothing more is sent. A 400 naming the credit balance is the service's billing answer.
STOP_STATUSES = (401, 403)
CREDIT_WORD = "credit"
RATE_STATUS, RATE_IN_A_ROW = 429, 3
# The constraints the service's own answer named as not held (the gate of 9d): taken off for sending only.
TAKEN_OFF = ("maxItems",)
MARGIN_S = 0.2


def sent_form(form: dict) -> dict:
    """The form as the service takes it: a copy with additionalProperties
    false on every object and the constraints of TAKEN_OFF removed.
    Nothing else is touched."""
    copied = copy.deepcopy(form)

    def walk(node):
        if not isinstance(node, dict):
            return
        for key in TAKEN_OFF:
            node.pop(key, None)
        if node.get("type") == "object":
            node["additionalProperties"] = False
        for sub in node.get("properties", {}).values():
            walk(sub)
        walk(node.get("items"))

    walk(copied)
    return copied


def moment(value: str | None) -> float | None:
    """A reset header's moment as seconds since the epoch, or None."""
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


class ClaudeEngine(Stops):
    name = "claude"

    def __init__(self, address: str = ADDRESS, key: str = "", expected: str | None = None,
                 urlopen: Callable = urllib.request.urlopen, sleep: Callable = time.sleep):
        # The expected address is read at the call, so a test may stand a made service in its place.
        self.address = own_address(address, expected or ADDRESS)
        self._key = key
        self._urlopen = urlopen
        self._sleep = sleep
        self._context: int | None = None
        self._lock = threading.Lock()
        self._remaining: dict[str, tuple[int, float | None]] = {}   # limit name: (remaining, reset moment)
        self._retry_until: float | None = None
        self._last_input: int | None = None
        self._rate_in_a_row = 0

    # ------------------------------------------------------------ the wire

    def headers(self, data: bytes | None) -> dict:
        found = {"x-api-key": self._key, "anthropic-version": VERSION}
        if data:
            found["content-type"] = "application/json"
        return found

    def _exchange(self, path: str, data: bytes | None, timeout_s: float) -> tuple[int, str, dict]:
        """One HTTP exchange: the status, the body as text and the reply's
        headers (lower-cased names), and only the joint's two exceptions."""
        request = urllib.request.Request(self.address + path, data=data, headers=self.headers(data))
        sent = data.decode("utf-8") if data else None
        try:
            with self._urlopen(request, timeout=timeout_s) as answer:
                return answer.status, answer.read().decode("utf-8", errors="replace"), {k.lower(): v for k, v in answer.headers.items()}
        except urllib.error.HTTPError as refused:
            return refused.code, refused.read().decode("utf-8", errors="replace"), {k.lower(): v for k, v in refused.headers.items()}
        except TimeoutError as slow:
            raise EngineTimeout(str(slow), sent) from slow
        except urllib.error.URLError as failed:
            if isinstance(failed.reason, TimeoutError):
                raise EngineTimeout(str(failed.reason), sent) from failed
            raise EngineUnreachable(str(failed.reason), sent) from failed
        except (OSError, http.client.HTTPException) as failed:
            raise EngineUnreachable(f"{type(failed).__name__}: {failed}", sent) from failed

    def _get_json(self, path: str, timeout_s: float) -> dict | None:
        try:
            status, text, _ = self._exchange(path, None, timeout_s)
            found = json.loads(text) if status == 200 else None
            return found if isinstance(found, dict) else None
        except (EngineUnreachable, EngineTimeout, ValueError):
            return None

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

    def _wait_for_rate(self, call: Call, body_length: int) -> int:
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

    # ------------------------------------------------------------ the call

    def build_request(self, call: Call) -> dict:
        body = {"model": call.tag, "max_tokens": call.max_tokens, "system": call.system,
                "messages": [{"role": "user", "content": call.user}],
                "output_config": {"format": {"type": "json_schema", "schema": sent_form(call.form)}}}
        if not call.think:
            body["thinking"] = {"type": "disabled"}
        return body

    def chat(self, call: Call) -> Reply:
        self.refuse_if_stopped()
        sent = encode(self.build_request(call))
        request = sent.decode("utf-8")
        if self._context is None:
            self._context = self.context(call.tag)   # read once, so no call carries it in its time
        if self._context is None:
            raise EngineUnreachable("the service did not say what context the model runs at", request)
        if self._context < call.context:
            return Reply("error", None, None, f"the service runs the model at a context of {self._context}, "
                         f"below the call's {call.context}", None, None, None, None, None, None, 0, request, None)
        waited_ms = self._wait_for_rate(call, len(sent))
        started = time.perf_counter()
        status, text, headers = self._exchange("/v1/messages", sent, call.timeout_s)
        wall_ms = round(1000 * (time.perf_counter() - started))
        self._note_limits(status, headers)
        self._rate_in_a_row = self._rate_in_a_row + 1 if status == RATE_STATUS else 0
        if status in STOP_STATUSES or (status == 400 and CREDIT_WORD in text.lower()):
            self.stop(stop_line(status))
        elif self._rate_in_a_row >= RATE_IN_A_ROW:
            self.stop(f"the service refused the rate (HTTP {RATE_STATUS}) {RATE_IN_A_ROW} times in a row; nothing more is sent")
        return self._read(status, text, wall_ms, waited_ms, request)

    def _read(self, status: int, text: str, wall_ms: int, waited_ms: int, request: str) -> Reply:
        """The reply into the joint's one Reply. total_ms is the exchange
        alone; load_ms the wait for the rate (the service has no load time)."""

        def failed(ended: str, error: str, answer: str | None = None, tokens=(None, None)) -> Reply:
            return Reply(ended, answer, status, error, tokens[0], tokens[1], wall_ms, waited_ms, None, None, wall_ms + waited_ms, request, text)

        if status != 200:
            return failed("did_not_fit" if self.did_not_fit(status, text) else "error", text[:2000])
        try:
            reply = json.loads(text)
            content, stop = reply["content"], reply.get("stop_reason")
            blocks = [b for b in content if isinstance(b, dict)]
        except (ValueError, KeyError, TypeError) as odd:
            return failed("error", f"not a message reply: {odd}")
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        answer = "".join(texts) if texts else None
        usage = reply.get("usage") or {}
        tokens = (usage.get("input_tokens"), usage.get("output_tokens"))
        if isinstance(tokens[0], int):
            self._last_input = tokens[0]
        if stop not in ("end_turn", "max_tokens"):
            details = reply.get("stop_details")
            return failed("error", f"the reply ended with stop_reason {stop}" + (f"; stop_details {json.dumps(details)}" if details else ""),
                          answer, tokens)
        return Reply("cut" if stop == "max_tokens" else "complete", answer, status, None, tokens[0], tokens[1],
                     wall_ms, waited_ms, None, None, wall_ms + waited_ms, request, text)

    def did_not_fit(self, status: int, text: str) -> bool:
        return status == 400 and "too long" in text.lower()

    # ------------------------------------------------------------ the identity

    def _model(self, tag: str, timeout_s: float) -> dict | None:
        listed = (self._get_json("/v1/models?limit=1000", timeout_s) or {}).get("data")
        for model in listed if isinstance(listed, list) else []:
            if isinstance(model, dict) and model.get("id") == tag:
                return model
        return None

    def context(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> int | None:
        """The model's room as the service's list gives it (max_input_tokens),
        for the fit rule (R19); the arm is not measured at it (status below)."""
        found = (self._model(tag, timeout_s) or {}).get("max_input_tokens")
        return found if isinstance(found, int) and not isinstance(found, bool) else None

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return ENGINE_VERSION

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return NO_DIGEST if self._model(tag, timeout_s) is not None else None

    def status(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> EngineStatus:
        """Running when the service lists the model. The context is None:
        the service's room is its own and not a setting of the arm."""
        digest = self.model_digest(tag, timeout_s)
        if digest is None:
            return EngineStatus(False, None, None, None)
        return EngineStatus(True, ENGINE_VERSION, True, digest, None)
