"""The one door to transcription (spec 5.1, 6, 11.4; 15.9). Every word of
speech reaches the app through open, feed and stop. Each gives one
result: lines, or a failure with its reason. It never raises into the
app. If the choice is absent or its worker has died, it says so and
tries nothing else (10.4). The rule against words from silence sits
here, so it holds for every choice (ruling 1). A choice with one
transcript gets its lines back at Stop from the door's own record of
what it gave, so nothing is written twice and nothing is lost (11.1)."""

from __future__ import annotations

import dataclasses
import itertools
import os
from pathlib import Path
from typing import Callable

from openconsult import words
from openconsult.settings import keys
from openconsult.speech import environment
from openconsult.speech.choices import WHISPERX_PYANNOTE, Choice
from openconsult.speech.lines import FAILURES, Final, Line, Live, Revision, Stamp, failed_final, failed_live
from openconsult.speech.loudness import Loudness, refuse_quiet
from openconsult.speech.turns import as_line, merge_into_turns
from openconsult.speech.worker import Worker, WorkerGone

# The Stop models load at Stop and the pass runs over the whole session.
STOP_TIMEOUT_S = 600.0

# The sentence for each failure a cloud worker reports by name (7.2).
# The worker gives the name and, where there is one, a detail.
SENTENCES = {
    "key_refused": words.KEY_REFUSED, "no_credit": words.NO_CREDIT, "no_internet": words.NO_INTERNET,
    "service_down": words.SERVICE_DOWN, "limit_reached": words.LIMIT_REACHED,
    "address_refused": words.ADDRESS_REFUSED, "connection_lost": words.CONNECTION_LOST,
}


class Door:
    def __init__(self, choice: Choice, make_worker: Callable[[], Worker],
                 installed: Callable[[], bool], key_present: Callable[[], bool] = lambda: True):
        self.choice = choice
        self._make_worker = make_worker
        self._installed = installed
        self._key_present = key_present
        self._worker: Worker | None = None
        self._session: str | None = None
        self._loudness: Loudness | None = None
        self._ids = itertools.count(1)
        self._line_ids = itertools.count(1)       # for a segment that comes with no id
        self._speakers_at_open: int | None = None
        self._given: dict[int, Line] = {}         # one transcript: every line given, by id
        self._refused: dict[int, Line] = {}

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

    @property
    def one_transcript(self) -> bool:
        return not self.choice.declares.second_transcript

    # ---------------------------------------------------------------- open

    def open(self, rate: int, speakers: int | None = None) -> Live:
        """Start a session at the sound's rate: the app records sound as the
        microphone gives it, and the new recordings are 48 kHz (spec 13.2;
        15.9 ruling 7). A choice whose labels are live is told the number
        of speakers here; it is given, never worked out (V1_LESSONS 2.1)."""
        if self._session is not None:
            # The open session goes on untouched: its sound is never thrown away.
            return failed_live("session_open", words.DOOR_SESSION_OPEN, self.fed_s, self.stamp)
        if not self._installed():
            return failed_live("not_installed", words.SPEECH_NEEDS_INSTALL, 0.0, None)
        if self.choice.key and not self._key_present():
            return failed_live("no_key", words.NO_KEY.format(service=self.choice.title, name=self.choice.key), 0.0, None)
        header = {"type": "open", "session": None, "rate": int(rate)}
        if self.choice.declares.speakers == "live":
            if speakers is None:
                return failed_live("bad_speakers", words.DOOR_SPEAKERS_NEEDED, 0.0, self.stamp)
            if int(speakers) < 1:
                return failed_live("bad_speakers", words.DOOR_BAD_SPEAKERS.format(speakers=speakers), 0.0, self.stamp)
            header["speakers"] = int(speakers)
        if self._worker is None or self._worker.state in ("stopped", "failed"):
            self._worker = self._make_worker()
            self._worker.start()
        if not self._worker.wait_ready():
            return failed_live(self._worker.kind or "died", self._worker.reason or words.WORKER_NOT_READY, 0.0, None)
        header["session"] = session = f"s{next(self._ids)}"
        try:
            reply = self._worker.request(header)
        except WorkerGone as gone:
            return failed_live(gone.kind, gone.detail, 0.0, self.stamp)
        if reply.get("type") != "opened":
            return failed_live(*self._error(reply), 0.0, self.stamp)
        self._session, self._loudness = session, Loudness(int(rate))
        self._speakers_at_open = header.get("speakers")
        self._given, self._refused = {}, {}
        return Live(True, 0.0, self.stamp)

    # ---------------------------------------------------------------- feed

    def feed(self, pcm: bytes) -> Live:
        """One piece of sound. Back come the lines made final, what the
        rule refused, the text not yet final, and any labels revised."""
        if self._session is None:
            return failed_live("no_session", words.DOOR_NO_SESSION, self.fed_s, self.stamp)
        self._loudness.add(pcm)
        try:
            reply = self._worker.request({"type": "audio", "session": self._session}, pcm)
        except WorkerGone as gone:
            self._session = None
            return failed_live(gone.kind, gone.detail, self.fed_s, self.stamp)
        if reply.get("type") != "lines":
            return failed_live(*self._error(reply), self.fed_s, self.stamp)
        try:
            final = [self._live_line(s) for s in reply.get("segments") or []]
            pending = [self._live_line(s) for s in reply.get("pending") or []]
            accepted, refused = refuse_quiet(final, self._loudness)
            self._record(accepted, refused)
            revisions = self._revise(reply.get("revisions") or [])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            return failed_live("bad_reply", words.DOOR_BAD_REPLY.format(reason=exc), self.fed_s, self.stamp)
        heard, _ = refuse_quiet(pending, self._loudness)
        return Live(True, self.fed_s, self.stamp, tuple(accepted), tuple(refused),
                    " ".join(line.text for line in heard), revisions=revisions)

    # ---------------------------------------------------------------- stop

    def stop(self, speakers: int) -> Final:
        """Stop. The number of speakers is given, never worked out
        (V1_LESSONS 2.1). The last live lines are made final first, so the
        check at Stop can see the end (11.5 rule 2; D45). With a second
        transcript the raw segments are kept as they came (V1_LESSONS 1.7);
        with one transcript the lines already given come back as they were
        given, with the last ones (11.1). Stop never refuses over a count
        that differs from the one at open: the last words are said at
        Stop, so both counts are recorded and the lines are given."""
        if self._session is None:
            return failed_final("no_session", words.DOOR_NO_SESSION, self.stamp)
        if int(speakers) < 1:
            # Refused here, with the session kept: pyannote would fail on it
            # and take the worker down for a wrong number.
            return failed_final("bad_speakers", words.DOOR_BAD_SPEAKERS.format(speakers=speakers), self.stamp)
        session, self._session = self._session, None
        try:
            reply = self._worker.request({"type": "stop", "session": session, "speakers": int(speakers)},
                                         timeout_s=STOP_TIMEOUT_S)
        except WorkerGone as gone:
            return failed_final(gone.kind, gone.detail, self.stamp)
        if reply.get("type") != "stopped":
            return failed_final(*self._error(reply), self.stamp)
        try:
            tail = [self._live_line(s) for s in reply.get("last_live") or []]
            tail_ok, tail_refused = refuse_quiet(tail, self._loudness)
            if self.one_transcript:
                return self._one_transcript_final(reply, tail_ok, tail_refused, int(speakers))
            raw = [dict(s) for s in reply.get("segments") or []]
            raw_lines = [as_line(s) for s in raw]
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            return failed_final("bad_reply", words.DOOR_BAD_REPLY.format(reason=exc), self.stamp)
        _, raw_refused = refuse_quiet(raw_lines, self._loudness)
        refused_ids = {id(r.line) for r in raw_refused}
        flagged = tuple({**seg, "refused": id(line) in refused_ids} for seg, line in zip(raw, raw_lines))
        kept = [seg for seg, line in zip(raw, raw_lines) if id(line) not in refused_ids]
        return Final(True, self.stamp, tuple(merge_into_turns(kept)), tuple(tail_ok),
                     tuple(tail_refused + raw_refused), flagged, dict(reply.get("seconds") or {}))

    def _one_transcript_final(self, reply: dict, tail_ok: list, tail_refused: list, speakers: int) -> Final:
        self._record(tail_ok, tail_refused)
        revisions = self._revise(reply.get("revisions") or [])
        return Final(True, self.stamp, tuple(self._given.values()), tuple(tail_ok), tuple(tail_refused), (),
                     dict(reply.get("seconds") or {}), revisions=revisions,
                     speakers={"open": self._speakers_at_open, "stop": speakers})

    def close(self) -> None:
        self._session = None
        if self._worker is not None:
            self._worker.stop()

    # ------------------------------------------------------------ the record

    def _live_line(self, segment: dict) -> Line:
        """A segment as a line. A choice whose labels are live gives each
        segment an id, a speaker or null and a confidence or null; the
        others give none of these, and the door numbers the line itself."""
        number = segment.get("id")
        if number is None and self.one_transcript:
            number = next(self._line_ids)
        speaker, confidence = segment.get("speaker"), segment.get("confidence")
        return Line(None if speaker is None else str(speaker), float(segment["start"]), float(segment["end"]),
                    str(segment["text"]).strip(), None if confidence is None else float(confidence),
                    None if number is None else int(number))

    def _record(self, accepted: list, refused: list) -> None:
        if not self.one_transcript:
            return
        for line in accepted:
            self._given[line.id] = line
        for item in refused:
            self._refused[item.line.id] = item.line

    def _revise(self, revisions: list) -> tuple[Revision, ...]:
        """A revision changes a label and nothing else (ruling 4), and never
        costs a line: one that names a refused line or an unknown id is
        recorded and the lines go on as if it had not come."""
        made = []
        for item in revisions:
            number, speaker = int(item["id"]), item.get("speaker")
            speaker = None if speaker is None else str(speaker)
            if number in self._given:
                self._given[number] = dataclasses.replace(self._given[number], speaker=speaker)
                made.append(Revision(number, speaker, True, self._given[number]))
            else:
                made.append(Revision(number, speaker, False, self._refused.get(number)))
        return tuple(made)

    def _error(self, reply: dict) -> tuple[str, str]:
        """A worker's error by name. A name the door knows passes through
        with its sentence; anything else is a worker error with the
        worker's own words."""
        if reply.get("type") != "error":
            return "bad_reply", words.DOOR_BAD_REPLY.format(reason=f"type {reply.get('type')!r}")
        reason, message = reply.get("reason"), str(reply.get("message") or words.WORKER_SAID_NOTHING)
        if reason in SENTENCES:
            return reason, SENTENCES[reason].format(service=self.choice.title, detail=reply.get("detail") or "")
        if reason in FAILURES and reason != "bad_reply":
            return reason, message
        return "worker_error", message


def make_door(data_folder: Path, choice: Choice = WHISPERX_PYANNOTE,
              environ=os.environ) -> Door:
    """The app's door: the real worker from the data folder's environment,
    or on the app's own Python for a cloud choice, with its one key in
    the worker's environment and nowhere in the door."""
    def key() -> str | None:
        return keys.read_key(choice.key, data_folder, environ) if choice.key else None

    return Door(
        choice,
        make_worker=lambda: Worker(environment.worker_command(data_folder, choice),
                                   log_path=environment.log_path(data_folder, choice),
                                   env=environment.worker_env(environ, choice.key, key())),
        installed=lambda: environment.installed(data_folder, choice),
        key_present=lambda: key() is not None,
    )
