"""A case of the bank starts, and the patient is presented (spec 12.1,
step 2; 10.4; 15.14, rulings 3, 7 and 15, and the details of run 10b:
The patient is presented, Cloud mode, Which model answers; R15). A made
bank, a made engine and made services: no model and no service is asked
for real, and nothing a model wrote is read."""

import copy
import re

import pytest

from openconsult import words
from openconsult.settings.path import CLAUDE, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from openconsult.teaching import words as t
from openconsult.teaching.bank import Bank, BankCase
from openconsult.teaching.scenario import speaks_for
from tests import made_teaching
from tests.conftest import refusal_on, text_of
from tests.fakes import FakeEngine
from tests.made_up_store import MadeStore
from tests.test_connect_screens import GOOD, NO_CARD, MadeTesters
from tests.test_statement import BEFORE_THE_LINE
from tests.test_teaching_frames import said_in, words_of
from tests.test_teaching_page import teaching_app

CLAUDE_KEY = {"ANTHROPIC_API_KEY": GOOD}
STARTED = "teaching.started"


def press_of(raw: str, number: int) -> str:
    """The token of the press on a row of the bank, as the page was made with it."""
    form = raw.split(f'id="start-form-{number}"', 1)[1].split("</form>", 1)[0]
    return re.search(r'name="press" value="([^"]+)"', form).group(1)


def start(client, number: int = 1):
    return client.post("/teaching/cases", data={"number": str(number), "press": press_of(client.get("/teaching").text, number)})


def events(app) -> list[tuple[str, str]]:
    return [(line.event, line.detail) for line in app.state.parts.audit.lines() if line.event.startswith("teaching.")]


def cloud_teaching(tmp_path, clock, held=CLAUDE_KEY, tick=True, testers=None, claude=None):
    """An app on a machine with no card, so the language model begins in the cloud (10.3), with a made Claude."""
    testers = testers or MadeTesters()
    claude = claude or FakeEngine()
    app, client = teaching_app(tmp_path, clock, NO_CARD, secure_store=MadeStore(held), testers=testers.both(),
                               claude_engine=lambda key: claude)
    p = app.state.parts
    made = statement_for(p.stored.path(NO_CARD.case))
    if tick:
        p.stored.tick_statement(made.sha256, p.stored.path(NO_CARD.case), made)
    return app, client, claude, testers


def test_12_1_step_2_a_case_of_the_bank_starts_and_the_patient_is_presented_by_name_age_sex_and_opening_words(tmp_path, clock, machine, engine):
    app, client = teaching_app(tmp_path, clock, machine, engine)
    answer = start(client, 1)
    assert answer.status_code == 303 and answer.headers["location"] == "/teaching/cases/1"
    raw = client.get("/teaching/cases/1").text
    page = text_of(client.get("/teaching/cases/1"))
    assert '<h2 id="presented">Made Up, 40, female</h2>' in raw
    assert '<span class="said">I have a made-up ache.</span>' in raw and f'<span class="speaker">{t.PATIENT}</span>' in raw
    assert "tester" not in page and "Speaks plainly." not in page                     # not the occupation, not the manner
    assert 'id="speaks-for"' not in raw
    # The label stands at the top of the case's page, with its number, its topic and its level (ruling 3).
    assert '<h1 class="page">Case 1</h1>' in raw and "<td>A made-up topic</td>" in raw and "<td>Straightforward</td>" in raw
    assert '<td id="case-label">Made from a clinician&#39;s script. The scenario is not yet reviewed.</td>' in raw
    assert raw.find('id="case-label"') < raw.find('id="presented"')
    # The row: the scenario as it stood at the start, the model held for the case, the history begun.
    row = app.state.parts.teaching.cases.get(1)
    assert (row["source"], row["bank_number"], row["level"], row["label"], row["language_model"], row["step"]) == (
        "bank", 1, "straightforward", "script", "this_computer", "history")
    assert row["scenario"] == made_teaching.SCENARIO
    # The audit line: counts and names of the app, never a word of the scenario.
    assert events(app) == [(STARTED, "case 1: bank case 1, level straightforward, language model this_computer")]
    # No model is asked to present a patient, and nothing of the examiner's side is on the page.
    assert engine.calls == []
    second_part = {key: value for key, value in made_teaching.SCENARIO.items() if key not in (
        "patient", "opening_words", "facts", "ideas", "concerns", "expectations", "hidden_agenda")}
    assert not words_of(said_in(second_part)) & words_of(page)
    assert "made-up day" not in page and "made-up strain" not in page                 # nor of the patient's side beyond the opening words


@pytest.mark.parametrize("written, shown", [("Her mother, Made Parent", "Her mother, Made Parent"), ("  A made-up father ", "A made-up father"),
                                            ("", None), ("nothing", None), ("None", None), ("NO", None), (" n/a ", None), ("N/A", None)])
def test_15_14_a_parent_who_speaks_for_a_child_has_a_line_under_the_name_and_a_parent_written_as_nothing_counts_as_none(
        tmp_path, clock, machine, written, shown):
    scenario = copy.deepcopy(made_teaching.SCENARIO)
    scenario["patient"]["parent"] = written
    assert speaks_for(scenario) == shown
    bank = Bank(made_teaching.TOPICS, (BankCase(1, made_teaching.TOPICS[0], "straightforward", "script", scenario),), 0)
    app, client = teaching_app(tmp_path, clock, machine, bank=bank)
    start(client, 1)
    raw = client.get("/teaching/cases/1").text
    if shown:
        assert f'<p class="mark" id="speaks-for">Speaking for the child: {shown}</p>' in raw
        assert raw.find('id="presented"') < raw.find('id="speaks-for"') < raw.find('id="opening-words"')
    else:
        assert 'id="speaks-for"' not in raw and "Speaking for the child" not in raw


def test_R15_the_same_press_twice_opens_the_same_case_and_a_case_that_is_not_in_the_list_is_refused(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine)
    press = press_of(client.get("/teaching").text, 2)
    first = client.post("/teaching/cases", data={"number": "2", "press": press})
    again = client.post("/teaching/cases", data={"number": "2", "press": press})
    assert first.headers["location"] == again.headers["location"] == "/teaching/cases/1"
    assert len(app.state.parts.teaching.cases.listed()) == 1 and len(events(app)) == 1
    # Another view of the page is another press: a second case of the same scenario.
    assert start(client, 2).headers["location"] == "/teaching/cases/2"
    assert client.get("/teaching/cases/2").text.count("Approved by a clinician") == 1
    # The two forms of one page have two tokens, so Case 1 pressed after Case 2 is its own case.
    raw = client.get("/teaching").text
    assert press_of(raw, 1) != press_of(raw, 2)
    for number in ("9", "0", "x", ""):
        refused = client.post("/teaching/cases", data={"number": number, "press": "made-press"})
        assert refused.status_code == 400 and refusal_on(refused.text, "start-bank") == t.NOT_IN_LIST
    assert len(app.state.parts.teaching.cases.listed()) == 2
    # A case that does not exist has no page: back to the teaching page.
    assert client.get("/teaching/cases/99").headers["location"] == "/teaching"


def test_R15_10_4_where_no_model_can_be_reached_the_press_says_so_and_no_case_starts(tmp_path, clock, machine):
    # No engine was fit at start: the sentence of This machine, on the control that was pressed.
    app, client = teaching_app(tmp_path / "none", clock, machine, FakeEngine(version=None))
    refused = start(client, 1)
    said = refusal_on(refused.text, "start-1")
    assert refused.status_code == 400 and said == t.CANNOT_START.format(reason=app.state.parts.decisions.language_model.sentence)
    assert said.startswith("A case cannot start: ") and refusal_on(refused.text, "start-2") == ""
    assert app.state.parts.teaching.cases.listed() == [] and events(app) == []
    # An engine that was chosen at start and does not answer now.
    quiet = FakeEngine()
    app, client = teaching_app(tmp_path / "quiet", clock, machine, quiet)
    quiet._version = None
    refused = start(client, 2)
    assert refused.status_code == 400 and refusal_on(refused.text, "start-2") == "A case cannot start: the language model does not answer on made-up."
    assert app.state.parts.teaching.cases.listed() == []
    quiet._version = "0.0-made-up"                                                    # it answers again: the same press starts the case
    assert start(client, 2).headers["location"] == "/teaching/cases/1"


def test_15_14_rulings_7_and_15_in_cloud_mode_no_case_starts_without_the_tick_on_a_statement_that_holds_the_line(tmp_path, clock):
    # Claude not connected.
    app, client, claude, testers = cloud_teaching(tmp_path / "no-key", clock, held={}, tick=False)
    refused = start(client, 1)
    assert refused.status_code == 400 and refusal_on(refused.text, "start-1") == "A case cannot start: Claude is not connected. Connect it in Settings."
    # Connected, the statement not ticked: said on the control, with the way to Settings.
    app, client, claude, testers = cloud_teaching(tmp_path / "no-tick", clock, tick=False)
    asked_at_start = list(testers.asked)                                              # the app's own test of a connection at its start
    refused = start(client, 1)
    assert refusal_on(refused.text, "start-1") == (
        "A case cannot start in cloud mode: the statement for your choices is not ticked. Read and tick it in Settings.")
    assert '<a id="start-lead" href="/settings#cloud-statement">' in refused.text
    # Ticked before the line for teaching stood: that tick does not count (ruling 15).
    p = app.state.parts
    p.stored.tick_statement(BEFORE_THE_LINE["both"], p.stored.path(NO_CARD.case))
    assert refusal_on(start(client, 1).text, "start-1") == t.CANNOT_START_NO_TICK
    assert p.teaching.cases.listed() == [] and testers.asked == asked_at_start and claude.calls == []   # nothing was sent anywhere
    # Ticked on the statement as it stands: the case starts, on Claude.
    made = statement_for(p.stored.path(NO_CARD.case))
    assert words.CLOUD_SENT_TEACHING in made.sent
    p.stored.tick_statement(made.sha256, p.stored.path(NO_CARD.case), made)
    assert start(client, 1).headers["location"] == "/teaching/cases/1"
    assert p.teaching.cases.get(1)["language_model"] == "claude"
    assert events(app) == [(STARTED, "case 1: bank case 1, level straightforward, language model claude")]


def test_R15_10_4_a_case_does_not_start_on_a_connection_that_is_down_and_the_model_is_held_for_the_case(tmp_path, clock):
    testers = MadeTesters()
    app, client, claude, testers = cloud_teaching(tmp_path, clock, testers=testers)
    testers.fail[CLAUDE] = "service_down"
    refused = start(client, 1)
    reason = app.state.parts.connections.state(CLAUDE).last.sentence
    assert refused.status_code == 400 and refusal_on(refused.text, "start-1") == t.CANNOT_START.format(reason=reason)
    assert app.state.parts.teaching.cases.listed() == []
    del testers.fail[CLAUDE]
    assert start(client, 1).headers["location"] == "/teaching/cases/1"
    # The model is held for the case: Settings moved to this computer afterwards, the case stays on Claude (10.4).
    p = app.state.parts
    p.stored.set_path(NO_CARD.case, ChosenPath(THIS_COMPUTER, THIS_COMPUTER))
    assert p.teaching.cases.get(1)["language_model"] == "claude"
    assert p.teaching.door_of(p.teaching.cases.get(1)["language_model"]) is p.claude_doors.door()


def test_15_14_ruling_15_under_the_mark_cloud_stand_the_owners_sentence_and_the_cost_on_each_teaching_page_in_cloud_mode(tmp_path, clock, machine):
    app, client, claude, testers = cloud_teaching(tmp_path / "cloud", clock)
    start(client, 1)
    for address in ("/teaching", "/teaching/cases/1"):
        raw = client.get(address).text
        mark = raw.split('id="cloud-mark"', 1)[1].split("</div>", 1)[0]
        assert f'<b class="cloud-word">{words.CLOUD_MARK}</b>' in mark
        assert "<li>What you type goes to Claude.</li><li>A teaching case costs about 1 US cent.</li>" in mark, address
        assert raw.find("<h1") < raw.find('id="cloud-mark"') < raw.find('<section class="pane"')        # at the top of the page
    # With the language model on this computer there is no mark, on either page.
    app, client = teaching_app(tmp_path / "local", clock, machine)
    start(client, 1)
    for address in ("/teaching", "/teaching/cases/1"):
        raw = client.get(address).text
        assert 'id="cloud-mark"' not in raw and "Claude" not in raw
    # A case started in cloud mode keeps its mark when Settings moves to this computer: its words still go to Claude.
    app, client, claude, testers = cloud_teaching(tmp_path / "moved", clock)
    start(client, 1)
    app.state.parts.stored.set_path(NO_CARD.case, ChosenPath(THIS_COMPUTER, THIS_COMPUTER))
    assert 'id="cloud-mark"' in client.get("/teaching/cases/1").text and 'id="cloud-mark"' not in client.get("/teaching").text
