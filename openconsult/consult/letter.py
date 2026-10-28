"""One referral letter (spec 15.12, rulings 1, 3 and 4; R2, R5, R11,
R20, R30; D24): the call on the approved note for the item's specialty,
the check, and the row with its stamp, the note lines sent, both bodies,
the check's detail (the allergy sentences dropped counted there) and
the four counts. The salutation, the Re line and
the sign-off are written by code from the record, never by the model:
Dear Consultant and the item's title, the patient's name, date of birth
and sex as the consultation ran with them (15.11 ruling 2), and the one
user's title and name. A failed call keeps its row, said plainly, and
nothing is asked a second time by itself (10.4)."""

from __future__ import annotations

import hashlib
from datetime import date

from openconsult import words
from openconsult.consult import letter_check, referral_note
from openconsult.consult.letter_rows import PARAGRAPH_GAP, LetterRow, Letters
from openconsult.llm.door import Door
from openconsult.patients.audit import Audit
from openconsult.patients.users import User
from openconsult.prompts import loader


def assemble(paragraphs: list[str], title: str, row: dict, user: User) -> str:
    """The letter's text: the salutation, the Re line from the
    consultation's own row, the body, the sign-off with the user's title
    and name; a blank line between each part."""
    born = date.fromisoformat(row["patient_date_of_birth"])
    parts = [words.LETTER_SALUTATION.format(title=title.strip()),
             words.LETTER_RE.format(name=row["patient_name"], born=words.plain_date(born), sex=words.SEX_WORDS.get(row["patient_sex"], ""))]
    parts += [p for p in paragraphs if p.strip()]
    parts.append(f"{words.LETTER_SIGN_OFF}\n{user.full_name}")
    return PARAGRAPH_GAP.join(parts) + "\n"


def draft(door: Door, letters: Letters, notes, consultations, audit: Audit, consultation_id: int, item: dict) -> dict:
    """The call, the check and the row for one item; the letter row."""
    approval = notes.approval(consultation_id)
    if approval is None:
        raise ValueError(f"consultation {consultation_id} has no approved note (R5)")
    row = consultations.get(consultation_id)
    patient = referral_note.patient_of(row)
    lines = referral_note.numbered_lines(approval["text"])
    sent = referral_note.letter_text(lines)
    result = door.ask("letter", referral_note.letter_message(approval["text"], item["specialty"], patient),
                      consultation_id=consultation_id)
    version, digest = door.identity()
    reasoning = model_body = body = detail = None
    total = grounded = placeholders = dropped = 0
    refused, failure = False, None
    if result.ok:
        reasoning = str(result.answer.get("reasoning") or "")
        model_body = [{"text": str(p.get("text", "")), "note_lines": list(p.get("note_lines") or [])}
                      for p in result.answer.get("paragraphs") or [] if isinstance(p, dict)]
        checked = letter_check.check(model_body, lines, {str(patient.age)})
        body, detail = PARAGRAPH_GAP.join(checked.paragraphs), checked.detail
        total, grounded, placeholders, dropped, refused = (checked.total, checked.grounded, checked.placeholders,
                                                           checked.dropped, checked.refused)
    else:
        failure = f"{result.failure}: {result.detail}"
    letter_id = letters.add_letter(LetterRow(
        consultation_id, item["id"], result.call_id, door.profile.engine, version, door.profile.tag, digest,
        hashlib.sha256(loader.prompt_bytes("letter")).hexdigest(), sent, reasoning, model_body, body, detail,
        total, grounded, placeholders, dropped, refused, failure, result.wall_ms))
    where = f"consultation {consultation_id}: item {item['id']}, letter {letter_id}"
    if failure:
        audit.record("letter.failed", f"{where}: {failure}")
    elif refused:
        audit.record("letter.refused_by_check", f"{where}: {grounded} of {total} sentences grounded")
    else:
        audit.record("letter.drafted", f"{where}: {total} sentences, {grounded} grounded, {placeholders} placeholders, "
                                       f"{dropped} expectation sentences dropped, "
                                       f"{letter_check.allergies_dropped(detail)} allergy sentences dropped, {result.wall_ms} ms")
    return letters.letter(letter_id)
