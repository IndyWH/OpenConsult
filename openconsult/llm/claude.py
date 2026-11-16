"""The Claude engine behind the joint (spec 15.13, rulings 14 to 16, 19
and 21, the details of runs 9d and 9b; 15.10 rulings 25 and 36), read by
the app and by the bench: the service's own Messages API. The app's
system message goes in the system field, its user message in the
messages field, the form in output_config.format, thinking is switched
off by the service's own field, and the job's limit on tokens written
stands; no temperature (the service refuses it), no seed (the API has
none), no effort (the service's default stands). The key goes in the
x-api-key header and nowhere else, to the service's own address over
https. Standard library only.

The form as sent is a copy for the wire (sent_form): every object marked
as taking no other property, which the service demands, and maxItems
taken off, which it does not hold. The door still judges every reply
against the whole form.

No call is sent a second time and nothing waits: a call the service
refuses, for the key, the credit or the rate, is a failed call with the
service's own answer as its reason, and the next call is tried.
"""

from __future__ import annotations

import copy
import http.client
import json
import time
import urllib.error
import urllib.request
from typing import Callable

from openconsult.llm.cloud import own_address
from openconsult.llm.engine import Call, EngineStatus, EngineTimeout, EngineUnreachable, Reply
from openconsult.llm.ollama import encode

ADDRESS = "https://api.anthropic.com"
KEY_NAME = "ANTHROPIC_API_KEY"
VERSION = "2026-10-21"                        # the API version the service's reference gives (7 Nov 2026)
# Thinking is switched off by the service's own field, which is no word a model reads. Claude Sonnet 5.5 refuses the
# type disabled and takes between_tools, with nothing else in the field, at its default effort (15.10 ruling 30; the
# service's own pages, read by Cowork on 14 Nov 2026). Every other model is sent what it was sent before.
THINKING_OFF = {"type": "disabled"}
THINKING_OFF_FOR = {"claude-sonnet-5-5": {"type": "between_tools"}}


def engine_version(effort: str | None) -> str:
    """What the request pins, for the record: the API version and the
    effort sent, or default when none is (the service gives no build version)."""
    return f"anthropic-version {VERSION}, effort {effort or 'default'}"


ENGINE_VERSION = engine_version(None)
NO_DIGEST = "no digest given by the service"
STATUS_TIMEOUT_S = 2.0
# The constraints the service's own answer named as not held (the gate of 9d): taken off for sending only.
TAKEN_OFF = ("maxItems",)


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


def thinking_off(tag: str) -> dict:
    """The service's own field that switches a model's thinking off."""
    return dict(THINKING_OFF_FOR.get(tag, THINKING_OFF))


class ClaudeEngine:
    name = "claude"

    def __init__(self, address: str = ADDRESS, key: str = "", expected: str | None = None,
                 urlopen: Callable = urllib.request.urlopen):
        # The expected address is given by a test alone, which stands a made service in the service's place.
        self.address = own_address(address, expected or ADDRESS)
        self._key = key
        self._urlopen = urlopen
        self._context: int | None = None

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

    # ------------------------------------------------------------ the call

    def build_request(self, call: Call) -> dict:
        body = {"model": call.tag, "max_tokens": call.max_tokens, "system": call.system,
                "messages": [{"role": "user", "content": call.user}],
                "output_config": {"format": {"type": "json_schema", "schema": sent_form(call.form)}}}
        if not call.think:
            body["thinking"] = thinking_off(call.tag)
        return body

    def before_send(self, call: Call, body_length: int) -> int:
        """The ms waited before the call is sent. The app never waits; the
        bench's kind keeps under the account's limits here."""
        return 0

    def after_exchange(self, status: int, text: str, headers: dict) -> None:
        """What the kind keeps of an answer for its next call. Nothing, for the app."""

    def chat(self, call: Call) -> Reply:
        sent = encode(self.build_request(call))
        request = sent.decode("utf-8")
        if self._context is None:
            self._context = self.context(call.tag)   # read once, so no call carries it in its time
        if self._context is None:
            raise EngineUnreachable("the service did not say what context the model runs at", request)
        if self._context < call.context:
            return Reply("error", None, None, f"the service runs the model at a context of {self._context}, "
                         f"below the call's {call.context}", None, None, None, None, None, None, 0, request, None)
        waited_ms = self.before_send(call, len(sent))
        started = time.perf_counter()
        status, text, headers = self._exchange("/v1/messages", sent, call.timeout_s)
        wall_ms = round(1000 * (time.perf_counter() - started))
        self.after_exchange(status, text, headers)
        return self._read(status, text, wall_ms, waited_ms, request)

    def _read(self, status: int, text: str, wall_ms: int, waited_ms: int, request: str) -> Reply:
        """The reply into the joint's one Reply. total_ms is the exchange
        alone; load_ms the wait for the rate (the service has no load time)."""

        def failed(ended: str, error: str, answer: str | None = None, tokens=(None, None), model: str | None = None) -> Reply:
            return Reply(ended, answer, status, error, tokens[0], tokens[1], wall_ms, waited_ms, None, None, wall_ms + waited_ms,
                         request, text, model)

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
        named = reply.get("model") if isinstance(reply.get("model"), str) else None
        if stop not in ("end_turn", "max_tokens"):
            details = reply.get("stop_details")
            return failed("error", f"the reply ended with stop_reason {stop}" + (f"; stop_details {json.dumps(details)}" if details else ""),
                          answer, tokens, named)
        return Reply("cut" if stop == "max_tokens" else "complete", answer, status, None, tokens[0], tokens[1],
                     wall_ms, waited_ms, None, None, wall_ms + waited_ms, request, text, named)

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
        return EngineStatus(True, self.version(timeout_s), True, digest, None)
