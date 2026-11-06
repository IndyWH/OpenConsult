"""The Ollama engine behind the joint (spec 15.7; 3.4). Standard library
only. It builds its own request from the parts of a call, in the shape
and key order v1 sent, plus what only Ollama needs: stream false,
keep_alive, and truncate false so an input that does not fit is refused
by Ollama rather than silently cut (V1_LESSONS 3.3; measured in stage 3).
"""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request
from typing import Callable

from openconsult.llm.engine import Call, EngineStatus, EngineTimeout, EngineUnreachable, Reply

DEFAULT_ADDRESS = "http://127.0.0.1:11434"
# v1's value: the model stays loaded between calls, so no reload stalls a consultation (R19).
KEEP_ALIVE = "30m"
STATUS_TIMEOUT_S = 2.0


def build_request(call: Call) -> dict:
    """The request body, a plain function so the bench can rebuild v1's.
    Key order is v1's, with truncate last."""
    return {
        "model": call.tag,
        "messages": [{"role": "system", "content": call.system},
                     {"role": "user", "content": call.user}],
        "format": call.form,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": call.temperature, "seed": call.seed,
                    "num_ctx": call.context, "num_predict": call.max_tokens},
        "think": call.think,
        "truncate": False,
    }


def encode(body: dict) -> bytes:
    """Compact, as v1's library encoded, so the bytes can be compared."""
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _ms(nanoseconds) -> int | None:
    return round(nanoseconds / 1_000_000) if isinstance(nanoseconds, (int, float)) else None


class OllamaEngine:
    name = "ollama"

    def __init__(self, address: str = DEFAULT_ADDRESS, urlopen: Callable = urllib.request.urlopen):
        self.address = address.rstrip("/")
        self._urlopen = urlopen

    # ------------------------------------------------------------ the wire

    def _request(self, path: str, data: bytes | None, timeout_s: float) -> tuple[int, str]:
        """One HTTP exchange. Gives the status and the body as text; raises
        only the joint's two exceptions."""
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
            status, text = self._request(path, None, timeout_s)
            return json.loads(text) if status == 200 else None
        except (EngineUnreachable, EngineTimeout, ValueError):
            return None

    # ----------------------------------------------------------- the calls

    def chat(self, call: Call) -> Reply:
        body = build_request(call)
        sent = encode(body)
        started = time.perf_counter()
        status, text = self._request("/api/chat", sent, call.timeout_s)
        wall_ms = round(1000 * (time.perf_counter() - started))
        request = sent.decode("utf-8")
        if status != 200:
            ended = "did_not_fit" if "exceed_context_size_error" in text else "error"
            return Reply(ended, None, status, text[:2000], None, None, None, None, None, None,
                         wall_ms, request, text)
        try:
            reply = json.loads(text)
            content = reply["message"]["content"]
        except (ValueError, KeyError, TypeError) as odd:
            return Reply("error", None, status, f"not a chat reply: {odd}", None, None, None,
                         None, None, None, wall_ms, request, text)
        ended = "cut" if reply.get("done_reason") == "length" else "complete"
        return Reply(ended, content, status, None, reply.get("prompt_eval_count"),
                     reply.get("eval_count"), _ms(reply.get("total_duration")),
                     _ms(reply.get("load_duration")), _ms(reply.get("prompt_eval_duration")),
                     _ms(reply.get("eval_duration")), wall_ms, request, text)

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        found = self._get_json("/api/version", timeout_s)
        return found.get("version") if isinstance(found, dict) else None

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        found = self._get_json("/api/tags", timeout_s)
        for model in (found or {}).get("models", []):
            if model.get("name") == tag:
                return model.get("digest")
        return None

    def status(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> EngineStatus:
        version = self.version(timeout_s)
        if version is None:
            return EngineStatus(False, None, None, None)
        digest = self.model_digest(tag, timeout_s)
        return EngineStatus(True, version, digest is not None, digest)
