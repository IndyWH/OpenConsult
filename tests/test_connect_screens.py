"""The connect screens and the section Connections (spec 7.2; 7.3 rule 3;
15.13, rulings 5, 30 and 34; the details of run 9b). A made secure store,
made tests of each connection, made keys. No real store, key or service."""

from __future__ import annotations

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store as settings_store
from openconsult.settings import connections
from openconsult.settings.connections import SERVICES
from openconsult.settings.machine import Card, describe
from openconsult.settings.path import CLAUDE, SPEECHMATICS
from openconsult.settings.statement import statement_for
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine
from tests.made_up_store import MadeStore

GOOD, BAD = "made-up-good-key-0123456789", "made-up-bad-key-9876543210"
NO_CARD = describe("Linux", "x86_64", [])
SUITABLE = describe("Linux", "x86_64", [Card("Made-up card", 24564)])


class MadeTesters:
    """A made test for each service: a key passes unless it is the bad one,
    or the service is set to fail with a reason. Every key it is given is
    kept, so a test can see what was tested and when."""

    def __init__(self):
        self.asked: list[tuple[str, str]] = []
        self.fail: dict[str, str] = {}

    def tester(self, service: str):
        def test(key: str) -> connections.Tested:
            self.asked.append((service, key))
            reason = self.fail.get(service) or ("key_refused" if key == BAD else None)
            return connections.Tested(service, reason is None, reason, "HTTP made-up", 0.01)
        return test

    def both(self) -> dict:
        return {CLAUDE: self.tester(CLAUDE), SPEECHMATICS: self.tester(SPEECHMATICS)}


def made_app(tmp_path, clock, machine=NO_CARD, store=None, testers=None):
    store = store if store is not None else MadeStore()
    testers = testers or MadeTesters()
    app = build_app(settings_store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, secure_store=store, testers=testers.both())
    client = browser(app)
    set_up(client)
    log_in(client)
    return app, client, store, testers


def everything_written(p) -> str:
    """Every row of every table as text: what a key must never be in."""
    found = []
    for table in p.db.tables():
        found += [repr(tuple(row)) for row in p.db.query(f"SELECT * FROM {table}")]
    return "\n".join(found)


def test_15_13_ruling_34_the_connect_screen_for_claude_holds_the_owners_words_the_line_why_this_model_and_the_services_page(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock)
    answer = client.get("/connect/claude")
    page = text_of(answer)
    assert answer.status_code == 200 and f'<h1 class="page">{words.CONNECT_CLAUDE_TITLE}</h1>' in answer.text
    assert all(line in page for line in words.CONNECT_CLAUDE_LINES)
    assert 'href="/why-this-model"' in answer.text and words.WHY_THIS_MODEL in page
    assert 'id="get-a-key" href="https://platform.claude.com/settings/keys" target="_blank" rel="noopener noreferrer"' in answer.text
    assert 'name="key" type="password" autocomplete="off"' in answer.text and "value=" not in answer.text.split('name="key"')[1].split(">")[0]
    assert words.NOT_CONNECTED in page and testers.asked == []                           # a view of the screen tests nothing
    # Speechmatics: the cost and the credit in the words of ruling 32's last line, and its third line, letter for letter.
    speech = text_of(client.get("/connect/speechmatics"))
    assert words.CONNECT_SPEECHMATICS_TITLE in speech and words.CLOUD_SPEECHMATICS_LINES[3] in speech and words.CLOUD_SPEECHMATICS_LINES[2] in speech
    assert 'href="https://portal.speechmatics.com/settings/api-keys/"' in client.get("/connect/speechmatics").text
    assert words.WHY_THIS_MODEL not in speech
    assert client.get("/connect/made-up").headers["location"] == "/settings"


def test_7_2_only_a_key_that_passed_its_test_is_saved_and_the_reply_never_holds_the_key(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock)
    p = app.state.parts
    refused = client.post("/connect/claude", data={"key": BAD})
    assert refused.status_code == 400 and refusal_on(refused.text, "test-connection") == "Claude refused the key. Check the key and try again."
    assert store.held == {} and BAD not in refused.text and not p.connections.connected(CLAUDE)
    assert testers.asked == [(CLAUDE, BAD)]                                                # tested once, never again
    saved = client.post("/connect/claude", data={"key": f"  {GOOD}  "})
    assert saved.status_code == 303 and saved.headers["location"] == "/connect/claude?done=connected"
    assert store.held == {"ANTHROPIC_API_KEY": GOOD} and p.connections.connected(CLAUDE) and p.connections.key(CLAUDE) == GOOD
    page = client.get("/connect/claude?done=connected")
    assert words.KEY_SAVED in text_of(page) and words.KEY_WHERE["store"] in text_of(page) and GOOD not in page.text
    events = [(l.event, l.detail) for l in p.audit.lines()]
    assert ("key.saved", "Claude: kept in the secure store after it passed its test") in events
    assert ("connection.tested", "Claude: a pasted key: key_refused (HTTP made-up)") in events and ("connection.tested", "Claude: answered") in events
    # With no key pasted the key in use is tested; with none in use the screen asks for one.
    assert client.post("/connect/claude", data={"key": ""}).headers["location"] == "/connect/claude?done=tested"
    empty = client.post("/connect/speechmatics", data={"key": ""})
    assert refusal_on(empty.text, "test-connection") == words.PASTE_A_KEY and store.held == {"ANTHROPIC_API_KEY": GOOD}


@pytest.mark.parametrize("service, title", [(CLAUDE, "Claude"), (SPEECHMATICS, "Speechmatics")])
@pytest.mark.parametrize("reason, sentence", [
    ("key_refused", "{service} refused the key. Check the key and try again."),
    ("no_credit", "{service} refused to start: the account has no credit left."),
    ("no_internet", "{service} could not be reached. Check the internet connection and try again."),
    ("service_down", "{service} is not answering. Try again later."),
    ("limit_reached", "{service} refused to start: a limit on the account was reached."),
    ("too_slow", "{service} did not answer within 10 seconds. Try again."),
])
def test_7_2_each_reason_of_a_failed_test_is_said_on_its_screen_on_the_control_pressed(tmp_path, clock, service, title, reason, sentence):
    app, client, store, testers = made_app(tmp_path, clock)
    testers.fail[service] = reason
    refused = client.post(f"/connect/{service}", data={"key": GOOD})
    assert refused.status_code == 400 and refusal_on(refused.text, "test-connection") == sentence.format(service=title)
    assert store.held == {} and GOOD not in refused.text                                  # nothing saved, and the key not shown again


def test_7_2_with_no_secure_store_the_screen_says_so_saves_nothing_and_names_the_developers_way(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, store=MadeStore(answers=False))
    answer = client.get("/connect/claude")
    assert refusal_on(answer.text, "test-connection") == words.NO_SECURE_STORE and ".env" in words.NO_SECURE_STORE
    assert 'name="key" type="password" autocomplete="off" spellcheck="false" disabled' in answer.text
    assert 'id="test-connection" aria-describedby="test-connection-refusal" disabled' in answer.text
    posted = client.post("/connect/claude", data={"key": GOOD})                            # a post made anyway
    assert posted.status_code == 400 and refusal_on(posted.text, "test-connection") == words.NO_SECURE_STORE
    assert store.held == {} and testers.asked == [] and not list(tmp_path.glob(".env"))    # no file is used in the store's place
    # A store that takes the key and does not keep it: said, and the key not counted as connected.
    app, client, store, testers = made_app(tmp_path / "b", clock, store=MadeStore(keeps=False))
    lost = client.post("/connect/claude", data={"key": GOOD})
    assert refusal_on(lost.text, "test-connection") == words.KEY_NOT_KEPT.format(reason="the secure store did not keep the key")
    assert not app.state.parts.connections.connected(CLAUDE)


def test_7_3_the_section_connections_says_connected_or_not_with_test_and_remove_and_nothing_of_the_key(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock)
    p = app.state.parts
    page = client.get("/settings").text
    assert f"<h2>{words.SECTION_CONNECTIONS}</h2>" in page
    for service in SERVICES:
        assert f'id="state-{service}">{words.NOT_CONNECTED}</p>' in page and f'id="test-{service}" aria-describedby="test-{service}-refusal" disabled' in page
    client.post("/connect/speechmatics", data={"key": GOOD})
    page = text_of(client.get("/settings"))
    assert f'id="state-speechmatics">{words.CONNECTED}</p>' in page and words.KEY_WHERE["store"] in page and GOOD not in page
    assert words.LAST_TEST_PASSED.format(date="4 Oct 2026", time="09:00") in page
    # Test: the key in use, now; a failure is said on the control with its reason, and the service is then not connected.
    testers.fail[SPEECHMATICS] = "no_internet"
    failed = client.post("/connections/speechmatics/test")
    assert refusal_on(failed.text, "test-speechmatics") == "Speechmatics could not be reached. Check the internet connection and try again."
    assert not p.connections.connected(SPEECHMATICS) and f'id="state-speechmatics">{words.NOT_CONNECTED}</p>' in failed.text
    del testers.fail[SPEECHMATICS]
    assert client.post("/connections/speechmatics/test").headers["location"] == "/settings?done=tested#connections"
    assert p.connections.connected(SPEECHMATICS)
    # Remove takes the key out of the store, and out of no other place.
    assert client.post("/connections/speechmatics/remove").headers["location"] == "/settings?done=removed#connections"
    assert store.held == {} and not p.connections.connected(SPEECHMATICS)
    assert (p.audit.lines()[0].event, p.audit.lines()[0].detail) == ("key.removed", "Speechmatics: taken out of the secure store")
    assert words.KEY_REMOVED in text_of(client.get("/settings?done=removed"))


def test_review_point_9_a_key_from_the_environment_or_the_file_counts_as_connected_only_after_a_test_and_remove_cannot_take_it_out(tmp_path, clock, monkeypatch):
    (tmp_path / ".env").write_text(f"SPEECHMATICS_API_KEY={GOOD}\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", GOOD)
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE)             # this computer for both: nothing is tested at start
    p = app.state.parts
    assert testers.asked == [] and not p.connections.connected(CLAUDE) and not p.connections.connected(SPEECHMATICS)
    page = text_of(client.get("/settings"))
    assert words.KEY_WHERE["environment"] in page and words.KEY_WHERE["file"] in page and words.NOT_TESTED_YET in page
    client.post("/connections/claude/test")
    assert p.connections.connected(CLAUDE) and store.held == {}                            # in use and tested, and never written to the store
    refused = client.post("/connections/claude/remove")
    assert refusal_on(refused.text, "remove-claude") == words.KEY_NOT_IN_STORE and p.connections.key(CLAUDE) == GOOD
    assert GOOD not in everything_written(p)


def test_details_of_9b_at_start_the_tests_run_for_the_services_the_chosen_path_uses_and_for_no_other(tmp_path, clock):
    held = {"ANTHROPIC_API_KEY": GOOD, "SPEECHMATICS_API_KEY": GOOD}
    app, client, store, testers = made_app(tmp_path / "local", clock, machine=SUITABLE, store=MadeStore(held))
    assert testers.asked == []                                                             # both on this computer: no service is asked
    assert app.state.parts.connections.connected(CLAUDE)                                   # a stored key passed its test when it was saved
    app, client, store, testers = made_app(tmp_path / "cloud", clock, machine=NO_CARD, store=MadeStore(held))
    assert sorted(testers.asked) == [(CLAUDE, GOOD), (SPEECHMATICS, GOOD)]                 # no card: both begin in the cloud (10.3)
    lines = [l.detail for l in app.state.parts.audit.lines() if l.event == "connection.tested"]
    assert sorted(lines) == ["Claude: answered", "Speechmatics: answered"]
    # This machine says each connection as it stands, with the reason of a failed test (R15).
    page = text_of(client.get("/settings"))
    assert f"<th>{words.ROW_CONNECTION.format(service='Claude')}</th><td>{words.MACHINE_CONNECTED.format(time='09:00')}</td>" in page
    testers.fail[CLAUDE] = "no_credit"
    client.post("/connections/claude/test")
    failed = words.MACHINE_TEST_FAILED.format(time="09:00", reason="Claude refused to start: the account has no credit left.")
    assert f"<th>{words.ROW_CONNECTION.format(service='Claude')}</th><td>{failed}</td>" in text_of(client.get("/settings"))
    app, client, store, testers = made_app(tmp_path / "none", clock, machine=NO_CARD)
    assert testers.asked == []                                                             # no key, no test
    assert f"<th>{words.ROW_CONNECTION.format(service='Claude')}</th><td>{words.NOT_CONNECTED}</td>" in text_of(client.get("/settings"))


def test_15_13_ruling_5_the_statement_stands_on_the_connect_screen_once_connected_and_its_tick_is_taken_only_for_the_text_shown(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock)                                # no card: the path begins in the cloud for both
    p = app.state.parts
    assert 'id="cloud-statement"' not in client.get("/connect/claude").text                # not connected yet: the screen comes first
    client.post("/connect/claude", data={"key": GOOD})
    answer = client.get("/connect/claude")
    page, made = text_of(answer), statement_for(p.stored.path("none"))
    assert 'id="cloud-statement"' in answer.text and made.heading == words.CLOUD_HEADING_BOTH
    assert all(line in page for line in (*made.sent, *made.stays, made.prototype, made.tick)) and all(
        line in page for _, lines in made.parts for line in lines)
    assert f'name="sha256" value="{made.sha256}"' in answer.text
    no_tick = client.post("/statement/tick", data={"sha256": made.sha256, "back": "/connect/claude"})
    assert no_tick.status_code == 400 and refusal_on(no_tick.text, "tick-statement") == words.STATEMENT_TICK_FIRST
    stale = client.post("/statement/tick", data={"sha256": "0" * 64, "understand": "yes", "back": "/connect/claude"})
    assert stale.status_code == 400 and refusal_on(stale.text, "tick-statement") == words.STATEMENT_CHANGED
    assert p.stored.ticked_sha256 is None
    ticked = client.post("/statement/tick", data={"sha256": made.sha256, "understand": "yes", "back": "/connect/claude"})
    assert ticked.headers["location"] == "/connect/claude?done=ticked" and p.stored.ticked(made)
    assert (p.audit.lines()[0].event, p.audit.lines()[0].detail) == (
        "statement.ticked", f"language model claude, transcription speechmatics, recording after Stop no; sha256 {made.sha256}")
    assert 'id="cloud-statement"' not in client.get("/connect/claude").text and 'id="cloud-statement"' not in client.get("/settings").text
    # A place to go back to that the app does not know is never followed.
    assert client.post("/statement/tick", data={"sha256": made.sha256, "understand": "yes", "back": "https://example.org/"}).headers[
        "location"] == "/settings?done=ticked"


def test_7_2_and_7_3_rule_3_a_made_key_is_in_no_table_no_audit_line_and_no_page_after_connect_test_and_remove(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock)
    p = app.state.parts
    pages = [client.post("/connect/claude", data={"key": BAD}).text]
    for service in SERVICES:
        client.post(f"/connect/{service}", data={"key": GOOD})
        pages += [client.get(f"/connect/{service}").text, client.post(f"/connections/{service}/test").text]
    testers.fail[CLAUDE] = "key_refused"
    pages += [client.post("/connections/claude/test").text, client.get("/settings").text, client.get("/log").text, client.get("/").text]
    assert store.held == {"ANTHROPIC_API_KEY": GOOD, "SPEECHMATICS_API_KEY": GOOD}
    client.post("/connections/claude/remove")
    pages += [client.get("/settings").text, client.get("/log").text]
    written = everything_written(p)
    for key in (GOOD, BAD):
        assert key not in written and not any(key in page for page in pages)
        assert not any(key in path.read_text(errors="replace") for path in tmp_path.rglob("*") if path.is_file() and path.suffix != ".db")
    assert store.held == {"SPEECHMATICS_API_KEY": GOOD}                                    # the one place a key is kept
