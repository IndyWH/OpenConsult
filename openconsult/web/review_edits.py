"""The edits of the review page (spec 15.10, rulings 7 and 11; rulings 26,
28, 33 and 40): the doctor's Save of a note entry, Swap, the Save of a
line's words and speaker, the Undo of a label the check changed, and the
tick of a doubted drug name's row. Each change is recorded with what
stood before; a press that cannot act is answered on the control that
was pressed (R15). They stood in web/review.py until step 9f and moved
here whole, so that the file of the page stays under its size (5.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.consult import drug_marks
from openconsult.consult.consultations import LABELS
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields
from openconsult.web.review import final_row, page_data, review_page

router = APIRouter()


@router.post("/consultations/{consultation_id}/entries/{entry_id}")
async def edit_entry(request: Request, consultation_id: int, entry_id: int, user=Depends(guards.logged_in)):
    """The doctor's edit of an entry's words; what stood before is kept."""
    p = parts(request)
    final_row(request, consultation_id)
    data = page_data(p, p.consultations.get(consultation_id))
    control = f"entry-{entry_id}"
    entry = p.notes.entry(entry_id)
    if entry is None or not data["draft"] or entry["draft_id"] != data["draft"]["id"]:
        raise Redirect(f"/consultations/{consultation_id}")
    if data["entries_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["entries_reason"]))
    text = (await form_fields(request)).get("text", "").strip()
    if not text:
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if text != entry["text"]:
        p.notes.set_entry_text(entry_id, text)
        p.audit.record("entry.edited", f"consultation {consultation_id}: entry {entry_id}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/swap")
async def swap_lines(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """v1's Swap: doctor and patient exchanged on every line; unsure stays."""
    p = parts(request)
    final_row(request, consultation_id)
    data = page_data(p, p.consultations.get(consultation_id))
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=("swap", data["transcript_reason"]))
    p.consultations.swap_labels(consultation_id)
    p.audit.record("labels.swapped", f"consultation {consultation_id}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/{n}")
async def edit_line(request: Request, consultation_id: int, n: int, user=Depends(guards.logged_in)):
    """The per-line label and the words, from one form; each change is
    recorded with what stood before, and draft again is then offered."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"save-line-{n}"
    line = p.consultations.line(consultation_id, n)
    if line is None:
        raise Redirect(f"/consultations/{consultation_id}")      # no such control on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["transcript_reason"]))
    fields = await form_fields(request)
    label, text = fields.get("label", ""), fields.get("text", "").strip()
    if label not in LABELS:
        return review_page(request, user, consultation_id, refused=(control, words.PICK_LABEL))
    # A line that holds words is never emptied here. One a drug-name correction left with no words may stay empty,
    # so that its speaker can still be set (the plan review of 6d, point 1).
    if not text and line["text"].strip():
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if text != line["text"]:
        p.consultations.set_line_words(consultation_id, n, text)
        p.audit.record("transcript.edited", f"consultation {consultation_id}: line {n}")
        # A doubted name typed over here: a mark whose words are gone leaves the page and stays in the record (ruling 20).
        drug_marks.after_edit(p.consultations, consultation_id, n, before={n: line["text"]})
    if label != line["label"]:
        p.consultations.set_line_label(consultation_id, n, label)
        p.audit.record("label.set", f"consultation {consultation_id}: line {n} to {label}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/{n}/undo")
async def undo_label(request: Request, consultation_id: int, n: int, user=Depends(guards.logged_in)):
    """One press puts back the label that stood before the check changed
    it (ruling 7; the details of step 6c, Undo): not the answer's label,
    which a Swap may have changed since."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"undo-{n}"
    line = p.consultations.line(consultation_id, n)
    if line is None:
        raise Redirect(f"/consultations/{consultation_id}")      # no such control on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["transcript_reason"]))
    before = p.consultations.undo_change(consultation_id, n)
    if before is None:
        return review_page(request, user, consultation_id, refused=(control, words.NOT_CHANGED_BY_CHECK))
    p.audit.record("label.undone", f"consultation {consultation_id}: line {n} back to {before}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/marks/{mark_id}")
async def tick_mark(request: Request, consultation_id: int, mark_id: int, user=Depends(guards.logged_in)):
    """The row of a doubted drug name, the one place to settle it (rulings
    26 and 28). A press on a tick that is not ticked keeps what the field
    holds: where the words differ from those on the line, the line is
    corrected by the function its own box uses; then the mark is settled,
    with the time. A press on a ticked tick opens it again; the line keeps
    what was typed. The button says which press it is, so a press from a
    stale page never turns a mark the wrong way. A third press, keep, is
    sent by the page's script when the doctor leaves the box (ruling 33):
    the typed words go into the line as at the tick, and the mark is not
    settled, so a stray click never settles a name. A tick with the box
    empty takes the doubted words out of the line and settles the mark
    (ruling 40): a leftover piece of a name the speech choice cut over
    two lines would otherwise go to the note's model as if it had been
    said. The line stays, the record keeps the words as heard, and a
    second press opens the mark with an empty box, so that words can be
    typed back. The note is never corrected by this: Draft the note
    again is offered, never run."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"tick-{mark_id}"
    mark = next((m for m in p.consultations.drug_marks(consultation_id) if m["id"] == mark_id), None)
    if mark is None:
        raise Redirect(f"/consultations/{consultation_id}#warnings")      # no such row on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["transcript_reason"]))
    fields = await form_fields(request)
    # With no script a row's press comes back at its row. The page's script keeps the place itself and asks for no anchor,
    # which would carry the row to the top of the window, past the next one (ruling 34).
    back = f"/consultations/{consultation_id}" + ("" if fields.get("place") == "keep" else f"#drug-mark-{mark_id}")
    where = f"consultation {consultation_id}: line {mark['heard_first']}"
    if fields.get("press") == "open":
        if mark["settled_at"] is not None:
            p.consultations.settle_mark(mark_id, settled=False)
            p.audit.record("drug_name.opened", where)
        raise Redirect(back)
    if mark["settled_at"] is not None:
        raise Redirect(back)                                              # ticked already: its words are locked, for a tick and for a keep
    typed = fields.get("words", mark["standing"]).strip()
    # An empty box with the tick or the Enter key takes the doubted words out of the line (ruling 40). Leaving an empty
    # box takes nothing out: the page's script sends no keep for one, and a keep that a stale page sends is refused as built.
    if not typed and mark["standing"] and fields.get("press") == "keep":
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if typed != mark["standing"]:
        drug_marks.correct(p.consultations, p.audit, consultation_id, mark, typed)
    if fields.get("press") == "keep":
        raise Redirect(back)                                              # kept in the line, not settled: the tick stays faded
    p.consultations.settle_mark(mark_id)
    p.audit.record("drug_name.settled", where)
    raise Redirect(back)
