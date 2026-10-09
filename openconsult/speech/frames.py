"""The app's side of the worker protocol, v1's frames kept word for word:
a 4-byte big-endian length, a JSON header of that length, then the
payload bytes the header counts. The worker holds its own copy, because
it cannot import the app (spec 6.2)."""

from __future__ import annotations

import json
import struct

HEADER = struct.Struct(">I")
MAX_HEADER = 1 << 20


class BadFrame(Exception):
    """The stream does not hold a frame the app can read."""


def write_frame(stream, header: dict, payload: bytes = b"") -> None:
    body = json.dumps({**header, "nbytes": len(payload)}).encode("utf-8")
    stream.write(HEADER.pack(len(body)) + body + payload)
    stream.flush()


def read_frame(stream) -> tuple[dict, bytes] | None:
    """One frame, or None at the end of the stream."""
    raw = _exact(stream, HEADER.size)
    if raw is None:
        return None
    (length,) = HEADER.unpack(raw)
    if length > MAX_HEADER:
        raise BadFrame(f"a header of {length} bytes")
    body = _exact(stream, length)
    if body is None:
        return None
    try:
        header = json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise BadFrame(f"the header is not JSON: {exc}") from None
    if not isinstance(header, dict):
        raise BadFrame("the header is not an object")
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
