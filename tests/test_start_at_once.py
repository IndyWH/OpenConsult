"""The Start screen is shown at once, and its connection tests fill in
after (spec 15.13, ruling 51, with ruling 37; 7.2; R15; the details of
run 9c; Cowork's review of the plan, point f). In run 9b the screen
showed nothing until its tests had answered: about 2 seconds, 10 when a
service did not answer. The rule that a consultation never begins on a
connection that is down is kept by the app, not by the page alone.
Made tests of each connection; no real service."""

from __future__ import annotations

import re
import threading

from openconsult import words
from openconsult.settings import connections
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from openconsult.web import start_tests
from tests.conftest import refusal_on, text_of
from tests.test_cloud_consultation import cloud_app, disabled_on
from tests.test_connect_screens import SUITABLE, MadeTesters
from tests.test_start import TICKS
from tests.test_stop import until

START = "/consultations/start/1"
TESTING = "Testing the connection. Start is offered when the test has answered."
STILL = "Start is not offered yet: the connection is still being tested."
DOWN = "Start is not offered: Speechmatics could not be reached. Check the internet connection and try again."


def run_of(page: str) -> str:
    """The run of tests the page names, as its form will send it."""
    return re.search(r'<input type="hidden" name="tests" value="(\d+)">', page).group(1)


def answer_of_tests(client, page: str) -> dict:
    """What the page's script reads: the result of the tests that run
    beside this view, asked again until they have answered."""
    address = re.search(r'id="start-tests" data-address="([^"]+)"', page).group(1)
    found = {}

    def answered() -> bool:
        found.update(client.get(address).json())
        return found["state"] != "running"
    assert until(answered)
    return found


class Held(MadeTesters):
    """Made tests that a test can hold: a service that has not answered
    yet. They answer at once until go is cleared, and again once it is set."""

    def __init__(self):
        super().__init__()
        self.go = threading.Event()
        self.go.set()

    def tester(self, service: str):
        plain = super().tester(service)

        def test(key: str):
            self.go.wait(10)
            return plain(key)
        return test


def test_15_13_ruling_51_the_page_is_sent_at_once_with_the_control_disabled_and_the_result_fills_in_at_its_own_address(tmp_path, clock, server):
    testers = Held()
    app, client, local, workers, _ = cloud_app(tmp_path, clock, server, testers=testers)
    testers.go.clear()                                                                      # from here the services do not answer
    before = len(testers.asked)
    page = client.get(START)                                                                # it comes back while the tests are held
    assert page.status_code == 200 and disabled_on(page.text) and refusal_on(page.text, "start") == TESTING == words.START_TESTING
    said = text_of(page)
    assert "Made-up Patient" in said and 'name="right_patient"' in page.text                # everything the page shows today is there
    assert 'id="cloud-mark"' in page.text and words.CHOICE_CLAUDE in said and words.CHOICE_SPEECHMATICS in said
    assert re.search(r'<script src="/static/start\.js\?v=[0-9a-f]{12}"></script>', page.text)
    # For a page whose script has not run: one line and a link that loads the page with the result.
    assert f'<p class="mark" id="start-no-script">{words.START_NO_SCRIPT} <a href="{START}?tests={run_of(page.text)}">{words.START_SHOW_RESULT}</a></p>' in said
    address = re.search(r'data-address="([^"]+)"', page.text).group(1)
    assert client.get(address).json() == {"state": "running"} and 'data-waits="yes"' in page.text
    testers.go.set()
    assert answer_of_tests(client, page.text) == {"state": "answered", "problem": None, "lead": None, "notice": None}
    assert len(testers.asked) == before + 2                                                 # side by side, each once (7.2)
    # The asks of the script are no use of the page: the lock's time is not pushed back by them (15.10, ruling 41).
    clock.advance(minutes=29)
    assert client.get(address).json()["state"] == "answered"
    clock.advance(minutes=2)                                                                 # 31 minutes since the last use
    assert client.get("/", follow_redirects=False).headers["location"].startswith("/login")


def test_15_13_ruling_51_a_press_before_the_tests_have_answered_is_refused_by_the_app_and_no_consultation_begins(tmp_path, clock, server):
    testers = Held()
    app, client, local, workers, _ = cloud_app(tmp_path, clock, server, testers=testers)
    p = app.state.parts
    testers.go.clear()
    page = client.get(START)
    early = client.post(START, data={**TICKS, "tests": run_of(page.text)})                  # a post made anyway: the control is disabled
    assert early.status_code == 400 and refusal_on(early.text, "start") == STILL == words.START_STILL_TESTING
    assert p.consultations.get(1) is None and p.running == {}
    assert disabled_on(early.text) and run_of(early.text) == run_of(page.text)              # the page sent back waits for the same run
    testers.go.set()
    assert answer_of_tests(client, early.text)["problem"] is None
    started = client.post(START, data={**TICKS, "tests": run_of(page.text)})
    assert started.status_code == 303 and p.consultations.get(1) is not None
    p.running[1].close()


def test_15_13_ruling_51_a_run_that_answered_is_used_by_the_press_and_a_failed_one_refuses_with_its_reason_and_its_link(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server)
    p = app.state.parts
    page = client.get(START)
    assert answer_of_tests(client, page.text)["problem"] is None
    asked = len(testers.asked)
    # A tick forgotten: the page sent back still names its run, and the press after it tests nothing again.
    forgot = client.post(START, data={**TICKS, "acted": "", "tests": run_of(page.text)})
    assert refusal_on(forgot.text, "start") == words.TICK_BOTH and run_of(forgot.text) == run_of(page.text)
    assert 'id="start-tests"' not in forgot.text                                            # nothing is left to fill in
    started = client.post(START, data={**TICKS, "tests": run_of(forgot.text)})
    assert started.status_code == 303 and len(testers.asked) == asked                       # the run's own tests were used
    p.running[1].close()
    # A service down: the tests' answer carries the reason and the link, and the press is refused with the same sentence.
    app, client, local, workers, testers = cloud_app(tmp_path / "down", clock, server)
    testers.fail[SPEECHMATICS] = "no_internet"
    page = client.get(START)
    found = answer_of_tests(client, page.text)
    assert found == {"state": "answered", "problem": DOWN, "lead": ["/connect/speechmatics", "Speechmatics"], "notice": None}
    refused = client.post(START, data={**TICKS, "tests": run_of(page.text)})
    assert refused.status_code == 400 and refusal_on(refused.text, "start") == DOWN and 'id="start-lead"><a href="/connect/speechmatics">' in refused.text
    assert app.state.parts.consultations.get(1) is None
    # The page with no script: its link loads the page with the result of that run.
    shown = client.get(f"{START}?tests={run_of(page.text)}")
    assert disabled_on(shown.text) and refusal_on(shown.text, "start") == DOWN and 'id="start-tests"' not in shown.text


def test_15_13_ruling_51_an_old_run_and_a_press_that_names_none_are_tested_at_the_press_itself(tmp_path, clock, server, monkeypatch):
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server)
    p = app.state.parts
    page = client.get(START)
    answer_of_tests(client, page.text)
    # The connection goes down after the view. A run older than the span no longer stands for it: tested at the press.
    testers.fail[CLAUDE] = "no_credit"
    asked = len(testers.asked)
    run = p.start_tests.get(run_of(page.text), p.stored.path("none").key())
    run.answered_at -= start_tests.FRESH_S + 1
    refused = client.post(START, data={**TICKS, "tests": run_of(page.text)})
    assert refused.status_code == 400 and "Claude refused to start: the account has no credit left." in refusal_on(refused.text, "start")
    assert len(testers.asked) == asked + 2 and p.consultations.get(1) is None
    # No run named, as before run 9c: tested at the press too.
    assert client.post(START, data=TICKS).status_code == 400 and len(testers.asked) == asked + 4
    assert start_tests.FRESH_S == 60.0


def test_15_13_ruling_51_a_service_that_never_answers_gives_its_reason_after_the_limit_and_start_stays_closed(tmp_path, clock, server):
    slow = MadeTesters()
    slow.tester = lambda service: (lambda key: connections.Tested(service, False, "too_slow", "no answer within 10 s", 10.0))
    app, client, local, workers, _ = cloud_app(tmp_path, clock, server, testers=slow)
    page = client.get(START)
    assert disabled_on(page.text) and refusal_on(page.text, "start") == TESTING           # the page did not wait for it
    found = answer_of_tests(client, page.text)
    assert found["problem"] == "Start is not offered: Speechmatics did not answer within 10 seconds. Try again."
    assert found["lead"][0] == "/connect/speechmatics" and connections.LIMIT_S == 10.0


def test_15_13_ruling_51_what_the_app_knows_at_once_is_said_at_once_and_a_path_on_this_computer_makes_no_run(tmp_path, clock, server):
    # Not connected: known at once, nothing tested, no run, no script.
    app, client, local, workers, testers = cloud_app(tmp_path / "a", clock, server, held={})
    page = client.get(START)
    assert disabled_on(page.text) and "Claude is not connected" in refusal_on(page.text, "start")
    assert 'name="tests"' not in page.text and "start.js" not in page.text and testers.asked == []
    # This computer for both: as it was. No run, no script, nothing to wait for.
    app, client, local, workers, testers = cloud_app(tmp_path / "b", clock, server, machine=SUITABLE)
    page = client.get(START)
    assert not disabled_on(page.text) and 'name="tests"' not in page.text and "start.js" not in page.text
    assert client.get(f"{START}/tests?run=1").json() == {"state": "gone"}                    # a run that is not: the script loads the page anew
    assert client.post(START, data=TICKS).status_code == 303
    app.state.parts.running[1].close()


def test_15_13_rulings_37_and_51_with_the_tick_alone_start_is_offered_at_once_and_the_notice_fills_in(tmp_path, clock, server):
    testers = Held()
    app, client, local, workers, _ = cloud_app(tmp_path, clock, server, machine=SUITABLE, testers=testers)
    p = app.state.parts
    ticked = ChosenPath(THIS_COMPUTER, THIS_COMPUTER, better_accuracy=True)
    p.stored.set_path("suitable", ticked)
    p.stored.tick_statement(statement_for(ticked).sha256, ticked, statement_for(ticked))
    testers.fail[SPEECHMATICS] = "no_internet"
    testers.go.clear()
    page = client.get(START)
    # Nothing of this consultation needs the service until after Stop: the control is not disabled and does not wait.
    assert not disabled_on(page.text) and refusal_on(page.text, "start") == "" and 'data-waits="no"' in page.text
    assert TESTING not in text_of(page) and words.CLOUD_MARK_RECORDING in text_of(page)
    # A press before the test has answered begins the consultation.
    started = client.post(START, data={**TICKS, "tests": run_of(page.text)})
    assert started.status_code == 303 and p.consultations.get(1)["better_accuracy"] == 1
    p.running[1].close()
    testers.go.set()
    assert client.get(f"{START}/tests?run={run_of(page.text)}").json() == {"state": "gone"}   # the run was spent by the consultation it began
    # On a view that is left to answer, the notice of ruling 37 comes with the tests' result, and Start stays offered.
    page = client.get(START)
    found = answer_of_tests(client, page.text)
    assert found["problem"] is None and found["notice"] == (
        "Speechmatics cannot be reached now: Speechmatics could not be reached. Check the internet connection and try again. "
        "The consultation can start. The better transcript may not be made after Stop.")
