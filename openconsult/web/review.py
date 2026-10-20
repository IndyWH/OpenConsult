"""The review page (spec 15.10, rulings 4, 8, 11 and 12; R2, R4, R15,
R20), in the busy GP's order: the draft note first, each entry's line
numbers a press that shows the line, the model's last differentials
beside the assessment under a heading that says they are not part of
the note; Approve and Refuse, the Approve control carrying the count of
warnings; the warnings; the transcript with the player; the model line.
Built from the tables always, so a consultation opened after a restart
shows the same page. Draft the note for a final consultation that has
none; draft again after an edit, never by itself. The copy text is served
as plain text so that a test proves it holds the note alone."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from openconsult import words
from openconsult.consult import note, speakers
from openconsult.consult.consultations import LABELS
from openconsult.consult.gate import LOW_CONFIDENCE
from openconsult.speech.choices import CHOICES
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
GATE_REFUSALS = ("too_short", "empty")
# The sentences the page scripts render, handed as data (15.6).
SCRIPT_WORDS = ("COPIED", "COPY_FAILED")


def script_words() -> dict:
    return {name: getattr(words, name) for name in SCRIPT_WORDS}


def final_row(request: Request, consultation_id: int) -> dict:
    row = parts(request).consultations.get(consultation_id)
    if row is None or row["state"] != "final":
        raise Redirect("/")
    return row


def warning_lines(rows: list[dict], lines: list[dict], choice_title: str) -> list[dict]:
    """Each stored warning as its sentence (ruling 8), and one for each
    label the check changed (ruling 7), each with its place for the
    player: a stretch, a line, or none."""
    found = []
    for w in rows:
        kind, detail = w["kind"], w["detail"] or ""
        if kind == "speech_failed":
            text = words.WARN_SPEECH_FAILED.format(reason=detail) if detail != words.APP_RESTARTED else detail
        elif kind == "label_check_refused":
            text = words.WARN_LABEL_CHECK_REFUSED.format(reason=detail)
        elif kind == "label_check_failed":
            text = words.WARN_LABEL_CHECK_FAILED.format(reason=detail)
        else:
            text = words.WARNING_SENTENCES.get(kind, "{detail}").format(
                start=w["start_s"], end=w["end_s"], n=w["line_n"], detail=detail, words=detail, score=detail, choice=choice_title)
        found.append({"kind": kind, "text": text, "start_s": w["start_s"], "end_s": w["end_s"], "line_n": w["line_n"]})
    for line in lines:
        if line["changed_by_check"]:
            found.append({"kind": "label_changed", "line_n": line["n"], "start_s": None, "end_s": None,
                          "text": words.WARN_LABEL_CHANGED.format(n=line["n"], label=words.LABEL_WORDS[line["label"]])})
    return found


def model_line_of(row: dict) -> str:
    """R20: from the row's stamps, not the running engine, so it is true after a restart."""
    choice = CHOICES.get(row["speech_choice"])
    return words.MODEL_LINE.format(speech=choice.title if choice else row["speech_choice"], model=row["model_tag"],
                                   engine=words.ENGINE_NAMES.get(row["engine"], row["engine"]), version=row["engine_version"] or "")


def _when(stamp: str) -> tuple[str, str]:
    when = datetime.fromisoformat(stamp)
    return words.plain_date(when), f"{when:%H:%M}"


def note_state(p, row: dict, gate_refused: bool) -> dict:
    """What the page shows of the note and which controls can act (R15):
    the draft on the page, its entries by section, the approval, the
    doctor's refusal, and the reason for each control that cannot act."""
    cid = row["id"]
    drafts = p.notes.drafts(cid)
    draft = drafts[-1] if drafts else None
    approval = p.notes.approval(cid)
    refused_by_doctor = bool(draft and any(r["draft_id"] == draft["id"] for r in p.notes.refusals(cid)))
    entries = p.notes.entries(draft["id"]) if draft else []
    has_note = bool(draft and not draft["refused"] and not draft["failure"])
    later_edit = draft is not None and (p.consultations.last_edit_id(cid) or 0) > (draft["last_edit_id"] or 0)
    if approval:
        draft_reason = words.NOTE_READ_ONLY
    elif gate_refused:
        draft_reason = words.NOTE_GATE_REFUSED.format(reason="")
    elif has_note and not later_edit:
        draft_reason = words.DRAFT_AGAIN_NEEDS_EDIT      # a note stands: draft again waits for an edit (ruling 11)
    else:
        draft_reason = None
    if approval:
        approve_reason = words.ALREADY_APPROVED
    elif not has_note or refused_by_doctor:
        approve_reason = words.NOTHING_TO_APPROVE
    else:
        approve_reason = None
    refuse_reason = (words.ALREADY_APPROVED if approval else words.ALREADY_REFUSED if refused_by_doctor
                     else words.NOTHING_TO_APPROVE if not has_note else None)
    return {"draft": draft, "entries": entries, "sections": {s: [e for e in entries if e["section"] == s] for s in note.SECTIONS},
            "approval": approval, "refused_by_doctor": refused_by_doctor, "has_note": has_note,
            "earlier": len(drafts) - 1 if drafts else 0,
            # After Approve the whole page is read-only; after Refuse the entries are, the transcript is not.
            "entries_read_only": bool(approval or refused_by_doctor), "transcript_read_only": bool(approval),
            "entries_reason": words.NOTE_READ_ONLY if approval else words.NOTE_NOT_EDITABLE if refused_by_doctor else None,
            "draft_control": words.DRAFT_AGAIN if has_note else words.DRAFT_THE_NOTE, "draft_reason": draft_reason,
            "approve_reason": approve_reason, "refuse_reason": refuse_reason, "asked_by": "again" if draft is not None else "draft"}


def page_data(p, row: dict) -> dict:
    cid = row["id"]
    lines = [r for r in p.consultations.transcript_lines(cid) if r["n"] is not None]
    for line in lines:
        score = line.get("confidence")
        line["low_confidence"] = (words.LOW_CONFIDENCE_MARK.format(score=f"{score:.2f}")
                                  if score is not None and score < LOW_CONFIDENCE else None)
    warning_rows = p.consultations.warnings(cid)
    gate_refused = any(w["kind"] in GATE_REFUSALS for w in warning_rows)
    gate_reason = " ".join(w["detail"] or words.WARNING_SENTENCES.get(w["kind"], "") for w in warning_rows if w["kind"] in GATE_REFUSALS)
    choice = CHOICES.get(row["speech_choice"])
    warnings = warning_lines(warning_rows, lines, choice.title if choice else row["speech_choice"])
    state = note_state(p, row, gate_refused)
    if gate_refused:
        state["draft_reason"] = words.NOTE_GATE_REFUSED.format(reason=gate_reason)
    return {"cid": cid, "row": row, "patient": p.patients.get(row["patient_id"]), "lines": lines, "warnings": warnings,
            "warning_count": words.WARNING_ONE if len(warnings) == 1 else words.WARNINGS_COUNT.format(count=len(warnings)),
            "differentials": note.last_shown_differentials(p.consultations.passes(cid)),
            "gate_refused": gate_refused, "gate_reason": gate_reason, "model_line": model_line_of(row),
            "date": words.plain_date(datetime.fromisoformat(row["started_at"])), **state,
            "approved_line": words.APPROVED_LINE.format(date=_when(state["approval"]["at"])[0], time=_when(state["approval"]["at"])[1])
            if state["approval"] else None}


def review_page(request: Request, user, consultation_id: int, refused: tuple | None = None):
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    draft = data["draft"]
    if draft and data["refused_by_doctor"]:
        when = [r["at"] for r in p.notes.refusals(consultation_id) if r["draft_id"] == draft["id"]][-1]
        data["refused_line"] = words.REFUSED_LINE.format(date=_when(when)[0], time=_when(when)[1])
    context = dict(user=user, active="new_patient", page_path=f"/consultations/{consultation_id}", timed_by_script=True,
                   words_json=json_words(), **data)
    if refused:
        return refuse(request, "review.html", refused[0], refused[1], **context)
    return render(request, "review.html", **context)


def json_words() -> str:
    import json
    return json.dumps(script_words())


# ------------------------------------------------------------- the controls

@router.post("/consultations/{consultation_id}/note/draft")
async def draft(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Draft the note for a final consultation that has none, or draft it
    again after an edit (ruling 11); never by itself. Refused on the
    control when the gate refused, the note is approved, or nothing has
    been edited (R15)."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["draft_reason"]:
        return review_page(request, user, consultation_id, refused=("draft", data["draft_reason"]))
    note.draft(p.door, p.consultations, p.notes, p.audit, consultation_id, data["asked_by"])
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/note/approve")
async def approve(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Approve: the approved note written as the copy text, audited (R2);
    after it the note is read-only."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["approve_reason"]:
        return review_page(request, user, consultation_id, refused=("approve", data["approve_reason"]))
    text = note.plain_text(data["entries"])
    p.notes.approve(consultation_id, data["draft"]["id"], text)
    p.audit.record("note.approved", f"consultation {consultation_id}: draft {data['draft']['n']}, {len(data['entries'])} entries")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/note/refuse")
async def refuse_note(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Refuse: recorded and audited; nothing enters the record."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["refuse_reason"]:
        return review_page(request, user, consultation_id, refused=("refuse", data["refuse_reason"]))
    p.notes.refuse(consultation_id, data["draft"]["id"])
    p.audit.record("note.refused", f"consultation {consultation_id}: draft {data['draft']['n']}")
    raise Redirect(f"/consultations/{consultation_id}")


# ---------------------------------------------- the edits (rulings 7 and 11)

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
        return review_page(request, user, consultation_id, refused=("swap", words.NOTE_READ_ONLY))
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
        return review_page(request, user, consultation_id, refused=(control, words.NOTE_READ_ONLY))
    fields = await form_fields(request)
    label, text = fields.get("label", ""), fields.get("text", "").strip()
    if label not in LABELS:
        return review_page(request, user, consultation_id, refused=(control, words.PICK_LABEL))
    if not text:
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if text != line["text"]:
        p.consultations.set_line_words(consultation_id, n, text)
        p.audit.record("transcript.edited", f"consultation {consultation_id}: line {n}")
    if label != line["label"]:
        p.consultations.set_line_label(consultation_id, n, label)
        p.audit.record("label.set", f"consultation {consultation_id}: line {n} to {label}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/{n}/undo")
async def undo_label(request: Request, consultation_id: int, n: int, user=Depends(guards.logged_in)):
    """One press puts back the label the who-spoke answer gave (ruling 7)."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"undo-{n}"
    line = p.consultations.line(consultation_id, n)
    if line is None:
        raise Redirect(f"/consultations/{consultation_id}")      # no such control on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, words.NOTE_READ_ONLY))
    if not line["changed_by_check"]:
        return review_page(request, user, consultation_id, refused=(control, words.NOT_CHANGED_BY_CHECK))
    answered = speakers.labels_from_answer([line], row["doctor_speaker"] or speakers.CANNOT_TELL)[n]["label"]
    p.consultations.set_line_label(consultation_id, n, answered, kind="undo")
    p.audit.record("label.undone", f"consultation {consultation_id}: line {n} back to {answered}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.get("/consultations/{consultation_id}/note.txt")
async def note_text(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """The copy text: the note alone in the four sections (ruling 4); the
    approved text once approved."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["approval"]:
        return PlainTextResponse(data["approval"]["text"])
    if not data["has_note"]:
        return PlainTextResponse(words.NO_NOTE_YET, status_code=404)
    return PlainTextResponse(note.plain_text(data["entries"]))
