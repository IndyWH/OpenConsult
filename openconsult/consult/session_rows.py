"""The rows of run 9b (spec 15.13, the details of the run: The record;
rulings 29 and 33): the speech sessions of a consultation whose
connection was lost, and the recording sent after Stop. A part of the
consultation's rows (consultations.py), kept apart for its size.

A consultation whose one session was never lost has no session row:
every line of it is of session 1. The rows begin when a session is
lost: the session that was lost, then each later one as it opens. Each
holds the second of the recording at which it opened and was lost, why,
and its own answer to which speaker was you, because a service names
its speakers afresh in every session.

The recording sent after Stop has one row for a consultation: when it
was sent and by which of the two ways, the job's name at the service,
when the result came, the delete's answer and each answer when the job
was asked for again. Never a key."""

from __future__ import annotations

import json

WAYS = ("tick", "press")
REQUESTS = ("not_made", "never_connected", "made")


class SessionRows:
    """Mixed into Consultations, which gives _db and _now."""

    # ------------------------------------------------------ the speech sessions

    def add_session(self, consultation_id: int, n: int, opened_at_s: float) -> None:
        self._db.execute("INSERT OR IGNORE INTO speech_session (consultation_id, n, opened_at_s) VALUES (?, ?, ?)",
                         (consultation_id, int(n), float(opened_at_s)))

    def lose_session(self, consultation_id: int, n: int, lost_at_s: float, reason: str) -> None:
        self._db.execute("UPDATE speech_session SET lost_at_s = ?, reason = ? WHERE consultation_id = ? AND n = ? AND lost_at_s IS NULL",
                         (float(lost_at_s), reason, consultation_id, int(n)))

    def answer_session(self, consultation_id: int, n: int, doctor_speaker: str) -> None:
        self._db.execute("UPDATE speech_session SET doctor_speaker = ? WHERE consultation_id = ? AND n = ?",
                         (doctor_speaker, consultation_id, int(n)))

    def sessions(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM speech_session WHERE consultation_id = ? ORDER BY n", (consultation_id,))
        return [dict(r) for r in rows]

    # ------------------------------------------- the recording sent after Stop

    def add_upload(self, consultation_id: int, way: str, file_name: str, size: int) -> int:
        if way not in WAYS:
            raise ValueError(f"not a way the recording is sent: {way}")
        cursor = self._db.execute("INSERT INTO recording_upload (consultation_id, way, sent_at, file_name, bytes) VALUES (?, ?, ?, ?, ?)",
                                  (consultation_id, way, self._now(), file_name, int(size)))
        return int(cursor.lastrowid)

    def note_upload_job(self, consultation_id: int, job_id: str) -> None:
        """The job's name at the service, written the moment the service
        takes the recording, so that a delete can be asked whatever follows."""
        self._db.execute("UPDATE recording_upload SET job_id = ? WHERE consultation_id = ?", (job_id, consultation_id))

    def replace_transcript_lines(self, consultation_id: int, rows: list[dict]) -> None:
        """The final transcript made anew from a recording sent whole: the
        lines at Stop give way to the service's, in one transaction. The
        live lines are another table and stay as what was heard live."""
        with self._db.transaction() as con:
            con.execute("DELETE FROM transcript_line WHERE consultation_id = ?", (consultation_id,))
            for row in rows:
                con.execute(
                    "INSERT INTO transcript_line (consultation_id, n, line_id, start_s, end_s, text, confidence, raw_speaker, "
                    "label, changed_by_check, revised_by_service, unsure, refused, session) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 0, ?)",
                    (consultation_id, row["n"], row.get("line_id"), row["start_s"], row["end_s"], row["text"], row.get("confidence"),
                     row.get("raw_speaker"), row["label"], int(bool(row.get("unsure"))), int(row.get("session") or 1)))

    def end_upload(self, consultation_id: int, job_id: str | None, seconds_to_result: float | None, counted_s: float | None,
                   applied: dict | None, delete_answer: dict | None, asked_again: list, gone: bool | None, proof: str | None,
                   failure: str | None, result: bool, request: str = "made") -> None:
        """What came of it, written once: the result's moment when one came,
        the delete and its proof, the failure in plain words if any; and
        request, what the record can show of the request that carried the
        recording: not_made, never_connected or made (15.13, ruling 52)."""
        if request not in REQUESTS:
            raise ValueError(f"not what a request can be: {request}")
        self._db.execute(
            "UPDATE recording_upload SET job_id = ?, result_at = ?, seconds_to_result = ?, counted_s = ?, applied = ?, "
            "failure = ?, request = ? WHERE consultation_id = ?",
            (job_id, self._now() if result else None, seconds_to_result, counted_s,
             json.dumps(applied, ensure_ascii=False) if applied is not None else None, failure, request, consultation_id))
        # The delete and its proof are written here only where they are given: since the ruling of 18 Nov 2026 they
        # run beside Stop and write for themselves, and this end of the sending must not take away what they wrote.
        if delete_answer is not None or asked_again:
            self.note_proof(consultation_id, delete_answer, asked_again)
        if gone is not None or proof is not None:
            self.judge_upload(consultation_id, gone, proof)

    def note_proof(self, consultation_id: int, delete_answer: dict | None, asked_again: list) -> None:
        """The delete's answer and every try of the asks so far, in order,
        written as they come: an app closed in their middle takes the
        proof up from here at its next start."""
        self._db.execute("UPDATE recording_upload SET delete_answer = ?, asked_again = ? WHERE consultation_id = ?",
                         (json.dumps(delete_answer, ensure_ascii=False) if delete_answer is not None else None,
                          json.dumps(asked_again, ensure_ascii=False), consultation_id))

    def judge_upload(self, consultation_id: int, gone: bool | None, proof: str | None) -> None:
        """The proof judged: proven gone, or not proven after its full
        tries, with the moment. A recording that the service took and
        that holds no such moment is one whose answer is still awaited."""
        self._db.execute("UPDATE recording_upload SET gone = ?, proof = ?, judged_at = ? WHERE consultation_id = ?",
                         (None if gone is None else int(bool(gone)), proof, self._now() if gone is not None else None, consultation_id))

    def open_proofs(self) -> list[int]:
        """The consultations whose recording the service took and whose
        delete is neither proven nor judged not proven: found at start."""
        return [r["consultation_id"] for r in self._db.query(
            "SELECT consultation_id FROM recording_upload WHERE job_id IS NOT NULL AND judged_at IS NULL ORDER BY consultation_id")]

    def upload(self, consultation_id: int) -> dict | None:
        row = self._db.query_one("SELECT * FROM recording_upload WHERE consultation_id = ?", (consultation_id,))
        if row is None:
            return None
        found = dict(row)
        for name in ("applied", "delete_answer", "asked_again"):
            found[name] = json.loads(found[name]) if found[name] else None
        return found
