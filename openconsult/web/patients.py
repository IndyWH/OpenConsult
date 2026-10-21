"""The patient's page (spec 15.11 ruling 2; 8.1; R2, R11, R15, R17): the
current details, each with its own Edit control, every change audited
with what stood before; the consultations newest first with their
state; New consultation. The details a consultation ran with are shown
on the consultation's own page (web/review.py). Delete patient arrives
with the deleting of ruling 8."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.patients.patients import FIELDS, parse_date, problem
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
CONTROLS = {"name": "save-name", "date_of_birth": "save-date", "sex": "save-sex"}


def consultation_state(row: dict, approved: bool, refused: bool) -> str:
    """The state word of a consultation on the patient's page (ruling 2):
    approved; a refused note; waiting for review; running; waiting at Stop."""
    if row["state"] == "live":
        return "running"
    if row["state"] == "stopping":
        return "at_stop"
    if approved:
        return "approved"
    return "refused" if refused else "review"


def consultation_rows(p, patient_id: int) -> list[dict]:
    found = []
    for row in p.consultations.of_patient(patient_id):
        cid = row["id"]
        drafts = p.notes.drafts(cid)
        latest = drafts[-1]["id"] if drafts else None
        refused = any(r["draft_id"] == latest for r in p.notes.refusals(cid)) if latest else False
        state = consultation_state(row, p.notes.approval(cid) is not None, refused)
        when = datetime.fromisoformat(row["started_at"])
        found.append({"id": cid, "when": f"{words.plain_date(when)} {when:%H:%M}", "state": words.STATE_WORDS[state]})
    return found


def _page(request: Request, user, patient_id: int, refused: tuple | None = None):
    p = parts(request)
    patient = p.patients.get(patient_id)
    if patient is None:
        raise Redirect("/")
    context = dict(user=user, active="home", patient=patient, born=patient.date_of_birth.isoformat(),
                   number=words.NUMBER_LINE.format(id=patient.id), consultations=consultation_rows(p, patient_id),
                   page_path=f"/patients/{patient_id}")
    if refused:
        return refuse(request, "patient.html", refused[0], refused[1], **context)
    return render(request, "patient.html", **context)


@router.get("/patients/{patient_id}")
async def patient_page(request: Request, patient_id: int, user=Depends(guards.logged_in)):
    return _page(request, user, patient_id)


@router.post("/patients/{patient_id}/{field}")
async def correct(request: Request, patient_id: int, field: str, user=Depends(guards.logged_in)):
    """One detail corrected on its own control (R15): checked as the
    new-patient form checks it (R11), then written with what stood
    before (R2). An earlier consultation keeps the details it ran with."""
    p = parts(request)
    if field not in FIELDS or p.patients.get(patient_id) is None:
        raise Redirect(f"/patients/{patient_id}")
    value = (await form_fields(request)).get("value", "").strip()
    current = p.patients.get(patient_id)
    fields = {"name": current.name, "date_of_birth": current.date_of_birth.isoformat(), "sex": current.sex, field: value}
    found = problem(fields["name"], fields["date_of_birth"], fields["sex"], p.patients.today())
    if found:
        from openconsult.web.consult import PATIENT_PROBLEMS
        return _page(request, user, patient_id, refused=(CONTROLS[field], PATIENT_PROBLEMS[found]))
    stored = parse_date(value).isoformat() if field == "date_of_birth" else value
    if not p.patients.correct(patient_id, field, stored, user.full_name):
        return _page(request, user, patient_id, refused=(CONTROLS[field], words.DETAIL_UNCHANGED))
    raise Redirect(f"/patients/{patient_id}")
