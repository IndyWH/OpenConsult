"""Why this model (spec 15.13, rulings 21 and 30; the details of run 9b):
the short account of the choice of Claude Haiku, held byte for byte as
the owner's side approved it, read only."""

from __future__ import annotations

import hashlib

from openconsult.web import cloud
from tests.conftest import browser, text_of

# The sha256 of the account as Cowork wrote it for the run of 9b (15 Nov 2026): the file in the app is those bytes.
APPROVED_SHA256 = "ba7df9b6925ac9335ba3ffb048a00a933aceaed0b148e2431f8a9e8ea9a94283"


def test_15_13_ruling_30_the_page_holds_the_short_account_byte_for_byte_and_nothing_on_it_acts(logged_in, app):
    assert hashlib.sha256(cloud.WHY_THIS_MODEL.read_bytes()).hexdigest() == APPROVED_SHA256
    title, paragraphs = cloud.account()
    assert title == "Why Claude Haiku" and len(paragraphs) == 8
    before = len(app.state.parts.audit.lines())
    answer = logged_in.get("/why-this-model")
    page = text_of(answer)
    assert answer.status_code == 200 and f"<h1 class=\"page\">{title}</h1>" in answer.text
    assert all(paragraph in page for paragraph in paragraphs)                     # every paragraph, word for word
    main = answer.text.split("<main", 1)[1].split("</main>", 1)[0]
    assert "<form" not in main and "<button" not in main and "<script" not in main
    assert len(app.state.parts.audit.lines()) == before                           # read only: nothing written


def test_15_6_the_account_is_behind_the_login_and_during_the_first_run_it_is_read_from_this_computer_alone(app):
    fresh = browser(app)
    assert fresh.get("/why-this-model").status_code == 200                        # the first run shows the connect screen, and its line
    assert browser(app, address="203.0.113.5").get("/why-this-model").status_code == 403
    from tests.conftest import set_up
    set_up(fresh)
    assert browser(app).get("/why-this-model").headers["location"] == "/login"   # after it, the login as every page
