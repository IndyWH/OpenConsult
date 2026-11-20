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

Stop does not wait for the delete or its proof (the owner's ruling of 18
Nov 2026: a doctor wants the note as soon as Stop is pressed). As soon
as the transcript is back and stored, the stage ends and Stop goes on.
The delete, the two asks and their second tries run beside it, on a
thread of their own, and write each answer to the record as it comes.
Until the proof is judged the record says that the answer is awaited,
and the review page says so in the owner's sentence. An app closed
before the service has answered finds, at its next start, every
recording the service took whose delete is neither proven nor judged
not proven, and finishes it beside the start: so a closed app leaves no
recording at the service.

Delete is never refused (the owner's ruling of 20 Nov 2026). A
consultation deleted while its recording is at the service, neither
proven gone nor judged, leaves the job's name and the state of its
delete apart from it, and nothing else. The thread that is asking goes
on; where none is, one is started; the next start finds what is kept and
finishes it by the same rule and limits. When it is proven or judged the
kept name is dropped, and the log says so in one line that names no
patient and no consultation.

When the upload fails or passes its limit of time, the live lines stay
the final transcript, the review page says why, and nothing is sent
again by itself. A delete that is not proven is said on the review
page in the owner's words and written to the audit log. The key is
read at the moment of sending and is in no row and no reason."""

from __future__ import annotations

import threading
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
# 345 s). A design choice set beside the 13 to 41 s of the bench's results; after it the job is deleted. The delete and
# the two asks are no part of the stage: they run beside Stop, each with the limits of speech/upload.py.
LIMIT_BASE_S, LIMIT_SHARE = 120.0, 0.25
MADE, FAILED, NOT_PROVEN = "better_transcript", "better_transcript_failed", "delete_not_proven"
KINDS = (MADE, FAILED, NOT_PROVEN)
# What the record holds of the delete of a recording the service took: the answer awaited, proven gone, or not proven.
AWAITED, PROVEN, UNPROVEN = "awaited", "proven", "not_proven"


def proof_state(sent: dict | None) -> str | None:
    """Which of the three the record of a sending holds at this moment;
    None where nothing was sent or the service took nothing."""
    if sent is None or not sent["job_id"]:
        return None
    if sent["gone"]:
        return PROVEN
    return AWAITED if sent["judged_at"] is None else UNPROVEN


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
        # The delete and its proof, each on its own thread: by the consultation's number, or by the job's name for one kept apart.
        self._proofs: dict[int | str, threading.Thread] = {}
        self._lock = threading.Lock()

    def http(self) -> upload.Http:
        return upload.Http(service.EU_HOST, self._send)

    def run(self, c, way: str) -> None:
        """Send and read, and start the delete and its proof beside Stop;
        or, for a consultation found at this stage after a restart, see
        that the delete that was owed is asked. Runs on the Stop thread,
        never raises into it (R30), and returns as soon as the transcript
        is stored: it does not wait for the delete."""
        if c.rows.upload(c.id) is not None:
            self._after_restart(c)
            return
        row = c.rows.get(c.id)
        path = folder_of(c.data_folder) / row["recording_file"] if row["recording_file"] else None
        key = self._key()
        if key is None or path is None or not path.is_file():
            c.rows.add_upload(c.id, way, FILE_NAME, 0)
            self._ended(c, way, {"request": upload.NOT_MADE},
                        {"at": "key" if key is None else "send", "detail": "no key in use" if key is None else "no recording file"},
                        lines=[], limit=0.0)
            return
        wav = path.read_bytes()
        recording_s = c.loudness.seconds if c.loudness is not None else 0.0
        limit = limit_s(recording_s)
        c.rows.add_upload(c.id, way, FILE_NAME, len(wav))
        noting = _Noting(lambda job: c.rows.note_upload_job(c.id, job["id"]))
        http = self.http()
        try:
            result = upload.run_upload(noting, http, key, wav, FILE_NAME, {"recording": FILE_NAME}, b"", int(row["sample_rate"] or 48000),
                                       clock=self._clock, sleep=self._sleep, timeout_s=limit, prove=False)
        except Exception as broke:  # noqa: BLE001 - what broke is said by its name; a job the service took is deleted beside Stop
            noted = c.rows.upload(c.id)
            self._ended(c, way, {"job": {"id": noted["job_id"]} if noted and noted["job_id"] else None,
                                 "request": upload.request_made(http.sent)},
                        {"at": "send", "detail": f"the upload broke: {type(broke).__name__}"}, lines=[], limit=limit)
            return
        if not result["upload"]["job"]:
            upload._delete_and_prove(service, http, key, None, [], result["upload"])      # no request: the record says that nothing was taken
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
        taken = bool(job.get("id"))
        # The sending's own end. Of the delete nothing is written here where the service took a job: it writes for itself.
        c.rows.end_upload(c.id, job.get("id"), up.get("seconds_to_result"), up.get("counted_s"), up.get("applied"), None, [],
                          None if taken else up.get("gone"), None if taken else up.get("proof"), reason, result=made,
                          # Where the record cannot show it, the request counts as made: the app never says that
                          # nothing left when it cannot show so (ruling 52).
                          request=up.get("request") or upload.MADE)
        if made:
            c.rows.add_warning(c.id, MADE, detail=way)
        else:
            c.rows.add_warning(c.id, FAILED, detail=reason)
        outcome = "the transcript made from it" if made else f"no transcript from it ({(failure or {}).get('at')})"
        c.audit.record("recording.sent", f"consultation {c.id}: by the {way}; {outcome}; "
                       + ("the service asked to delete it, beside Stop" if taken else "nothing was taken by the service"))
        if taken:
            self.prove(c.rows, c.audit, c.id, lines)

    # ------------------------------------------ the delete and its proof, beside Stop

    def prove(self, rows, audit, consultation_id: int, lines: list[dict] | None = None) -> bool:
        """Start the delete and its proof for one consultation on a thread
        of its own. Never two for one consultation, and none for a
        recording whose delete is judged or that the service never took.
        lines: the result's lines where they are in hand; else they are
        read from the record."""
        with self._lock:
            running = self._proofs.get(consultation_id)
            if running is not None and running.is_alive():
                return False
            if proof_state(rows.upload(consultation_id)) != AWAITED:
                return False
            thread = threading.Thread(target=self._prove, args=(rows, audit, consultation_id, lines),
                                      name=f"delete-proof-{consultation_id}", daemon=True)
            self._proofs[consultation_id] = thread
            thread.start()
        return True

    def finish_open(self, rows, audit) -> list[int]:
        """At the app's start: every recording the service took whose
        delete is neither proven nor judged not proven is taken up where
        its record stands, each on its own thread, beside the start; and
        so is every job kept apart from a consultation that was deleted
        meanwhile. Returns the consultations taken up."""
        found = [cid for cid in rows.open_proofs() if self.prove(rows, audit, cid)]
        for job_id in rows.left_jobs():
            self.prove_left(rows, audit, job_id)
        return found

    def prove_left(self, rows, audit, job_id: str, consultation_id: int | None = None) -> bool:
        """Finish the delete of a job kept apart from a deleted consultation,
        on a thread of its own. None is started where the thread of that
        consultation is still asking: it goes on, and drops the kept name
        itself when it has judged. Never two for one job."""
        with self._lock:
            for running in (self._proofs.get(consultation_id), self._proofs.get(job_id)):
                if running is not None and running.is_alive():
                    return False
            thread = threading.Thread(target=self._prove_left, args=(rows, audit, job_id), name="delete-proof-left", daemon=True)
            self._proofs[job_id] = thread
            thread.start()
        return True

    def wait(self, timeout_s: float = 30.0) -> bool:
        """Until no delete is in flight, or the time is up: for a test and
        for the bench of a browser look. The app itself never waits."""
        end = time.monotonic() + timeout_s
        with self._lock:
            threads = list(self._proofs.values())
        for thread in threads:
            thread.join(max(0.0, end - time.monotonic()))
        return not any(thread.is_alive() for thread in threads)

    def _prove(self, rows, audit, cid: int, lines: list[dict] | None) -> None:
        """The delete, the asks and their second tries, each answer written
        as it comes; then the judgement, the warning where it is not
        proven, and the line of the log. Never raises (R30): whatever
        broke, the delete is judged not proven and said."""
        up: dict = {"gone": None, "proof": None}
        job_id = None

        def note() -> None:
            # Each step to the consultation's record; and to the row kept apart, where the consultation was deleted meanwhile.
            rows.note_proof(cid, up["delete"], up["asked_again"])
            rows.note_left(job_id, up["delete"], up["asked_again"])

        try:
            noted = rows.upload(cid)
            job_id = noted["job_id"]
            up.update(job={"id": job_id}, delete=noted["delete_answer"], asked_again=list(noted["asked_again"] or []))
            if lines is None:
                # Taken up after a restart: the words of the result are the transcript's, where one was made from it.
                lines = [{"text": r["text"]} for r in rows.transcript_lines(cid) if r["n"] is not None] if noted["result_at"] else []
            key = self._key()
            if key is None:
                up["gone"], up["proof"] = False, "no key in use: the service could not be asked"
            else:
                upload._delete_and_prove(service, self.http(), key, up["job"], lines, up, self._sleep, note=note)
        except Exception as broke:  # noqa: BLE001
            up["gone"], up["proof"] = False, f"the delete broke: {type(broke).__name__}"
        try:
            # The judgement first, then the kept name: a Delete of the consultation either finds the judgement and
            # keeps nothing, or came before it, and then what it kept is dropped here.
            rows.judge_upload(cid, bool(up["gone"]), up["proof"])
            if job_id and rows.drop_left(job_id):
                self._say_left(audit, up)
            elif up["gone"]:
                audit.record("recording.deleted", f"consultation {cid}: {up['proof']}")
            else:
                # Said on the review page in the owner's words, also when the page is already open, and written to the log.
                if rows.upload(cid) is not None:
                    rows.add_warning(cid, NOT_PROVEN)
                audit.record("recording.delete_not_proven", f"consultation {cid}: {up['proof'] or 'no answer'}")
        except Exception:  # noqa: BLE001 - the tables are gone (the app is closing): the next start finds the proof open
            pass

    def _prove_left(self, rows, audit, job_id: str) -> None:
        """The same delete and the same asks for a job kept apart from a
        deleted consultation, taken up where the kept state stands. The
        words of its result went with the consultation, so only an answer
        that the job is gone proves it. Never raises (R30)."""
        up: dict = {"gone": None, "proof": None}
        try:
            kept = rows.left(job_id)
            if kept is None:
                return                                  # proven or judged meanwhile: nothing is owed
            up.update(job={"id": job_id}, delete=kept["delete"], asked_again=kept["asked_again"])
            key = self._key()
            if key is None:
                up["gone"], up["proof"] = False, "no key in use: the service could not be asked"
            else:
                upload._delete_and_prove(service, self.http(), key, up["job"], [], up, self._sleep, words_held=False,
                                         note=lambda: rows.note_left(job_id, up["delete"], up["asked_again"]))
        except Exception as broke:  # noqa: BLE001
            up["gone"], up["proof"] = False, f"the delete broke: {type(broke).__name__}"
        try:
            if rows.drop_left(job_id):
                self._say_left(audit, up)
        except Exception:  # noqa: BLE001 - the tables are gone (the app is closing): the next start finds the job kept
            pass

    @staticmethod
    def _say_left(audit, up: dict) -> None:
        """The one line of the log for a job whose consultation is deleted:
        what was found, and that the kept name is dropped. No patient, no
        consultation's number, no job's name."""
        event = "recording.left_deleted" if up["gone"] else "recording.left_not_proven"
        audit.record(event, f"{up['proof'] or 'no answer'}; the job's name is no longer kept")

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
        owed is asked beside Stop, unless the app's start has already
        taken it up, and its answer kept."""
        noted = c.rows.upload(c.id)
        if noted["result_at"] is not None or noted["failure"] is not None:
            return                                      # the upload had ended before the restart
        up: dict = {"job": {"id": noted["job_id"]} if noted["job_id"] else None}
        self._ended(c, noted["way"], up, {"at": "restart", "detail": "the app was closed while the recording was being sent"}, lines=[], limit=0.0)
