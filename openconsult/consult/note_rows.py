"""The rows of the note (spec 15.10, The record; rulings 8 and 11; R2,
R20): each draft with its stamp, its prompt hash, what the model read,
its entries with their line numbers, its citation count and whether it
was refused; the doctor's edits to entries; the approval, audited by the
caller; the refusal. Adds and reads; an entry's words are the one thing
that changes, and what stood before is kept. Nothing here talks to a
model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local

SECTIONS = ("subjective", "objective", "assessment", "plan")
ASKED_BY = ("stop", "draft", "again")


@dataclass(frozen=True)
class DraftRow:
    """What one draft writes: the stamp, the hash, the text read, the
    counts, and the entries as the citation check left them."""
    consultation_id: int
    asked_by: str
    call_id: int | None
    engine: str
    engine_version: str | None
    model_tag: str
    model_digest: str | None
    prompt_sha256: str
    transcript: str
    last_edit_id: int | None
    reasoning: str | None
    entries_total: int
    entries_cited: int
    refused: bool
    failure: str | None
    wall_ms: int
    entries: list = field(default_factory=list)   # each: section, text, turns, lines, uncited


class Notes:
    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    # ------------------------------------------------------------- drafts

    def add_draft(self, row: DraftRow) -> int:
        if row.asked_by not in ASKED_BY:
            raise ValueError(f"not a way a draft is asked for: {row.asked_by}")
        last = self._db.query_one("SELECT MAX(n) AS n FROM note_draft WHERE consultation_id = ?", (row.consultation_id,))
        n = int(last["n"] or 0) + 1 if last else 1
        cursor = self._db.execute(
            "INSERT INTO note_draft (consultation_id, n, at, asked_by, call_id, engine, engine_version, model_tag, "
            "model_digest, prompt_sha256, transcript, last_edit_id, reasoning, entries_total, entries_cited, refused, "
            "failure, wall_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row.consultation_id, n, self._now(), row.asked_by, row.call_id, row.engine, row.engine_version, row.model_tag,
             row.model_digest, row.prompt_sha256, row.transcript, row.last_edit_id, row.reasoning, row.entries_total,
             row.entries_cited, int(bool(row.refused)), row.failure, row.wall_ms))
        draft_id = int(cursor.lastrowid)
        for section in SECTIONS:
            for position, entry in enumerate(e for e in row.entries if e["section"] == section):
                self._db.execute(
                    "INSERT INTO note_entry (draft_id, section, position, model_text, text, turns, lines, uncited) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (draft_id, section, position, entry["text"], entry["text"], json.dumps(list(entry["turns"])),
                     json.dumps(list(entry["lines"])), int(bool(entry["uncited"]))))
        return draft_id

    def drafts(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM note_draft WHERE consultation_id = ? ORDER BY n", (consultation_id,))
        return [dict(r) for r in rows]

    def current_draft(self, consultation_id: int) -> dict | None:
        """The draft on the page: the latest; the earlier ones are kept (ruling 11)."""
        found = self.drafts(consultation_id)
        return found[-1] if found else None

    def draft(self, draft_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM note_draft WHERE id = ?", (draft_id,))
        return dict(found) if found else None

    # ------------------------------------------------------------ entries

    def entries(self, draft_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM note_entry WHERE draft_id = ? ORDER BY id", (draft_id,))
        return [self._entry(r) for r in rows]

    def entry(self, entry_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM note_entry WHERE id = ?", (entry_id,))
        return self._entry(found) if found else None

    @staticmethod
    def _entry(row) -> dict:
        return {**dict(row), "turns": json.loads(row["turns"]), "lines": json.loads(row["lines"])}

    def set_entry_text(self, entry_id: int, text: str) -> int:
        """The doctor's edit: the words before are kept in the edit row."""
        before = self.entry(entry_id)["text"]
        self._db.execute("UPDATE note_entry SET text = ? WHERE id = ?", (text, entry_id))
        cursor = self._db.execute("INSERT INTO note_edit (entry_id, at, text_before, text_after) VALUES (?, ?, ?, ?)",
                                  (entry_id, self._now(), before, text))
        return int(cursor.lastrowid)

    def edits(self, entry_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM note_edit WHERE entry_id = ? ORDER BY id", (entry_id,))
        return [dict(r) for r in rows]

    # ------------------------------------------------- approval and refusal

    def approve(self, consultation_id: int, draft_id: int, text: str) -> int:
        """At most one approval for a consultation: the table's UNIQUE
        refuses a second (R2)."""
        cursor = self._db.execute("INSERT INTO note_approval (consultation_id, draft_id, at, text) VALUES (?, ?, ?, ?)",
                                  (consultation_id, draft_id, self._now(), text))
        return int(cursor.lastrowid)

    def approval(self, consultation_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM note_approval WHERE consultation_id = ?", (consultation_id,))
        return dict(found) if found else None

    def approvals_of_patient(self, patient_id: int) -> list[dict]:
        """Every approved note of a patient, newest consultation first, with
        the consultation's start and the approval's time (15.11 rulings 3
        and 4; R25). A deleted consultation has no rows here."""
        rows = self._db.query(
            "SELECT a.consultation_id, c.started_at, a.at AS approved_at, a.text FROM note_approval a "
            "JOIN consultation c ON c.id = a.consultation_id WHERE c.patient_id = ? ORDER BY c.started_at DESC, c.id DESC",
            (patient_id,))
        return [dict(r) for r in rows]

    def refuse(self, consultation_id: int, draft_id: int) -> int:
        cursor = self._db.execute("INSERT INTO note_refusal (consultation_id, draft_id, at) VALUES (?, ?, ?)",
                                  (consultation_id, draft_id, self._now()))
        return int(cursor.lastrowid)

    def refusals(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM note_refusal WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [dict(r) for r in rows]
