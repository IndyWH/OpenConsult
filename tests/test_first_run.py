"""The first run: the statement, This machine, the user, in that order
(spec 7.1, 15.6 ruling 4, D20)."""

import pytest

from openconsult import words
from openconsult.patients.users import MIN_PASSWORD
from tests.conftest import PASSWORD, browser, refusal_on, set_up, text_of


def test_ruling_4_every_page_leads_to_the_statement_before_set_up(client):
    for path in ("/", "/login"):
        response = client.get(path)
        assert response.status_code == 303 and response.headers["location"] == "/first-run", path
    page = client.get("/first-run")
    assert page.status_code == 200
    assert words.STATEMENT_TICK in page.text


def test_ruling_4_no_user_can_be_set_up_before_the_statement(client, app):
    response = client.post(
        "/first-run/user",
        data={"title": "Dr", "name": "Example", "password": PASSWORD, "password_again": PASSWORD},
    )
    assert response.status_code == 303 and response.headers["location"] == "/first-run"
    assert not app.state.parts.users.exists()
    assert client.get("/login").status_code == 303


def test_ruling_4_accepting_the_statement_needs_the_tick_and_is_audited(client, app):
    refused = client.post("/first-run/statement", data={})
    assert refused.status_code == 400
    assert refusal_on(refused.text, "continue") == words.TICK_TO_CONTINUE
    assert app.state.parts.audit.lines() == []
    accepted = client.post("/first-run/statement", data={"agree": "yes"})
    assert accepted.status_code == 303
    assert app.state.parts.audit.lines()[0].event == "statement.accepted"


def test_15_6_the_first_run_resumes_at_the_first_step_not_done(app, machine):
    first = browser(app)
    first.post("/first-run/statement", data={"agree": "yes"})
    second = browser(app)  # the browser was closed and opened again
    page = second.get("/first-run")
    assert machine.sentence in text_of(page) and words.STATEMENT_TICK not in page.text
    second.post("/first-run/machine", data={})
    third = browser(app)
    page = third.get("/first-run")
    assert words.FIRST_RUN_USER_INTRO in page.text


def test_d20_set_up_refuses_a_request_not_from_this_computer(app):
    # Pins D20: the second guard, in case the first (listening on this
    # computer only) were ever opened by mistake.
    elsewhere = browser(app, address="203.0.113.5")
    here = browser(app)
    assert elsewhere.post("/first-run/statement", data={"agree": "yes"}).status_code == 403
    here.post("/first-run/statement", data={"agree": "yes"})
    assert elsewhere.post("/first-run/machine", data={}).status_code == 403
    here.post("/first-run/machine", data={})
    fields = {"title": "Dr", "name": "Example", "password": PASSWORD, "password_again": PASSWORD}
    assert elsewhere.post("/first-run/user", data=fields).status_code == 403
    assert not app.state.parts.users.exists()
    assert here.post("/first-run/user", data=fields).status_code == 303


BAD_FIELDS = [
    ({"name": "", "password": PASSWORD, "password_again": PASSWORD}, words.NAME_MISSING),
    ({"name": "Example", "password": "seven77", "password_again": "seven77"},
     words.PASSWORD_SHORT.format(least=MIN_PASSWORD)),
    ({"name": "Example", "password": PASSWORD, "password_again": PASSWORD + "x"}, words.PASSWORDS_DIFFER),
]


@pytest.mark.parametrize("fields, message", BAD_FIELDS)
def test_15_6_set_up_needs_a_name_and_the_same_password_twice(client, app, fields, message):
    client.post("/first-run/statement", data={"agree": "yes"})
    client.post("/first-run/machine", data={})
    refused = client.post("/first-run/user", data={"title": "", **fields})
    assert refused.status_code == 400
    assert refusal_on(refused.text, "save") == message
    assert not app.state.parts.users.exists()


def test_15_6_after_set_up_the_first_run_is_over(client, app):
    # The title may be empty, for a learner who has none.
    done = set_up(client, title="", name="Example")
    assert done.status_code == 303 and done.headers["location"] == "/login?why=set_up"
    assert client.get("/first-run").headers["location"] == "/login"
    assert client.get("/login").status_code == 200
    user = app.state.parts.users.get()
    assert user.title == "" and user.full_name == "Example"
    assert app.state.parts.audit.lines()[0].event == "user.set_up"
