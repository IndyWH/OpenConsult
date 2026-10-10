"""What the two cloud speech workers share (spec 15.9, rulings 5, 9 and 10;
the details of 5b). A cloud worker runs on the app's own Python as a
process of its own, on the frame of 5a: ready, then open, audio, stop and
close over the frames. It imports nothing from the app.

The address. Each worker holds the EU address of its service as a named
constant, and dial refuses, before any connection is opened, an address
whose scheme is not wss or whose host is not exactly that EU host. main
takes no argument and reads no environment value for the address.

The certificate. The connection is made with the library's own checking
of the service's certificate and host name (the default context of
Python's ssl); nothing here passes an ssl argument, so no setting and no
environment value can weaken it. The library honours a proxy named in
the environment (HTTPS_PROXY, WSS_PROXY); the TLS session still ends at
the service, and the host is still checked.

A dead line. The library sends a ping every PING_INTERVAL_S, gives the
connection up when no pong comes within PING_TIMEOUT_S, and then waits
CLOSE_TIMEOUT_S for a close that never comes, so a line that dies
without closing is noticed within the sum of the three. The figures are
the library's own defaults (websockets 17: ping_interval 20, ping_timeout
20, close_timeout 10). Nothing reconnects: a lost connection is the
failure connection_lost, the session ends, and a new open starts a new
session.

The key is read from this process's environment under the one name the
worker is given, and goes into the handshake header and nowhere else.
"""

from __future__ import annotations

import importlib.metadata
import os
import queue
import socket
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frames import read_frame, write_frame  # noqa: E402

PING_INTERVAL_S = 20.0
PING_TIMEOUT_S = 20.0
CLOSE_TIMEOUT_S = 10.0
NOTICED_WITHIN_S = PING_INTERVAL_S + PING_TIMEOUT_S + CLOSE_TIMEOUT_S
OPEN_TIMEOUT_S = 10.0       # the library's default for the handshake
FIRST_REPLY_S = 15.0        # the service's first message after the handshake
STOP_WAIT_S = 30.0          # the last words after the end message
SAMPLE_WIDTH = 2            # 16-bit PCM

_CLOSED = object()


class Refused(Exception):
    """A failure the door knows by name: kind is one of its FAILURES."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def versions() -> dict:
    return {"websockets": importlib.metadata.version("websockets"),
            "python": sys.version.split()[0]}


# ------------------------------------------------------------------ dial

def dial(address: str, eu_host: str, headers: dict, connect=None):
    """Open the one connection a session uses, to the EU host only."""
    parts = urlsplit(address)
    if parts.scheme != "wss" or parts.hostname != eu_host:
        raise Refused("address_refused", address)
    return open_connection(address, headers, connect)


def open_connection(address: str, headers: dict, connect=None, ping_interval_s: float = PING_INTERVAL_S,
                    ping_timeout_s: float = PING_TIMEOUT_S, close_timeout_s: float = CLOSE_TIMEOUT_S):
    """The handshake, with the library's own certificate and host checking
    (no ssl argument is ever passed). Its failures become the door's names."""
    from websockets.exceptions import InvalidHandshake, InvalidStatus
    if connect is None:
        from websockets.sync.client import connect
    try:
        return connect(address, additional_headers=headers, open_timeout=OPEN_TIMEOUT_S, ping_interval=ping_interval_s,
                       ping_timeout=ping_timeout_s, close_timeout=close_timeout_s, legacy=True)
    except InvalidStatus as refused:
        raise Refused(*_by_status(refused.response.status_code)) from None
    except InvalidHandshake as broken:
        raise Refused("service_down", f"{type(broken).__name__}: {broken}"[:200]) from None
    except socket.gaierror as lookup:
        raise Refused("no_internet", f"{lookup}"[:200]) from None
    except (OSError, TimeoutError) as gone:
        raise Refused("no_internet", f"{type(gone).__name__}: {gone}"[:200]) from None


def _by_status(status: int) -> tuple[str, str]:
    if status in (401, 403):
        return "key_refused", f"HTTP {status}"
    if status == 402:
        return "no_credit", f"HTTP {status}"
    if status == 429:
        return "limit_reached", f"HTTP {status}"
    return "service_down", f"HTTP {status}"


# ---------------------------------------------------------------- reader

class Reader:
    """A thread that takes the service's messages into a queue, and the
    close of the connection after them."""

    def __init__(self, ws):
        self.ws = ws
        self.queue: queue.Queue = queue.Queue()
        self.closed: tuple[int | None, str] | None = None
        threading.Thread(target=self._run, name="cloud-read", daemon=True).start()

    def _run(self) -> None:
        from websockets.exceptions import ConnectionClosed
        try:
            while True:
                self.queue.put(self.ws.recv())
        except ConnectionClosed as closed:
            self.closed = (closed.rcvd.code if closed.rcvd else None,
                           closed.rcvd.reason if closed.rcvd else "")
        except Exception as exc:  # noqa: BLE001 - the connection is gone either way
            self.closed = (None, f"{type(exc).__name__}: {exc}"[:200])
        self.queue.put(_CLOSED)

    def next(self, timeout_s: float | None):
        """The next message, None when none within the time, or raises
        Refused when the connection has closed."""
        try:
            item = self.queue.get(timeout=timeout_s)
        except queue.Empty:
            return None
        if item is _CLOSED:
            self.queue.put(_CLOSED)
            raise Refused(*self.on_close(*(self.closed or (None, ""))))
        return item

    def pending(self) -> list:
        """Every message waiting now, without waiting for more."""
        found = []
        while True:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                return found
            if item is _CLOSED:
                self.queue.put(_CLOSED)
                raise Refused(*self.on_close(*(self.closed or (None, ""))))
            found.append(item)

    def on_close(self, code: int | None, reason: str) -> tuple[str, str]:
        """A connection that closed before Stop: a lost line, unless the
        service said why. A worker gives the mapping for its own codes."""
        return "connection_lost", f"{code}: {reason}"[:200]


# ---------------------------------------------------------- the sessions

class Session:
    """One session on one connection. A worker fills in the protocol:
    start (the opening message and the first reply), take (one of the
    service's messages into lines, partial text and revisions) and the
    end message. Lines carry an id, a speaker or none and a confidence or
    none; no word list is ever sent (ruling 3)."""

    def __init__(self, ws, rate: int, speakers: int):
        self.ws = ws
        self.rate = int(rate)
        self.speakers = int(speakers)
        self.reader = Reader(ws)
        self.reader.on_close = self.on_close
        self.sent_bytes = 0
        self.pieces = 0
        self.segments: list = []
        self.revisions: list = []
        self.partial = ""
        self.stopped = False

    # a worker fills these in
    def start(self) -> None:
        raise NotImplementedError

    def take(self, message) -> None:
        raise NotImplementedError

    def end_message(self) -> str:
        raise NotImplementedError

    def ended(self, message) -> bool:
        raise NotImplementedError

    def on_close(self, code: int | None, reason: str) -> tuple[str, str]:
        return "connection_lost", f"{code}: {reason}"[:200]

    @property
    def sent_s(self) -> float:
        return self.sent_bytes / SAMPLE_WIDTH / self.rate

    def send(self, data) -> None:
        """A send on a connection the library has given up is the loss of
        the line, by the door's name, never the library's error."""
        from websockets.exceptions import ConnectionClosed
        try:
            self.ws.send(data)
        except ConnectionClosed as closed:
            sent = closed.sent
            raise Refused(*self.on_close(closed.rcvd.code if closed.rcvd else None,
                                         closed.rcvd.reason if closed.rcvd else (sent.reason if sent else ""))) from None

    def accept(self, pcm: bytes) -> dict:
        """One piece of sound to the service, then what the service has
        said meanwhile."""
        self.send(pcm)
        self.sent_bytes += len(pcm)
        self.pieces += 1
        for message in self.reader.pending():
            self.take(message)
        return self._collect()

    def finish(self) -> dict:
        """The end message, then every message until the service says it
        has ended, so the last words arrive."""
        started = time.perf_counter()
        self.send(self.end_message())
        self.stopped = True
        deadline = started + STOP_WAIT_S
        while True:
            message = self.reader.next(max(0.0, deadline - time.perf_counter()))
            if message is None:
                raise Refused("service_down", "no end message within the limit")
            self.take(message)
            if self.ended(message):
                break
        tail = self._collect()
        self.close()
        return {"last_live": tail["segments"], "revisions": tail["revisions"],
                "seconds": {"stop": round(time.perf_counter() - started, 2), "sent": round(self.sent_s, 2)}}

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:  # noqa: BLE001 - already gone
            pass

    def _collect(self) -> dict:
        found = {"segments": self.segments, "pending": [{"start": 0.0, "end": self.sent_s, "text": self.partial}]
                 if self.partial else [], "revisions": self.revisions}
        self.segments, self.revisions = [], []
        return found

    def first_reply(self, timeout_s: float = FIRST_REPLY_S):
        message = self.reader.next(timeout_s)
        if message is None:
            raise Refused("service_down", "no first reply within the limit")
        return message


# ------------------------------------------------------------- the loop

def serve(inp, out, open_session) -> int:
    """The request loop on the frames, as the WhisperX worker's: one
    session at a time; a Refused from the service is an error reply with
    its name and the session ends; any other exception is fatal."""
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
                sessions[sid] = open_session(int(header.get("rate") or 0), int(header.get("speakers") or 0))
                write_frame(out, {"type": "opened", "session": sid})
            elif kind == "close":
                session = sessions.pop(sid, None)
                if session is not None:
                    session.close()
                write_frame(out, {"type": "closed", "session": sid})
            elif kind in ("audio", "stop") and sid not in sessions:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown session {sid!r}"})
            elif kind == "audio":
                write_frame(out, {"type": "lines", "session": sid, **sessions[sid].accept(payload)})
            elif kind == "stop":
                write_frame(out, {"type": "stopped", "session": sid, **sessions.pop(sid).finish()})
            else:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown request {kind!r}"})
        except Refused as refused:
            session = sessions.pop(sid, None)
            if session is not None:
                session.close()
            write_frame(out, {"type": "error", "session": sid, "fatal": False, "reason": refused.kind,
                              "detail": refused.detail, "message": f"{refused.kind}: {refused.detail}"[:300]})
        except Exception as exc:  # noqa: BLE001 - reported, then the process ends
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "session": sid, "fatal": True,
                              "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


def run(service: str, key_name: str, address: str, stamp: dict, open_session, dial_with) -> int:
    """A cloud worker's main: the protocol on the real stdout, logs on
    stderr, the key from this process's environment, ready, then serve."""
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    key = os.environ.get(key_name) or ""
    if not key:
        write_frame(out, {"type": "error", "fatal": True, "reason": "no_key", "message": f"no {key_name} in the environment"})
        return 1
    started = time.perf_counter()
    write_frame(out, {"type": "ready", "models": {service: {"address": address, **stamp}},
                      "versions": versions(), "load_s": round(time.perf_counter() - started, 2)})
    return serve(inp, out, lambda rate, speakers: open_session(dial_with(key), rate, speakers))
