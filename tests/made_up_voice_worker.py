"""A made-up voice worker for the suite: it speaks the real frames from the
real worker folder (loaded by path, no heavy library) and answers learn and
score with made-up distances. Run as a subprocess by the voice tests, on all
three systems. Nothing here hears any sound."""

from __future__ import annotations

import os
import sys

from tests.made_up_worker import load_frames

RATES = (16000, 48000)


def distance_for(n: int) -> float:
    """Made up: odd lines near the voice, even lines far from it."""
    return 0.3 if n % 2 else 0.9


def main() -> int:
    frames = load_frames()
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    frames.write_frame(out, {"type": "ready", "models": {"embed": {"repo": "made-up/voice", "revision": "0"}},
                             "versions": {"made-up": "0"}, "device": "cpu", "load_s": 0.0, "least_s": 0.2})
    learnt = False
    while True:
        frame = frames.read_frame(inp)
        if frame is None:
            return 0
        header, payload = frame
        kind = header.get("type")
        if kind in ("learn", "score") and header.get("rate") not in RATES:
            frames.write_frame(out, {"type": "error", "fatal": False, "reason": "rate_not_supported",
                                     "message": f"made-up: takes 16000 or 48000, not {header.get('rate')}"})
        elif kind == "ping":
            frames.write_frame(out, {"type": "pong"})
        elif kind == "learn":
            learnt = True
            frames.write_frame(out, {"type": "learnt", "seconds": 0.1, "seconds_used": len(payload) / 2 / header["rate"],
                                     "seconds_trimmed": 0.0})
        elif kind == "score" and not learnt:
            frames.write_frame(out, {"type": "error", "fatal": False, "message": "no voice has been learnt"})
        elif kind == "score":
            frames.write_frame(out, {"type": "scored", "seconds": 0.2, "lines": [
                {"n": line["n"], "distance": distance_for(line["n"]), "seconds": 0.01} for line in header["lines"]]})
        else:
            frames.write_frame(out, {"type": "error", "fatal": False, "message": f"made-up: unknown {kind!r}"})


if __name__ == "__main__":
    sys.exit(main())
