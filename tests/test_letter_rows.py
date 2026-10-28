"""The rows of the referral letters (spec 15.12, The record; rulings 2
and 4; R2, R20). Made-up rows; nothing here is what a model said."""

import sqlite3
from datetime import date

import pytest

from openconsult.consult.consultations import Consultations
from openconsult.consult.letter_rows import ItemRow, LetterRow, Letters, ListRow, paragraphs_of
from openconsult.consult.note_rows import DraftRow, Notes
from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.patients.patients import Patients


def approved_consultation(db, clock, patient_id=None):
    """A final consultation with an approved made note; the approval's id."""
    cons, notes, audit = Consultations(db, clock), Notes(db, clock), Audit(db, clock)
    if patient_id is None:
        patient_id = Patients(db, audit, clock).add("Made-up", date(1990, 1, 1), "F").id
    cid = cons.start(patient_id, 15, "nemotron", "made-up", "0", "tag", "digest", 2)
    cons.set(cid, state="final")
    draft = notes.add_draft(DraftRow(cid, "stop", None, "made-up", "0", "tag", "digest", "h" * 64, "x", None, None, 1, 1, False, None, 1))
    approval = notes.approve(cid, draft, "Subjective\nmade up\n\nObjective\n\nAssessment\nmade up\n\nPlan\nmade up\n")
    return cid, approval, patient_id


def letter_row(cid, item_id, body="First made paragraph.\n\nSecond made paragraph.", refused=False, failure=None):
    return LetterRow(cid, item_id, None, "made-up", "0", "tag", "digest", "p" * 64, "[1] Subjective\n[2] made up", "made reasoning",
                     [{"text": "First made paragraph.", "note_lines": [2]}], body, {"paragraphs": []}, 2, 2, 0, 0, refused, failure, 7)


def test_R20_the_letter_row_keeps_the_stamp_the_prompt_hash_and_the_note_lines_sent(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    letters = Letters(db, clock)
    cid, approval, _ = approved_consultation(db, clock)
    assert letters.list_of(cid) is None and letters.items(cid) == []
    list_id = letters.add_list(ListRow(cid, approval, None, "[1] Subjective\n[2] made up", "made reasoning", None, 9))
    listed = letters.list_of(cid)
    assert (listed["id"], listed["approval_id"], listed["note_lines"], listed["reasoning"], listed["failure"], listed["wall_ms"]) == \
        (list_id, approval, "[1] Subjective\n[2] made up", "made reasoning", None, 9)
    with pytest.raises(sqlite3.DatabaseError):
        letters.add_list(ListRow(cid, approval, None, "x", None, None, 1))               # one list per approved note
    # The items: the list's in position, then the named ones in the order made.
    named = letters.add_item(ItemRow(cid, None, "named", "Made-up specialty", "Physician", None, None, [], None, 0))
    second = letters.add_item(ItemRow(cid, list_id, "suggested", "Suggested specialty", "Surgeon", "a made reason", "routine", [5, 2], None, 1))
    first = letters.add_item(ItemRow(cid, list_id, "stated", "Stated specialty", "Physician", "a made reason", "urgent", [9], None, 0))
    assert [(i["id"], i["kind"], i["note_lines"], i["position"]) for i in letters.items(cid)] == \
        [(first, "stated", [9], 0), (second, "suggested", [5, 2], 1), (named, "named", [], 0)]
    assert letters.item(first)["title"] == "Physician" and letters.item(999) is None
    with pytest.raises(ValueError):
        letters.add_item(ItemRow(cid, list_id, "guessed", "x", "y", None, None, [], None, 0))
    with pytest.raises(ValueError):
        letters.add_item(ItemRow(cid, list_id, "stated", "x", "y", None, "soon", [], None, 0))
    assert letters.set_title(first, "ENT Surgeon") == "Physician" and letters.item(first)["title"] == "ENT Surgeon"
    # The letters: the stamp, the hash, the note lines sent, both bodies, the counts; n within the consultation.
    assert letters.latest_letter(first) is None
    one = letters.add_letter(letter_row(cid, first))
    row = letters.letter(one)
    assert (row["n"], row["engine"], row["engine_version"], row["model_tag"], row["model_digest"], row["prompt_sha256"][:3]) == \
        (1, "made-up", "0", "tag", "digest", "ppp")
    assert row["note_lines"] == "[1] Subjective\n[2] made up" and row["model_body"] == [{"text": "First made paragraph.", "note_lines": [2]}]
    assert row["paragraphs"] == ["First made paragraph.", "Second made paragraph."] and row["check_detail"] == {"paragraphs": []}
    assert (row["sentences_total"], row["sentences_grounded"], row["placeholders"], row["expectations_dropped"], row["refused"],
            row["failure"], row["wall_ms"], row["doctor_refused_at"]) == (2, 2, 0, 0, 0, None, 7, None)
    two = letters.add_letter(letter_row(cid, first, body=None, failure="too_slow: made up"))
    assert letters.letter(two)["n"] == 2 and letters.letter(two)["paragraphs"] == [] and letters.latest_letter(first)["id"] == two
    assert [l["id"] for l in letters.letters_of_item(first)] == [one, two] and [l["n"] for l in letters.letters(cid)] == [1, 2]
    assert letters.letters_of_item(second) == [] and letters.letter(999) is None
    # A paragraph edit keeps what stood before; the body changes in place.
    edit = letters.set_paragraph(one, 1, "Second paragraph, edited.")
    assert letters.letter(one)["paragraphs"] == ["First made paragraph.", "Second paragraph, edited."]
    assert [(e["id"], e["paragraph"], e["text_before"], e["text_after"]) for e in letters.edits(one)] == \
        [(edit, 1, "Second made paragraph.", "Second paragraph, edited.")]
    with pytest.raises(IndexError):
        letters.set_paragraph(one, 2, "x")
    assert paragraphs_of("a\n\n\n\nb") == ["a", "b"] and paragraphs_of(None) == []
    # The approval, once (R2); the doctor's refusal marks the letter.
    letters.approve(one, "Dear Consultant ENT Surgeon,\n\nmade up")
    assert letters.approval(one)["text"].startswith("Dear Consultant") and letters.approval(two) is None
    with pytest.raises(sqlite3.DatabaseError):
        letters.approve(one, "again")
    letters.refuse(two)
    assert letters.letter(two)["doctor_refused_at"] == clock().isoformat(timespec="seconds")
    db.close()
