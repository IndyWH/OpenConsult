"""Which speech pipeline transcribes the live consultation (Task 13, v1.1).

Two pipelines, chosen by SPEECH_PIPELINE:

- **whisper** (the default): today's path, unchanged. faster-whisper
  transcribes live in this process, and at Stop the finalisation
  pipeline unloads the CDS model, re-transcribes the recording with
  WhisperX and diarises it with pyannote.
- **nemotron**: NVIDIA Nemotron 3.5 ASR streaming plus
  Nemotron-3-Diarization run live in a separate process, from their own
  environment (speech_nemotron/), in the way Piper does. Speaker-tagged
  lines are stored as they arrive. At Stop the final transcript is built
  from those stored lines: the CDS model stays loaded, and neither
  WhisperX nor pyannote is loaded.

There is **no silent fallback** between them. With nemotron chosen and
its process not ready, recording does not start, and the live page says
why. An unknown value is a configuration error, reported the same way;
it is never quietly read as whisper.

This is a research and education prototype, not a medical device.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import select
import struct
import subprocess
import threading
import time
from pathlib import Path

from app.live import BYTES_PER_SAMPLE, LiveSession
from app.transcription import SAMPLE_RATE, Segment

logger = logging.getLogger(__name__)

WHISPER = "whisper"
NEMOTRON = "nemotron"
PIPELINES = (WHISPER, NEMOTRON)

SPEECH_PIPELINE = os.getenv("SPEECH_PIPELINE", WHISPER).strip().lower()

# The most speakers the live diariser keeps apart. The default is the
# count today's pyannote call uses, finalize.DEFAULT_SPEAKERS (2) — the
# owner's instruction at approval of Task 13: the same number as today,
# and 4 only if today's call set none. It is an upper bound for the
# streaming diariser, not an exact count as pyannote's is.
SPEECH_MAX_SPEAKERS = int(os.getenv("SPEECH_MAX_SPEAKERS", "2"))

# Where speech_nemotron/setup.sh builds the environment (its own default).
NEMOTRON_HOME = Path(os.path.expanduser(
    os.getenv("NEMOTRON_HOME", "~/.local/share/openconsult-nemotron")))


def configuration_error() -> str | None:
    """A plain sentence when the settings cannot be acted on, else None."""
    if SPEECH_PIPELINE not in PIPELINES:
        return (f"SPEECH_PIPELINE is set to '{SPEECH_PIPELINE}', which is not "
                f"one of: {', '.join(PIPELINES)}. Recording is off until it is "
                "corrected and the service restarted.")
    if SPEECH_MAX_SPEAKERS < 1:
        return "SPEECH_MAX_SPEAKERS must be 1 or more."
    return None


def uses_nemotron() -> bool:
    """True when anything other than plain whisper is configured — an
    invalid value counts, so it blocks recording instead of falling back."""
    return SPEECH_PIPELINE != WHISPER


# --- the worker process ------------------------------------------------------
#
# Thread-based on purpose: the service drives it from its event loop and the
# test suite from TestClient's, and a pipe owned by one asyncio loop cannot
# be used from another. Requests are strictly one at a time (a lock), each
# with a deadline; async callers go through asyncio.to_thread.

REPO = Path(__file__).resolve().parent.parent
WORKER_SCRIPT = REPO / "speech_nemotron" / "worker.py"
_HEADER = struct.Struct(">I")

# Loading both models took 25 s in Task 13 Part 1, plus warm-up; a cold
# page cache after a reboot is slower. Generous, because a slow start is
# reported as "still loading", not as a failure, until this passes.
READY_TIMEOUT_S = 300.0
# One 1.5 s batch of audio took at most ~0.05 s after warm-up (Part 1).
REQUEST_TIMEOUT_S = 10.0
# The flush at Stop took 0.03 s in Part 1. If it has not answered in this
# long the worker is treated as crashed and the consultation's transcript
# is refused (owner, at approval: never a transcript from a partial flush).
FLUSH_TIMEOUT_S = 20.0
# After a failure, wait this long before trying to start a new worker.
RESTART_COOLDOWN_S = 30.0


class WorkerError(Exception):
    """The worker did not answer, answered with an error, or has gone."""


def _write_frame(fh, header: dict, payload: bytes = b"") -> None:
    body = json.dumps({**header, "nbytes": len(payload)}).encode("utf-8")
    fh.write(_HEADER.pack(len(body)) + body + payload)
    fh.flush()


def _read_exact(fd: int, n: int, deadline: float) -> bytes:
    chunks, got = [], 0
    while got < n:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise TimeoutError
        chunk = os.read(fd, n - got)
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def _read_frame(fd: int, timeout_s: float) -> tuple[dict, bytes]:
    deadline = time.monotonic() + timeout_s
    (length,) = _HEADER.unpack(_read_exact(fd, _HEADER.size, deadline))
    header = json.loads(_read_exact(fd, length, deadline).decode("utf-8"))
    nbytes = int(header.get("nbytes", 0))
    payload = _read_exact(fd, nbytes, deadline) if nbytes else b""
    return header, payload


def worker_command(max_speakers: int | None = None) -> list[str]:
    python = NEMOTRON_HOME / "Speech" / ".venv" / "bin" / "python"
    return [str(python), str(WORKER_SCRIPT), "--max-speakers",
            str(max_speakers or SPEECH_MAX_SPEAKERS)]


class SpeechWorker:
    """The one Nemotron worker process: started once, kept loaded."""

    def __init__(self, command: list[str], *, log_path: Path | None = None,
                 env: dict | None = None,
                 ready_timeout_s: float = READY_TIMEOUT_S,
                 request_timeout_s: float = REQUEST_TIMEOUT_S) -> None:
        self.command = command
        self.log_path = log_path
        self.env = env
        self.ready_timeout_s = ready_timeout_s
        self.request_timeout_s = request_timeout_s
        self._lock = threading.Lock()          # one request at a time
        self._state_lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self.state = "stopped"                 # stopped | starting | ready | failed
        self.reason: str | None = None
        self.info: dict = {}
        self.failed_at: float | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Spawn the process; the models load in it while the app serves.
        Returns at once. `state` says when it is ready."""
        with self._state_lock:
            if self.state in ("starting", "ready"):
                return
            self.state, self.reason, self.info = "starting", None, {}
        executable = Path(self.command[0])
        if not executable.exists():
            self._fail(f"the Nemotron environment was not found at {executable}; "
                       "build it with speech_nemotron/setup.sh")
            return
        log = open(self.log_path, "ab") if self.log_path else subprocess.DEVNULL  # noqa: SIM115
        try:
            self._proc = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=log, env=self.env, close_fds=True)
        except OSError as exc:
            self._fail(f"the speech worker could not be started: {exc}")
            return
        finally:
            if log is not subprocess.DEVNULL:
                log.close()
        threading.Thread(target=self._await_ready, name="nemotron-ready",
                         daemon=True).start()

    def _await_ready(self) -> None:
        proc = self._proc
        try:
            header, _ = _read_frame(proc.stdout.fileno(), self.ready_timeout_s)
        except TimeoutError:
            self._fail(f"the speech models did not load within {self.ready_timeout_s:.0f} s")
            return
        except (EOFError, OSError, ValueError):
            self._fail(self._exit_reason("the speech worker stopped while loading"))
            return
        if header.get("type") == "ready":
            with self._state_lock:
                if self._proc is proc:
                    self.state, self.info = "ready", header
            logger.info("Nemotron speech worker ready: %s", header)
        else:
            self._fail(header.get("message") or f"unexpected first message {header!r}")

    def _exit_reason(self, what: str) -> str:
        code = None
        if self._proc is not None:
            try:                       # the pipe closes a moment before the exit is reaped
                code = self._proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                code = None
        tail = ""
        if self.log_path and self.log_path.exists():
            with open(self.log_path, "rb") as fh:
                fh.seek(max(0, self.log_path.stat().st_size - 4096))
                lines = fh.read().decode(errors="replace").strip().splitlines()
            tail = next((ln for ln in reversed(lines) if ln.strip()), "")[:200]
        return what + (f" (exit code {code})" if code is not None else "") + \
            (f": {tail}" if tail else "")

    def _fail(self, reason: str) -> None:
        with self._state_lock:
            self.state, self.reason, self.failed_at = "failed", reason, time.monotonic()
            proc, self._proc = self._proc, None
        logger.error("Nemotron speech worker failed: %s", reason)
        if proc is not None and proc.poll() is None:
            proc.kill()

    def stop(self) -> None:
        with self._state_lock:
            proc, self._proc = self._proc, None
            self.state = "stopped"
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def ensure_running(self) -> None:
        """Start a fresh worker after a failure, once the cooldown has passed.
        Never during a consultation: callers check at session open only."""
        if self.state == "stopped" or (
                self.state == "failed" and self.failed_at is not None
                and time.monotonic() - self.failed_at >= RESTART_COOLDOWN_S):
            self.start()

    @property
    def ready(self) -> bool:
        if self.state == "ready" and self._proc is not None and self._proc.poll() is not None:
            self._fail(self._exit_reason("the speech worker exited"))
        return self.state == "ready"

    # -- requests ----------------------------------------------------------

    def request(self, header: dict, payload: bytes = b"",
                timeout_s: float | None = None) -> dict:
        with self._lock:
            if not self.ready:
                raise WorkerError(self.reason or "the speech worker is not ready")
            proc = self._proc
            try:
                _write_frame(proc.stdin, header, payload)
                reply, _ = _read_frame(proc.stdout.fileno(),
                                       timeout_s or self.request_timeout_s)
            except TimeoutError:
                reason = (f"the speech worker did not answer a {header.get('type')} "
                          f"request within {timeout_s or self.request_timeout_s:.0f} s")
                self._fail(reason)
                raise WorkerError(reason) from None
            except (EOFError, OSError, BrokenPipeError, ValueError):
                reason = self._exit_reason("the speech worker exited")
                self._fail(reason)
                raise WorkerError(reason) from None
        if reply.get("type") == "error":
            if reply.get("fatal"):
                self._fail(reply.get("message") or "fatal worker error")
            raise WorkerError(reply.get("message") or "worker error")
        return reply

    async def arequest(self, header: dict, payload: bytes = b"",
                       timeout_s: float | None = None) -> dict:
        return await asyncio.to_thread(self.request, header, payload, timeout_s)


def start_worker() -> SpeechWorker:
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1"}
    NEMOTRON_HOME.mkdir(parents=True, exist_ok=True)
    worker = SpeechWorker(worker_command(), log_path=NEMOTRON_HOME / "worker.log", env=env)
    worker.start()
    return worker


def status(worker: SpeechWorker | None) -> dict:
    """What the live page shows before Start. Plain sentences."""
    if not uses_nemotron():
        return {"pipeline": WHISPER, "ready": True, "state": "ready", "detail": None}
    error = configuration_error()
    if error is not None:
        return {"pipeline": SPEECH_PIPELINE, "ready": False, "state": "misconfigured",
                "detail": error}
    if worker is None:
        return {"pipeline": NEMOTRON, "ready": False, "state": "stopped",
                "detail": "The Nemotron speech engine is not running. Recording "
                          "cannot start until it is."}
    worker.ensure_running()
    if worker.ready:
        return {"pipeline": NEMOTRON, "ready": True, "state": "ready", "detail": None,
                "max_speakers": worker.info.get("max_speakers")}
    if worker.state == "starting":
        return {"pipeline": NEMOTRON, "ready": False, "state": "starting",
                "detail": "The Nemotron speech engine is still loading. Recording "
                          "can start when it is ready (about half a minute after "
                          "the service starts)."}
    return {"pipeline": NEMOTRON, "ready": False, "state": worker.state,
            "detail": f"The Nemotron speech engine is not working: {worker.reason}. "
                      "Recording cannot start. It is not replaced by Whisper; "
                      "set SPEECH_PIPELINE=whisper and restart to use Whisper."}


# --- the live session ------------------------------------------------------

class NemotronLiveSession(LiveSession):
    """LiveSession for the nemotron pipeline: the same hooks, another engine.

    The recording, the speaking windows and the zero-fill are LiveSession's
    own and are not changed. This class only replaces what happens to the
    muted audio: it goes to the worker instead of to faster-whisper. Every
    member main.py and auto mode use keeps its meaning — append_pcm16,
    process, flush, audio_seconds, new_audio_seconds, speaking, the window
    calls and save_recording — so main.py's loop needs no change.

    **Order** (owner, at approval): the speakers' lines can commit out of
    time order. Lines are held and released in start-time order, up to the
    worker's watermark, so transcript_parts (what the CDS reads) runs in
    the order the consultation was spoken.

    **Storage**: each line is written to live_speech_segment the moment it
    arrives, with its speaker and times, before any ordering.

    **Failure**: any worker error ends live transcription for the session.
    The page is told at once (take_notices). The recording carries on.
    `failure` is kept, so finalisation refuses this transcript — no silent
    fallback, and never a transcript from a partial flush.
    """

    def __init__(self, worker: SpeechWorker, session_id: str, store) -> None:
        super().__init__(transcriber=None)
        self._worker = worker
        self.session_id = session_id
        self._store = store
        self._pending = bytearray()      # muted PCM16 not yet sent
        self._held: list[dict] = []      # committed lines waiting for the watermark
        self._released_start = -math.inf
        self.failure: str | None = None
        self.flushed = False
        self.order_violations = 0
        self.lines = 0
        self._notices: list[dict] = []

    async def open(self) -> None:
        await self._worker.arequest({"type": "open", "session": self.session_id})

    # -- audio: LiveSession.append_pcm16's guarantee, the muted copy kept as PCM

    def append_pcm16(self, data: bytes) -> None:
        start = self._recorded_bytes
        self._recording.append(data)
        self._recorded_bytes = end = start + len(data)
        muted = self._mute_range(start, end)
        if muted is None:
            self._pending += data
        else:
            lo, hi = muted
            chunk = bytearray(data)
            chunk[lo - start:hi - start] = bytes(hi - lo)
            self._pending += chunk
        self._new_samples += len(data) // BYTES_PER_SAMPLE

    @property
    def audio_seconds(self) -> float:
        """Total audio received — the session clock, as LiveSession's."""
        return self._recorded_bytes / BYTES_PER_SAMPLE / SAMPLE_RATE

    # -- lines ---------------------------------------------------------------

    def _fail(self, reason: str) -> None:
        if self.failure is None:
            self.failure = reason
            logger.error("Live session %s: Nemotron transcription stopped: %s",
                         self.session_id, reason)
            self._notices.append({
                "type": "speech_failed",
                "detail": ("Live transcription has stopped: the Nemotron speech engine "
                           f"failed ({reason}). The recording carries on and is saved, "
                           "but this consultation's transcript will be refused at Stop "
                           "and no note will be drafted from it.")})

    def take_notices(self) -> list[dict]:
        notices, self._notices = self._notices, []
        return notices

    async def _handle(self, reply: dict) -> list[Segment]:
        segments = reply.get("segments") or []
        revisions = reply.get("revisions") or []
        if segments:
            await self._store.save(self.session_id, segments)
            self.lines += len(segments)
        if revisions:
            await self._store.revise(self.session_id, revisions)
        self._held.extend(segments)
        watermark = reply.get("watermark")
        due = [ln for ln in self._held if watermark is None or ln["start"] < watermark]
        self._held = [ln for ln in self._held if not (watermark is None or ln["start"] < watermark)]
        released = []
        for line in sorted(due, key=lambda ln: (ln["start"], ln["id"])):
            if line["start"] < self._released_start:
                # Cannot happen if the watermark holds; counted, not hidden.
                self.order_violations += 1
            self._released_start = max(self._released_start, line["start"])
            released.append(Segment(start=line["start"], end=line["end"], text=line["text"]))
        return released

    async def _send_pending(self, timeout_s: float | None = None) -> dict | None:
        if not self._pending:
            return None
        payload, self._pending = bytes(self._pending), bytearray()
        return await self._worker.arequest(
            {"type": "audio", "session": self.session_id}, payload, timeout_s)

    async def process(self) -> tuple[list[Segment], str]:
        self._new_samples = 0
        if self.failure is not None:
            self._pending.clear()
            return [], ""
        try:
            reply = await self._send_pending()
            if reply is None:
                return [], ""
            return await self._handle(reply), reply.get("partial") or ""
        except WorkerError as exc:
            self._fail(str(exc))
            return [], ""

    async def flush(self) -> list[Segment]:
        """Stop: send the last audio, take every remaining line. On any
        failure, including no answer within FLUSH_TIMEOUT_S, nothing more is
        returned and `failure` says why — the transcript will be refused."""
        if self.flushed:
            return []
        if self.failure is not None:
            return []
        try:
            released = []
            reply = await self._send_pending(FLUSH_TIMEOUT_S)
            if reply is not None:
                released += await self._handle(reply)
            reply = await self._worker.arequest(
                {"type": "flush", "session": self.session_id}, b"", FLUSH_TIMEOUT_S)
            reply["watermark"] = None            # the flush commits everything
            released += await self._handle(reply)
            self.flushed = True
            logger.info("Live session %s: Nemotron flushed, %d lines, stats %s",
                        self.session_id, self.lines, reply.get("stats"))
            return released
        except WorkerError as exc:
            self._fail(f"at Stop: {exc}")
            return []
