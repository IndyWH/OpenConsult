"""A fresh scenario, written by the model for a topic and a level (spec
12.3, rule 5; 10.4; 15.14, rulings 1, 5, 10, 14 and 23, and the details
of run 10b: A fresh scenario; the owner's okay of 25 Nov 2026 for the
third check; R15; R30). A made engine answers with a made scenario:
what a model would write is never read or asserted."""

import copy
import re

import pytest

from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.teaching import frames, words as t
from openconsult.web import teaching as teaching_web
from tests import made_teaching
from tests.conftest import refusal_on, text_of
from tests.fakes import FakeEngine
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import cloud_teaching, events

SCENARIO = made_teaching.SCENARIO
TOPIC, LEVEL = "Another made-up topic", "hidden"


def fresh_app(tmp_path, clock, machine, written, held: bool = False):
    engine = FakeEngine(script={"teaching_case": list(written)})
    app, client = teaching_app(tmp_path, clock, machine, engine)
    works = []
    app.state.parts.teaching.run = works.append if held else (lambda work: work())
    return app, client, engine, works


def press_of(raw: str) -> str:
    form = raw.split('id="start-fresh-form"', 1)[1].split("</form>", 1)[0]
    return re.search(r'name="press" value="([^"]+)"', form).group(1)


def write(client, topic=TOPIC, level=LEVEL, press=None):
    return client.post("/teaching/cases", data={"topic": topic, "level": level, "press": press or press_of(client.get("/teaching").text)})


def with_(**changes) -> dict:
    return {**copy.deepcopy(SCENARIO), **changes}


def test_15_14_rulings_1_and_5_the_form_of_a_new_case_holds_the_menu_with_surprise_me_first_and_the_three_levels(tmp_path, clock, machine):
    app, client, engine, works = fresh_app(tmp_path, clock, machine, [])
    raw = client.get("/teaching").text
    found = [raw.find(f'id="{part}"') for part in ("no-real-patient", "new-case", "bank")]
    assert all(f >= 0 for f in found) and found == sorted(found)                       # the order of the details
    form = raw.split('id="start-fresh-form"', 1)[1].split("</form>", 1)[0]
    options = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', form)
    assert options == [("surprise", "Surprise me")] + [(topic, topic) for topic in made_teaching.TOPICS]
    # The three levels, each with its line as the details give it; straightforward is the one picked (ruling 5).
    for value, line in (("straightforward", "Straightforward: the story points to the diagnosis."),
                        ("hidden", "Hidden: what must not be missed is not the first thing the story suggests."),
                        ("noisy", "Noisy: another worry or a wrong idea stands in the way.")):
        assert re.search(rf'<input type="radio" name="level" value="{value}"( checked)?> {re.escape(line)}</label>', form), value
    assert form.count(" checked>") == 1 and '<input type="radio" name="level" value="straightforward" checked>' in form
    assert ">Write a new case</button>" in form
    assert "It is AI-written and not reviewed by a clinician." in text_of(client.get("/teaching"))
    # The app's own menu is the 26 titles, in the order of the file.
    own, own_client = teaching_app(tmp_path / "own", clock, machine, bank=None)
    assert len(re.findall(r"<option ", own_client.get("/teaching").text)) == 27


def test_15_14_ruling_10_a_fresh_case_is_asked_for_its_topic_and_level_with_its_own_sampling_and_the_page_says_it_is_being_written(
        tmp_path, clock, machine):
    app, client, engine, works = fresh_app(tmp_path, clock, machine, [SCENARIO], held=True)
    cases = app.state.parts.teaching.cases
    sent = write(client)
    assert sent.status_code == 303 and sent.headers["location"] == "/teaching/cases/1"
    row = cases.get(1)
    assert (row["source"], row["bank_number"], row["topic"], row["level"], row["label"], row["step"], row["scenario"]) == (
        "fresh", None, TOPIC, LEVEL, "ai", "writing", None)
    assert events(app) == [("teaching.started", "case 1: a fresh scenario, level hidden, language model this_computer")]
    # Being written beside the page: it says so and how long, and asks again by itself. No patient yet.
    raw = client.get("/teaching/cases/1").text
    assert '<p class="waiting" id="case-writing" role="status">The case is being written. This usually takes about 10 seconds, at most 3 minutes.</p>' in raw
    assert '<meta http-equiv="refresh" content="2;url=/teaching/cases/1?quiet">' in raw and 'id="presented"' not in raw and 'id="write-again"' not in raw
    # The label of a scenario a model writes stands at the top from the first moment (12.3, rule 5).
    assert '<h1 class="page">A new case</h1>' in raw and '<td id="case-label">AI-written, not reviewed by a clinician</td>' in raw
    assert "<td>Another made-up topic</td>" in raw and "<td>Hidden</td>" in raw
    assert engine.calls == [] and len(works) == 1
    works.pop()()
    # One call, built by frames: the topic and the level, and the case's own sampling with a seed drawn afresh.
    call, = engine.calls_for("teaching_case")
    assert call.system == loader.prompt("teaching_case") and call.user == frames.case_message(TOPIC, LEVEL)
    assert call.temperature == frames.CASE_TEMPERATURE == 0.7 and 0 <= call.seed < 2 ** 31
    row = cases.get(1)
    assert row["step"] == "history" and row["scenario"] == SCENARIO and row["failure"] is None
    assert app.state.parts.calls.get(cases.calls(1)[0])["job"] == "teaching_case"
    # The patient appears, under the same label.
    raw = client.get("/teaching/cases/1").text
    assert '<h2 id="presented">Made Up, 40, female</h2>' in raw and "AI-written, not reviewed by a clinician" in text_of(client.get("/teaching/cases/1"))
    assert "http-equiv=\"refresh\"" not in raw and 'id="say-box"' in raw
    # The same press a second time opens the same case and asks for nothing more.
    press = press_of(client.get("/teaching").text)
    assert write(client, press=press).headers["location"] == write(client, press=press).headers["location"] == "/teaching/cases/2"
    assert len(works) == 1 and len(cases.listed()) == 2


def test_15_14_surprise_me_draws_one_of_the_topics_of_the_menu_and_the_drawn_topic_is_the_cases_own(tmp_path, clock, machine, monkeypatch):
    app, client, engine, works = fresh_app(tmp_path, clock, machine, [SCENARIO])
    drawn = []
    monkeypatch.setattr(teaching_web.secrets, "choice", lambda topics: drawn.append(tuple(topics)) or topics[-1])
    assert write(client, topic="surprise", level="noisy").status_code == 303
    assert drawn == [made_teaching.TOPICS]                                             # drawn from the whole menu, by chance
    row = app.state.parts.teaching.cases.get(1)
    assert (row["topic"], row["level"]) == (made_teaching.TOPICS[-1], "noisy")
    assert engine.calls_for("teaching_case")[0].user == frames.case_message(made_teaching.TOPICS[-1], "noisy")


@pytest.mark.parametrize("written, why", [
    (with_(plan=[{"step": "Give 40 mg of a made-up medicine", "urgency": "none"}]), "its plan held a dose, and a dose written by a model is not shown"),
    (with_(facts=[]), "it came back incomplete"),
    (with_(differential=[]), "it came back incomplete"),
    (with_(marking_points={"data_gathering": [], "management": [], "relating": []}), "it came back incomplete"),
    ({"patient": "not the form"}, "the reply did not fit its form"),
    (EngineTimeout("made-up: no answer"), "too slow"),
], ids=["a dose in the plan", "no fact", "no diagnosis", "no marking point", "not the form", "no answer"])
def test_15_14_mark_six_R30_a_scenario_that_cannot_be_shown_brings_no_patient_and_is_written_again_by_a_press_alone(
        tmp_path, clock, machine, written, why):
    app, client, engine, works = fresh_app(tmp_path, clock, machine, [written, SCENARIO])
    cases = app.state.parts.teaching.cases
    write(client)
    assert cases.get(1)["step"] == "writing" and cases.get(1)["scenario"] is None      # nothing of it is kept as the case's scenario
    for _ in range(3):                                                                 # nothing is asked a second time by itself
        raw = client.get("/teaching/cases/1").text
    assert len(engine.calls_for("teaching_case")) == 1 and "http-equiv=\"refresh\"" not in raw
    assert f'<p class="refusal" id="write-failed" role="alert">The case could not be written: {why}.</p>' in raw
    assert '<button class="primary" id="write-again">Write it again</button>' in raw
    assert 'id="presented"' not in raw and "Made Up" not in raw and "made-up medicine" not in raw      # no patient appears, and no word of it
    again = client.post("/teaching/cases/1/again")
    assert again.status_code == 303 and len(engine.calls_for("teaching_case")) == 2
    assert cases.get(1)["step"] == "history" and '<h2 id="presented">Made Up, 40, female</h2>' in client.get("/teaching/cases/1").text
    assert len(cases.calls(1)) == 2                                                    # both calls are the case's, and go with it


def test_R15_a_new_case_is_refused_on_its_own_control_and_keeps_what_was_picked(tmp_path, clock, machine):
    app, client, engine, works = fresh_app(tmp_path / "local", clock, machine, [SCENARIO])
    refused = write(client, topic="A topic that is not on the menu")
    assert refused.status_code == 400 and refusal_on(refused.text, "start-fresh") == "Pick a topic."
    refused = write(client, level="easy")
    assert refusal_on(refused.text, "start-fresh") == "Pick a level."
    assert f'<option value="{TOPIC}" selected>' in refused.text                        # what was picked is still picked
    assert app.state.parts.teaching.cases.listed() == [] and engine.calls == []
    # Where no model can be reached the press says so and starts nothing, as for a case of the bank.
    quiet = FakeEngine()
    app, client = teaching_app(tmp_path / "quiet", clock, machine, quiet)
    quiet._version = None
    refused = write(client)
    assert refused.status_code == 400 and refusal_on(refused.text, "start-fresh") == "A case cannot start: the language model does not answer on made-up."
    assert f'<option value="{TOPIC}" selected>' in refused.text and '<input type="radio" name="level" value="hidden" checked>' in refused.text
    # In cloud mode without the tick: said on the control, with the way to Settings; nothing is asked of Claude.
    app, client, claude, testers = cloud_teaching(tmp_path / "cloud", clock, tick=False)
    refused = write(client)
    assert refusal_on(refused.text, "start-fresh") == t.CANNOT_START_NO_TICK and '<a id="start-lead" href="/settings#cloud-statement">' in refused.text
    assert app.state.parts.teaching.cases.listed() == [] and claude.calls == []


def test_R30_a_writing_that_the_apps_stop_cut_short_is_said_plainly_and_a_press_from_an_older_page_asks_nothing(tmp_path, clock, machine):
    app, client, engine, works = fresh_app(tmp_path, clock, machine, [SCENARIO], held=True)
    teaching = app.state.parts.teaching
    write(client)
    assert t.STALE in text_of(client.post("/teaching/cases/1/again")) and len(works) == 1      # while it is written: nothing a second time
    works.clear()
    teaching._making.clear()                                                           # the app was closed while it was written
    page = text_of(client.get("/teaching/cases/1"))
    assert "The case could not be written: OpenConsult was closed before the answer came." in page and engine.calls == []
    assert client.post("/teaching/cases/1/again").status_code == 303 and len(works) == 1
    works.pop()()
    assert teaching.cases.get(1)["step"] == "history"
