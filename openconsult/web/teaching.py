"""The pages of teaching mode (spec 12; 15.14 and the details of run 10b;
R24): the one module of pages that teaching has. Its addresses are its
own, all under /teaching, and it reaches teaching through the one
object of openconsult/teaching/play.py. Every page is behind the login.

The name of a bank file and the id inside it name the diagnosis: a page
knows a case of the bank by its number alone."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from openconsult.teaching import words as t
from openconsult.web import guards
from openconsult.web.guards import parts
from openconsult.web.pages import render

router = APIRouter()


def bank_rows(teaching) -> list[dict]:
    """The cases of the bank as the page lists them: number, topic, level and label, and nothing else of a file."""
    return [{"number": case.number, "name": t.CASE_NUMBER.format(n=case.number), "topic": case.topic,
             "level": t.LEVEL_NAMES[case.level], "label": t.LABELS[case.label]} for case in teaching.bank.cases]


@router.get("/teaching")
async def teaching_page(request: Request, user=Depends(guards.logged_in)):
    """The teaching page, in the order of the details: the line of no
    affiliation, the line on a real patient's details, then the cases."""
    teaching = parts(request).teaching
    return render(request, "teaching.html", user=user, active="teaching", t=t, bank=bank_rows(teaching),
                  unread=t.bank_unread(teaching.bank.unread))
