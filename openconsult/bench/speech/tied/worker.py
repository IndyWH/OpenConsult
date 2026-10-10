"""The tied pair's worker, an arm of the bench only (spec 15.9, rulings 8
and 15): one long-lived process on the frame of 5b, run by the bench with
the Nemotron environment's Python. It imports nothing from the app; the
frames and the conversion it shares with the app's workers are loaded
by path from the speech folder.

Requests and replies as the Nemotron worker's:
    open {session, rate, speakers}  -> opened, or error {reason: rate_not_supported}
    audio {session} + PCM           -> lines {segments, pending, revisions}
    stop {session, speakers}        -> stopped {last_live, revisions, seconds, notes}
    close {session}                 -> closed
    ping                            -> pong
notes carries the late changes of committed lines (the plan of 5c, part one).
"""

from __future__ import annotations

import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "speech", "common")
sys.path.insert(0, HERE)
sys.path.insert(0, COMMON)

import models  # noqa: E402 - light at import: the table only; the libraries load in main
from frames import read_frame, write_frame  # noqa: E402

FETCH = "openconsult-bench speech-fetch"
QUIET_LOGGERS = ("nemo_logger", "nemo", "torch", "lightning", "pytorch_lightning", "huggingface_hub",
                 "transformers", "numba", "lhotse")


def serve(inp, out, open_session) -> int:
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
                write_frame(out, {"type": "error", "fatal": False, "message": "a session is already open"})
            elif kind == "open":
                try:
                    sessions[sid] = open_session(int(header.get("rate") or 0), int(header.get("speakers") or 0))
                except models.RateNotSupported as refused:
                    write_frame(out, {"type": "error", "fatal": False, "reason": "rate_not_supported",
                                      "message": f"this arm takes sound at 16,000 or 48,000 samples a second, not {refused}"})
                    continue
                write_frame(out, {"type": "opened", "session": sid})
            elif kind == "close":
                sessions.pop(sid, None)
                write_frame(out, {"type": "closed", "session": sid})
            elif kind in ("audio", "stop") and sid not in sessions:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown session {sid!r}"})
            elif kind == "audio":
                write_frame(out, {"type": "lines", "session": sid, **sessions[sid].accept(payload)})
            elif kind == "stop":
                write_frame(out, {"type": "stopped", "session": sid, **sessions.pop(sid).finish()})
            else:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown request {kind!r}"})
        except Exception as exc:  # noqa: BLE001 - reported, then the process ends
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "session": sid, "fatal": True, "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


def quiet_logs() -> None:
    """The log never holds a word that was said (D44)."""
    import logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, force=True)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    os.environ.setdefault("NEMO_LOGGING_LEVEL", "WARNING")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "warning")


def main() -> int:
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    quiet_logs()
    started = time.perf_counter()
    try:
        models.check_present()
        from nemo.utils import logging as nemo_logging
        nemo_logging.setLevel(nemo_logging.WARNING)
        device = models.device_name()
        loaded = models.Models(device)
        load_s = round(time.perf_counter() - started, 2)
        models.warm_up(loaded)
        ready = {"type": "ready", "models": models.stamp(), "versions": models.versions(), "device": device,
                 "load_s": load_s, "warm_s": round(time.perf_counter() - started - load_s, 2)}
    except models.ModelMissing as missing:
        write_frame(out, {"type": "error", "fatal": True, "reason": "model_missing",
                          "message": f"the model {missing} is not on this computer; run {FETCH}"})
        return 1
    except Exception as exc:  # noqa: BLE001 - reported to the app, then exit
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True, "message": f"could not load the models: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)
    return serve(inp, out, lambda rate, speakers: models.Session(loaded, rate, speakers))


if __name__ == "__main__":
    sys.exit(main())
