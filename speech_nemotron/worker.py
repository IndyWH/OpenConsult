"""The Nemotron speech worker: one long-lived process, models loaded once.

Spawned by the app (app/speech_pipeline.py) with the Nemotron
environment's own Python. It never imports anything from the app, and the
app never imports it. They share only the wire protocol below.

**Protocol.** Frames on stdin and stdout: a 4-byte big-endian length, a
UTF-8 JSON header of that length, then `nbytes` (from the header) of raw
payload. Strictly request and reply, one reply per request:

    app -> worker                          worker -> app
    {"type": "ping"}                       {"type": "pong", "sessions": [...]}
    {"type": "open", "session": s}         {"type": "opened", "session": s}
    {"type": "audio", "session": s} + PCM  {"type": "lines", "session": s, "segments",
                                            "revisions", "watermark", "partial", ...}
    {"type": "flush", "session": s}        {"type": "flushed", "session": s, "segments",
                                            "revisions", "stats", ...}
    {"type": "close", "session": s}        {"type": "closed", "session": s}

Before any request, the worker writes one unsolicited frame:
`{"type": "ready", ...}` once both models are loaded and warmed, or
`{"type": "error", "fatal": true, "message": ...}` before it exits.

PCM is mono 16 kHz little-endian 16-bit. The app has already zeroed
Alba's speaking windows in it (app/live.py), so the system's own voice
never reaches this process.

**Failure.** A request about an unknown session gets a non-fatal error
reply. Any other exception is reported as a fatal error, and the process
exits non-zero, because a CUDA error leaves the context unusable. The
app then marks the engine failed and refuses that consultation's
transcript (no silent fallback).

Only stderr is free for logging. Before NeMo is imported, file
descriptor 1 is pointed at stderr, so library prints cannot corrupt the
protocol stream.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
import traceback

HEADER = struct.Struct(">I")
MAX_HEADER = 1 << 20


def write_frame(out, header: dict, payload: bytes = b"") -> None:
    body = json.dumps({**header, "nbytes": len(payload)}).encode("utf-8")
    out.write(HEADER.pack(len(body)) + body + payload)
    out.flush()


def _read_exact(inp, n: int) -> bytes | None:
    chunks, got = [], 0
    while got < n:
        chunk = inp.read(n - got)
        if not chunk:
            return None
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def read_frame(inp) -> tuple[dict, bytes] | None:
    """One frame, or None at end of input (the app has gone)."""
    raw = _read_exact(inp, HEADER.size)
    if raw is None:
        return None
    (length,) = HEADER.unpack(raw)
    if length > MAX_HEADER:
        raise ValueError(f"header of {length} bytes refused")
    body = _read_exact(inp, length)
    if body is None:
        return None
    header = json.loads(body.decode("utf-8"))
    payload = _read_exact(inp, int(header.get("nbytes", 0))) if header.get("nbytes") else b""
    if payload is None:
        return None
    return header, payload


def serve(inp, out, open_stream) -> int:
    """The request loop. `open_stream()` returns a fresh per-consultation
    stream with accept(pcm16) -> dict, flush() -> dict and stats() -> dict
    (speech_nemotron.nemotron_stream.Stream, or a test double)."""
    sessions: dict[str, object] = {}
    while True:
        frame = read_frame(inp)
        if frame is None:
            return 0
        header, payload = frame
        kind, sid = header.get("type"), header.get("session")
        try:
            if kind == "ping":
                write_frame(out, {"type": "pong", "sessions": sorted(sessions)})
            elif kind == "open":
                # One consultation at a time on the GPU: the app enforces it
                # too. A stale session (the app lost track) is dropped.
                sessions.clear()
                sessions[sid] = open_stream()
                write_frame(out, {"type": "opened", "session": sid})
            elif kind == "close":                 # idempotent: flush already ended it
                sessions.pop(sid, None)
                write_frame(out, {"type": "closed", "session": sid})
            elif kind in ("audio", "flush") and sid not in sessions:
                write_frame(out, {"type": "error", "session": sid, "fatal": False,
                                  "message": f"unknown session {sid!r}"})
            elif kind == "audio":
                result = sessions[sid].accept(payload)
                write_frame(out, {"type": "lines", "session": sid, **result})
            elif kind == "flush":
                stream = sessions.pop(sid)
                result = stream.flush()
                write_frame(out, {"type": "flushed", "session": sid, **result,
                                  "stats": stream.stats()})
            else:
                write_frame(out, {"type": "error", "session": sid, "fatal": False,
                                  "message": f"unknown request {kind!r}"})
        except Exception as exc:  # noqa: BLE001 - reported, then the process ends
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "session": sid, "fatal": True,
                              "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nemotron speech worker")
    parser.add_argument("--max-speakers", type=int, required=True)
    args = parser.parse_args(argv)

    # The protocol keeps the real stdout; everything else printed goes to stderr.
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer

    started = time.perf_counter()
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import numpy as np
        import torch

        import nemotron_stream as ns

        models = ns.Models(max_speakers=args.max_speakers)
        load_s = time.perf_counter() - started
        # Warm-up: the first steps that run the ASR took 0.6 s and 2.2 s in
        # Task 13 Part 1 (steady steps ~0.03 s). Paid here, not by the first
        # consultation. Silence alone does not do it: cache gating runs the
        # ASR only for speakers the diariser hears, so on silence the ASR
        # never runs. The warm-up stream therefore runs it for every speaker
        # slot, once with each count of active speakers (1 .. max).
        for active in range(1, args.max_speakers + 1):
            warm = ns.Stream(models)
            warm.streamer._cache_gating = False
            warm.streamer.n_active_speakers_per_stream = active
            warm.accept((np.zeros(4 * ns.SAMPLE_RATE, dtype="<i2")).tobytes())
            warm.flush()
            del warm
        torch.cuda.empty_cache()
        ready = {"type": "ready", "load_s": round(load_s, 2),
                 "warmup_s": round(time.perf_counter() - started - load_s, 2),
                 "max_speakers": args.max_speakers,
                 "models": {ns.ASR_MODEL: ns.ASR_REVISION, ns.DIAR_MODEL: ns.DIAR_REVISION},
                 "target_lang": ns.TARGET_LANG,
                 "torch_reserved_mib": round(torch.cuda.memory_reserved() / 2**20)}
    except Exception as exc:  # noqa: BLE001 - reported to the app, then exit
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True,
                          "message": f"could not load the models: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)
    return serve(inp, out, lambda: ns.Stream(models))


if __name__ == "__main__":
    sys.exit(main())
