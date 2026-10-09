"""A made-up speech worker for the suite: it speaks the real frames from
the real worker folder (loaded by path, no heavy library) and does what
its mode says. Run as a subprocess by the worker frame's tests, on all
three systems. Nothing here hears any sound.

Modes: ready (answers), no_ready (never speaks), die_at_start (a fatal
error, then exit 2), die_mid (exits 3 on the first request, after a last
word on stderr), hang (ready, then never answers), die_once MARKER (dies
mid-request the first time, then is ready: the marker file remembers).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

FRAMES = Path(__file__).resolve().parents[1] / "openconsult" / "speech" / "whisperx" / "frames.py"


def load_frames():
    spec = importlib.util.spec_from_file_location("worker_frames", FRAMES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> int:
    mode = argv[0]
    frames = load_frames()
    # As the real worker: the protocol keeps the real stdout; prints go to stderr.
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    if mode == "no_ready":
        time.sleep(30)
        return 0
    if mode == "die_at_start":
        frames.write_frame(out, {"type": "error", "fatal": True, "message": "made-up: could not load"})
        return 2
    if mode == "die_once":
        marker = Path(argv[1])
        if marker.exists():
            mode = "ready"
        else:
            marker.write_text("died once")
            mode = "die_mid"
    frames.write_frame(out, {"type": "ready", "pid": os.getpid(), "mode": mode,
                             "models": {"made-up": {"revision": "0"}}, "versions": {"made-up": "0"}})
    while True:
        frame = frames.read_frame(inp)
        if frame is None:
            return 0
        header, payload = frame
        if mode == "die_mid":
            print("made-up: last words", file=sys.stderr, flush=True)
            return 3
        if mode == "hang":
            time.sleep(30)
            return 0
        kind = header.get("type")
        if kind == "ping":
            frames.write_frame(out, {"type": "pong"})
        elif kind == "open":
            frames.write_frame(out, {"type": "opened", "session": header.get("session"), "rate": header.get("rate")})
        elif kind == "audio":
            frames.write_frame(out, {"type": "lines", "session": header.get("session"),
                                     "segments": [], "pending": [], "bytes": len(payload)})
        elif kind == "stop":
            frames.write_frame(out, {"type": "stopped", "session": header.get("session"),
                                     "speakers": header.get("speakers"), "last_live": [], "segments": [],
                                     "seconds": {}})
        else:
            frames.write_frame(out, {"type": "error", "fatal": False, "message": f"made-up: unknown {kind!r}"})


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
