"""What every page carries (R1), and the refusal helper's twin (R15)."""

import pytest

from openconsult import words
from openconsult.web.pages import LostRefusal, refuse
from tests.conftest import PASSWORD, log_in, set_up


def test_r1_every_page_carries_the_statement(client):
    # The standing statement is on every page, in the words given.
    assert words.STATEMENT in client.get("/first-run").text
    set_up(client)
    assert words.STATEMENT in client.get("/login").text
    log_in(client)
    for path in ("/", "/settings", "/log"):
        page = client.get(path)
        assert page.status_code == 200, path
        assert words.STATEMENT in page.text, path
    assert words.HOME_SO_FAR in client.get("/").text


def test_r15_a_refusal_for_a_control_the_page_does_not_have_is_never_lost(client):
    # The twin: a message that would land nowhere raises instead of
    # vanishing (V1_LESSONS 5.1: four swallowed actions in a week).
    set_up(client)
    request = client.build_request("GET", "/login")

    class FakeRequest:
        url = request.url
        state = type("State", (), {})()

    with pytest.raises(LostRefusal):
        refuse(FakeRequest(), "login.html", "no-such-control", "a message", why="")
    shown = refuse(FakeRequest(), "login.html", "login", "a message", why="")
    assert shown.status_code == 400 and "a message" in shown.body.decode()


def test_15_6_the_log_page_lists_the_newest_first_and_is_read_only(logged_in, app):
    logged_in.post("/settings/you", data={"title": "Dr", "name": "Sample", "current_password": PASSWORD})
    page = logged_in.get("/log").text
    events = [words.EVENTS[e] for e in ("name.changed", "login", "user.set_up", "statement.accepted")]
    positions = [page.index(event) for event in events]
    assert positions == sorted(positions)
    assert "from Example to Sample" in page
    assert logged_in.post("/log", data={}).status_code == 405
    assert len(app.state.parts.audit.lines()) == 4
