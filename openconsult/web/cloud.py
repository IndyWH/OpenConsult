"""The pages of the cloud services (spec 7.2; 15.13, rulings 5, 30 and
34; the details of run 9b): the short account Why this model, kept as a
file of its own beside this one so that its bytes are the approved
ones; the two connect screens, where a key is pasted, tested and, only
if it passed, kept in the system's secure store; the tick of the cloud
statement; and the Test and Remove of the section Connections. A key is
never in a page, a reason, a log line or the audit log, and is never
shown again after it is pasted."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.settings import connections, keys
from openconsult.settings.path import CLAUDE
from openconsult.settings.statement import statement_for
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

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


# ------------------------------------------------------ the connect screens

BACK_TO = ("/settings", "/connect/claude", "/connect/speechmatics", "/first-run")
DONE = {"connected": words.KEY_SAVED, "tested": words.CONNECTED, "ticked": words.SAVED}


def service_or_404(name: str) -> str:
    if name not in connections.SERVICES:
        raise Redirect("/settings")
    return name


def when(at) -> tuple[str, str]:
    return f"{at.day} {at:%b %Y}", f"{at:%H:%M}"


def connection_view(p, service: str) -> dict:
    """What a page says of one service: connected or not, where the key
    in use came from, the last test. Nothing of the key itself."""
    state = p.connections.state(service)
    if state.last is None:
        last = words.NOT_TESTED_YET if state.has_key else None
    else:
        date, time = when(state.last_at)
        last = (words.LAST_TEST_PASSED.format(date=date, time=time) if state.last.ok
                else words.LAST_TEST_FAILED.format(date=date, time=time, reason=state.last.sentence))
    return {"name": service, "title": words.SERVICE_TITLES[service], "connected": state.connected,
            "state": words.CONNECTED if state.connected else words.NOT_CONNECTED,
            "where": words.KEY_WHERE[state.where] if state.where else None, "last": last, "has_key": state.has_key,
            "in_store": state.where == keys.STORE}


def statement_view(p, back: str) -> dict | None:
    """The statement of the path as it stands, when it has one and it is
    not ticked: shown where the doctor is, with its tick (ruling 5)."""
    path = p.stored.path(p.machine.case)
    made = statement_for(path)
    if made is None or p.stored.ticked(made):
        return None
    return {"made": made, "back": back}


def connect_page(request: Request, user, service: str, refused=None):
    p = parts(request)
    store_reason = p.connections.store_reason()
    view = connection_view(p, service)
    path = p.stored.path(p.machine.case)
    context = dict(user=user, active="settings", service=view, key_page=connections.SERVICES[service].key_page,
                   title=words.CONNECT_CLAUDE_TITLE if service == CLAUDE else words.CONNECT_SPEECHMATICS_TITLE,
                   lines=(words.CONNECT_CLAUDE_LINES if service == CLAUDE else
                          (words.CONNECT_SPEECHMATICS_LINE, words.CLOUD_SPEECHMATICS_LINES[2], words.CLOUD_SPEECHMATICS_LINES[3])),
                   why=service == CLAUDE, no_store=words.NO_SECURE_STORE if store_reason else None,
                   notice=DONE.get(request.query_params.get("done", "")),
                   # The statement stands on this screen once the service is connected, when the path as chosen uses it.
                   to_tick=statement_view(p, f"/connect/{service}") if view["connected"] and service in path.services else None,
                   page_path=f"/connect/{service}")
    if refused:
        return refuse(request, "connect.html", refused[0], refused[1], **context)
    return render(request, "connect.html", **context)


@router.get("/connect/{service}")
async def connect(request: Request, service: str):
    return connect_page(request, reader(request), service_or_404(service))


@router.post("/connect/{service}")
async def test_connection(request: Request, service: str):
    """Test connection. A pasted key is tested and, only if it passed,
    kept in the secure store; with no key pasted the key in use is
    tested. The reply never holds the key (7.2)."""
    user, service, p = reader(request), service_or_404(service), parts(request)
    pasted = (await form_fields(request)).get("key", "").strip()
    if not pasted:
        tested = await asyncio.to_thread(p.connections.test, service)
        if tested is None:
            return connect_page(request, user, service, ("test-connection", words.PASTE_A_KEY))
        if not tested.ok:
            return connect_page(request, user, service, ("test-connection", tested.sentence))
        raise Redirect(f"/connect/{service}?done=tested")
    if p.connections.store_reason():
        return connect_page(request, user, service, ("test-connection", words.NO_SECURE_STORE))
    try:
        tested = await asyncio.to_thread(p.connections.connect, service, pasted)
    except connections.KeyNotSaved as not_kept:
        return connect_page(request, user, service, ("test-connection", words.KEY_NOT_KEPT.format(reason=not_kept)))
    if not tested.ok:
        return connect_page(request, user, service, ("test-connection", tested.sentence))
    raise Redirect(f"/connect/{service}?done=connected")


# ---------------------------------------------------------- the statement

@router.post("/statement/tick")
async def tick_statement(request: Request):
    """The tick for the statement of the path as it stands: taken only for
    the text that is on the page now, by its checksum, and written to the
    audit log with the checksum and the path (ruling 5; 7.3, rule 4)."""
    user, p = reader(request), parts(request)
    fields = await form_fields(request)
    back = fields.get("back", "") if fields.get("back", "") in BACK_TO else "/settings"
    path = p.stored.path(p.machine.case)
    made = statement_for(path)
    if made is None:
        raise Redirect(back)
    if fields.get("sha256") != made.sha256:
        return _back_page(request, user, back, ("tick-statement", words.STATEMENT_CHANGED))
    if fields.get("understand") != "yes":
        return _back_page(request, user, back, ("tick-statement", words.STATEMENT_TICK_FIRST))
    p.stored.tick_statement(made.sha256, path)
    raise Redirect(f"{back}?done=ticked")


def _back_page(request: Request, user, back: str, refused):
    if back.startswith("/connect/"):
        return connect_page(request, user, back.rsplit("/", 1)[1], refused)
    from openconsult.web import routes
    return routes._settings_page(request, user, refused)


# ------------------------------------------------- the section Connections

@router.post("/connections/{service}/test")
async def test_in_use(request: Request, service: str, user=Depends(guards.logged_in)):
    from openconsult.web import routes
    service, p = service_or_404(service), parts(request)
    tested = await asyncio.to_thread(p.connections.test, service)
    if tested is None:
        return routes._settings_page(request, user, (f"test-{service}", words.NOT_CONNECTED))
    if not tested.ok:
        return routes._settings_page(request, user, (f"test-{service}", tested.sentence))
    raise Redirect("/settings?done=tested#connections")


@router.post("/connections/{service}/remove")
async def remove_key(request: Request, service: str, user=Depends(guards.logged_in)):
    from openconsult.web import routes
    service, p = service_or_404(service), parts(request)
    if not p.connections.remove(service):
        return routes._settings_page(request, user, (f"remove-{service}", words.KEY_NOT_IN_STORE))
    raise Redirect("/settings?done=removed#connections")
