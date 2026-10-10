"""The Nemotron worker: one long-lived process, both models loaded once
(spec 6.2; 15.9, ruling 8). Run by the app with the speech environment's
own Python. It never imports the app, and the app never imports it; they
share only the frames.

Requests and replies, one reply to each:
    open {session, rate, speakers}  -> opened, or error {reason: rate_not_supported}
    audio {session} + PCM           -> lines {segments, pending, revisions}
    stop {session, speakers}        -> stopped {last_live, revisions, seconds}
    close {session}                 -> closed
    ping                            -> pong
Before any request one unsolicited frame: ready {models, versions,
load_s, device}, or error {fatal: true, message} before exit.

PCM is mono 16-bit little-endian at 16,000 samples a second; any other
rate is refused plainly. There is one transcript: the lines are final as
they are given, and Stop gives the last ones. Only stderr is free for
logging: before any library is imported, file descriptor 1 is pointed at
stderr and the protocol keeps the real stdout. The log never holds a
word that was said (D44). A CUDA error ends the process (v1).
"""

from __future__ import annotations

import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "common"))   # the frames every worker shares

import models  # noqa: E402 - light at import: the table only; the libraries load in main
from frames import read_frame, write_frame  # noqa: E402

INSTALL = "openconsult install-speech --choice nemotron"
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
                                      "message": f"this choice takes sound at 16,000 samples a second, not {refused}"})
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
            # The traceback shows code, never data; the message is the
            # exception's own words, which name no word that was said.
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "session": sid, "fatal": True,
                              "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


def quiet_logs() -> None:
    """The log in the data folder is not part of any consultation, so it
    must never hold spoken words (D44): the libraries are held to warnings
    and above, where no text is echoed."""
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
        from nemo.utils import logging as nemo_logging    # NeMo's own logger ignores the standard levels
        nemo_logging.setLevel(nemo_logging.WARNING)
        device = models.device_name()
        loaded = models.Models(device)
        load_s = round(time.perf_counter() - started, 2)
        models.warm_up(loaded)
        ready = {"type": "ready", "models": models.stamp(), "versions": models.versions(), "device": device,
                 "load_s": load_s, "warm_s": round(time.perf_counter() - started - load_s, 2)}
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
    return serve(inp, out, lambda rate, speakers: models.Session(loaded, rate, speakers))


if __name__ == "__main__":
    sys.exit(main())
