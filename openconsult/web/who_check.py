"""The controls of the who-spoke check on the review page (spec 15.10
ruling 19; R15): Check who spoke, and Undo all the changes of the
check. A press that cannot act changes nothing and is answered with the
reason beside the control: the running sentence while a run lasts, that
the check has already run, or that the note is approved."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from openconsult.web import guards, review
from openconsult.web.guards import Redirect, parts

router = APIRouter()


@router.post("/consultations/{consultation_id}/who-check")
async def check(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """One press starts one run; the page then waits for it."""
    p = parts(request)
    row = review.final_row(request, consultation_id)
    state = review.page_data(p, row)["who_check"]
    if not state["has_lines"]:
        raise Redirect(f"/consultations/{consultation_id}")      # no such control on the page
    if not state["offered"]:
        return review.review_page(request, user, consultation_id, refused=("check-who", state["reason"]))
    p.who_checks.start(consultation_id)
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/who-check/undo-all")
async def undo_all(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """One press puts back the label before on every line still marked."""
    p = parts(request)
    row = review.final_row(request, consultation_id)
    data = review.page_data(p, row)
    if data["transcript_read_only"]:
        return review.review_page(request, user, consultation_id, refused=("undo-all", data["transcript_reason"]))
    if not data["who_check"]["undo_all"]:
        raise Redirect(f"/consultations/{consultation_id}")      # no line is marked: no such control on the page
    p.who_checks.undo_all(consultation_id)
    raise Redirect(f"/consultations/{consultation_id}")
