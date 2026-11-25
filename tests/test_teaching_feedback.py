"""The feedback as a learner is shown it (spec 12.4; 12.3, rule 4; D5;
D36; 15.14, rulings 13 and 20, and the details of run 10b: The
feedback, What did not come back, The known fault on the page). The
answers here are made up, to put each case of the details on a page:
nothing a model wrote is read, and nothing a model would write is
asserted."""

import html
import re

from openconsult.teaching import feedback as feedback_module, words as t
from openconsult.teaching.feedback import built
from tests import made_teaching
from tests.conftest import text_of
from tests.test_teaching_questions import answer_all, at_the_questions
from tests.test_teaching_start import cloud_teaching, start

SCENARIO = made_teaching.SCENARIO
SAID = [("doctor", "first line"), ("patient", "first reply"), ("doctor", "second line"), ("patient", "second reply")]
ANSWERS = {"differential": "Qdiagone and a Made-Up Extra, I think.", "investigations": "A made-up investigation.", "plan": "A made-up plan."}
# A made answer that holds every case of the details. Points 1 to 3 are data gathering, 4 to 6 management, 7 to 9
# relating. Turn 2 is the patient's. Points 6 to 9, diagnosis 3 and both steps of the plan did not come back.
ANSWER = {
    "reasoning": "made up",
    "points": [{"number": 1, "met": True, "turns": [1, 2]},        # met, with its line: the patient's turn is dropped by the rule
               {"number": 2, "met": True, "turns": [2]},           # met, and no line of the learner's is left
               {"number": 3, "met": True, "turns": []},            # met, and none was given
               {"number": 4, "met": False, "turns": [3]},          # not met
               {"number": 5, "met": True, "turns": [3, 1, 3]}],    # met, with two lines
    "differential": [{"number": 1, "named": True}, {"number": 2, "named": False}],
    "differential_extra": ["a made-up extra", "words never typed"],
    "investigations": [{"number": 1, "named": True}, {"number": 1, "named": False}],
    "investigations_extra": [],
    "plan": [], "plan_extra": [],
    "most_important_missed": 4, "done_well": [1, 4, 7, 5, 2, 3],
    "signposted": True, "signpost_turns": [3, 2],
}


def with_(**changes) -> dict:
    return {**ANSWER, **changes}


def finished(tmp_path, clock, machine, answer=ANSWER):
    """A case of the made bank played to its feedback, with two lines, the made engine answering with this."""
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [answer], lines=("first line", "second line"))
    for question, name in enumerate(("differential", "investigations", "plan"), 1):
        client.post("/teaching/cases/1/answer", data={"question": str(question), "text": ANSWERS[name]})
    assert app.state.parts.teaching.cases.get(1)["step"] == "done"
    return app, client, engine


def words_in(part: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", part)).split())


def section(raw: str) -> str:
    return raw.split('<section class="pane" id="feedback">', 1)[1].split("</section>", 1)[0]


def point(raw: str, n: int) -> str:
    return words_in(raw.split(f'id="point-{n}">', 1)[1].split("</div>", 1)[0])


def test_12_4_the_five_parts_stand_in_their_order_and_every_word_of_a_point_is_the_scenarios_own(tmp_path, clock, machine):
    app, client, engine = finished(tmp_path, clock, machine)
    raw = section(client.get("/teaching/cases/1").text)
    found = [raw.find(f'id="{part}"') for part in ("feedback-missed", "feedback-done-well", "feedback-lists", "feedback-points", "feedback-signposting")]
    assert all(f >= 0 for f in found) and found == sorted(found)
    assert [words_in(h) for h in re.findall(r"<h3[^>]*>(.*?)</h3>", raw)] == [
        "The most important thing missed", "Done well", "Your differential, investigations and plan, set against the case",
        "The marking points", "Signposting"]
    # The marking points under the three headings of 12.4, each in the scenario's own words.
    assert [words_in(h) for h in re.findall(r"<h4>(.*?)</h4>", raw.split('id="feedback-points"', 1)[1])] == [
        "Data gathering and diagnosis", "Clinical management and medical complexity", "Relating to others"]
    for n, words in enumerate(["Qpointone.", "Qpointtwo.", "Qpointthree.", "Qpointfour.", "Qpointfive.", "Qpointsix.", "Qpointseven.",
                               "Qpointeight.", "Qpointnine."], 1):
        assert point(raw, n).startswith(words)
    # The reasoning the model wrote for itself is on no page.
    assert "made up" not in words_in(raw).replace("A made-up", "").replace("a made-up", "")


def test_15_14_ruling_20_a_point_met_shows_the_learners_own_lines_or_says_plainly_that_none_is_quoted(tmp_path, clock, machine):
    app, client, engine = finished(tmp_path, clock, machine)
    raw = section(client.get("/teaching/cases/1").text)
    # Above the marking points, on every feedback: the line that tells the learner to check each credit.
    assert '<p class="sentence" id="check-each-met">The feedback is made by a language model and can be wrong. Check each Met against your own line beside it.</p>' in raw
    assert raw.find('id="check-each-met"') < raw.find('id="point-1"')
    # Met, with its line: the learner's own words, by the learner's own number. The patient's turn is never quoted.
    assert point(raw, 1) == "Qpointone. ✓ Met Your line 1: first line"
    assert point(raw, 5) == "Qpointfive. ✓ Met Your line 1: first line Your line 2: second line"
    assert "first reply" not in raw and "second reply" not in raw
    # Met, with no line of the learner's left to quote, or none given: the page says so.
    for n, words in ((2, "Qpointtwo."), (3, "Qpointthree.")):
        assert point(raw, n) == f"{words} ✓ Met No line of yours is quoted for this point. Check it yourself."
    # Not met: no line under it.
    assert point(raw, 4) == "Qpointfour. ✗ Not met"
    # What did not come back is not judged, in those words, and never not met.
    for n, words in ((6, "Qpointsix."), (7, "Qpointseven."), (8, "Qpointeight."), (9, "Qpointnine.")):
        assert point(raw, n) == f"{words} – Not judged"
    assert '<p class="mark" id="not-judged-line">Not judged: the model&#39;s answer left this out.</p>' in raw
    assert words_in(raw).count("Not met") == 1 and words_in(raw).count("No line of yours is quoted for this point.") == 2
    # Each state is told by its word; the sign beside it is for the eye alone.
    states = re.findall(r'<span class="state ([a-z-]+)"><span class="sign" aria-hidden="true">(.)</span> ([A-Za-z ]+)</span>', raw)
    assert {(name, word) for name, _, word in states} == {("met", "Met"), ("not-met", "Not met"), ("not-judged", "Not judged"),
                                                           ("named", "Named"), ("not-named", "Not named")}


def test_15_14_the_most_important_thing_missed_in_its_three_cases():
    missed = lambda answer: built(SCENARIO, SAID, ANSWERS, answer)["missed"]           # noqa: E731
    # It names a point that the page shows as not met: that point, in the scenario's own words.
    assert missed(ANSWER) == {"words": "Qpointfour."}
    # The model names none, and no point is shown as not met.
    all_met = [{"number": n, "met": True, "turns": [1]} for n in range(1, 10)]
    assert missed(with_(points=all_met, most_important_missed=0)) == {"sentence": "none_missed"}
    assert t.MISSED_SENTENCES["none_missed"] == "No marking point was marked as missed."
    # Every other case: a point shown as met; one not judged; a number the case does not have; none named while a
    # point is not met; none named while points were left out and none is shown as not met is still none missed.
    for number in (3, 7, 99, 0, -1):
        assert missed(with_(most_important_missed=number)) == {"sentence": "no_single_point"}, number
    assert t.MISSED_SENTENCES["no_single_point"] == "The feedback named no single most important point."
    some_left_out = [{"number": n, "met": True, "turns": [1]} for n in range(1, 5)]
    assert missed(with_(points=some_left_out, most_important_missed=0)) == {"sentence": "none_missed"}


def test_15_14_done_well_is_up_to_three_points_that_the_page_shows_as_met_and_the_rest_are_dropped(tmp_path, clock, machine):
    made = built(SCENARIO, SAID, ANSWERS, ANSWER)
    assert made["done_well"] == ["Qpointone.", "Qpointfive.", "Qpointtwo."]            # 4 is not met, 7 not judged; then the first three
    assert built(SCENARIO, SAID, ANSWERS, with_(done_well=[4, 7, 99, 0]))["done_well"] == []
    assert built(SCENARIO, SAID, ANSWERS, with_(done_well=[1, 1, 1]))["done_well"] == ["Qpointone."]
    app, client, engine = finished(tmp_path, clock, machine, with_(done_well=[4, 7]))
    raw = section(client.get("/teaching/cases/1").text)
    assert '<p class="plain-sentence" id="done-well">Nothing is listed here.</p>' in raw
    assert '<p class="scenario-words" id="missed">Qpointfour.</p>' in raw


def test_12_4_the_three_lists_are_set_against_the_case_with_the_answer_whole_and_what_the_learner_also_named(tmp_path, clock, machine):
    app, client, engine = finished(tmp_path, clock, machine)
    raw = section(client.get("/teaching/cases/1").text)
    differential = words_in(raw.split('id="against-differential">', 1)[1].split("</div>", 1)[0])
    # Each item in the scenario's own words, with Named, Not named, or Not judged where its number did not come back;
    # the diagnosis that must not be missed marked as such; the learner's own answer whole beside them.
    assert differential == ("Differential Qdiagone Must not be missed ✓ Named Qdiagtwo ✗ Not named Qdiagthree – Not judged "
                            "Your answer: Qdiagone and a Made-Up Extra, I think. You also named a Made-Up Extra")
    # You also named: only words that stand in the learner's answer, as the learner typed them. The rest is dropped.
    assert "words never typed" not in raw and "a made-up extra" not in raw
    # An item that came back twice is named only if every entry says so.
    investigations = words_in(raw.split('id="against-investigations">', 1)[1].split("</div>", 1)[0])
    assert investigations == "Investigations Qinvone ✗ Not named Your answer: A made-up investigation."
    assert "qreasonone" not in raw                                                     # the reason of an investigation is the whole scenario's
    # A step of the plan with its urgency where it has one; both steps were left out: not judged, never not named.
    plan = words_in(raw.split('id="against-plan">', 1)[1].split("</div>", 1)[0])
    assert plan == "Plan Qstepone Urgency: urgent – Not judged Qsteptwo – Not judged Your answer: A made-up plan."
    # A list the case does not hold says so.
    empty = built({**SCENARIO, "investigations": []}, SAID, ANSWERS, ANSWER)["lists"][1]
    assert empty["items"] == [] and empty["answer"] == "A made-up investigation." and t.CASE_LISTS_NONE == "The case lists none."


def test_D36_signposting_is_shown_with_the_learners_own_lines_and_never_on_a_patients_turn(tmp_path, clock, machine):
    app, client, engine = finished(tmp_path / "yes", clock, machine)
    raw = section(client.get("/teaching/cases/1").text)
    signposting = words_in(raw.split('id="feedback-signposting"', 1)[1].split(">", 1)[1])
    assert signposting == "Signposting The feedback found signposting in these lines of yours: Your line 2: second line"
    # On the patient's turn alone, or none: by the rule it is no signposting.
    for turns in ([2], []):
        made = built(SCENARIO, SAID, ANSWERS, with_(signpost_turns=turns))
        assert made["signposted"] is False and made["signpost_lines"] == []
    app, client, engine = finished(tmp_path / "no", clock, machine, with_(signposted=False, signpost_turns=[]))
    assert '<p class="plain-sentence" id="signposting">The feedback found no signposting.</p>' in section(client.get("/teaching/cases/1").text)


def test_D5_no_grade_no_pass_or_fail_and_no_count_of_points_anywhere(tmp_path, clock, machine):
    app, client, engine = finished(tmp_path, clock, machine)
    made = built(SCENARIO, SAID, ANSWERS, ANSWER)
    assert set(made) == {"missed", "done_well", "lists", "headings", "any_not_judged", "signposted", "signpost_lines"}
    assert not [value for value in made.values() if isinstance(value, (int, float)) and not isinstance(value, bool)]     # no number is built
    page = words_in(section(client.get("/teaching/cases/1").text)).lower()
    for word in ("grade", "score", "pass", "fail", "%", "points met", "out of", "total"):
        assert word not in page, word
    assert not re.search(r"\b\d+\s*(of|/)\s*\d+\b", page)                              # no count such as 5 of 9


def test_15_14_a_point_that_came_back_twice_and_a_number_the_case_does_not_have():
    # The rule of run 10a: one that came back more than once is met only if every entry is; a number the case does not have is dropped.
    twice = with_(points=[{"number": 1, "met": True, "turns": [1]}, {"number": 1, "met": False, "turns": [3]},
                          {"number": 2, "met": True, "turns": [1]}, {"number": 2, "met": True, "turns": [3]},
                          {"number": 99, "met": True, "turns": [1]}, {"number": 0, "met": True, "turns": [1]}])
    points = [point for group in built(SCENARIO, SAID, ANSWERS, twice)["headings"] for point in group["points"]]
    assert len(points) == 9 and [group["heading"] for group in built(SCENARIO, SAID, ANSWERS, twice)["headings"]] == list(feedback_module.frames.HEADINGS)
    assert (points[0]["state"], points[0]["lines"]) == ("not_met", [])
    assert (points[1]["state"], points[1]["lines"]) == ("met", [{"line": 1, "text": "first line"}, {"line": 2, "text": "second line"}])
    assert all(point["state"] == "not_judged" for point in points[2:])
    # A turn that does not exist is never quoted.
    beyond = built(SCENARIO, SAID, ANSWERS, with_(points=[{"number": 1, "met": True, "turns": [5, 7, 0, -1]}]))
    assert beyond["headings"][0]["points"][0] == {"n": 1, "heading": "data_gathering", "words": "Qpointone.", "state": "met", "lines": []}


def test_15_14_ruling_22_a_finished_case_opens_as_stored_asks_no_model_and_carries_no_mark_cloud(tmp_path, clock, machine):
    app, client, engine = finished(tmp_path / "local", clock, machine)
    asked = len(engine.calls)
    first = client.get("/teaching/cases/1").text
    assert client.get("/teaching/cases/1").text.replace(" ", "") != "" and len(engine.calls) == asked
    assert section(first) == section(client.get("/teaching/cases/1").text)
    assert "first line" in first and "Qexamone: qfindone" in first and "Qdiagone and a Made-Up Extra, I think." in first
    assert 'id="say-box"' not in first and 'id="answer-box"' not in first and 'id="feedback-again"' not in first
    # In cloud mode the mark stands on a case until its feedback has been made, and not after (the owner's okay of 25 Nov 2026).
    from tests.fakes import FakeEngine
    from tests.test_teaching_examination import came
    from tests.test_teaching_history import reply
    claude = FakeEngine(script={"teaching_patient": [reply("A made-up reply.")], "teaching_examination": [came(asked=[1])],
                                "teaching_feedback": [ANSWER]})
    app, client, claude, testers = cloud_teaching(tmp_path / "cloud", clock, claude=claude)
    app.state.parts.teaching.run = lambda work: work()
    start(client, 1)
    client.post("/teaching/cases/1/say", data={"line": "1", "text": "first line"})
    client.post("/teaching/cases/1/end-history", data={"text": ""})
    client.post("/teaching/cases/1/examine", data={"n": "1", "text": "Made-up one."})
    client.post("/teaching/cases/1/finish-examination", data={"text": ""})
    assert 'id="cloud-mark"' in client.get("/teaching/cases/1").text                   # at the questions: still on its way to Claude
    answer_all(client)
    done = client.get("/teaching/cases/1").text
    assert app.state.parts.teaching.cases.get(1)["step"] == "done" and 'id="feedback"' in done and 'id="cloud-mark"' not in done
    assert 'id="cloud-mark"' in client.get("/teaching").text                           # the teaching page keeps it: a new case would go to Claude
