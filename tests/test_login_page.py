"""Logging in and out through the pages (spec 7.1, 15.6; ruling 5; R15)."""

import pytest

from openconsult import words
from openconsult.patients.logins import LOCK_AFTER
from tests.conftest import PASSWORD, browser, log_in, refusal_on, set_up


def test_7_1_the_password_is_asked_each_time_the_app_is_opened(client, app):
    set_up(client)
    assert client.get("/").headers["location"] == "/login"
    log_in(client)
    assert client.get("/").status_code == 200
    again = browser(app)  # a new browser session has no cookie
    assert again.get("/").headers["location"] == "/login"


def test_r15_a_wrong_password_is_said_on_the_control_and_audited(client, app):
    set_up(client)
    refused = log_in(client, "not-the-password")
    assert refused.status_code == 400
    assert refusal_on(refused.text, "login") == words.WRONG_PASSWORD.format(wait=words.plain_time(1))
    assert app.state.parts.audit.lines()[0].event == "login.wrong_password"
    # The next try must wait, even with the right password.
    too_soon = log_in(client)
    assert refusal_on(too_soon.text, "login") == words.NOT_YET.format(wait=words.plain_time(1))
    assert client.get("/").headers["location"] == "/login"


@pytest.mark.parametrize("why", list(words.WHY) + ["something-else"])
def test_15_6_the_login_page_says_why_it_asks(client, why):
    set_up(client)
    page = client.get(f"/login?why={why}")
    assert page.status_code == 200
    assert words.WHY.get(why, words.WHY["plain"]) in page.text


def test_15_6_logout_ends_the_login_and_is_audited(logged_in, app):
    out = logged_in.post("/logout")
    assert out.status_code == 303 and out.headers["location"] == "/login?why=logged_out"
    assert logged_in.get("/").headers["location"] == "/login"
    assert app.state.parts.audit.lines()[0].event == "logout"


def test_ruling_5_a_page_locks_itself_and_the_lock_is_audited(logged_in, app, clock):
    # Pins ruling 5 as the plan review's change 2 reads it: a page left
    # open moves to the login page by itself once the 30 minutes pass,
    # the move is not use, and the lock is written when the screen locks.
    seconds = int(LOCK_AFTER.total_seconds())
    page = logged_in.get("/")
    assert f'content="{seconds + 1};url=/?quiet"' in page.text
    clock.advance(seconds=seconds)
    moved = logged_in.get("/?quiet")
    assert moved.status_code == 303 and moved.headers["location"] == "/login?why=locked"
    assert app.state.parts.audit.lines()[0].event == "lock"
    assert words.WHY["locked"] in logged_in.get("/login?why=locked").text


def test_ruling_5_a_login_in_use_elsewhere_keeps_the_page_waiting(logged_in, app, clock):
    # The twin: another tab used the login, so the page stays, waits the
    # time left, and the timed check itself never pushes the lock back.
    seconds = int(LOCK_AFTER.total_seconds())
    clock.advance(minutes=20)
    assert logged_in.get("/").status_code == 200  # use, from another tab
    clock.advance(minutes=10)
    stayed = logged_in.get("/?quiet")
    assert stayed.status_code == 200
    assert f'content="{seconds - 10 * 60 + 1};url=/?quiet"' in stayed.text
    clock.advance(minutes=10)
    assert logged_in.get("/?quiet").status_code == 200
    clock.advance(minutes=10)
    assert logged_in.get("/?quiet").headers["location"] == "/login?why=locked"


def test_15_6_the_cookie_lasts_only_for_the_browser_session(client):
    set_up(client)
    cookie = log_in(client).headers["set-cookie"].lower()
    assert "max-age" not in cookie and "expires" not in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie
