"""The pages (spec 15.6): the first run, login and logout, home."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from openconsult import words
from openconsult.patients.users import MIN_PASSWORD, name_problem, password_problem
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()


@router.get("/")
async def home(request: Request, user=Depends(guards.logged_in)):
    return render(request, "home.html", user=user, active="home")


# ------------------------------------------------------------ the first run

STEP_PAGE = {
    "statement": "first_run_statement.html",
    "machine": "first_run_machine.html",
    "user": "first_run_user.html",
}


@router.get("/first-run")
async def first_run(request: Request):
    step = parts(request).first_run.next_step()
    if step is None:
        raise Redirect("/login")
    return render(request, STEP_PAGE[step], machine=parts(request).machine)


def _at_step(request: Request, step: str) -> None:
    """A step's form is only taken at that step; otherwise back to the
    first step not done, so nobody can set up a user before accepting
    the statement (15.6 ruling 4)."""
    if parts(request).first_run.next_step() != step:
        raise Redirect("/first-run")


@router.post("/first-run/statement", dependencies=[Depends(guards.this_computer)])
async def accept_statement(request: Request):
    _at_step(request, "statement")
    fields = await form_fields(request)
    if fields.get("agree") != "yes":
        return refuse(request, STEP_PAGE["statement"], "continue", words.TICK_TO_CONTINUE)
    p = parts(request)
    p.first_run.mark_done("statement")
    p.audit.record("statement.accepted")
    raise Redirect("/first-run")


@router.post("/first-run/machine", dependencies=[Depends(guards.this_computer)])
async def seen_machine(request: Request):
    _at_step(request, "machine")
    parts(request).first_run.mark_done("machine")
    raise Redirect("/first-run")


@router.post("/first-run/user", dependencies=[Depends(guards.this_computer)])
async def set_up_user(request: Request):
    _at_step(request, "user")
    fields = await form_fields(request)
    problem = _details_problem(fields)
    if problem:
        return refuse(request, STEP_PAGE["user"], "save", problem)
    parts(request).users.set_up(fields.get("title", ""), fields["name"], fields["password"])
    raise Redirect("/login?why=set_up")


def _details_problem(fields: dict[str, str]) -> str | None:
    if name_problem(fields.get("name", "")):
        return words.NAME_MISSING
    return _password_sentence(fields.get("password", ""), fields.get("password_again", ""))


def _password_sentence(password: str, again: str) -> str | None:
    problem = password_problem(password, again)
    if problem == "short":
        return words.PASSWORD_SHORT.format(least=MIN_PASSWORD)
    if problem == "differ":
        return words.PASSWORDS_DIFFER
    return None


# ----------------------------------------------------------- login, logout

@router.get("/login", dependencies=[Depends(guards.first_run_done)])
async def login_page(request: Request):
    why = request.query_params.get("why", "plain")
    return render(request, "login.html", why=words.WHY.get(why, words.WHY["plain"]))


@router.post("/login", dependencies=[Depends(guards.first_run_done)])
async def login(request: Request):
    p = parts(request)
    fields = await form_fields(request)
    wait = p.logins.wait_left()
    if wait:
        return _login_refusal(request, words.NOT_YET.format(wait=words.plain_time(wait)))
    if not p.users.verify(fields.get("password", "")):
        wait = p.logins.wrong_password()
        return _login_refusal(request, words.WRONG_PASSWORD.format(wait=words.plain_time(wait)))
    p.logins.right_password()
    token = p.logins.start(p.users.get().generation)
    p.audit.record("login")
    response = RedirectResponse("/", status_code=303)
    # No expiry, so the cookie lasts only for the browser session (15.6).
    response.set_cookie(guards.COOKIE, token, httponly=True, samesite="strict")
    return response


def _login_refusal(request: Request, message: str):
    return refuse(request, "login.html", "login", message, why=words.WHY["plain"])


@router.post("/logout")
async def logout(request: Request):
    p = parts(request)
    token = request.cookies.get(guards.COOKIE)
    if token in p.logins.tokens():
        p.audit.record("logout")
    p.logins.end(token)
    raise Redirect("/login?why=logged_out", clear_login=True)


# ---------------------------------------------------------------- settings

NOTICE = {"you": words.SAVED, "password": words.PASSWORD_CHANGED}


def _settings_page(request: Request, user, refused=None):
    context = dict(user=user, active="settings", machine=parts(request).machine,
                   least=MIN_PASSWORD, notice=NOTICE.get(request.query_params.get("done", "")),
                   page_path="/settings")
    if refused:
        return refuse(request, "settings.html", refused[0], refused[1], **context)
    return render(request, "settings.html", **context)


@router.get("/settings")
async def settings_page(request: Request, user=Depends(guards.logged_in)):
    return _settings_page(request, user)


def _current_password_refusal(request: Request, fields: dict[str, str]) -> str | None:
    """A wrong current password in Settings is a wrong password: it is
    written to the log and it makes the next try wait longer, on the same
    counter as the login page, so nobody at an unlocked screen can guess
    without limit (STAGE_02_FIXES, fix 2; spec 15.6)."""
    p = parts(request)
    wait = p.logins.wait_left()
    if wait:
        return words.NOT_YET.format(wait=words.plain_time(wait))
    if not p.users.verify(fields.get("current_password", "")):
        wait = p.logins.wrong_password()
        return words.WRONG_PASSWORD_NOTHING_CHANGED.format(wait=words.plain_time(wait))
    p.logins.right_password()
    return None


@router.post("/settings/you")
async def change_you(request: Request, user=Depends(guards.logged_in)):
    """Title and name. Asks for the current password first (ruling 7)."""
    p = parts(request)
    fields = await form_fields(request)
    refusal = _current_password_refusal(request, fields)
    if refusal:
        return _settings_page(request, user, ("save-you", refusal))
    if name_problem(fields.get("name", "")):
        return _settings_page(request, user, ("save-you", words.NAME_MISSING))
    p.users.change_details(fields.get("title", ""), fields["name"])
    raise Redirect("/settings?done=you")


@router.post("/settings/password")
async def change_password(request: Request, user=Depends(guards.logged_in)):
    p = parts(request)
    fields = await form_fields(request)
    refusal = _current_password_refusal(request, fields)
    if refusal:
        return _settings_page(request, user, ("change-password", refusal))
    problem = password_problem(fields.get("new_password", ""), fields.get("new_password_again", ""))
    if problem == "short":
        return _settings_page(request, user, ("change-password", words.NEW_PASSWORD_SHORT.format(least=MIN_PASSWORD)))
    if problem == "differ":
        return _settings_page(request, user, ("change-password", words.NEW_PASSWORDS_DIFFER))
    changed = p.users.change_password(fields["new_password"])
    p.logins.renew(request.cookies.get(guards.COOKIE), changed.generation)
    raise Redirect("/settings?done=password")


# --------------------------------------------------------------------- log

@router.get("/log")
async def log_page(request: Request, user=Depends(guards.logged_in)):
    rows = [
        {"when": line.at[:19].replace("T", " "),
         "what": words.EVENTS.get(line.event, line.event),
         "details": line.detail or ""}
        for line in parts(request).audit.lines()
    ]
    return render(request, "log.html", user=user, active="log", rows=rows)
