"""One delete that really deletes (spec 15.11 ruling 8; D44; V1_LESSONS
10.3, 10.4, 10.5): the rows of one consultation in one transaction, the
recording file after, and one audit line with the patient's number, the
consultation's date and the counts, never a word of the note or the
transcript. No undo, no void state, no purge step. A consultation that
is not final is refused (Stop first), and so is one that is gone, so a
second delete is refused and never repeated. A crash between the rows
and the file leaves a file with no row, which the start-up sweep of
orphans reports. A patient is deleted only when no consultation is left."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openconsult.consult.recording import folder_of


class NotFinal(Exception):
    """Stop first: a live or stopping consultation is never deleted."""


class NoSuchConsultation(Exception):
    pass


class ConsultationsRemain(Exception):
    """A patient is deleted only when no consultation is left."""


# The rows of a consultation, children first, each with its count's name.
ROW_DELETIONS = (
    ("edits", "DELETE FROM note_edit WHERE entry_id IN (SELECT e.id FROM note_entry e JOIN note_draft d ON d.id = e.draft_id "
              "WHERE d.consultation_id = ?)"),
    ("entries", "DELETE FROM note_entry WHERE draft_id IN (SELECT id FROM note_draft WHERE consultation_id = ?)"),
    ("approvals", "DELETE FROM note_approval WHERE consultation_id = ?"),
    ("refusals", "DELETE FROM note_refusal WHERE consultation_id = ?"),
    ("drafts", "DELETE FROM note_draft WHERE consultation_id = ?"),
    ("transcript_edits", "DELETE FROM transcript_edit WHERE consultation_id = ?"),
    ("lines", "DELETE FROM transcript_line WHERE consultation_id = ?"),
    ("live_lines", "DELETE FROM live_line WHERE consultation_id = ?"),
    ("warnings", "DELETE FROM warning WHERE consultation_id = ?"),
    ("passes", "DELETE FROM cds_pass WHERE consultation_id = ?"),
    ("model_calls", "DELETE FROM model_call WHERE consultation_id = ?"),
    ("consultation", "DELETE FROM consultation WHERE id = ?"),
)


@dataclass(frozen=True)
class Deleted:
    consultation_id: int
    patient_id: int
    date: str
    counts: dict
    file_name: str | None
    file_bytes: int

    def line(self) -> str:
        """The audit line: numbers only, never words."""
        parts = ", ".join(f"{self.counts[name]} {name.replace('_', ' ')}" for name, _ in ROW_DELETIONS if name != "consultation")
        file_part = f"1 recording file, {self.file_bytes} bytes" if self.file_name else "no recording file"
        return f"patient {self.patient_id}, consultation {self.consultation_id} of {self.date}: {parts}, {file_part}"


def delete_rows(con, consultation_id: int) -> dict:
    """Every row of the consultation, children first, on one connection
    inside the caller's transaction; the counts by name."""
    counts = {}
    for name, sql in ROW_DELETIONS:
        counts[name] = con.execute(sql, (consultation_id,)).rowcount
    return counts


def delete_consultation(p, consultation_id: int) -> Deleted:
    """The one function. Rows first, in one transaction; then the file;
    then the audit line; the object dropped from the running table."""
    row = p.consultations.get(consultation_id)
    if row is None:
        raise NoSuchConsultation(consultation_id)
    if row["state"] != "final":
        raise NotFinal(consultation_id)
    with p.db.transaction() as con:
        counts = delete_rows(con, consultation_id)
    file_name, file_bytes = row["recording_file"], 0
    if file_name:
        path = folder_of(p.settings.data_folder) / file_name
        if path.is_file():
            file_bytes = path.stat().st_size
            path.unlink()
        else:
            file_name = None
    p.running.pop(consultation_id, None)
    date = datetime.fromisoformat(row["started_at"]).date().isoformat()
    deleted = Deleted(consultation_id, row["patient_id"], date, counts, file_name, file_bytes)
    p.audit.record("consultation.deleted", deleted.line())
    return deleted


def delete_patient(p, patient_id: int) -> None:
    """Allowed only when no consultation is left (ruling 8); the changes
    and the row go in one transaction; the audit line keeps the number."""
    if p.patients.get(patient_id) is None:
        raise NoSuchConsultation(patient_id)
    if p.consultations.of_patient(patient_id):
        raise ConsultationsRemain(patient_id)
    with p.db.transaction() as con:
        con.execute("DELETE FROM patient_change WHERE patient_id = ?", (patient_id,))
        con.execute("DELETE FROM patient WHERE id = ?", (patient_id,))
    p.audit.record("patient.deleted", f"patient {patient_id}")
