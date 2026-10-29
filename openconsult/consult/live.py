"""The live consultation, as a class with named fields (spec 5.1; 15.10;
V1_LESSONS 6.2, 10). One object for one consultation from Start to the
final transcript. Each thing the page can do is one method: the capture
settings, a piece of sound, an acknowledgement, Stop, the who-spoke
answer. The state the page shows is one dict from page_state(), computed
here and run by tests; the page script only renders it (V1_LESSONS 5.2).
No model call and no worker request runs on the page's own loop: sound
goes to the speech door on the caller's thread, a pass runs on one thread
of its own, and Stop runs on one thread of its own (stop.py)."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from openconsult.consult import recording as recording_module
from openconsult.consult.cds_pass import run_pass
from openconsult.consult.consultations import Consultations
from openconsult.consult.messages import Patient
from openconsult.consult.note_rows import Notes
from openconsult.consult.passes import Passes
from openconsult.consult.recording import Recording
from openconsult.consult.transcript import Transcript
from openconsult.guidelines.panel import PanelState
from openconsult.llm.door import Door
from openconsult.patients.audit import Audit, Clock, now_local
from openconsult.patients.patients import PatientRow
from openconsult.speech.door import Door as SpeechDoor

SPEAKERS = 2          # the doctor and the patient (ruling 9)
WITHIN, OVER = "within", "over"
LIVE, STOPPING, FINAL = "live", "stopping", "final"
# The named in-progress states a spinner may show (V1_LESSONS 5.3).
SPINNING = ("speech_starting", "pass_running", "speech", "label_check", "checks", "gate", "note")
# A thread that has returned leaves the table a moment later; close waits for
# that moment, far beyond its length on the slowest machine, and no longer, so
# that the app's shutdown never hangs on a thread that will not end.
CLOSE_WAIT_S = 5.0


def clock_state(used_s: float, intended_minutes: int) -> str:
    """Ruling 10: at and after the intended time the clock changes colour,
    and nothing else happens."""
    return OVER if used_s >= intended_minutes * 60 else WITHIN


@dataclass
class Capture:
    echo_cancellation: bool | None
    noise_suppression: bool | None
    auto_gain: bool | None
    rate: int


@dataclass
class Speech:
    """What the speech door is doing: starting, open, failed (with the
    reason) or stopped at Stop."""
    state: str = "not_started"
    reason: str | None = None


@dataclass
class Final:
    """What Stop leaves, for the final page: the transcript rows as they
    stand, the warnings, whether the gate refused, and the figures."""
    lines: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    refused: bool = False
    figures: dict = field(default_factory=dict)


class Consultation:
    def __init__(self, consultation_id: int, patient: PatientRow, intended_minutes: int, started_at: datetime,
                 speech: SpeechDoor, llm: Door, rows: Consultations, audit: Audit, data_folder: Path,
                 clock: Clock = now_local, timer: Callable[[], float] = time.perf_counter,
                 on_stop: Callable | None = None, notes: Notes | None = None, converter=None,
                 background: str | None = None, guidelines=None):
        self.id = consultation_id
        self.notes = notes                # the note's rows (6b), given by the app
        self.converter = converter        # the recording converter (7a), given by the app; None keeps the WAV
        self.background = background      # the block of 15.11 ruling 5 for the two calls, or None (7b)
        self.guideline = PanelState(guidelines, self) if guidelines is not None else None   # the panel (8b), given by the app
        self.patient = patient
        self.intended_minutes = int(intended_minutes)
        self.started_at = started_at
        self.speech_door = speech
        self.llm = llm
        self.rows = rows
        self.audit = audit
        self.data_folder = Path(data_folder)
        self.clock = clock
        self.timer = timer
        self.on_stop = on_stop            # the finaliser (stop.py), given by the app
        self.on_final: Callable | None = None   # the app's hook once the final transcript is ready
        self.speakers_given = SPEAKERS
        self.resume_pending = False       # built again after a restart, not yet carried on
        self.closed = False
        self.state = LIVE
        self.stop_stage: str | None = None
        self.capture: Capture | None = None
        self.speech = Speech()
        self.speech_failure: str | None = None
        self.recording: Recording | None = None
        self.transcript = Transcript()
        self.passes = Passes()
        self.final = Final()
        self.stopped_at: datetime | None = None
        self.doctor_speaker: str | None = None
        self.answer_event = threading.Event()
        self.version = 0
        self.lock = threading.RLock()
        self._pending: list[bytes] = []
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"consultation-{consultation_id}")
        self._pass: Future | None = None
        self._stop_thread: threading.Thread | None = None

    # ------------------------------------------------------------ patient

    @property
    def age(self) -> int:
        return self.patient.age_on(self.clock().date())

    @property
    def model_patient(self) -> Patient:
        return Patient(self.age, self.patient.sex)

    def _changed(self) -> None:
        self.version += 1

    # ------------------------------------------------------------ capture

    def begin_sound(self, capture: Capture) -> None:
        """The page's first message: the three microphone values as the
        browser applied them and the session's rate (11.5 rule 3; ruling
        7). The recording opens at that rate, then the speech door, which
        starts its worker. Sound that arrived meanwhile is fed after."""
        with self.lock:
            if self.state != LIVE or self.capture is not None:
                return
            self.capture = capture
            self.rows.set(self.id, echo_cancellation=_flag(capture.echo_cancellation),
                          noise_suppression=_flag(capture.noise_suppression), auto_gain=_flag(capture.auto_gain),
                          sample_rate=capture.rate)
            self.speech = Speech("starting")
            self._changed()
        self._open_recording(capture.rate)
        opened = self.speech_door.open(capture.rate, speakers=self.speakers_given)
        with self.lock:
            if not opened.ok:
                self._speech_failed(opened.detail or opened.failure)
                return
            self.speech = Speech("open")
            self.rows.set(self.id, speech_stamp=_stamp_json(self.speech_door.stamp))
            waiting, self._pending = self._pending, []
            self._changed()
        for pcm in waiting:
            self._feed(pcm)

    def _open_recording(self, rate: int) -> None:
        path = recording_module.folder_of(self.data_folder) / recording_module.file_name(self.id)
        self.recording = Recording(path, rate)
        self.rows.set(self.id, recording_file=path.name)

    def _speech_failed(self, reason: str) -> None:
        """A failure of the speech choice is said with its reason and the
        consultation goes on: the recording goes on, nothing is retried in
        silence (10.4; carried from 5b)."""
        if self.speech_failure is None:
            self.speech_failure = reason
            self.rows.set(self.id, speech_failure=reason)
        self.speech = Speech("failed", reason)
        self._changed()

    # -------------------------------------------------------------- sound

    def sound(self, pcm: bytes) -> None:
        """One piece from the page: the file first, so no sound is lost to a
        failed worker; then the door; then a pass if one is due."""
        with self.lock:
            if self.state != LIVE:
                return
            if self.recording is not None:
                self.recording.add(pcm)
            if self.speech.state != "open":
                if self.speech.state in ("not_started", "starting"):
                    self._pending.append(pcm)
                return
        self._feed(pcm)

    def _feed(self, pcm: bytes) -> None:
        live = self.speech_door.feed(pcm)
        with self.lock:
            if self.state != LIVE:
                return
            if not live.ok:
                self._speech_failed(live.detail or live.failure)
                return
            for shown in self.transcript.add(live):
                self.rows.add_live_line(self.id, shown.n, shown.line, shown.refused, shown.shown_at_s)
            self._changed()
            if self.passes.due(self.transcript):
                self._start_pass()

    # ------------------------------------------------------------- passes

    def _start_pass(self) -> None:
        n = self.passes.begin()
        text = self.transcript.mark_sent()
        carried = self.passes.carried
        self._changed()
        self._pass = self._pool.submit(self._run_pass, n, text, carried)

    def _run_pass(self, n: int, text: str, carried) -> None:
        started = self.timer()
        result = run_pass(self.llm, text, self.model_patient, carried, consultation_id=self.id,
                          background=self.background)
        wall_ms = round(1000 * (self.timer() - started))
        with self.lock:
            shown = self.state == LIVE
            stored = self.passes.settle(n, result, shown, wall_ms)
            self.rows.add_pass(self.id, n, text, result.alarm.call_id, result.assessment.call_id, stored, shown)
            self._changed()
            if shown and self.guideline is not None:
                self.guideline.after_pass(n, result.assessment)    # after the pass is stored and shown: it can touch nothing of it (R30)

    def wait_for_pass(self, timeout_s: float = 30.0) -> None:
        """For tests and for Stop: the pass in flight, if any, lands."""
        if self._pass is not None:
            self._pass.result(timeout=timeout_s)

    def wait_for_guideline(self, timeout_s: float = 30.0) -> None:
        if self.guideline is not None:
            self.guideline.wait(timeout_s)

    def acknowledge(self, key: str) -> bool:
        with self.lock:
            done = self.passes.acknowledge(key)
            if done:
                self.audit.record("alarm.acknowledged", f"consultation {self.id}: {key}")
                self._changed()
            return done

    # --------------------------------------------------------------- stop

    def stop(self) -> bool:
        """The first Stop: the recording is closed, the moment and the audit
        line written (R2), and the finaliser started. A second Stop while
        one is finalising waits for it: it returns False and changes
        nothing (V1_LESSONS 1.12)."""
        with self.lock:
            if self.state != LIVE:
                return False
            self.state = STOPPING
            self.stop_stage = "speech"
            self.stopped_at = self.clock()
            if self.recording is not None:
                self.recording.close()
            self.rows.set(self.id, state=STOPPING, stop_stage="speech",
                          stopped_at=self.stopped_at.isoformat(timespec="seconds"))
            self.audit.record("consultation.stopped", f"consultation {self.id}")
            self._changed()
        if self.on_stop is not None:
            self.run_stop_thread(self.on_stop)
        return True

    def run_stop_thread(self, step: Callable) -> None:
        """The Stop thread: one of its own, marked so that it never holds
        the process open; it waits on the doctor with no limit (2.2) and
        ends with the app, which joins it at close (the small fix of 7b)."""
        self._stop_thread = threading.Thread(target=step, args=(self,), name=f"stop-{self.id}", daemon=True)
        self._stop_thread.start()

    def set_stage(self, stage: str | None) -> None:
        with self.lock:
            self.stop_stage = stage
            self.rows.set(self.id, stop_stage=stage)
            self._changed()

    def close(self) -> None:
        """At the app's shutdown, and at the end of a test: no thread of the
        consultation outlives it. A Stop waiting at who-spoke returns at
        once; a conversion in flight finishes (its command has a limit);
        a pass in flight lands and is recorded."""
        self.closed = True
        self.answer_event.set()
        if self._stop_thread is not None and self._stop_thread is not threading.current_thread():
            self._stop_thread.join()
        self._pool.shutdown(wait=True)
        if self.guideline is not None:
            self.guideline.close()
        self._wait_for_my_threads()

    def _is_mine(self, thread: threading.Thread) -> bool:
        """The Stop thread, or a worker of the pass pool (named prefix_N), of
        this consultation and no other: consultation 1 is not 10."""
        return thread.name == f"stop-{self.id}" or thread.name.startswith(f"consultation-{self.id}_")

    def _wait_for_my_threads(self) -> None:
        """Until no thread of the consultation is on the table, bounded by
        CLOSE_WAIT_S: what close promises, not what a caller hopes."""
        end = time.monotonic() + CLOSE_WAIT_S
        while True:
            left = [t for t in threading.enumerate() if self._is_mine(t) and t is not threading.current_thread()]
            remaining = end - time.monotonic()
            if not left or remaining <= 0:
                return
            if left[0].is_alive():
                left[0].join(timeout=remaining)

    # -------------------------------------------------------------- state

    def used_s(self) -> float:
        end = self.stopped_at or self.clock()
        return max(0.0, (end - self.started_at).total_seconds())

    def spinning(self) -> str | None:
        """The one named in-progress state a spinner may show, or none."""
        if self.state == LIVE:
            if self.speech.state == "starting":
                return "speech_starting"
            if self.passes.running:
                return "pass_running"
            return None
        if self.state == STOPPING and self.stop_stage in SPINNING:
            return self.stop_stage
        return None

    def page_state(self) -> dict:
        with self.lock:
            used = self.used_s()
            return {
                "id": self.id,
                "version": self.version,
                "state": self.state,
                "stop_stage": self.stop_stage,
                "spinning": self.spinning(),
                "started_at": self.started_at.isoformat(timespec="seconds"),
                "intended_minutes": self.intended_minutes,
                "used_s": round(used, 1),
                "clock": clock_state(used, self.intended_minutes),
                "speech": {"state": self.speech.state, "reason": self.speech.reason, "failure": self.speech_failure},
                "background": self.background is not None,     # the mark of 8.5
                "transcript": {
                    "lines": [{"n": s.n, "speaker": s.line.speaker, "text": s.line.text, "start": s.line.start,
                               "end": s.line.end, "confidence": s.line.confidence} for s in self.transcript.heard],
                    "partial": self.transcript.partial,
                },
                "passes": self.passes.state(),
                "guidelines": self.guideline.state() if self.guideline is not None else None,
            }


def _flag(value: bool | None) -> int | None:
    return None if value is None else int(bool(value))


def _stamp_json(stamp) -> str | None:
    return json.dumps(asdict(stamp), ensure_ascii=False) if stamp else None
