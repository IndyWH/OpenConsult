"""The pages (spec 15.6): the first run, login and logout, home."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from openconsult import words
from openconsult.patients import patients as patients_module
from openconsult.patients.users import MIN_PASSWORD, name_problem, password_problem
from openconsult.settings import thresholds
from openconsult.settings.stored import DEFAULT_RETENTION_DAYS, retention_problem
from openconsult.settings.connections import SERVICES
from openconsult.settings.path import CLAUDE
from openconsult.web import cloud as cloud_web, guards, guidelines as guidelines_web, panel as panel_web, settings_local, steps as steps_web
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()


def room_lines(request: Request) -> list[tuple[str, str]]:
    """The rows of the small table under the picture of This machine
    (15.13, the details of run 9c): what the boxes do not say. Where the
    guideline search sits (15.8, rulings 32 and 36), on a suitable card
    only; and the recording converter (15.11 ruling 7), on every
    machine. From the decisions held since start: nothing is asked at a
    view. What a box says, the language model and its engine, the speech
    models and each connection, is not said a second time here."""
    p = parts(request)
    found = [(words.ROW_GUIDELINE_SEARCH, p.decisions.guideline_search.sentence)] if p.machine.case == "suitable" else []
    return found + [(words.ROW_CONVERTER, p.decisions.converter.sentence)]


@router.get("/")
async def home(request: Request, user=Depends(guards.logged_in)):
    """The home page is the Patients page (15.11 ruling 1; 8.1; R1): at
    the top each consultation waiting at Stop with one control, Continue
    (review point 3; R15), and each final consultation with no approved
    note, once, with one control, Review (6b); then the search box; then
    the list, last seen first, read from the tables every time."""
    p = parts(request)
    waiting = [{"id": row["id"], "line": words.HOME_WAITING_LINE.format(
        name=row["patient_name"], when=row["started_at"][:16].replace("T", " "))}
        for row in p.consultations.in_state("stopping")]
    review = [{"id": row["id"], "line": words.HOME_WAITING_LINE.format(
        name=row["patient_name"], when=row["started_at"][:16].replace("T", " "))}
        for row in p.consultations.waiting_for_review()]
    query = request.query_params.get("q", "").strip()
    found = patients_module.search(p.patients.listed(), query)
    rows = [{"id": r.patient.id, "name": r.patient.name, "born": words.plain_date(r.patient.date_of_birth),
             "sex": words.SEX_WORDS[r.patient.sex],
             "seen": words.plain_date(r.last_seen) if r.last_seen else words.NEVER_SEEN} for r in found]
    deleted = request.query_params.get("deleted", "")
    return render(request, "patients.html", user=user, active="home", waiting=waiting, review=review,
                  query=query, rows=rows, none_found=words.SEARCH_NONE.format(query=query) if query and not rows else None,
                  notice=words.PATIENT_DELETED.format(id=deleted) if deleted.isdigit() else None)


# ------------------------------------------------------------ the first run

STEP_PAGE = {
    "statement": "first_run_statement.html",
    "machine": "first_run_machine.html",
    "user": "first_run_user.html",
}


@router.get("/first-run")
async def first_run(request: Request):
    """The walk (7.1): the statement, This machine, then each step between
    them and the user that is needed and not yet met, then the user. A
    data folder that has its user meets the steps that are new to it
    here, once, behind its login."""
    p = parts(request)
    step = p.first_run.next_step()
    if step in (None, "user"):
        user = guards.logged_in(request) if step is None else None      # no user yet: from this computer; a user: the login
        if step == "user":
            guards.this_computer(request)
        middle = steps_web.walk_step(p)
        if middle is not None:
            return steps_web.step_page(request, user, middle)
        if step is None:
            raise Redirect("/")
    at_machine = step == "machine"
    # Step 2 shows the same picture as Settings (15.13, ruling 56); there is no user yet, so no box offers Choose.
    return render(request, STEP_PAGE[step], machine=parts(request).machine, room=room_lines(request) if at_machine else [],
                  panel=panel_web.build(p, first_run=True) if at_machine else None,
                  pointer=pointer(request) if at_machine else None, least=MIN_PASSWORD)


def pointer(request: Request) -> str | None:
    """Where no local model runs and no cloud model is connected, This
    machine says so and leads to the connect screen (15.8, ruling 37)."""
    p = parts(request)
    local = p.machine.case == "suitable" and p.decisions.start_offered
    return None if local or p.connections.state(CLAUDE).has_key else words.POINTER_TO_CONNECT


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
    # A set-up step this data folder has not met yet is met once, at the login (7.1; the details of 9b).
    response = RedirectResponse("/first-run" if steps_web.walk_step(p) is not None else "/", status_code=303)
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

NOTICE = {"you": words.SAVED, "password": words.PASSWORD_CHANGED, "retention": words.RETENTION_SAVED,
          "tested": words.CONNECTED, "removed": words.KEY_REMOVED, "path": words.PATH_SAVED, "ticked": words.SAVED}


def _settings_page(request: Request, user, refused=None, pending=None, from_panel: bool = False):
    """pending: a change of the path that waits for its tick, drawn in its
    own section with the statement of the path as it would then stand.
    from_panel: the change was pressed in the picture at the top."""
    context = dict(user=user, active="settings", machine=parts(request).machine,
                   # The picture of This machine, with the small table of what its boxes do not say (15.13, ruling 56).
                   panel=panel_web.build(parts(request)), room=room_lines(request), pointer=pointer(request),
                   # A choice pressed in the picture that waits for its statement: the page goes to it by itself.
                   go_to=f"not-saved-{pending['which']}" if pending and from_panel else None,
                   least=MIN_PASSWORD, notice=NOTICE.get(request.query_params.get("done", "")),
                   # Saved is said beside the control that was changed, and only there (15.13, ruling 47).
                   done=request.query_params.get("done", ""),
                   saved_at=request.query_params.get("at") if request.query_params.get("done") in ("path", "less") else None,
                   # A path saved under a wider tick shows what leaves now (ruling 48): under its control right after
                   # the save, and on later views where a statement to tick would stand.
                   less_at=request.query_params.get("at") if request.query_params.get("done") == "less" else None,
                   covered=None if pending else cloud_web.covered_view(parts(request)),
                   retention_days=parts(request).stored.audio_retention_days, retention_default=DEFAULT_RETENTION_DAYS,
                   thresholds=thresholds_view(parts(request)),
                   guidelines=guidelines_web.section_data(request), page_path="/settings",
                   connections=[cloud_web.connection_view(parts(request), service) for service in SERVICES],
                   path_sections=cloud_web.path_sections(parts(request), pending),
                   better_accuracy=cloud_web.better_accuracy_view(parts(request), pending),
                   speech_model=settings_local.speech_model_view(parts(request)),
                   local_models=settings_local.local_models(parts(request)),
                   to_tick=None if pending else cloud_web.statement_view(parts(request), "/settings"))
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


@router.post("/settings/retention")
async def change_retention(request: Request, user=Depends(guards.logged_in)):
    """The retention days (15.11 ruling 7; 7.3): a whole number from 0 up,
    0 keeps; audited from what to what; read by the next sweep."""
    p = parts(request)
    fields = await form_fields(request)
    days = retention_problem(fields.get("days", ""))
    if days is None:
        return _settings_page(request, user, ("save-retention", words.RETENTION_BAD))
    p.stored.set_audio_retention_days(days)
    raise Redirect("/settings?done=retention")


def thresholds_view(p) -> dict:
    """The two thresholds of the gate as Settings shows them (7.3): each
    with its value, its default and its bounds, the score with two places."""
    t = thresholds
    return {"fewest_words": {"value": p.stored.fewest_words, "default": t.FEWEST_WORDS_DEFAULT,
                             "low": t.FEWEST_WORDS_LOW, "high": t.FEWEST_WORDS_HIGH},
            "low_score": {"value": f"{p.stored.low_score:.2f}", "default": f"{t.LOW_SCORE_DEFAULT:.2f}",
                          "low": f"{t.LOW_SCORE_LOW:.2f}", "high": f"{t.LOW_SCORE_HIGH:.2f}"}}


@router.post("/settings/fewest-words")
async def change_fewest_words(request: Request, user=Depends(guards.logged_in)):
    """The fewest words a note is drafted from (7.3; the details of run
    9c): a whole number within the owner's bounds, refused on the control
    outside them; audited from what to what; taken by a consultation at
    its Start and held there, so one that has begun is not touched."""
    p = parts(request)
    fields = await form_fields(request)
    number = thresholds.fewest_words_of(fields.get("words", ""))
    if number is None:
        view = thresholds_view(p)["fewest_words"]
        return _settings_page(request, user, ("save-fewest-words", words.FEWEST_WORDS_BAD.format(**view)))
    p.stored.set_fewest_words(number)
    # With no script the page comes back at the field; the page's script keeps the window's place itself (ruling 47).
    raise Redirect("/settings?done=fewest-words" + ("" if fields.get("place") == "keep" else "#fewest-words"))


@router.post("/settings/low-score")
async def change_low_score(request: Request, user=Depends(guards.logged_in)):
    """The score under which a line is marked as low confidence: as the
    fewest words, a number of at most two places."""
    p = parts(request)
    fields = await form_fields(request)
    score = thresholds.low_score_of(fields.get("score", ""))
    if score is None:
        view = thresholds_view(p)["low_score"]
        return _settings_page(request, user, ("save-low-score", words.LOW_SCORE_BAD.format(**view)))
    p.stored.set_low_score(score)
    raise Redirect("/settings?done=low-score" + ("" if fields.get("place") == "keep" else "#low-score"))


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
