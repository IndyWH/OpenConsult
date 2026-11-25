"""The examination of a teaching case (spec 12.1, step 4; 12.3, rule 1;
D10; 15.14, rulings 12, 16 and 21, and the details of run 10b: The
examination; R15; R30). The model writes no finding: it names which
findings of the scenario were asked for, and the page shows the
scenario's own words. A made scenario and a made engine: nothing a
model wrote is read."""

import copy

import pytest

from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.teaching import frames, room, words as t
from openconsult.teaching.bank import Bank, BankCase
from openconsult.teaching.scenario import examined_blocks, findings, other_findings
from tests import made_teaching
from tests.conftest import refusal_on, text_of
from tests.fakes import FakeEngine
from tests.test_teaching_history import box_of
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import start

SCENARIO = made_teaching.SCENARIO
ONE, TWO, THREE = "Qexamone: qfindone", "Qexamtwo: qfindtwo", "Qtestone: qresultone"
NO_FINDING = "The case gives no finding for this."


def came(asked=(), not_in_case=()) -> dict:
    return {"asked": list(asked), "not_in_case": list(not_in_case)}


def examining(tmp_path, clock, machine, answers, number: int = 1, bank="made"):
    """A case at its examination, on a made engine that answers the examination's calls with these."""
    engine = FakeEngine(script={"teaching_examination": list(answers)})
    app, client = teaching_app(tmp_path, clock, machine, engine, bank=bank)
    start(client, number)
    assert client.post("/teaching/cases/1/end-history", data={"text": ""}).status_code == 303
    return app, client, engine


def examine(client, n: int, text: str):
    return client.post("/teaching/cases/1/examine", data={"n": str(n), "text": text})


def block(raw: str, n: int) -> str:
    return text_of_part(raw.split(f'id="examined-{n}">', 1)[1].split("</div>", 1)[0])


def text_of_part(part: str) -> str:
    import html
    import re
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", part)).split())


def test_15_14_ruling_12_the_numbers_of_the_findings_are_the_frames_and_each_is_the_scenarios_own_words():
    lay = loader.layout("teaching")
    assert findings(SCENARIO) == [ONE, TWO, THREE]                                     # examination first, then results
    assert frames.findings(SCENARIO, lay).splitlines() == [f"{n}. {words}" for n, words in enumerate(findings(SCENARIO), 1)]
    assert findings({**SCENARIO, "examination": [], "results": []}) == []


def test_15_14_ruling_12_a_finding_asked_for_is_shown_in_the_scenarios_own_words_once_and_nothing_else_of_the_case(tmp_path, clock, machine):
    app, client, engine = examining(tmp_path, clock, machine, [came(asked=[1, 1])])
    raw = client.get("/teaching/cases/1").text
    assert "Type what you would examine. You may send more than once." in text_of(client.get("/teaching/cases/1"))
    assert "qfindone" not in raw and "qfindtwo" not in raw and "qresultone" not in raw       # nothing before it is asked for
    sent = examine(client, 1, "  I would look at made-up one.  ")
    assert sent.status_code == 303 and sent.headers["location"] == "/teaching/cases/1"
    # The request is built by frames and by nothing else.
    call, = engine.calls_for("teaching_examination")
    assert call.system == loader.prompt("teaching_examination") and call.user == frames.examination_message(SCENARIO, "I would look at made-up one.")
    raw = client.get("/teaching/cases/1").text
    assert block(raw, 1) == f"You typed: I would look at made-up one. {ONE}"
    assert raw.count("qfindone") == 1 and "qfindtwo" not in raw and "qresultone" not in raw   # once, and not the rest
    # Stored as it came, tied to the case; what was typed is kept as typed.
    cases = app.state.parts.teaching.cases
    assert [(e["n"], e["text"], e["asked"], e["not_in_case"]) for e in cases.examined(1)] == [(1, "I would look at made-up one.", [1, 1], [])]
    assert app.state.parts.calls.get(cases.calls(1)[-1])["job"] == "teaching_examination"
    assert 'name="n" value="2"' in raw and box_of(raw, "examine-box") == ""


def test_15_14_rulings_16_and_21_what_the_case_does_not_hold_is_the_learners_own_words_and_the_owners_sentence(tmp_path, clock, machine):
    app, client, engine = examining(tmp_path, clock, machine, [
        came(asked=[2], not_in_case=["a made-up Elbow"]), came(not_in_case=["words the learner never typed"]), came(not_in_case=["", " "])])
    examine(client, 1, "Made-up two, and A MADE-UP ELBOW please.")
    examine(client, 2, "A made-up scan of the made-up knee.")
    examine(client, 3, "Something made up.")
    raw = client.get("/teaching/cases/1").text
    assert t.NO_FINDING == NO_FINDING                                                  # the owner's, letter for letter
    # The learner's own words, as the learner typed them, with the owner's sentence; and the finding that was held.
    assert block(raw, 1) == f"You typed: Made-up two, and A MADE-UP ELBOW please. {TWO} A MADE-UP ELBOW : {NO_FINDING}"
    # Words that are not the learner's are never shown as the learner's: the whole typed request stands in their place.
    assert block(raw, 2) == f"You typed: A made-up scan of the made-up knee. A made-up scan of the made-up knee. : {NO_FINDING}"
    assert "words the learner never typed" not in raw
    # Something came back and nothing of it can be shown: said plainly, and never the sentence of no finding.
    assert block(raw, 3) == "You typed: Something made up. Nothing could be shown for this request. Try it in other words."
    assert raw.count(NO_FINDING) == 2


def test_15_14_both_lists_empty_is_no_examination_and_a_number_that_is_no_finding_is_dropped_and_never_shown(tmp_path, clock, machine):
    app, client, engine = examining(tmp_path, clock, machine, [came(), came(asked=[9, 0, -1, 3]), came(asked=[7])])
    examine(client, 1, "Send a made-up test away.")
    examine(client, 2, "A made-up bedside test.")
    examine(client, 3, "Another made-up thing.")
    raw = client.get("/teaching/cases/1").text
    assert block(raw, 1) == "You typed: Send a made-up test away. That is not an examination or a bedside test. Investigations come next."
    assert block(raw, 2) == f"You typed: A made-up bedside test. {THREE}"            # 3 is a finding; 9, 0 and -1 are not
    assert block(raw, 3) == "You typed: Another made-up thing. Nothing could be shown for this request. Try it in other words."
    assert "qfindone" not in raw and "qfindtwo" not in raw and NO_FINDING not in raw
    # The same by the function, with every case of the details on the made scenario.
    blocks = examined_blocks(SCENARIO, [{"n": 1, "text": "x", "asked": [True, 1, 2, 1, 9], "not_in_case": []},
                                        {"n": 2, "text": "An Elbow and a knee", "asked": [], "not_in_case": ["elbow", "A KNEE", "elbow"]}])
    assert blocks[0]["found"] == [ONE, TWO] and blocks[0]["not_held"] == [] and not blocks[0]["no_examination"] and not blocks[0]["nothing"]
    assert blocks[1]["found"] == [] and blocks[1]["not_held"] == ["Elbow", "a knee"]   # the learner's letters, each once


def test_D10_finish_the_examination_shows_the_rest_under_its_own_heading_and_brings_the_first_question(tmp_path, clock, machine):
    app, client, engine = examining(tmp_path, clock, machine, [came(asked=[1])])
    examine(client, 1, "Made-up one.")
    raw = client.get("/teaching/cases/1").text
    form = raw.split('id="examine"', 1)[1].split("</form>", 1)[0]
    assert 0 < form.find('id="examine-send"') < form.find('id="finish-examination" formaction="/teaching/cases/1/finish-examination"')
    assert ">Finish the examination</button>" in form and "This shows the case&#39;s other findings and brings the first question." in form
    assert 'id="other-findings"' not in raw and TWO not in raw                         # the rest is not on the page yet
    # A request typed and not sent travels with the press and refuses it.
    refused = client.post("/teaching/cases/1/finish-examination", data={"text": "Typed and not sent."})
    assert refused.status_code == 400 and box_of(refused.text, "examine-box") == "Typed and not sent."
    assert refusal_on(refused.text, "finish-examination") == (
        "You have typed something and not sent it. Send it, or clear the box, before you finish the examination.")
    done = client.post("/teaching/cases/1/finish-examination", data={"text": ""})
    assert done.status_code == 303 and done.headers["location"] == "/teaching/cases/1"
    cases = app.state.parts.teaching.cases
    assert cases.get(1)["step"] == "question_1" and cases.get(1)["examination_finished_at"]
    raw = client.get("/teaching/cases/1").text
    rest = raw.split('<h3 id="other-findings">The case&#39;s other findings</h3>', 1)[1].split("</section>", 1)[0]
    assert f'<li class="finding">{TWO}</li><li class="finding">{THREE}</li>' in rest and "qfindone" not in rest
    assert raw.count("qfindone") == 1                                                  # what was shown stays, once
    assert 'id="examine-box"' not in raw and 'id="finish-examination"' not in raw      # no press that cannot act
    # One way: a request or a second Finish from an older page stores nothing and says so, with the words.
    late = examine(client, 2, "A request after the end.")
    assert late.status_code == 200 and len(cases.examined(1)) == 1 and len(engine.calls) == 1
    assert t.STALE + " You had typed: A request after the end." in text_of(late)
    assert other_findings(SCENARIO, cases.examined(1)) == [TWO, THREE]


def test_15_14_where_nothing_is_left_and_where_the_case_holds_no_finding_at_all_the_page_says_so(tmp_path, clock, machine):
    app, client, engine = examining(tmp_path / "all", clock, machine, [came(asked=[1, 2, 3])])
    examine(client, 1, "Everything made up.")
    client.post("/teaching/cases/1/finish-examination", data={"text": ""})
    raw = client.get("/teaching/cases/1").text
    assert '<p class="not-held" id="no-other-finding">The case holds no other finding.</p>' in raw and 'id="the-rest"' not in raw
    # Case 2 of the made bank holds no finding at all: the request is answered with the owner's sentence, and Finish says so.
    app, client, engine = examining(tmp_path / "none", clock, machine, [came(not_in_case=["a made-up chest"])], number=2)
    examine(client, 1, "Listen to a made-up chest.")
    assert block(client.get("/teaching/cases/1").text, 1) == f"You typed: Listen to a made-up chest. a made-up chest : {NO_FINDING}"
    client.post("/teaching/cases/1/finish-examination", data={"text": ""})
    raw = client.get("/teaching/cases/1").text
    assert '<p class="not-held" id="no-finding-at-all">This case holds no examination finding.</p>' in raw
    assert "The case holds no other finding." not in raw


@pytest.mark.parametrize("answer, why", [(EngineTimeout("made-up: no answer"), "too slow"), ({"asked": "not a list"}, "the reply did not fit its form")])
def test_R30_a_failed_examination_shows_no_finding_and_no_sentence_about_one_and_keeps_the_words(tmp_path, clock, machine, answer, why):
    app, client, engine = examining(tmp_path, clock, machine, [answer, came(asked=[1])])
    refused = examine(client, 1, "Made-up one, typed & kept.")
    assert refused.status_code == 400 and refusal_on(refused.text, "examine-send") == (
        f"The examination could not be read: {why}. Your words are still in the box, and no finding is shown for them.")
    assert box_of(refused.text, "examine-box") == "Made-up one, typed & kept."
    assert 'id="examined-1"' not in refused.text and NO_FINDING not in refused.text and "qfindone" not in refused.text
    assert app.state.parts.teaching.cases.examined(1) == [] and len(engine.calls) == 1          # nothing asked again by itself
    assert examine(client, 1, "Made-up one, typed & kept.").status_code == 303                  # sent again by the learner
    assert block(client.get("/teaching/cases/1").text, 1) == f"You typed: Made-up one, typed & kept. {ONE}"


def test_R15_an_empty_request_a_second_press_and_requests_past_their_room_store_nothing_and_say_so(tmp_path, clock, machine):
    app, client, engine = examining(tmp_path, clock, machine, [came(asked=[1])] + [came()] * 4)
    assert refusal_on(examine(client, 1, "  ").text, "examine-send") == "Type what you would examine first."
    assert refusal_on(examine(client, 1, "x" * 1001).text, "examine-send") == "This request is too long. Shorten it to 1,000 characters or fewer."
    assert engine.calls == []
    assert examine(client, 1, "Made-up one.").status_code == 303
    again = examine(client, 1, "Made-up one.")                                         # the same press a second time
    assert again.status_code == 200 and t.STALE in text_of(again) and box_of(again.text, "examine-box") == "Made-up one."
    assert len(app.state.parts.teaching.cases.examined(1)) == 1 and len(engine.calls) == 1
    # The room kept for every request of a case together: past it the request is not sent, and the way on is said.
    assert room.EXAMINED_ROOM == 3000
    for n in (2, 3):
        assert examine(client, n, "y" * 1000).status_code == 303
    full = examine(client, 4, "z" * 1000)
    assert full.status_code == 400 and refusal_on(full.text, "examine-send") == "No more requests can be read for this case. Finish the examination to go on."
    assert len(engine.calls) == 3 and box_of(full.text, "examine-box") == "z" * 1000
