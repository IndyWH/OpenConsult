"""The rows of a consultation (spec 15.10, The record; 6.3): the
consultation itself with its stamps (R20), the live lines as shown, the
lines at Stop as the choice gave them and as they stand after the label
check, each pass as settled, and every warning the gate raised; since
6b the doctor's edits to words and labels, each kept with what stood
before (rulings 7 and 11). Adds and reads; the few columns that change
as a consultation moves on are set by name. Nothing here reads a setting
or talks to a model."""

from __future__ import annotations

import json
from dataclasses import asdict

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local
from openconsult.speech.lines import Line

STATES = ("live", "stopping", "final")
STOP_STAGES = ("who_spoke", "label_check", "checks", "gate", "note")
EDIT_KINDS = ("words", "label", "undo", "swap")
SWAPPED = {"doctor": "patient", "patient": "doctor"}
LABELS = ("doctor", "patient", "unsure")
SETTABLE = ("stopped_at", "final_at", "speech_stamp", "echo_cancellation", "noise_suppression", "auto_gain",
            "sample_rate", "doctor_speaker", "recording_file", "loudness", "stop_raw", "state", "stop_stage",
            "speech_failure", "recording_format", "conversion_failure", "audio_deleted_at")
FORMATS = ("wav", "opus")


class Consultations:
    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    # ------------------------------------------------------ the consultation

    def start(self, patient_id: int, intended_minutes: int, speech_choice: str, engine: str,
              engine_version: str | None, model_tag: str, model_digest: str | None, speakers_given: int,
              earlier_notes_shown: bool | None = None, earlier_notes: list[int] | None = None) -> int:
        """The row at Start. The patient's three details are copied as they
        stand at this moment, so the consultation keeps what the doctor saw
        and the model read whatever is corrected later (15.11 ruling 2;
        R11; R17). earlier_notes_shown is the switch of ruling 3: None where
        no switch was offered; earlier_notes the numbers listed at Start."""
        patient = self._db.query_one("SELECT name, date_of_birth, sex FROM patient WHERE id = ?", (patient_id,))
        if patient is None:
            raise ValueError(f"no patient {patient_id}")
        cursor = self._db.execute(
            "INSERT INTO consultation (patient_id, started_at, intended_minutes, speech_choice, engine, "
            "engine_version, model_tag, model_digest, speakers_given, state, patient_name, patient_date_of_birth, "
            "patient_sex, earlier_notes_shown, earlier_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'live', ?, ?, ?, ?, ?)",
            (patient_id, self._now(), int(intended_minutes), speech_choice, engine, engine_version, model_tag,
             model_digest, int(speakers_given), patient["name"], patient["date_of_birth"], patient["sex"],
             None if earlier_notes_shown is None else int(bool(earlier_notes_shown)),
             json.dumps(list(earlier_notes or []))))
        return int(cursor.lastrowid)

    def get(self, consultation_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM consultation WHERE id = ?", (consultation_id,))
        return dict(found) if found else None

    def set(self, consultation_id: int, **columns) -> None:
        for name in columns:
            if name not in SETTABLE:
                raise KeyError(f"not a column that is set: {name}")
        if "state" in columns and columns["state"] not in STATES:
            raise ValueError(f"not a state: {columns['state']}")
        if "recording_format" in columns and columns["recording_format"] not in FORMATS:
            raise ValueError(f"not a format: {columns['recording_format']}")
        assignment = ", ".join(f"{name} = ?" for name in columns)
        self._db.execute(f"UPDATE consultation SET {assignment} WHERE id = ?", (*columns.values(), consultation_id))

    def last_intended(self) -> int | None:
        """The intended time of the last consultation started, for the list
        that opens on the time used last (D38)."""
        found = self._db.query_one("SELECT intended_minutes FROM consultation ORDER BY id DESC LIMIT 1")
        return int(found["intended_minutes"]) if found else None

    def all_rows(self) -> list[dict]:
        rows = self._db.query("SELECT * FROM consultation ORDER BY id")
        return [dict(r) for r in rows]

    def of_patient(self, patient_id: int) -> list[dict]:
        """Every consultation of a patient, newest first (15.11 ruling 2)."""
        rows = self._db.query("SELECT * FROM consultation WHERE patient_id = ? ORDER BY id DESC", (patient_id,))
        return [dict(r) for r in rows]

    def in_state(self, state: str) -> list[dict]:
        rows = self._db.query("SELECT c.*, p.name AS patient_name FROM consultation c JOIN patient p ON p.id = c.patient_id "
                              "WHERE c.state = ? ORDER BY c.id", (state,))
        return [dict(r) for r in rows]

    # -------------------------------------------------------- the live lines

    def add_live_line(self, consultation_id: int, n: int, line: Line, refused: bool, shown_at_s: float) -> None:
        self._db.execute(
            "INSERT INTO live_line (consultation_id, n, line_id, speaker, start_s, end_s, text, confidence, refused, "
            "shown_at_s) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (consultation_id, n, line.id, line.speaker, line.start, line.end, line.text, line.confidence,
             1 if refused else 0, shown_at_s))

    def live_lines(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM live_line WHERE consultation_id = ? ORDER BY n", (consultation_id,))
        return [dict(r) for r in rows]

    # --------------------------------------------------- the lines at Stop

    def add_transcript_lines(self, consultation_id: int, rows: list[dict]) -> None:
        """Each row: n, line_id, start_s, end_s, text, confidence, raw_speaker,
        label, changed_by_check, revised_by_service, unsure, refused."""
        for row in rows:
            if row["label"] not in LABELS:
                raise ValueError(f"not a label: {row['label']}")
            self._db.execute(
                "INSERT INTO transcript_line (consultation_id, n, line_id, start_s, end_s, text, confidence, raw_speaker, "
                "label, changed_by_check, revised_by_service, unsure, refused) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (consultation_id, row.get("n"), row.get("line_id"), row["start_s"], row["end_s"], row["text"],
                 row.get("confidence"), row.get("raw_speaker"), row["label"], int(bool(row.get("changed_by_check"))),
                 int(bool(row.get("revised_by_service"))), int(bool(row.get("unsure"))), int(bool(row.get("refused")))))

    def transcript_lines(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM transcript_line WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [dict(r) for r in rows]

    def set_labels(self, consultation_id: int, labels: dict[int, dict]) -> None:
        """After the label check: for each line number, its label, whether
        the check changed it, and whether it is unsure. The words are never
        touched here: only these three columns are set."""
        for n, row in labels.items():
            if row["label"] not in LABELS:
                raise ValueError(f"not a label: {row['label']}")
            self._db.execute(
                "UPDATE transcript_line SET label = ?, changed_by_check = ?, unsure = ? WHERE consultation_id = ? AND n = ?",
                (row["label"], int(bool(row.get("changed_by_check"))), int(bool(row.get("unsure"))), consultation_id, n))

    # ------------------------------------------------- the doctor's edits (6b)

    def add_transcript_edit(self, consultation_id: int, kind: str, line_n: int | None, before: str | None,
                            after: str | None) -> int:
        if kind not in EDIT_KINDS:
            raise ValueError(f"not a kind of edit: {kind}")
        cursor = self._db.execute(
            "INSERT INTO transcript_edit (consultation_id, at, kind, line_n, before, after) VALUES (?, ?, ?, ?, ?, ?)",
            (consultation_id, self._now(), kind, line_n, before, after))
        return int(cursor.lastrowid)

    def transcript_edits(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM transcript_edit WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [dict(r) for r in rows]

    def last_edit_id(self, consultation_id: int) -> int | None:
        found = self._db.query_one("SELECT MAX(id) AS last FROM transcript_edit WHERE consultation_id = ?", (consultation_id,))
        return int(found["last"]) if found and found["last"] is not None else None

    def line(self, consultation_id: int, n: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM transcript_line WHERE consultation_id = ? AND n = ?", (consultation_id, n))
        return dict(found) if found else None

    def set_line_words(self, consultation_id: int, n: int, text: str) -> int:
        """The doctor's edit of a line's words: the words before are kept
        in the edit row; the line's own text changes (the plan, CHOICE)."""
        before = self.line(consultation_id, n)["text"]
        self._db.execute("UPDATE transcript_line SET text = ? WHERE consultation_id = ? AND n = ?", (text, consultation_id, n))
        return self.add_transcript_edit(consultation_id, "words", n, before, text)

    def set_line_label(self, consultation_id: int, n: int, label: str, kind: str = "label") -> int:
        """The doctor sets a line's label, or undoes the check's change
        (kind undo): the mark of the check is cleared, the line is marked
        set by the doctor, and unsure follows the label."""
        if label not in LABELS:
            raise ValueError(f"not a label: {label}")
        before = self.line(consultation_id, n)["label"]
        self._db.execute("UPDATE transcript_line SET label = ?, changed_by_check = 0, unsure = ?, set_by_doctor = 1 "
                         "WHERE consultation_id = ? AND n = ?", (label, int(label == "unsure"), consultation_id, n))
        return self.add_transcript_edit(consultation_id, kind, n, before, label)

    def swap_labels(self, consultation_id: int) -> int:
        """v1's Swap: every doctor line becomes patient and every patient
        line doctor; unsure lines stay. One edit row for the whole swap."""
        for row in self.transcript_lines(consultation_id):
            if row["n"] is not None and row["label"] in SWAPPED:
                self._db.execute("UPDATE transcript_line SET label = ?, set_by_doctor = 1 WHERE id = ?",
                                 (SWAPPED[row["label"]], row["id"]))
        return self.add_transcript_edit(consultation_id, "swap", None, None, None)

    def waiting_for_review(self) -> list[dict]:
        """Each final consultation with no approved note, once, newest
        first (R15: the home page's list)."""
        rows = self._db.query(
            "SELECT c.id, c.started_at, p.name AS patient_name FROM consultation c JOIN patient p ON p.id = c.patient_id "
            "WHERE c.state = 'final' AND NOT EXISTS (SELECT 1 FROM note_approval a WHERE a.consultation_id = c.id) "
            "ORDER BY c.id DESC")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ the passes

    def add_pass(self, consultation_id: int, n: int, transcript: str, alarm_call_id: int | None,
                 assessment_call_id: int | None, result: dict, shown: bool) -> int:
        cursor = self._db.execute(
            "INSERT INTO cds_pass (consultation_id, n, at, transcript, alarm_call_id, assessment_call_id, result, shown) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (consultation_id, n, self._clock().isoformat(timespec="milliseconds"), transcript, alarm_call_id,
             assessment_call_id, json.dumps(result, ensure_ascii=False), 1 if shown else 0))
        return int(cursor.lastrowid)

    def passes(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM cds_pass WHERE consultation_id = ? ORDER BY n", (consultation_id,))
        return [{**dict(r), "result": json.loads(r["result"])} for r in rows]

    # ---------------------------------------------------------- the warnings

    def add_warning(self, consultation_id: int, kind: str, start_s: float | None = None, end_s: float | None = None,
                    line_n: int | None = None, detail: str | None = None) -> None:
        self._db.execute(
            "INSERT INTO warning (consultation_id, kind, start_s, end_s, line_n, detail) VALUES (?, ?, ?, ?, ?, ?)",
            (consultation_id, kind, start_s, end_s, line_n, detail))

    def warnings(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM warning WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [dict(r) for r in rows]

    def model_calls(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM model_call WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [dict(r) for r in rows]


def line_as_row(line: Line, n: int | None, label: str, refused: bool = False, unsure: bool = False,
                revised: bool = False) -> dict:
    """A line of the door as a transcript row, its raw speaker kept."""
    return {"n": n, "line_id": line.id, "start_s": line.start, "end_s": line.end, "text": line.text,
            "confidence": line.confidence, "raw_speaker": line.speaker, "label": label, "changed_by_check": False,
            "revised_by_service": revised, "unsure": unsure, "refused": refused}


def row_as_line(row: dict) -> Line:
    return Line(row.get("raw_speaker", row.get("speaker")), float(row["start_s"]), float(row["end_s"]), row["text"],
                row.get("confidence"), row.get("line_id"))


def lines_json(lines) -> str:
    return json.dumps([asdict(line) for line in lines], ensure_ascii=False)
