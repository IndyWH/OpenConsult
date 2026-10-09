"""The WhisperX with pyannote worker: one long-lived process, the live
model loaded once (spec 6.2; 15.9). Run by the app with the speech
environment's own Python. It never imports the app, and the app never
imports it; they share only the frames.

Requests and replies, one reply to each:
    open {session, rate}      -> opened, or error {reason: rate_not_supported}
    audio {session} + PCM     -> lines {segments, pending}
    stop {session, speakers}  -> stopped {last_live, segments, seconds}
    close {session}           -> closed
    ping                      -> pong
Before any request one unsolicited frame: ready {models, versions,
load_s, device}, or error {fatal: true, message} before exit.

PCM is mono 16-bit little-endian at the session's rate; 5a takes 16,000.
Only stderr is free for logging: before any library is imported, file
descriptor 1 is pointed at stderr and the protocol keeps the real stdout.
A request about an unknown session is a non-fatal error. Any other
exception is fatal and the process exits non-zero, because a CUDA error
leaves the context unusable (v1).
"""

from __future__ import annotations

import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models  # noqa: E402 - light at import: the table only; the libraries load in main
from frames import read_frame, write_frame  # noqa: E402

INSTALL = "openconsult install-speech"


def serve(inp, out, open_stream, stop_pass) -> int:
    sessions: dict = {}
    while True:
        frame = read_frame(inp)
        if frame is None:
            return 0
        header, payload = frame
        kind, sid = header.get("type"), header.get("session")
        try:
            if kind == "ping":
                write_frame(out, {"type": "pong", "sessions": sorted(sessions)})
            elif kind == "open" and sessions:
                # One session at a time, and the open one is never thrown away.
                write_frame(out, {"type": "error", "fatal": False, "message": "a session is already open"})
            elif kind == "open":
                try:
                    sessions[sid] = open_stream(int(header.get("rate") or 0))
                except RateRefused as refused:
                    write_frame(out, {"type": "error", "fatal": False, "reason": "rate_not_supported",
                                      "message": f"this choice takes sound at 16,000 samples a second, "
                                                 f"not {refused}"})
                    continue
                write_frame(out, {"type": "opened", "session": sid})
            elif kind == "close":
                sessions.pop(sid, None)
                write_frame(out, {"type": "closed", "session": sid})
            elif kind in ("audio", "stop") and sid not in sessions:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown session {sid!r}"})
            elif kind == "audio":
                write_frame(out, {"type": "lines", "session": sid, **sessions[sid].accept(payload)})
            elif kind == "stop" and int(header.get("speakers") or 0) < 1:
                write_frame(out, {"type": "error", "fatal": False, "message": "the number of speakers must be 1 or more"})
            elif kind == "stop":
                stream = sessions.pop(sid)
                started = time.perf_counter()
                tail = stream.finish()
                segments, seconds = stop_pass(bytes(stream.pcm), int(header.get("speakers") or 0))
                seconds["tail"] = round(time.perf_counter() - started - seconds.get("stop", 0.0), 2)
                write_frame(out, {"type": "stopped", "session": sid, "last_live": tail,
                                  "segments": segments, "seconds": seconds})
            else:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown request {kind!r}"})
        except Exception as exc:  # noqa: BLE001 - reported, then the process ends
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "session": sid, "fatal": True,
                              "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


class RateRefused(Exception):
    pass


def main() -> int:
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    started = time.perf_counter()
    try:
        import torch  # noqa: F401 - first, so ctranslate2 finds the CUDA libraries torch loads

        models.check_present()
        device = models.device_name()
        live = models.LiveModel(device)
        import numpy as np
        live.transcribe(np.zeros(SAMPLE_RATE_WARM, dtype=np.float32))     # the first call is slow
        ready = {"type": "ready", "models": models.stamp(), "versions": models.versions(),
                 "device": device, "load_s": round(time.perf_counter() - started, 2)}
    except models.ModelMissing as missing:
        write_frame(out, {"type": "error", "fatal": True, "reason": "model_missing",
                          "message": f"the model {missing} is not on this computer; run {INSTALL}"})
        return 1
    except Exception as exc:  # noqa: BLE001 - reported to the app, then exit
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True,
                          "message": f"could not load the models: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)

    def open_stream(rate: int):
        try:
            return models.LiveStream(live, rate)
        except models.RateNotSupported:
            raise RateRefused(rate) from None

    return serve(inp, out, open_stream, lambda pcm, speakers: models.stop_pass(pcm, speakers, device))


SAMPLE_RATE_WARM = 16000


if __name__ == "__main__":
    sys.exit(main())
