"""What the bench's two engines share (spec 15.8). llama.cpp's server
and vLLM both speak the chat completions shape, so one class holds the
HTTP exchange, the request built from the parts of a call, and the reply
read into the joint's one Reply. Standard library only.

These engines are modules of the bench. The app imports none of this
and cannot reach them (R31): no setting chooses an engine.

Such a server fixes its context size when it starts, so the size cannot
be sent with a call. The engine reads the server's own figure once and
gives a call back as an error if it is not the call's (R19).
"""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request
from typing import Callable

from openconsult.llm.engine import Call, EngineStatus, EngineTimeout, EngineUnreachable, Reply
from openconsult.llm.ollama import encode

STATUS_TIMEOUT_S = 2.0


def ms(value) -> int | None:
    return round(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class ChatEngine:
    name = ""
    # Every sampling setting the engine would otherwise fill in by itself,
    # set to the values of Ollama's own tag and Ollama's defaults (spec 15.8).
    sampling: dict = {}

    def __init__(self, address: str, urlopen: Callable = urllib.request.urlopen):
        self.address = address.rstrip("/")
        self._urlopen = urlopen
        self._context: int | None = None

    # ------------------------------------------------------------ the wire

    def _exchange(self, path: str, data: bytes | None, timeout_s: float) -> tuple[int, str]:
        """One HTTP exchange, as the Ollama engine's: the status and the
        body as text, and only the joint's two exceptions."""
        request = urllib.request.Request(self.address + path, data=data,
                                         headers={"Content-Type": "application/json"} if data else {})
        sent = data.decode("utf-8") if data else None
        try:
            with self._urlopen(request, timeout=timeout_s) as answer:
                return answer.status, answer.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as refused:
            return refused.code, refused.read().decode("utf-8", errors="replace")
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
            status, text = self._exchange(path, None, timeout_s)
            found = json.loads(text) if status == 200 else None
            return found if isinstance(found, dict) else None
        except (EngineUnreachable, EngineTimeout, ValueError):
            return None

    # ------------------------------------------- each engine's own way

    def did_not_fit(self, status: int, text: str) -> bool:
        raise NotImplementedError

    def times(self, reply: dict) -> tuple[int | None, int | None]:
        """The engine's own read time and write time, in ms, where it gives them."""
        raise NotImplementedError

    def context(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> int | None:
        raise NotImplementedError

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        raise NotImplementedError

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        raise NotImplementedError

    # ----------------------------------------------------------- the calls

    def build_request(self, call: Call) -> dict:
        return {
            "model": call.tag,
            "messages": [{"role": "system", "content": call.system},
                         {"role": "user", "content": call.user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": call.job, "schema": call.form}},
            "chat_template_kwargs": {"enable_thinking": call.think},
            "temperature": call.temperature, "seed": call.seed, "max_tokens": call.max_tokens,
            "stream": False, **self.sampling,
        }

    def chat(self, call: Call) -> Reply:
        sent = encode(self.build_request(call))
        request = sent.decode("utf-8")
        if self._context is None:
            self._context = self.context(call.tag)   # read once, so no call carries it in its time
        if self._context is None:
            raise EngineUnreachable("the engine did not say what context it runs at", request)
        if self._context != call.context:
            return Reply("error", None, None, f"the engine runs at a context of {self._context}, "
                         f"not {call.context}", None, None, None, None, None, None, 0, request, None)
        started = time.perf_counter()
        status, text = self._exchange("/v1/chat/completions", sent, call.timeout_s)
        wall_ms = round(1000 * (time.perf_counter() - started))

        def failed(ended: str, error: str) -> Reply:
            return Reply(ended, None, status, error, None, None, None, None, None, None, wall_ms, request, text)

        if status != 200:
            return failed("did_not_fit" if self.did_not_fit(status, text) else "error", text[:2000])
        try:
            reply = json.loads(text)
            choice = reply["choices"][0]
            content, finish = choice["message"]["content"], choice["finish_reason"]
        except (ValueError, KeyError, IndexError, TypeError) as odd:
            return failed("error", f"not a chat reply: {odd}")
        if finish not in ("stop", "length"):
            return failed("error", f"the reply ended with finish_reason {finish}")
        usage = reply.get("usage") or {}
        read_ms, write_ms = self.times(reply)
        return Reply("cut" if finish == "length" else "complete", content, status, None,
                     usage.get("prompt_tokens"), usage.get("completion_tokens"), None, None,
                     read_ms, write_ms, wall_ms, request, text)

    def status(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> EngineStatus:
        version = self.version(timeout_s)
        if version is None:
            return EngineStatus(False, None, None, None)
        digest = self.model_digest(tag, timeout_s)
        return EngineStatus(True, version, digest is not None, digest)
