"""A made-up embedding worker for the suite: it speaks the real frames
(loaded by path, no heavy library) and answers made-up vectors. Run as a
subprocess, on all three systems. Nothing here is what a model gave.

Modes: ready (768 made-up numbers for each text); short (767 numbers);
nan (a not-a-number in the vector); die_at_second (dies on the second
request, after a last word on stderr); refuse (an error reply).
"""

from __future__ import annotations

import math
import os
import sys

import importlib.util
from pathlib import Path

FRAMES = Path(__file__).resolve().parents[1] / "openconsult" / "speech" / "common" / "frames.py"


def load_frames():
    spec = importlib.util.spec_from_file_location("worker_frames", FRAMES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector(text: str, mode: str) -> list:
    made = [round(0.001 * ((i * 7 + len(text)) % 100), 3) for i in range(768)]
    if mode == "short":
        return made[:-1]
    if mode == "nan":
        made[5] = math.nan
    return made


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else "ready"
    device = argv[argv.index("--device") + 1] if "--device" in argv else "cpu"
    frames = load_frames()
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    reranker = "--reranker" in argv
    frames.write_frame(out, {"type": "ready", "model": "made-up/embedder", "revision": "0", "device": device,
                             "dtype": "made-up", "versions": {"made-up": "0"}, "load_s": 0.0,
                             "reranker": "made-up/reranker" if reranker else None, "reranker_revision": "r0" if reranker else None,
                             "reranker_device": (argv[argv.index("--reranker-device") + 1] if "--reranker-device" in argv else device) if reranker else None})
    requests = 0
    while True:
        frame = frames.read_frame(inp)
        if frame is None:
            return 0
        header, _ = frame
        requests += 1
        if mode == "die_at_second" and requests == 2:
            print("made-up: CUDA out of memory (pretended)", file=sys.stderr, flush=True)
            return 3
        kind = header.get("type")
        if kind == "ping":
            frames.write_frame(out, {"type": "pong"})
        elif kind == "embed" and mode == "refuse":
            frames.write_frame(out, {"type": "error", "fatal": False, "message": "made-up: refused"})
        elif kind == "embed":
            texts = list(header.get("texts") or [])
            frames.write_frame(out, {"type": "vectors", "vectors": [vector(t, mode) for t in texts],
                                     "seconds": 0.001, "texts_seen": texts})
        elif kind == "rerank" and not reranker:
            frames.write_frame(out, {"type": "error", "fatal": False, "message": "no reranker is loaded"})
        elif kind == "rerank":
            texts = list(header.get("texts") or [])
            # The made-up score: a text's length, so a test can order them as it likes.
            frames.write_frame(out, {"type": "scores", "scores": [float(len(t)) for t in texts], "seconds": 0.001})
        else:
            frames.write_frame(out, {"type": "error", "fatal": False, "message": f"made-up: unknown {kind!r}"})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
