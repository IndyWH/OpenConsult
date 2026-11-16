"""The pages of the cloud services (spec 7.2; 15.13, rulings 5, 30 and
34; the details of run 9b). This file begins with the short account Why
this model, which the line on the connect screen for Claude opens: the
road to Claude Haiku 5.5 in plain words, kept as a file of its own
beside this one, so that its bytes are the approved ones."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from openconsult.web import guards
from openconsult.web.guards import parts
from openconsult.web.pages import render

router = APIRouter()
WHY_THIS_MODEL = Path(__file__).parent / "why_this_model.md"


def reader(request: Request):
    """The user behind a page that the first run also shows, before there
    is a user: during the first run a request from this computer, with
    no user; after it the login, as every page."""
    if parts(request).first_run.next_step() is not None:
        guards.this_computer(request)
        return None
    return guards.logged_in(request)


def account() -> tuple[str, list[str]]:
    """The account as its file gives it: the first line is its name, each
    block of text after it a paragraph."""
    blocks = [block.strip() for block in WHY_THIS_MODEL.read_text(encoding="utf-8").split("\n\n") if block.strip()]
    return blocks[0], blocks[1:]


@router.get("/why-this-model")
async def why_this_model(request: Request):
    """Read only: nothing on the page acts, and nothing is written."""
    user = reader(request)
    title, paragraphs = account()
    return render(request, "why_this_model.html", user=user, active="settings", title=title, paragraphs=paragraphs)
