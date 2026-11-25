"""The pages of teaching mode (spec 12; 15.14 and the details of run 10b;
R24): the one module of pages that teaching has. Its addresses are its
own, all under /teaching, and it reaches teaching through the one
object of openconsult/teaching/play.py. Every page is behind the login.

The name of a bank file and the id inside it name the diagnosis: a page
knows a case of the bank by its number alone. A page of a case is given
what may be shown at its step and nothing else of the scenario."""

from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.llm.choose import SHORT_WAIT_S
from openconsult.settings.path import CLAUDE
from openconsult.settings.statement import statement_for
from openconsult.teaching import words as t
from openconsult.teaching.scenario import speaks_for
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
SETTINGS_STATEMENT = "/settings#cloud-statement"


def bank_rows(teaching) -> list[dict]:
    """The cases of the bank as the page lists them: number, topic, level and label, and nothing else of a file.
    press is the token of this row's press on this view of the page: the same press twice starts one case (R15)."""
    return [{"number": case.number, "name": t.CASE_NUMBER.format(n=case.number), "topic": case.topic,
             "level": t.LEVEL_NAMES[case.level], "label": t.LABELS[case.label], "press": secrets.token_urlsafe(12)}
            for case in teaching.bank.cases]


def cloud_lines() -> tuple[str, str]:
    """Under the mark Cloud on a teaching page (ruling 15): the owner's sentence, then the cost."""
    return t.CLOUD_TYPED, t.CLOUD_COST


def language_model(p) -> str:
    """The language model chosen in Settings, as for every job (the details: Which model answers)."""
    return p.stored.path(p.machine.case).language_model


def cannot_start(p) -> tuple[str, str | None] | None:
    """Why a case cannot start now, for the control that was pressed (R15;
    10.4), with the address where it is mended, or None when it can.
    This computer: no engine was fit at start, or the engine does not
    answer now. Claude: not connected; the statement of the path not
    ticked, or ticked before it held the line for teaching (rulings 7
    and 15); or its connection failing now. Nothing is ever tried on the
    other model."""
    path = p.stored.path(p.machine.case)
    if path.claude:
        if not p.connections.state(CLAUDE).has_key:
            return t.CANNOT_START_NOT_CONNECTED, "/connect/claude"
        if not p.stored.covers(statement_for(path)):
            return t.CANNOT_START_NO_TICK, SETTINGS_STATEMENT
        tested = p.connections.test(CLAUDE)
        if tested is not None and not tested.ok:
            return t.CANNOT_START.format(reason=tested.sentence), "/connect/claude"
    elif not p.decisions.start_offered:
        return t.CANNOT_START.format(reason=p.decisions.language_model.sentence), None
    elif not p.engine.status(p.door.profile.tag, SHORT_WAIT_S).running:
        return t.CANNOT_START_NO_ANSWER.format(engine=words.ENGINE_NAMES.get(p.engine.name, p.engine.name)), None
    return None


def _teaching_page(request: Request, user, refused: tuple[str, str] | None = None, lead: str | None = None):
    """lead: where the reason of a refusal is mended, drawn as a link beside it."""
    p = parts(request)
    context = dict(user=user, active="teaching", t=t, bank=bank_rows(p.teaching), unread=t.bank_unread(p.teaching.bank.unread),
                   mark=cloud_lines() if language_model(p) == CLAUDE else None, lead=lead, page_path="/teaching")
    if refused:
        return refuse(request, "teaching.html", refused[0], refused[1], **context)
    return render(request, "teaching.html", **context)


@router.get("/teaching")
async def teaching_page(request: Request, user=Depends(guards.logged_in)):
    """The teaching page, in the order of the details: the line of no
    affiliation, the line on a real patient's details, then the cases."""
    return _teaching_page(request, user)


@router.post("/teaching/cases")
async def start_case(request: Request, user=Depends(guards.logged_in)):
    """The press that starts a case of the bank, by its number. Where no
    model can be reached, or in cloud mode without the tick, it says so
    on the control and starts nothing."""
    p = parts(request)
    fields = await form_fields(request)
    number = fields.get("number", "")
    case = p.teaching.bank.case(int(number)) if number.isdigit() else None
    if case is None:
        return _teaching_page(request, user, ("start-bank", t.NOT_IN_LIST))
    press = fields.get("press") or secrets.token_urlsafe(12)
    started = p.teaching.cases.by_press(press)
    if started is None:
        problem = await asyncio.to_thread(cannot_start, p)
        if problem is not None:
            return _teaching_page(request, user, (f"start-{case.number}", problem[0]), lead=problem[1])
        started = p.teaching.start_bank(case.number, press, language_model(p))
    raise Redirect(f"/teaching/cases/{started}")


def case_view(row: dict) -> dict:
    """What every page of a case shows at its top: the case's name, its
    topic, its level and its label, and the patient as presented: the
    name, the age and the sex, a parent who speaks for a child, and the
    opening words. Not the occupation and not the manner."""
    scenario = row["scenario"]
    patient, parent = scenario["patient"], speaks_for(scenario)
    return {"id": row["id"], "heading": t.CASE_NUMBER.format(n=row["bank_number"]) if row["source"] == "bank" else t.NEW_CASE,
            "topic": row["topic"], "level": t.LEVEL_NAMES[row["level"]], "label": t.LABELS[row["label"]],
            "presented": t.PRESENTED.format(name=patient["name"], age=patient["age"], sex=patient["sex"]),
            "speaks_for": t.SPEAKS_FOR.format(parent=parent) if parent else None, "opening_words": scenario["opening_words"]}


@router.get("/teaching/cases/{case_id}")
async def case_page(request: Request, case_id: int, user=Depends(guards.logged_in)):
    """The case where it stands. The mark Cloud stands on it while its own
    language model is Claude, whatever Settings says by now."""
    row = parts(request).teaching.cases.get(case_id)
    if row is None:
        raise Redirect("/teaching")
    return render(request, "teaching_case.html", user=user, active="teaching", t=t, case=case_view(row),
                  mark=cloud_lines() if row["language_model"] == CLAUDE else None, page_path=f"/teaching/cases/{case_id}")
