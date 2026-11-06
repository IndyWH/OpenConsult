"""The Ollama cloud kind of the bench (spec 15.13, rulings 3, 4 and 8; the
details for run 9a). The local Ollama engine's own request and reading of
a reply, so the words a model reads are the same byte for byte, sent to
the service's own address over https with the key in the Authorization
header and nowhere else. The bench's alone (R31): the app's engines and
its order of choosing do not know it, as 3b's bench reached llama.cpp
before 3c wired an engine; 9b wires it to the settings if the owner
rules so. After the service refuses the key or the credit is used up it
sends nothing more, and the run stops for the owner (rule 9); a server
error or a timeout is an ordinary failed call, stored and counted.
"""

from __future__ import annotations

import urllib.request
from typing import Callable

from openconsult.llm.engine import Call, EngineUnreachable, Reply
from openconsult.llm.ollama import STATUS_TIMEOUT_S, OllamaEngine

ADDRESS = "https://ollama.com"
KEY_NAME = "OLLAMA_API_KEY"
# What the record holds when the service lists the model with no digest (R20).
NO_DIGEST = "no digest given by the service"
# The key refused, payment needed, forbidden, or the usage limit: nothing more is sent.
STOP_STATUSES = (401, 402, 403, 429)


class AddressRefused(ValueError):
    """The key goes to the service's own address and to no other."""


class OllamaCloudEngine(OllamaEngine):
    name = "ollama-cloud"

    def __init__(self, address: str = ADDRESS, key: str = "", expected: str | None = None,
                 urlopen: Callable = urllib.request.urlopen):
        expected = expected or ADDRESS   # read at the call, so a test may stand a made service in its place
        if address.rstrip("/") != expected.rstrip("/"):
            raise AddressRefused(f"the cloud kind speaks to {expected} alone, not {address}")
        super().__init__(address, urlopen)
        self._key = key
        self.stopped: str | None = None

    def headers(self, data: bytes | None) -> dict:
        return {**super().headers(data), "Authorization": f"Bearer {self._key}"}

    def chat(self, call: Call) -> Reply:
        if self.stopped:
            raise EngineUnreachable(self.stopped)
        reply = super().chat(call)
        if reply.status in STOP_STATUSES:
            self.stopped = (f"the service answered HTTP {reply.status}, so the key is refused or the credit "
                            f"is used up; nothing more is sent")
        return reply

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        found = self._get_json("/api/tags", timeout_s)
        for model in (found or {}).get("models", []):
            if model.get("name") == tag:
                return model.get("digest") or NO_DIGEST
        return None
