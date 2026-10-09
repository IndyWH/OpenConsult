"""This machine's two lines about the speech choice (spec 15.9): on a
suitable card only, read from the data folder and the stored result,
with no worker started and no model loaded."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.speech.choices import WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from openconsult.speech.selftest import Outcome, SelfTests
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import MadeUpWorker
from tests.test_machine_status import MAC, SMALLER, SUITABLE

STATES = ["not_installed", "not_run", "passed", "failed"]
EXPECTED = {
    "not_installed": (words.SPEECH_NOT_INSTALLED, words.SELF_TEST_NOT_POSSIBLE),
    "not_run": (words.SPEECH_INSTALLED, words.SELF_TEST_NOT_RUN),
    "passed": (words.SPEECH_INSTALLED, words.SELF_TEST_PASSED.format(date="4 Oct 2026", time="09:00")),
    "failed": (words.SPEECH_INSTALLED, words.SELF_TEST_FAILED.format(date="4 Oct 2026", time="09:00",
                                                                     reason="made-up reason")),
}


def app_in(tmp_path, clock, machine, state, worker):
    installed = state != "not_installed"
    door = Door(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: installed)
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, speech=door)
    if state in ("passed", "failed"):
        outcome = Outcome(state == "passed", None if state == "passed" else "made-up reason", [], [], {})
        SelfTests(app.state.parts.db, clock).add("whisperx_pyannote", outcome)
    return app


@pytest.mark.parametrize("state", STATES)
def test_15_9_this_machine_says_whether_the_choice_is_installed_and_the_last_self_test(tmp_path, clock, state):
    worker = MadeUpWorker()
    app = app_in(tmp_path, clock, SUITABLE, state, worker)
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    installed_line, self_test_line = EXPECTED[state]
    for page in (first_run, settings):
        assert words.ROW_SPEECH in page and installed_line in page and self_test_line in page
    assert worker.starts == 0 and worker.requests == []        # nothing started, nothing loaded


def test_15_9_the_newest_self_test_is_the_one_shown(tmp_path, clock):
    app = app_in(tmp_path, clock, SUITABLE, "failed", MadeUpWorker())
    clock.advance(hours=1)
    SelfTests(app.state.parts.db, clock).add("whisperx_pyannote", Outcome(True, None, [], [], {}))
    client = browser(app)
    set_up(client)
    log_in(client)
    page = text_of(client.get("/settings"))
    assert words.SELF_TEST_PASSED.format(date="4 Oct 2026", time="10:00") in page
    assert "made-up reason" not in page


@pytest.mark.parametrize("machine", [SMALLER, MAC])
def test_15_9_on_any_other_machine_nothing_about_speech_is_shown(tmp_path, clock, machine):
    app = app_in(tmp_path, clock, machine, "passed", MadeUpWorker())
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    for page in (first_run, settings):
        assert words.ROW_SPEECH not in page and words.ROW_SELF_TEST not in page
        assert words.SPEECH_INSTALLED not in page and words.SELF_TEST_PASSED[:6] not in page
