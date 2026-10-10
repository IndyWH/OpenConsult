"""The workers' own copy of the frame protocol, shared by every worker
folder: a 4-byte big-endian length, a JSON header, then the payload
bytes the header counts. The app's copy is openconsult/speech/frames.py;
a test proves they agree. This file imports nothing but Python itself,
so any worker's Python can run it."""

from __future__ import annotations

import json
import struct

HEADER = struct.Struct(">I")
MAX_HEADER = 1 << 20


def write_frame(stream, header: dict, payload: bytes = b"") -> None:
    body = json.dumps({**header, "nbytes": len(payload)}).encode("utf-8")
    stream.write(HEADER.pack(len(body)) + body + payload)
    stream.flush()


def read_frame(stream) -> tuple[dict, bytes] | None:
    """One frame, or None at the end of input (the app has gone)."""
    raw = _exact(stream, HEADER.size)
    if raw is None:
        return None
    (length,) = HEADER.unpack(raw)
    if length > MAX_HEADER:
        raise ValueError(f"a header of {length} bytes refused")
    body = _exact(stream, length)
    if body is None:
        return None
    header = json.loads(body.decode("utf-8"))
    nbytes = int(header.get("nbytes", 0))
    payload = _exact(stream, nbytes) if nbytes else b""
    if payload is None:
        return None
    return header, payload


def _exact(stream, n: int) -> bytes | None:
    chunks, got = [], 0
    while got < n:
        chunk = stream.read(n - got)
        if not chunk:
            return None
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)
