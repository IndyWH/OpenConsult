"""The DeepInfra kind of the bench (spec 15.13, ruling 11 and the details
for run 9a2). The app's chat engine, the one the vLLM engine is, so the
request is the vLLM arm's but the model's name, sent to the host's own
address over https with the key in the Authorization header and nowhere
else. The bench's alone (R31): the app's engines and its order of
choosing do not know it; 9b wires it to the settings if the owner rules
so. After the host refuses the key or the credit is used up it sends
nothing more, and the run stops for the owner; a server error or a
timeout is an ordinary failed call, stored and counted (R30; 10.4).
"""

from __future__ import annotations

import urllib.request
from typing import Callable

from openconsult.llm.chat_engine import STATUS_TIMEOUT_S, ChatEngine
from openconsult.llm.engine import Call, EngineStatus, EngineUnreachable, Reply
from openconsult.llm.vllm import VllmEngine

ADDRESS = "https://api.deepinfra.com"
KEY_NAME = "DEEPINFRA_API_KEY"
# The host gives nothing to identify its build (R20): the record says so.
NO_VERSION = "no version given by the host"
NO_DIGEST = "no digest given by the host"
# The key refused, payment needed, forbidden, or the usage limit: nothing more is sent.
STOP_STATUSES = (401, 402, 403, 429)


class AddressRefused(ValueError):
    """The key goes to the host's own address and to no other."""


class DeepInfraEngine(ChatEngine):
    name = "deepinfra"
    # The six fields the vLLM arm sends, so the chains at 0.5 are sampled
    # as the local model's were (the plan review of 9a2, point 1).
    sampling = VllmEngine.sampling

    def __init__(self, address: str = ADDRESS, key: str = "", expected: str | None = None,
                 urlopen: Callable = urllib.request.urlopen):
        expected = expected or ADDRESS   # read at the call, so a test may stand a made host in its place
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
            self.stopped = (f"the host answered HTTP {reply.status}, so the key is refused or the credit "
                            f"is used up; nothing more is sent")
        return reply

    def did_not_fit(self, status: int, text: str) -> bool:
        return status == 400 and "context" in text.lower()

    def times(self, reply: dict) -> tuple[int | None, int | None]:
        return None, None   # the host gives no read or write time; the wall is what is measured

    def _model(self, tag: str, timeout_s: float) -> dict | None:
        listed = (self._get_json("/v1/models", timeout_s) or {}).get("data")
        for model in listed if isinstance(listed, list) else []:
            if isinstance(model, dict) and model.get("id") == tag:
                return model
        return None

    def context(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> int | None:
        """The model's room as the host's list gives it, for the fit rule
        (R19); the arm is not measured at it (status below)."""
        found = ((self._model(tag, timeout_s) or {}).get("metadata") or {}).get("context_length")
        return found if isinstance(found, int) and not isinstance(found, bool) else None

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return NO_VERSION

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return NO_DIGEST if self._model(tag, timeout_s) is not None else None

    def status(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> EngineStatus:
        """Running when the host lists the model. The context is None: the
        host's room is its own and not a setting of the arm, so the arm
        opener does not hold it to the profile's figure."""
        digest = self.model_digest(tag, timeout_s)
        if digest is None:
            return EngineStatus(False, None, None, None)
        return EngineStatus(True, NO_VERSION, True, digest, None)
