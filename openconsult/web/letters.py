"""The Referral letters section of the review page and the letter's own
page (spec 15.12, rulings 1, 2, 4 and 8; the detail The page; R2, R5,
R15, R20, R30). After Approve, under the approved note: the items the
note states, then, under a line saying they are the model's suggestions
and not advice, the model's, then name a specialty; each item's title
editable, its reason with the note line a press that shows the line's
words, one control to draft. The letter opens on its own page: each
paragraph editable, the counts, the refusal line, Draft again, Approve
and Refuse, the model line; after Approve read-only with one copy
control that copies the letter alone. Built from the tables always."""

from __future__ import annotations

from datetime import datetime

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from openconsult import words
from openconsult.consult import letter as letter_module
from openconsult.consult import letter_check, referral_note, referrals
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
SCRIPT_WORDS = ("COPIED", "COPY_FAILED")


def script_words() -> dict:
    return {name: getattr(words, name) for name in SCRIPT_WORDS}


def ensure_list(p, consultation_id: int) -> None:
    """The list call, once, at the first opening of the review page after
    Approve (ruling 2); nothing before an approved note (R5)."""
    if p.notes.approval(consultation_id) is not None and p.letters.list_of(consultation_id) is None:
        referrals.make_list(p.door, p.letters, p.notes, p.consultations, p.audit, consultation_id)


def item_status(p, item: dict) -> dict:
    """What the item shows beside its specialty: nothing before a letter,
    else the state of its latest letter and the press to open it."""
    latest = p.letters.latest_letter(item["id"])
    if latest is None:
        return {"letter": None, "status": None}
    if p.letters.approval(latest["id"]):
        status = words.ITEM_APPROVED
    elif latest["failure"]:
        status = words.ITEM_FAILED
    elif latest["refused"]:
        status = words.ITEM_REFUSED_BY_CHECK
    elif latest["doctor_refused_at"]:
        status = words.ITEM_REFUSED
    else:
        status = words.ITEM_DRAFTED
    return {"letter": latest, "status": status}


def section_data(p, row: dict) -> dict | None:
    """The section's data, or None before Approve."""
    cid = row["id"]
    approval = p.notes.approval(cid)
    if approval is None:
        return None
    line_words = referral_note.words_of(referral_note.numbered_lines(approval["text"]))
    listed = p.letters.list_of(cid)
    items = []
    for item in p.letters.items(cid):
        items.append({**item, **item_status(p, item),
                      "urgency_word": words.URGENCY_WORDS.get(item["urgency"], ""),
                      "cited": [{"n": n, "text": line_words.get(n, "")} for n in item["note_lines"]]})
    listed_items = [i for i in items if i["kind"] != referrals.NAMED]
    return {"list": listed, "failed": words.LIST_FAILED.format(reason=listed["failure"]) if listed and listed["failure"] else None,
            "stated": [i for i in items if i["kind"] == referrals.STATED],
            "suggested": [i for i in items if i["kind"] == referrals.SUGGESTED],
            "named": [i for i in items if i["kind"] == referrals.NAMED],
            "none": words.NO_REFERRALS if listed and not listed["failure"] and not listed_items else None}


# -------------------------------------------------------------- the items

def _review(request: Request, user, consultation_id: int, control: str, message: str):
    from openconsult.web.review import review_page
    return review_page(request, user, consultation_id, refused=(control, message))


def _approved_row(request: Request, consultation_id: int) -> dict:
    from openconsult.web.review import final_row
    row = final_row(request, consultation_id)
    if parts(request).notes.approval(consultation_id) is None:
        raise Redirect(f"/consultations/{consultation_id}")       # no section before Approve: no such control (R5)
    return row


def _item_of(request: Request, consultation_id: int, item_id: int) -> dict:
    item = parts(request).letters.item(item_id)
    if item is None or item["consultation_id"] != consultation_id:
        raise Redirect(f"/consultations/{consultation_id}")
    return item


@router.post("/consultations/{consultation_id}/referrals/list")
async def list_again(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Make the list again after a failed call (R30); never by itself."""
    p = parts(request)
    _approved_row(request, consultation_id)
    listed = p.letters.list_of(consultation_id)
    if listed is None or not listed["failure"]:
        return _review(request, user, consultation_id, "list-again", words.LIST_STANDS)
    referrals.make_list(p.door, p.letters, p.notes, p.consultations, p.audit, consultation_id, again=True)
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/referrals/named")
async def named(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Name a specialty (ruling 8): a specialty and a title typed by the
    doctor, the item made and its letter drafted with no list call."""
    p = parts(request)
    _approved_row(request, consultation_id)
    fields = await form_fields(request)
    specialty, title = fields.get("specialty", "").strip(), fields.get("title", "").strip()
    if not specialty:
        return _review(request, user, consultation_id, "draft-named", words.SPECIALTY_EMPTY)
    if not title:
        return _review(request, user, consultation_id, "draft-named", words.TITLE_EMPTY)
    item_id = referrals.name_item(p.letters, p.audit, consultation_id, specialty, title)
    drafted = letter_module.draft(p.door, p.letters, p.notes, p.consultations, p.audit, consultation_id, p.letters.item(item_id))
    raise Redirect(f"/consultations/{consultation_id}/letters/{drafted['id']}")


@router.post("/consultations/{consultation_id}/referrals/{item_id}/title")
async def set_title(request: Request, consultation_id: int, item_id: int, user=Depends(guards.logged_in)):
    """The consultant's title corrected on the item, audited from what to what."""
    p = parts(request)
    _approved_row(request, consultation_id)
    item = _item_of(request, consultation_id, item_id)
    control = f"title-{item_id}"
    title = (await form_fields(request)).get("title", "").strip()
    if not title:
        return _review(request, user, consultation_id, control, words.TITLE_EMPTY)
    if title == item["title"]:
        return _review(request, user, consultation_id, control, words.TITLE_UNCHANGED)
    before = p.letters.set_title(item_id, title)
    p.audit.record("referral.title_changed", f"consultation {consultation_id}: item {item_id} from {before} to {title}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/referrals/{item_id}/draft")
async def draft_item(request: Request, consultation_id: int, item_id: int, user=Depends(guards.logged_in)):
    """One press drafts the item's letter (ruling 2); the page moves to it."""
    p = parts(request)
    _approved_row(request, consultation_id)
    item = _item_of(request, consultation_id, item_id)
    drafted = letter_module.draft(p.door, p.letters, p.notes, p.consultations, p.audit, consultation_id, item)
    raise Redirect(f"/consultations/{consultation_id}/letters/{drafted['id']}")


# ---------------------------------------------------------- the letter page

def _when(stamp: str) -> tuple[str, str]:
    when = datetime.fromisoformat(stamp)
    return words.plain_date(when), f"{when:%H:%M}"


def letter_state(p, row: dict, found: dict) -> dict:
    """What the page shows of one letter and which controls can act (R15)."""
    item = p.letters.item(found["item_id"])
    approval = p.letters.approval(found["id"])
    refused_by_doctor = bool(found["doctor_refused_at"])
    has_body = not found["failure"] and not found["refused"]
    user = p.users.get()
    text = letter_module.assemble(found["paragraphs"], item["title"], row, user) if has_body else None
    read_only = bool(approval or refused_by_doctor or not has_body)
    if approval:
        approve_reason = words.LETTER_ALREADY_APPROVED
    elif not has_body or refused_by_doctor:
        approve_reason = words.LETTER_NOTHING_TO_APPROVE
    else:
        approve_reason = None
    refuse_reason = (words.LETTER_ALREADY_APPROVED if approval else words.LETTER_ALREADY_REFUSED if refused_by_doctor
                     else words.LETTER_NOTHING_TO_APPROVE if not has_body else None)
    earlier = sum(1 for l in p.letters.letters_of_item(item["id"]) if l["n"] < found["n"])
    return {"letter": found, "item": item, "approval": approval, "has_body": has_body, "read_only": read_only,
            "paragraphs_reason": words.LETTER_READ_ONLY if approval else words.LETTER_NOT_EDITABLE if read_only else None,
            "approve_reason": approve_reason, "refuse_reason": refuse_reason,
            "again_reason": words.LETTER_READ_ONLY if approval else None,
            "salutation": words.LETTER_SALUTATION.format(title=item["title"]),
            "re_line": text.split("\n\n")[1] if text else None,
            "sign_off": f"{words.LETTER_SIGN_OFF} {user.full_name}" if user else words.LETTER_SIGN_OFF,
            "counts": words.LETTER_COUNTS.format(total=found["sentences_total"], grounded=found["sentences_grounded"],
                                                 placeholders=found["placeholders"], dropped=found["expectations_dropped"],
                                                 allergies=letter_check.allergies_dropped(found["check_detail"])),
            "refused_line": words.LETTER_REFUSED.format(grounded=found["sentences_grounded"], total=found["sentences_total"]) if found["refused"] else None,
            "failed_line": words.LETTER_CALL_FAILED.format(reason=found["failure"]) if found["failure"] else None,
            "approved_line": words.LETTER_APPROVED_LINE.format(date=_when(approval["at"])[0], time=_when(approval["at"])[1]) if approval else None,
            "doctor_refused_line": words.LETTER_REFUSED_LINE.format(date=_when(found["doctor_refused_at"])[0], time=_when(found["doctor_refused_at"])[1]) if refused_by_doctor else None,
            "earlier": (words.EARLIER_LETTERS if earlier == 1 else words.EARLIER_LETTERS_MANY).format(count=earlier) if earlier else None,
            "model_line": words.LETTER_MODEL_LINE.format(model=found["model_tag"], engine=words.ENGINE_NAMES.get(found["engine"], found["engine"]),
                                                         version=found["engine_version"] or "")}


def _letter_of(request: Request, consultation_id: int, letter_id: int) -> tuple[dict, dict]:
    from openconsult.web.review import final_row
    row = final_row(request, consultation_id)
    found = parts(request).letters.letter(letter_id)
    if found is None or found["consultation_id"] != consultation_id:
        raise Redirect(f"/consultations/{consultation_id}")
    return row, found


def letter_page(request: Request, user, consultation_id: int, letter_id: int, refused: tuple | None = None):
    p = parts(request)
    row, found = _letter_of(request, consultation_id, letter_id)
    context = dict(user=user, active="new_patient", cid=consultation_id, words_json=json.dumps(script_words()),
                   page_path=f"/consultations/{consultation_id}/letters/{letter_id}", timed_by_script=True,
                   title_line=words.LETTER_TITLE.format(specialty=p.letters.item(found["item_id"])["specialty"]),
                   **letter_state(p, row, found))
    if refused:
        return refuse(request, "letter.html", refused[0], refused[1], **context)
    return render(request, "letter.html", **context)


@router.get("/consultations/{consultation_id}/letters/{letter_id}")
async def show_letter(request: Request, consultation_id: int, letter_id: int, user=Depends(guards.logged_in)):
    return letter_page(request, user, consultation_id, letter_id)


@router.post("/consultations/{consultation_id}/letters/{letter_id}/paragraphs/{k}")
async def edit_paragraph(request: Request, consultation_id: int, letter_id: int, k: int, user=Depends(guards.logged_in)):
    """The doctor's edit of one paragraph; what stood before is kept."""
    p = parts(request)
    row, found = _letter_of(request, consultation_id, letter_id)
    control = f"paragraph-{k}"
    state = letter_state(p, row, found)
    if not state["has_body"] or not 0 <= k < len(found["paragraphs"]):
        raise Redirect(f"/consultations/{consultation_id}/letters/{letter_id}")      # no such control on the page
    if state["read_only"]:
        return letter_page(request, user, consultation_id, letter_id, refused=(control, state["paragraphs_reason"]))
    text = (await form_fields(request)).get("text", "").strip()
    if not text:
        return letter_page(request, user, consultation_id, letter_id, refused=(control, words.PARAGRAPH_EMPTY))
    if text != found["paragraphs"][k]:
        p.letters.set_paragraph(letter_id, k, text)
        p.audit.record("letter.edited", f"consultation {consultation_id}: letter {letter_id}, paragraph {k + 1}")
    raise Redirect(f"/consultations/{consultation_id}/letters/{letter_id}")


@router.post("/consultations/{consultation_id}/letters/{letter_id}/again")
async def draft_again(request: Request, consultation_id: int, letter_id: int, user=Depends(guards.logged_in)):
    """A new letter for the same item; the earlier is kept; the page moves to the new one."""
    p = parts(request)
    row, found = _letter_of(request, consultation_id, letter_id)
    state = letter_state(p, row, found)
    if state["again_reason"]:
        return letter_page(request, user, consultation_id, letter_id, refused=("again", state["again_reason"]))
    drafted = letter_module.draft(p.door, p.letters, p.notes, p.consultations, p.audit, consultation_id, state["item"])
    raise Redirect(f"/consultations/{consultation_id}/letters/{drafted['id']}")


@router.post("/consultations/{consultation_id}/letters/{letter_id}/approve")
async def approve(request: Request, consultation_id: int, letter_id: int, user=Depends(guards.logged_in)):
    """Approve: the assembled letter as it stands written to the record, audited (R2); read-only after."""
    p = parts(request)
    row, found = _letter_of(request, consultation_id, letter_id)
    state = letter_state(p, row, found)
    if state["approve_reason"]:
        return letter_page(request, user, consultation_id, letter_id, refused=("approve", state["approve_reason"]))
    text = letter_module.assemble(found["paragraphs"], state["item"]["title"], row, p.users.get())
    p.letters.approve(letter_id, text)
    p.audit.record("letter.approved", f"consultation {consultation_id}: letter {letter_id}, item {found['item_id']}, "
                                      f"{len(found['paragraphs'])} paragraphs")
    raise Redirect(f"/consultations/{consultation_id}/letters/{letter_id}")


@router.post("/consultations/{consultation_id}/letters/{letter_id}/refuse")
async def refuse_letter(request: Request, consultation_id: int, letter_id: int, user=Depends(guards.logged_in)):
    p = parts(request)
    row, found = _letter_of(request, consultation_id, letter_id)
    state = letter_state(p, row, found)
    if state["refuse_reason"]:
        return letter_page(request, user, consultation_id, letter_id, refused=("refuse", state["refuse_reason"]))
    p.letters.refuse(letter_id)
    p.audit.record("letter.refused", f"consultation {consultation_id}: letter {letter_id}")
    raise Redirect(f"/consultations/{consultation_id}/letters/{letter_id}")


@router.get("/consultations/{consultation_id}/letters/{letter_id}/letter.txt")
async def letter_text(request: Request, consultation_id: int, letter_id: int, user=Depends(guards.logged_in)):
    """The copy text: the approved letter alone (R2); nothing before Approve."""
    p = parts(request)
    _letter_of(request, consultation_id, letter_id)
    approval = p.letters.approval(letter_id)
    if approval is None:
        return PlainTextResponse(words.NO_LETTER_TEXT_YET, status_code=404)
    return PlainTextResponse(approval["text"])
