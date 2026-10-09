"""The one door to transcription (spec 5.1, 6, 11.4; 15.9). Every word of
speech reaches the app through open, feed and stop. Each gives one
result: lines, or a failure with its reason. It never raises into the
app. If the choice is absent or its worker has died, it says so and
tries nothing else (10.4). The rule against words from silence sits
here, so it holds for every choice (ruling 1)."""

from __future__ import annotations

import itertools
import os
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE, Choice
from openconsult.speech.lines import Final, Line, Live, Stamp, failed_final, failed_live
from openconsult.speech.loudness import Loudness, refuse_quiet
from openconsult.speech.turns import as_line, merge_into_turns
from openconsult.speech.worker import Worker, WorkerGone

# The Stop models load at Stop and the pass runs over the whole session.
STOP_TIMEOUT_S = 600.0


class Door:
    def __init__(self, choice: Choice, make_worker: Callable[[], Worker],
                 installed: Callable[[], bool]):
        self.choice = choice
        self._make_worker = make_worker
        self._installed = installed
        self._worker: Worker | None = None
        self._session: str | None = None
        self._loudness: Loudness | None = None
        self._ids = itertools.count(1)

    @property
    def declares(self):
        return self.choice.declares

    @property
    def stamp(self) -> Stamp | None:
        """The choice, its models and its library versions, as the worker
        reported them when ready (R20)."""
        info = self._worker.info if self._worker else {}
        if not info:
            return None
        return Stamp(self.choice.name, dict(info.get("models") or {}), dict(info.get("versions") or {}))

    @property
    def installed(self) -> bool:
        return bool(self._installed())

    @property
    def ready_info(self) -> dict:
        """What the worker said when ready: its load time and device too."""
        return dict(self._worker.info) if self._worker else {}

    @property
    def fed_s(self) -> float:
        return self._loudness.seconds if self._loudness else 0.0

    # ---------------------------------------------------------------- open

    def open(self, rate: int) -> Live:
        """Start a session at the sound's rate (plan review, change 2)."""
        if not self._installed():
            return failed_live("not_installed", words.SPEECH_NEEDS_INSTALL, 0.0, None)
        if self._worker is None or self._worker.state in ("stopped", "failed"):
            self._worker = self._make_worker()
            self._worker.start()
        if not self._worker.wait_ready():
            return failed_live(self._worker.kind or "died", self._worker.reason or words.WORKER_NOT_READY, 0.0, None)
        session = f"s{next(self._ids)}"
        try:
            reply = self._worker.request({"type": "open", "session": session, "rate": int(rate)})
        except WorkerGone as gone:
            return failed_live(gone.kind, gone.detail, 0.0, self.stamp)
        if reply.get("type") != "opened":
            return failed_live(*_error(reply), 0.0, self.stamp)
        self._session, self._loudness = session, Loudness(int(rate))
        return Live(True, 0.0, self.stamp)

    # ---------------------------------------------------------------- feed

    def feed(self, pcm: bytes) -> Live:
        """One piece of sound. Back come the lines made final, what the
        rule refused, and the text not yet final."""
        if self._session is None:
            return failed_live("no_session", words.DOOR_NO_SESSION, self.fed_s, self.stamp)
        self._loudness.add(pcm)
        try:
            reply = self._worker.request({"type": "audio", "session": self._session}, pcm)
        except WorkerGone as gone:
            self._session = None
            return failed_live(gone.kind, gone.detail, self.fed_s, self.stamp)
        if reply.get("type") != "lines":
            return failed_live(*_error(reply), self.fed_s, self.stamp)
        try:
            final = [_live_line(s) for s in reply.get("segments") or []]
            pending = [_live_line(s) for s in reply.get("pending") or []]
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            return failed_live("bad_reply", words.DOOR_BAD_REPLY.format(reason=exc), self.fed_s, self.stamp)
        accepted, refused = refuse_quiet(final, self._loudness)
        heard, _ = refuse_quiet(pending, self._loudness)
        return Live(True, self.fed_s, self.stamp, tuple(accepted), tuple(refused),
                    " ".join(line.text for line in heard))

    # ---------------------------------------------------------------- stop

    def stop(self, speakers: int) -> Final:
        """The pass at Stop. The number of speakers is given, never worked
        out (V1_LESSONS 2.1). The last live lines are made final first
        (change 3). Raw segments are kept as they came (V1_LESSONS 1.7)."""
        if self._session is None:
            return failed_final("no_session", words.DOOR_NO_SESSION, self.stamp)
        session, self._session = self._session, None
        try:
            reply = self._worker.request({"type": "stop", "session": session, "speakers": int(speakers)},
                                         timeout_s=STOP_TIMEOUT_S)
        except WorkerGone as gone:
            return failed_final(gone.kind, gone.detail, self.stamp)
        if reply.get("type") != "stopped":
            return failed_final(*_error(reply), self.stamp)
        try:
            tail = [_live_line(s) for s in reply.get("last_live") or []]
            raw = [dict(s) for s in reply.get("segments") or []]
            raw_lines = [as_line(s) for s in raw]
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            return failed_final("bad_reply", words.DOOR_BAD_REPLY.format(reason=exc), self.stamp)
        tail_ok, tail_refused = refuse_quiet(tail, self._loudness)
        _, raw_refused = refuse_quiet(raw_lines, self._loudness)
        refused_ids = {id(r.line) for r in raw_refused}
        flagged = tuple({**seg, "refused": id(line) in refused_ids} for seg, line in zip(raw, raw_lines))
        kept = [seg for seg, line in zip(raw, raw_lines) if id(line) not in refused_ids]
        return Final(True, self.stamp, tuple(merge_into_turns(kept)), tuple(tail_ok),
                     tuple(tail_refused + raw_refused), flagged, dict(reply.get("seconds") or {}))

    def close(self) -> None:
        self._session = None
        if self._worker is not None:
            self._worker.stop()


def _live_line(segment: dict) -> Line:
    return Line(None, float(segment["start"]), float(segment["end"]), str(segment["text"]).strip(), None)


def _error(reply: dict) -> tuple[str, str]:
    if reply.get("type") == "error":
        reason = "rate_not_supported" if reply.get("reason") == "rate_not_supported" else "worker_error"
        return reason, str(reply.get("message") or words.WORKER_SAID_NOTHING)
    return "bad_reply", words.DOOR_BAD_REPLY.format(reason=f"type {reply.get('type')!r}")


def make_door(data_folder: Path, choice: Choice = WHISPERX_PYANNOTE,
              environ=os.environ) -> Door:
    """The app's door: the real worker from the data folder's environment."""
    return Door(
        choice,
        make_worker=lambda: Worker(environment.worker_command(data_folder, choice),
                                   log_path=environment.log_path(data_folder, choice),
                                   env=environment.worker_env(environ)),
        installed=lambda: environment.installed(data_folder, choice),
    )
