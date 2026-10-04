"""The two guards at the door (spec 15.6: other web pages cannot drive
the app)."""

import pytest

from openconsult import words
from tests.conftest import ORIGIN, PASSWORD, browser, set_up

HOSTS = [
    ("127.0.0.1:8765", 200),
    ("localhost:8765", 200),
    ("[::1]:8765", 200),
    ("127.0.0.1:8001", 421),
    ("example.test:8765", 421),
    ("", 421),
]


@pytest.mark.parametrize("host, status", HOSTS)
def test_15_6_the_app_answers_only_when_addressed_as_this_computer(client, host, status):
    response = client.get("/first-run", headers={"host": host})
    assert response.status_code == status
    if status == 421:
        assert words.WRONG_HOST.format(address=ORIGIN) in response.text


def test_15_6_a_change_must_come_from_the_apps_own_pages(app):
    from_elsewhere = browser(app, origin="http://evil.test")
    assert from_elsewhere.post("/first-run/statement", data={"agree": "yes"}).status_code == 403
    no_origin = browser(app)
    no_origin.headers.pop("Origin")
    assert no_origin.post("/first-run/statement", data={"agree": "yes"}).status_code == 403
    assert app.state.parts.audit.lines() == []
    assert browser(app).post("/first-run/statement", data={"agree": "yes"}).status_code == 303
