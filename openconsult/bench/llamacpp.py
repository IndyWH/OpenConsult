"""The llama.cpp engine of the bench (spec 15.8): its server, spoken to
directly. One server holds one model, so the model's digest is the
sha256 of the file the server says it loaded, taken from the file itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from openconsult.bench.chat_engine import STATUS_TIMEOUT_S, ChatEngine, ms


class LlamaCppEngine(ChatEngine):
    name = "llama.cpp"
    # top_k and top_p are the values of Ollama's own tag. min_p 0.0 is
    # Ollama's default; llama.cpp's own is 0.05. The rest equal both defaults.
    sampling = {"top_k": 64, "top_p": 0.95, "min_p": 0.0, "repeat_penalty": 1.0,
                "presence_penalty": 0.0, "frequency_penalty": 0.0}

    def __init__(self, address: str, **kwargs):
        super().__init__(address, **kwargs)
        self._digests: dict[str, str] = {}

    def did_not_fit(self, status: int, text: str) -> bool:
        return status == 400 and "exceed_context_size_error" in text

    def times(self, reply: dict) -> tuple[int | None, int | None]:
        timings = reply.get("timings") or {}
        return ms(timings.get("prompt_ms")), ms(timings.get("predicted_ms"))

    def _props(self, timeout_s: float) -> dict:
        return self._get_json("/props", timeout_s) or {}

    def context(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> int | None:
        """The context of one slot, which is what a call gets."""
        settings = self._props(timeout_s).get("default_generation_settings")
        found = settings.get("n_ctx") if isinstance(settings, dict) else None
        return found if isinstance(found, int) else None

    def version(self, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        return self._props(timeout_s).get("build_info")

    def model_digest(self, tag: str, timeout_s: float = STATUS_TIMEOUT_S) -> str | None:
        """None when the file cannot be read from this computer: the
        bench then refuses to start rather than run a model it cannot name."""
        path = self._props(timeout_s).get("model_path")
        if not isinstance(path, str) or not Path(path).is_file():
            return None
        if path not in self._digests:
            digest = hashlib.sha256()
            with open(path, "rb") as file:
                for block in iter(lambda: file.read(1 << 22), b""):
                    digest.update(block)
            self._digests[path] = digest.hexdigest()
        return self._digests[path]
