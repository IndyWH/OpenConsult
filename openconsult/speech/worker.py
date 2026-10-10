"""The worker frame (spec 6.2; 15.9): how the app runs a speech worker
and talks to it. Start, ready, request, death, stop. v1's Nemotron
worker is the reference. A reader thread takes frames from the worker's
stdout into a queue, so there is no select on a pipe, which Windows does
not offer: the same code runs on the three systems (spec 5.1)."""

from __future__ import annotations

import queue
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.speech.frames import BadFrame, read_frame, write_frame

# Loading the speech models took up to half a minute in v1; a cold cache
# after a reboot is slower. A slow start is "not ready yet", not a failure,
# until this passes.
READY_TIMEOUT_S = 300.0
# A live piece took at most about 0.05 s after warm-up in v1 (Task 13).
REQUEST_TIMEOUT_S = 10.0
STOP_WAIT_S = 10.0
LOG_TAIL_BYTES = 4096

# The reason of a death is one plain sentence (spec 15.9, the details of
# 5b): a library's terminal colour codes and its traceback stay in the
# worker's log, and a harmless warning is never taken for the reason.
TERMINAL_CODES = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
TRACEBACK_LINE = re.compile(r'^(Traceback \(most recent call last\):|File ".*", line \d+)')
# A worker's own record lines are marked [note]; they are not a reason either.
WARNING_LINE = re.compile(r"^(WARNING\b|warnings\.warn\(|.*:\d+: \w*Warning: |\[NeMo [IWD] |\[note\] )")

_END = object()


class WorkerGone(Exception):
    """The worker died or did not answer. kind is died or no_answer."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


class Worker:
    """One worker process: started once, kept loaded, one request at a time."""

    def __init__(self, command: list[str], log_path: Path | None = None,
                 env: dict | None = None, ready_timeout_s: float = READY_TIMEOUT_S,
                 request_timeout_s: float = REQUEST_TIMEOUT_S,
                 popen: Callable = subprocess.Popen):
        self.command = command
        self.log_path = log_path
        self.env = env
        self.ready_timeout_s = ready_timeout_s
        self.request_timeout_s = request_timeout_s
        self._popen = popen
        self._lock = threading.Lock()         # one request at a time
        self._state_lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._frames: queue.Queue = queue.Queue()
        self._settled = threading.Event()     # ready, failed or stopped
        self.state = "stopped"                # stopped, starting, ready or failed
        self.kind: str | None = None          # died or no_answer, when failed
        self.reason: str | None = None
        self.info: dict = {}                  # the worker's ready frame
        self.exit_code: int | None = None

    # ---------------------------------------------------------- lifecycle

    def start(self) -> None:
        """Spawn the process and return at once; the models load in it."""
        with self._state_lock:
            if self.state in ("starting", "ready"):
                return
            self.state, self.kind, self.reason, self.info = "starting", None, None, {}
            self._frames, self._settled = queue.Queue(), threading.Event()
        log = open(self.log_path, "ab") if self.log_path else subprocess.DEVNULL  # noqa: SIM115
        try:
            proc = self._popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=log, env=self.env)
        except OSError as exc:
            self._fail("died", words.WORKER_NOT_STARTED.format(reason=exc))
            return
        finally:
            if log is not subprocess.DEVNULL:
                log.close()
        with self._state_lock:
            self._proc = proc
            frames, settled = self._frames, self._settled
        threading.Thread(target=self._read, args=(proc, frames, settled),
                         name="speech-worker-read", daemon=True).start()

    def _read(self, proc, frames: queue.Queue, settled: threading.Event) -> None:
        """The reader thread: the first frame says ready or not; the rest
        are replies. The end of the stream is the worker's death. It holds
        its own queue and event, so a thread left from an earlier start
        can never touch a later one."""
        first = True
        while True:
            try:
                frame = read_frame(proc.stdout)
            except (BadFrame, OSError, ValueError):
                frame = None
            if frame is None:
                break
            header, payload = frame
            if first:
                first = False
                if header.get("type") == "ready":
                    with self._state_lock:
                        if self._proc is proc:
                            self.state, self.info = "ready", header
                    settled.set()
                    continue
                self._fail("died", words.WORKER_REFUSED.format(
                    message=header.get("message") or words.WORKER_SAID_NOTHING), proc)
                return
            frames.put((header, payload))
        self._fail("died", self._exit_reason(proc), proc)
        frames.put(_END)
        settled.set()

    def wait_ready(self, timeout_s: float | None = None) -> bool:
        """Wait until the worker is ready, or has failed, or the limit passes."""
        limit = self.ready_timeout_s if timeout_s is None else timeout_s
        self._settled.wait(limit)
        if self.state == "starting":
            self._fail("no_answer", words.WORKER_NO_ANSWER.format(seconds=f"{limit:.0f}"))
        return self.state == "ready"

    def stop(self) -> None:
        with self._state_lock:
            proc, self._proc = self._proc, None
            self.state = "stopped"
        self._settled.set()
        self._frames.put(_END)
        if proc is not None:
            self.exit_code = _end(proc)

    # ----------------------------------------------------------- requests

    def request(self, header: dict, payload: bytes = b"",
                timeout_s: float | None = None) -> dict:
        """One request, one reply. Raises WorkerGone with the reason when
        the worker is not ready, dies, or does not answer in time."""
        limit = self.request_timeout_s if timeout_s is None else timeout_s
        with self._lock:
            if self.state != "ready":
                raise WorkerGone(self.kind or "died", self.reason or words.WORKER_NOT_READY)
            proc = self._proc
            try:
                write_frame(proc.stdin, header, payload)
            except (OSError, ValueError):
                self._fail("died", self._exit_reason(proc))
                raise WorkerGone(self.kind, self.reason) from None
            try:
                item = self._frames.get(timeout=limit)
            except queue.Empty:
                self._fail("no_answer", words.WORKER_NO_ANSWER.format(seconds=f"{limit:.0f}"))
                raise WorkerGone(self.kind, self.reason) from None
            if item is _END:
                raise WorkerGone(self.kind or "died", self.reason or words.WORKER_NOT_READY)
            return item[0]

    # ------------------------------------------------------------ failure

    def _fail(self, kind: str, reason: str, proc=None) -> None:
        """Mark the worker failed and end its process. A reason from a
        reader whose process is no longer the current one is ignored."""
        with self._state_lock:
            if self.state == "stopped" or (proc is not None and self._proc is not proc):
                return
            self.state, self.kind, self.reason = "failed", kind, reason
            proc, self._proc = self._proc, None
        if proc is not None:
            self.exit_code = _end(proc)
        self._settled.set()
        self._frames.put(_END)

    def _exit_reason(self, proc) -> str:
        try:
            code = proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            code = None
        last = self._log_tail()
        if last:
            return words.WORKER_DIED_SAYING.format(code=code, last=last)
        return words.WORKER_DIED.format(code=code)

    def _log_tail(self) -> str:
        if not self.log_path or not self.log_path.exists():
            return ""
        size = self.log_path.stat().st_size
        with open(self.log_path, "rb") as fh:
            fh.seek(max(0, size - LOG_TAIL_BYTES))
            text = fh.read().decode(errors="replace")
        if size > LOG_TAIL_BYTES:
            text = text.partition("\n")[2]           # the first line of the window may be cut
        return plain_last_line(text)


def plain_last_line(text: str) -> str:
    """The last line of a log that is a reason: not a traceback's frame
    or code line, not a warning, with no terminal codes."""
    for raw in reversed(text.splitlines()):
        line = TERMINAL_CODES.sub("", raw)
        if not line.strip() or line[:1].isspace():      # a traceback's code line is indented
            continue
        if TRACEBACK_LINE.match(line) or WARNING_LINE.match(line):
            continue
        return line.strip()[:200]
    return ""


def _end(proc) -> int | None:
    """Close its input, ask it to stop, then make it; wait for it to be gone."""
    if proc.poll() is None:
        try:
            proc.stdin.close()
        except OSError:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=STOP_WAIT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    for stream in (proc.stdout, proc.stdin):
        try:
            stream.close()
        except (OSError, ValueError):
            pass
    return proc.returncode
