"""The recording sent after Stop (spec 15.9, rulings 28, 36 and 42; 15.13,
rulings 29 and 33 and the details of run 9b). Two ways lead here and no
other: the tick for better accuracy, on a path whose transcription runs
on this computer; and the one press after a lost connection, on a path
whose transcription runs in the cloud. Never by itself.

The recording as it was written is sent once to the service's EU
address under a plain name with no date, with the request the bench
sent. The lines of the result become the final transcript, words and
speakers, and the lines of the live page stay in the record as what was
heard live. The job is deleted as soon as the result is held and asked
for again, and each answer is kept. Whenever the service has taken a
job, a delete is asked and its answer kept: after a failure, after the
limit of time, and after a restart of the app, because the job's name
is written down the moment the service gives it.

When the upload fails or passes its limit of time, the live lines stay
the final transcript, the review page says why, and nothing is sent
again by itself. A delete that is not proven is said on the review
page in the owner's words and written to the audit log. The key is
read at the moment of sending and is in no row and no reason."""

from __future__ import annotations

import time
from typing import Callable

from openconsult import words
from openconsult.consult.consultations import line_as_row
from openconsult.consult.recording import folder_of
from openconsult.speech import speechmatics_upload as service
from openconsult.speech import upload
from openconsult.speech.lines import Line

TICK, PRESS = "tick", "press"
FILE_NAME = "recording.wav"          # a plain name with no date, no number and no person
# The limit of time for the result: two minutes and a quarter of the recording's length (a 15-minute consultation:
# 345 s). A design choice set beside the 13 to 41 s of the bench's results; after it the job is deleted.
LIMIT_BASE_S, LIMIT_SHARE = 120.0, 0.25
MADE, FAILED, NOT_PROVEN = "better_transcript", "better_transcript_failed", "delete_not_proven"
KINDS = (MADE, FAILED, NOT_PROVEN)


def limit_s(recording_s: float) -> float:
    return LIMIT_BASE_S + LIMIT_SHARE * max(0.0, recording_s)


def way_of(row: dict, pressed: bool | None) -> str | None:
    """Which of the two ways sends this consultation's recording, or None."""
    if row["better_accuracy"] and row["transcription_path"] == "this_computer":
        return TICK
    if pressed and row["transcription_path"] == "speechmatics":
        return PRESS
    return None


def reason_of(failure: dict | None, limit: float) -> str:
    """Why the better transcript could not be made, in one sentence."""
    title = words.SERVICE_TITLES["speechmatics"]
    at, detail = (failure or {}).get("at"), (failure or {}).get("detail") or ""
    if at == "key":
        return words.NOT_CONNECTED_SERVICE.format(service=title)
    if at == "send":
        if "HTTP 401" in detail or "HTTP 403" in detail:
            return words.KEY_REFUSED.format(service=title)
        if "HTTP 402" in detail:
            return words.NO_CREDIT.format(service=title)
        if detail.endswith("HTTP 0"):
            return words.NO_INTERNET.format(service=title)
        return words.SERVICE_DOWN.format(service=title)
    if at == "result" and "no result within" in detail:
        return words.UPLOAD_TOO_SLOW.format(service=title, seconds=f"{limit:.0f}")
    if at == "model":
        return words.UPLOAD_WRONG_SETTINGS.format(service=title)
    if at == "restart":
        return words.UPLOAD_APP_CLOSED
    return words.SERVICE_DOWN.format(service=title)


class _Noting:
    """The service's module, with the job's name written down the moment
    the service takes the recording: so that a delete can always be asked."""

    def __init__(self, note: Callable):
        self._note = note

    def __getattr__(self, name):
        return getattr(service, name)

    def submit(self, http, key, wav, file_name, boundary=None):
        job, problem = service.submit(http, key, wav, file_name, boundary)
        if job:
            self._note(job)
        return job, problem


class WholeRecording:
    """Held by the app for its run: the key in use, read at each sending,
    and the sender, which a test replaces with a made service."""

    def __init__(self, key: Callable[[], str | None], send: Callable | None = None, sleep: Callable = time.sleep,
                 clock: Callable = time.monotonic):
        self._key, self._send, self._sleep, self._clock = key, send, sleep, clock

    def http(self) -> upload.Http:
        return upload.Http(service.EU_HOST, self._send)

    def run(self, c, way: str) -> None:
        """Send, read, delete and prove; or, for a consultation found at
        this stage after a restart, ask the delete that was owed. Runs on
        the Stop thread and never raises into it (R30)."""
        if c.rows.upload(c.id) is not None:
            self._after_restart(c)
            return
        row = c.rows.get(c.id)
        path = folder_of(c.data_folder) / row["recording_file"] if row["recording_file"] else None
        key = self._key()
        if key is None or path is None or not path.is_file():
            c.rows.add_upload(c.id, way, FILE_NAME, 0)
            self._ended(c, way, None, {"at": "key" if key is None else "send", "detail": "no key in use" if key is None else "no recording file"},
                        lines=[], limit=0.0)
            return
        wav = path.read_bytes()
        recording_s = c.loudness.seconds if c.loudness is not None else 0.0
        limit = limit_s(recording_s)
        c.rows.add_upload(c.id, way, FILE_NAME, len(wav))
        noting = _Noting(lambda job: c.rows.note_upload_job(c.id, job["id"]))
        try:
            result = upload.run_upload(noting, self.http(), key, wav, FILE_NAME, {"recording": FILE_NAME}, b"", int(row["sample_rate"] or 48000),
                                       clock=self._clock, sleep=self._sleep, timeout_s=limit)
        except Exception as broke:  # noqa: BLE001 - the delete was asked in run_upload's own ending; what broke is said by its name
            noted = c.rows.upload(c.id)
            self._ended(c, way, {"job": {"id": noted["job_id"]} if noted and noted["job_id"] else None, "gone": None,
                                 "proof": f"the upload broke: {type(broke).__name__}"},
                        {"at": "send", "detail": f"the upload broke: {type(broke).__name__}"}, lines=[], limit=limit)
            return
        self._ended(c, way, result["upload"], result["failure"], lines=result["stop"]["lines"], limit=limit)

    def _ended(self, c, way: str, up: dict | None, failure: dict | None, lines: list[dict], limit: float) -> None:
        up = up or {}
        job = up.get("job") or {}
        made = failure is None and bool(lines)
        if failure is None and not lines:
            failure = {"at": "result", "detail": "the result held no words"}
        if made:
            self._make_final(c, lines)
        reason = None if made else reason_of(failure, limit)
        c.rows.end_upload(c.id, job.get("id"), up.get("seconds_to_result"), up.get("counted_s"), up.get("applied"), up.get("delete"),
                          up.get("asked_again") or [], up.get("gone"), up.get("proof"), reason, result=made)
        if made:
            c.rows.add_warning(c.id, MADE, detail=way)
        else:
            c.rows.add_warning(c.id, FAILED, detail=reason)
        # A job the service took and whose delete is not proven: said on the review page and written to the log.
        not_proven = bool(job.get("id")) and up.get("gone") is not True
        if not_proven:
            c.rows.add_warning(c.id, NOT_PROVEN)
            c.audit.record("recording.delete_not_proven", f"consultation {c.id}: {up.get('proof') or 'no answer'}")
        outcome = "the transcript made from it" if made else f"no transcript from it ({(failure or {}).get('at')})"
        c.audit.record("recording.sent", f"consultation {c.id}: by the {way}; {outcome}; "
                       + ("nothing was taken by the service" if not job.get("id") else "deleted and proven gone" if not not_proven else "the delete not proven"))

    def _make_final(self, c, lines: list[dict]) -> None:
        """The service's lines as the final transcript, each as the service
        gave it, numbered in order, its speaker unsure until the answer."""
        rows = [{**line_as_row(Line(None if line.get("speaker") is None else str(line["speaker"]), float(line["start"]), float(line["end"]),
                                    str(line["text"]), line.get("confidence"), None), n, "unsure", unsure=True), "session": 1}
                for n, line in enumerate(lines, start=1)]
        c.rows.replace_transcript_lines(c.id, rows)

    def _after_restart(self, c) -> None:
        """The app was closed while the recording was at the service. It is
        not sent again. If the service had taken it, the delete that was
        owed is asked now and its answer kept."""
        noted = c.rows.upload(c.id)
        if noted["result_at"] is not None or noted["failure"] is not None:
            return                                      # the upload had ended before the restart
        up: dict = {"job": {"id": noted["job_id"]} if noted["job_id"] else None, "delete": None, "asked_again": [], "gone": None, "proof": None}
        key = self._key()
        if noted["job_id"] and key is not None:
            try:
                upload._delete_and_prove(service, self.http(), key, up["job"], [], up)
            except Exception as broke:  # noqa: BLE001
                up["gone"], up["proof"] = None, f"the delete broke: {type(broke).__name__}"
        self._ended(c, noted["way"], up, {"at": "restart", "detail": "the app was closed while the recording was being sent"}, lines=[], limit=0.0)
