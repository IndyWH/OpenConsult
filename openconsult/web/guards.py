"""The guards (spec 15.6, D20).

Two at the door, for every request: the app answers only when addressed
as this computer, and a request that changes anything must come from
its own pages. Two more on routes: the first run must be done, and a
page behind the login needs a live login. Set-up also refuses any
request not from this computer.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from openconsult import words

COOKIE = "openconsult_login"
LOOPBACK = ("127.0.0.1", "::1")

# What the login page is told when a login has ended (R15: the page
# says why it asks).
WHY_FOR = {"locked": "locked", "password_changed": "password_changed", "unknown": "ended"}


class Redirect(Exception):
    def __init__(self, url: str, clear_login: bool = False):
        self.url = url
        self.clear_login = clear_login


class NotThisComputer(Exception):
    pass


def install(app: FastAPI, port: int, address: str) -> None:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    origins = {f"http://{host}" for host in hosts}

    @app.middleware("http")
    async def door(request: Request, call_next):
        if request.headers.get("host", "") not in hosts:
            return PlainTextResponse(words.WRONG_HOST.format(address=address), status_code=421)
        if request.method not in ("GET", "HEAD") and request.headers.get("origin") not in origins:
            return PlainTextResponse(words.WRONG_ORIGIN, status_code=403)
        return await call_next(request)

    @app.exception_handler(Redirect)
    async def redirect(request: Request, exc: Redirect):
        response = RedirectResponse(exc.url, status_code=303)
        if exc.clear_login:
            response.delete_cookie(COOKIE)
        return response

    @app.exception_handler(NotThisComputer)
    async def not_this_computer(request: Request, exc: NotThisComputer):
        return PlainTextResponse(words.NOT_THIS_COMPUTER, status_code=403)


def parts(request: Request):
    return request.app.state.parts


def first_run_done(request: Request) -> None:
    if parts(request).first_run.next_step() is not None:
        raise Redirect("/first-run")


def this_computer(request: Request) -> None:
    """The second guard of D20: set-up refuses a request that did not
    come from this computer, even if the first guard were ever opened."""
    if request.client is None or request.client.host not in LOOPBACK:
        raise NotThisComputer()


def logged_in(request: Request):
    """The user, for a page behind the login. A request with ?quiet is
    the page's own timed check and is not use (plan review, change 2)."""
    first_run_done(request)
    p = parts(request)
    token = request.cookies.get(COOKIE)
    if token is None:
        raise Redirect("/login")
    user = p.users.get()
    found = p.logins.find(token, user.generation, touch="quiet" not in request.query_params)
    if found.login is None:
        raise Redirect(f"/login?why={WHY_FOR[found.reason]}", clear_login=True)
    request.state.seconds_left = p.logins.seconds_left(found.login)
    return user
