"""The settings page: This machine, and You (spec 7.3; 15.6 ruling 7)."""

from openconsult import words
from openconsult.patients.users import MIN_PASSWORD
from tests.conftest import PASSWORD, browser, log_in, refusal_on, text_of


def change_you(client, title="Dr", name="Sample", current=PASSWORD):
    return client.post("/settings/you", data={"title": title, "name": name, "current_password": current})


def test_ruling_7_changing_your_details_asks_for_the_current_password(logged_in, app, clock):
    refused = change_you(logged_in, current="not-it")
    assert refused.status_code == 400
    assert refusal_on(refused.text, "save-you") == words.WRONG_PASSWORD_NOTHING_CHANGED.format(wait=words.plain_time(1))
    assert app.state.parts.users.get().name == "Example"
    clock.advance(seconds=1)
    refused = change_you(logged_in, name="")
    assert refusal_on(refused.text, "save-you") == words.NAME_MISSING
    assert app.state.parts.users.get().name == "Example"


def test_ruling_7_a_change_of_title_or_name_is_audited_from_what_to_what(logged_in, app):
    done = change_you(logged_in, title="Professor", name="Sample")
    assert done.status_code == 303 and done.headers["location"] == "/settings?done=you"
    assert words.SAVED in logged_in.get("/settings?done=you").text
    assert app.state.parts.users.get().full_name == "Professor Sample"
    events = [(line.event, line.detail) for line in app.state.parts.audit.lines()[:2]]
    assert ("name.changed", "from Example to Sample") in events
    assert ("title.changed", "from Dr to Professor") in events
    # Change it back: the log shows that too, and the page shows the new value.
    change_you(logged_in, title="Dr", name="Example")
    assert app.state.parts.audit.lines()[0].detail == "from Sample to Example"
    assert 'value="Example"' in logged_in.get("/settings").text


def change_password(client, current=PASSWORD, new="second-password", again=None):
    return client.post("/settings/password", data={
        "current_password": current, "new_password": new,
        "new_password_again": new if again is None else again,
    })


def test_ruling_7_changing_the_password_needs_the_current_one_and_the_new_one_twice(logged_in, app, clock):
    cases = [
        (dict(current="not-it"), words.WRONG_PASSWORD_NOTHING_CHANGED.format(wait=words.plain_time(1))),
        (dict(new="seven77"), words.NEW_PASSWORD_SHORT.format(least=MIN_PASSWORD)),
        (dict(again="second-passwor"), words.NEW_PASSWORDS_DIFFER),
    ]
    for fields, message in cases:
        clock.advance(seconds=1)
        refused = change_password(logged_in, **fields)
        assert refusal_on(refused.text, "change-password") == message
    assert app.state.parts.users.verify(PASSWORD)
    other = browser(app)
    log_in(other)
    assert other.get("/").status_code == 200
    done = change_password(logged_in)
    assert done.headers["location"] == "/settings?done=password"
    assert words.PASSWORD_CHANGED in logged_in.get("/settings?done=password").text
    assert app.state.parts.users.verify("second-password")
    assert app.state.parts.audit.lines()[0].event == "password.changed"
    # Every other login has ended; this one carries on.
    assert other.get("/").headers["location"] == "/login?why=ended"
    assert logged_in.get("/").status_code == 200


def test_15_6_the_settings_page_shows_this_machine(logged_in, machine):
    page = text_of(logged_in.get("/settings"))
    assert machine.system in page and machine.card_line in page and machine.sentence in page


def test_15_6_a_wrong_current_password_in_settings_is_logged_and_makes_the_next_try_wait(logged_in, app, clock):
    # Pins STAGE_02_FIXES fix 2 and spec 15.6: each wrong password is in
    # the log, and the wait grows on the same counter as the login page.
    wrong = change_you(logged_in, current="not-it")
    assert app.state.parts.audit.lines()[0].event == "login.wrong_password"
    assert refusal_on(wrong.text, "save-you") == words.WRONG_PASSWORD_NOTHING_CHANGED.format(wait=words.plain_time(1))
    # While the wait runs, both forms refuse on their own control, even with the right password.
    too_soon = change_you(logged_in)
    assert refusal_on(too_soon.text, "save-you") == words.NOT_YET.format(wait=words.plain_time(1))
    too_soon = change_password(logged_in)
    assert refusal_on(too_soon.text, "change-password") == words.NOT_YET.format(wait=words.plain_time(1))
    assert app.state.parts.users.get().name == "Example" and app.state.parts.users.verify(PASSWORD)
    # The counter is shared with the login page: a second wrong try there waits longer.
    clock.advance(seconds=1)
    second = change_password(logged_in, current="still-not-it")
    assert refusal_on(second.text, "change-password") == words.WRONG_PASSWORD_NOTHING_CHANGED.format(wait=words.plain_time(2))
    clock.advance(seconds=2)
    at_login = log_in(browser(app), "nope")
    assert refusal_on(at_login.text, "login") == words.WRONG_PASSWORD.format(wait=words.plain_time(4))
    # A right current password clears the counter.
    clock.advance(seconds=4)
    assert change_you(logged_in, name="Sample").status_code == 303
    clock.advance(seconds=1)
    again = change_you(logged_in, current="not-it")
    assert refusal_on(again.text, "save-you") == words.WRONG_PASSWORD_NOTHING_CHANGED.format(wait=words.plain_time(1))
