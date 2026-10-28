"""The rows of the referral letters (spec 15.12, The record; rulings 1, 2,
4 and 11; R2, R5, R20): the list made once from an approved note with
the note lines it sent, its items in three kinds, each letter with its
stamp, the note lines sent, both bodies, the check's detail and its
counts, the doctor's paragraph edits with what stood before, and the
approval, once per letter. Adds and reads; the title of an item and a
paragraph of a draft letter are the two things that change, and what
stood before is kept. Nothing here talks to a model."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass

from openconsult.db import Database
from openconsult.patients.audit import Clock, now_local

KINDS = ("stated", "suggested", "named")
URGENCIES = ("urgent", "routine")
PARAGRAPH_GAP = "\n\n"


@dataclass(frozen=True)
class ListRow:
    consultation_id: int
    approval_id: int
    call_id: int | None
    note_lines: str          # the numbered note as sent, the named part of ruling 11
    reasoning: str | None
    failure: str | None
    wall_ms: int


@dataclass(frozen=True)
class ItemRow:
    consultation_id: int
    list_id: int | None      # None for a named item
    kind: str
    specialty: str
    title: str
    reason: str | None
    urgency: str | None
    note_lines: list         # the note line numbers cited
    call_id: int | None
    position: int


@dataclass(frozen=True)
class LetterRow:
    consultation_id: int
    item_id: int
    call_id: int | None
    engine: str
    engine_version: str | None
    model_tag: str
    model_digest: str | None
    prompt_sha256: str
    note_lines: str          # the numbered, masked note as sent
    reasoning: str | None
    model_body: list | None  # the paragraphs as the model gave them
    body: str | None         # as the check left it, paragraphs joined by one blank line
    check_detail: dict | None
    sentences_total: int
    sentences_grounded: int
    placeholders: int
    expectations_dropped: int
    refused: bool
    failure: str | None
    wall_ms: int


def paragraphs_of(body: str | None) -> list[str]:
    return [p for p in (body or "").split(PARAGRAPH_GAP) if p.strip()]


class Letters:
    def __init__(self, db: Database, clock: Clock = now_local):
        self._db = db
        self._clock = clock
        # Two openings of the review page at once make one list call (ruling 2).
        self.list_lock = threading.Lock()

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    # ------------------------------------------------------------ the list

    def add_list(self, row: ListRow) -> int:
        """One list per approved note: the table's UNIQUE refuses a second."""
        cursor = self._db.execute(
            "INSERT INTO referral_list (consultation_id, approval_id, at, call_id, note_lines, reasoning, failure, wall_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (row.consultation_id, row.approval_id, self._now(), row.call_id, row.note_lines, row.reasoning, row.failure,
             row.wall_ms))
        return int(cursor.lastrowid)

    def list_of(self, consultation_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM referral_list WHERE consultation_id = ? ORDER BY id DESC LIMIT 1",
                                   (consultation_id,))
        return dict(found) if found else None

    def drop_failed_list(self, list_id: int) -> None:
        """A list whose call failed holds no item and no word of a reply;
        it gives way to the call made again (R30). A list that stands
        with items is never dropped."""
        self._db.execute("DELETE FROM referral_list WHERE id = ? AND failure IS NOT NULL", (list_id,))

    # ----------------------------------------------------------- the items

    def add_item(self, row: ItemRow) -> int:
        if row.kind not in KINDS:
            raise ValueError(f"not a kind of item: {row.kind}")
        if row.urgency is not None and row.urgency not in URGENCIES:
            raise ValueError(f"not an urgency: {row.urgency}")
        cursor = self._db.execute(
            "INSERT INTO referral_item (consultation_id, list_id, kind, specialty, title, reason, urgency, note_lines, "
            "call_id, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row.consultation_id, row.list_id, row.kind, row.specialty, row.title, row.reason, row.urgency,
             json.dumps([int(n) for n in row.note_lines]), row.call_id, row.position, self._now()))
        return int(cursor.lastrowid)

    def items(self, consultation_id: int) -> list[dict]:
        """The list's items in their position, then the named ones in the
        order they were made."""
        rows = self._db.query("SELECT * FROM referral_item WHERE consultation_id = ? "
                              "ORDER BY (list_id IS NULL), position, id", (consultation_id,))
        return [self._item(r) for r in rows]

    def item(self, item_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM referral_item WHERE id = ?", (item_id,))
        return self._item(found) if found else None

    @staticmethod
    def _item(row) -> dict:
        return {**dict(row), "note_lines": json.loads(row["note_lines"])}

    def set_title(self, item_id: int, title: str) -> str:
        """The doctor's correction of the consultant's title; gives back
        what stood before, for the caller's audit line."""
        before = self.item(item_id)["title"]
        self._db.execute("UPDATE referral_item SET title = ? WHERE id = ?", (title, item_id))
        return before

    # --------------------------------------------------------- the letters

    def add_letter(self, row: LetterRow) -> int:
        last = self._db.query_one("SELECT MAX(n) AS n FROM letter WHERE consultation_id = ?", (row.consultation_id,))
        n = int(last["n"] or 0) + 1 if last else 1
        cursor = self._db.execute(
            "INSERT INTO letter (consultation_id, item_id, n, at, call_id, engine, engine_version, model_tag, model_digest, "
            "prompt_sha256, note_lines, reasoning, model_body, body, check_detail, sentences_total, sentences_grounded, "
            "placeholders, expectations_dropped, refused, failure, wall_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row.consultation_id, row.item_id, n, self._now(), row.call_id, row.engine, row.engine_version, row.model_tag,
             row.model_digest, row.prompt_sha256, row.note_lines, row.reasoning,
             json.dumps(row.model_body, ensure_ascii=False) if row.model_body is not None else None, row.body,
             json.dumps(row.check_detail, ensure_ascii=False) if row.check_detail is not None else None,
             row.sentences_total, row.sentences_grounded, row.placeholders, row.expectations_dropped,
             int(bool(row.refused)), row.failure, row.wall_ms))
        return int(cursor.lastrowid)

    def letter(self, letter_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM letter WHERE id = ?", (letter_id,))
        return self._letter(found) if found else None

    def letters(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM letter WHERE consultation_id = ? ORDER BY n", (consultation_id,))
        return [self._letter(r) for r in rows]

    def letters_of_item(self, item_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM letter WHERE item_id = ? ORDER BY n", (item_id,))
        return [self._letter(r) for r in rows]

    def latest_letter(self, item_id: int) -> dict | None:
        """The letter an item has: its latest; the earlier ones are kept."""
        found = self.letters_of_item(item_id)
        return found[-1] if found else None

    @staticmethod
    def _letter(row) -> dict:
        return {**dict(row), "model_body": json.loads(row["model_body"]) if row["model_body"] else None,
                "check_detail": json.loads(row["check_detail"]) if row["check_detail"] else None,
                "paragraphs": paragraphs_of(row["body"])}

    def set_paragraph(self, letter_id: int, paragraph: int, text: str) -> int:
        """The doctor's edit of one paragraph of a draft; the words before
        are kept in the edit row."""
        found = self.letter(letter_id)
        paragraphs = found["paragraphs"]
        if not 0 <= paragraph < len(paragraphs):
            raise IndexError(f"letter {letter_id} has no paragraph {paragraph}")
        before = paragraphs[paragraph]
        paragraphs[paragraph] = text
        self._db.execute("UPDATE letter SET body = ? WHERE id = ?", (PARAGRAPH_GAP.join(paragraphs), letter_id))
        cursor = self._db.execute(
            "INSERT INTO letter_edit (letter_id, paragraph, at, text_before, text_after) VALUES (?, ?, ?, ?, ?)",
            (letter_id, paragraph, self._now(), before, text))
        return int(cursor.lastrowid)

    def edits(self, letter_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM letter_edit WHERE letter_id = ? ORDER BY id", (letter_id,))
        return [dict(r) for r in rows]

    # ------------------------------------------------- approval and refusal

    def approve(self, letter_id: int, text: str) -> int:
        """At most one approval for a letter: the table's UNIQUE refuses a second (R2)."""
        cursor = self._db.execute("INSERT INTO letter_approval (letter_id, at, text) VALUES (?, ?, ?)",
                                  (letter_id, self._now(), text))
        return int(cursor.lastrowid)

    def approval(self, letter_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM letter_approval WHERE letter_id = ?", (letter_id,))
        return dict(found) if found else None

    def refuse(self, letter_id: int) -> None:
        self._db.execute("UPDATE letter SET doctor_refused_at = ? WHERE id = ?", (self._now(), letter_id))
