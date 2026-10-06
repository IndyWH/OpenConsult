"""The vLLM engine of the bench (spec 15.8). vLLM does not report which
revision of a model it serves, so the server is started on a Hugging
Face snapshot folder, whose name is the revision, and that name is the
model's digest here.
"""

from __future__ import annotations

import re

from openconsult.bench.chat_engine import STATUS_TIMEOUT_S, ChatEngine, ms

_REVISION = re.compile(r"[0-9a-f]{40}")


class VllmEngine(ChatEngine):
    name = "vllm"
    # top_k and top_p are the values of Ollama's own tag; the rest are
    # Ollama's defaults, which are vLLM's too.
    sampling = {"top_k": 64, "top_p": 0.95, "min_p": 0.0, "repetition_penalty": 1.0,
                "presence_penalty": 0.0, "frequency_penalty": 0.0}

    def did_not_fit(self, status: int, text: str) -> bool:
        return status == 400 and "maximum context length" in text

    def times(self, reply: dict) -> tuple[int | None, int | None]:
        metrics = reply.get("metrics") or {}
        return ms(metrics.get("time_to_first_token_ms")), ms(metrics.get("generation_time_ms"))

    def _model(self, tag: str, timeout_s: float) -> dict:
        listed = (self._get_json("/v1/models", timeout_s) or {}).get("data")
        for model in listed if isinstance(listed, list) else []:
            if isinstance(model, dict) and model.get("id") == tag:
                return model
        return {}

    def context(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> int | None:
        found = self._model(tag, timeout_s).get("max_model_len")
        return found if isinstance(found, int) else None

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return (self._get_json("/version", timeout_s) or {}).get("version")

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        root = str(self._model(tag, timeout_s).get("root") or "")
        last = root.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        return last if _REVISION.fullmatch(last) else None
