"""The earlier approved notes of a patient (spec 15.11 rulings 3 and 4;
8.2; 8.3; R25; D23): read from note_approval as stage 6 stored it, never
a draft or a refused note, and never a deleted consultation, which has
no rows. The approved text is split into its four sections on the
blank lines, so the parse does not hang on the heading words; the
bracketed citations are stripped as the copy text strips them. The
Start screen lists them all by date; the live page's panel shows the
last three approved before the consultation started; the block of
ruling 5 reads the same three (consult/background.py)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openconsult.consult.note import SECTIONS, strip_citations

# D23: the last three.
LAST = 3


@dataclass(frozen=True)
class ApprovedNote:
    consultation_id: int
    started_at: datetime
    approved_at: datetime
    sections: dict          # section -> the entries' words, citations stripped

    def headline(self) -> str:
        """The assessment, or the first plan entry where it is empty (ruling 4)."""
        assessment = self.sections.get("assessment") or []
        if assessment:
            return "; ".join(assessment)
        plan = self.sections.get("plan") or []
        return plan[0] if plan else ""


def sections_of(text: str) -> dict:
    """The four sections of an approved text: one block for each, split
    on blank lines, the block's first line its heading and the rest its
    entries, one a line. Fewer blocks leave the later sections empty."""
    blocks = [b for b in (text or "").strip().split("\n\n") if b.strip()]
    found = {section: [] for section in SECTIONS}
    for section, block in zip(SECTIONS, blocks):
        lines = [strip_citations(line) for line in block.split("\n")[1:] if line.strip()]
        found[section] = [line for line in lines if line]
    return found


def approved_notes(notes, patient_id: int, before: datetime | None = None, except_id: int | None = None,
                   limit: int | None = None) -> list[ApprovedNote]:
    """The patient's approved notes, newest first; with before, only those
    approved before that moment (a consultation's start), never the
    consultation itself; with limit, the first so many."""
    found = []
    for row in notes.approvals_of_patient(patient_id):
        approved_at = datetime.fromisoformat(row["approved_at"])
        if row["consultation_id"] == except_id:
            continue
        if before is not None and approved_at >= before:
            continue
        found.append(ApprovedNote(row["consultation_id"], datetime.fromisoformat(row["started_at"]), approved_at,
                                  sections_of(row["text"])))
    return found[:limit] if limit is not None else found


def panel_notes(notes, patient_id: int, started_at: datetime, consultation_id: int) -> list[ApprovedNote]:
    """The last three for the live page's panel (ruling 4)."""
    return approved_notes(notes, patient_id, before=started_at, except_id=consultation_id, limit=LAST)
