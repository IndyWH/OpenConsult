"""The three questions and the making of the feedback (spec 12.1, step 5;
15.14, ruling 13 and the details of run 10b: The three questions; R15;
R30). The questions are the owner's words and go to no model. A made
scenario and a made engine: nothing a model wrote is read."""

import pytest

from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.teaching import frames, words as t
from tests import made_teaching
from tests.conftest import refusal_on, text_of
from tests.fakes import FakeEngine
from tests.test_teaching_examination import came
from tests.test_teaching_history import reply
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import events, start

SCENARIO = made_teaching.SCENARIO
Q1, Q2, Q3 = ("What is your differential diagnosis?", "What investigations would you order?",
              "What is your plan, and does this patient need a referral?")
SAID = [("doctor", "A made-up line."), ("patient", "A made-up reply.")]
THE_ANSWERS = {"differential": "A made-up differential.", "investigations": "A made-up investigation.", "plan": "A made-up plan."}


def at_the_questions(tmp_path, clock, machine, feedback, held: bool = False, number: int = 1, lines=("A made-up line.",)):
    """A case of the made bank at its first question: one line, one examination request. The feedback is made at
    once where the app would make it beside the page; with held, the work is kept in a list for the test to run."""
    engine = FakeEngine(script={"teaching_patient": [reply("A made-up reply.")] * len(lines), "teaching_examination": [came(asked=[1])],
                                "teaching_feedback": list(feedback)})
    app, client = teaching_app(tmp_path, clock, machine, engine)
    works = []
    app.state.parts.teaching.run = works.append if held else (lambda work: work())
    start(client, number)
    for n, line in enumerate(lines, 1):
        client.post("/teaching/cases/1/say", data={"line": str(n), "text": line})
    client.post("/teaching/cases/1/end-history", data={"text": ""})
    client.post("/teaching/cases/1/examine", data={"n": "1", "text": "Made-up one."})
    client.post("/teaching/cases/1/finish-examination", data={"text": ""})
    return app, client, engine, works


def answer(client, question: int, text: str):
    return client.post("/teaching/cases/1/answer", data={"question": str(question), "text": text})


def answer_all(client):
    for question, name in enumerate(("differential", "investigations", "plan"), 1):
        assert answer(client, question, THE_ANSWERS[name]).status_code == 303


def test_12_1_step_5_the_three_questions_are_the_owners_words_one_at_a_time_and_go_to_no_model(tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [made_teaching.FEEDBACK_OK], held=True)
    assert t.QUESTIONS == (Q1, Q2, Q3)                                                 # the owner's, letter for letter
    asked_before = len(engine.calls)
    for n, (question, later) in enumerate([(Q1, (Q2, Q3)), (Q2, (Q3,)), (Q3, ())], 1):
        raw = client.get("/teaching/cases/1").text
        page = text_of(client.get("/teaching/cases/1"))
        assert f'<label for="answer-box" class="question" id="question">{question}</label>' in text_of(client.get("/teaching/cases/1"))
        assert f'<p class="mark" id="question-of">Question {n} of 3</p>' in raw and f'name="question" value="{n}"' in raw
        assert not [q for q in later if q in page]                                     # one at a time: the later ones are not on the page
        assert raw.count('id="answer-box"') == 1 and 'maxlength="1500"' in raw
        sent = answer(client, n, f"  A made-up answer {n}.\nOn two lines.  ")
        # After the first and the second the next question's box takes the keyboard; after the third the page comes back
        # at the questions, where it says that the feedback is being made.
        assert sent.status_code == 303 and sent.headers["location"] == "/teaching/cases/1" + ("#questions" if n == 3 else "")
        # Answered, it stands above with the learner's answer as typed.
        raw = client.get("/teaching/cases/1").text
        assert f'id="answered-{n}"' in raw and f"A made-up answer {n}.\nOn two lines." in raw
    assert len(engine.calls) == asked_before and works and len(works) == 1             # no question went to a model
    row = app.state.parts.teaching.cases.get(1)
    assert (row["answer_differential"], row["answer_investigations"], row["answer_plan"], row["step"]) == (
        "A made-up answer 1.\nOn two lines.", "A made-up answer 2.\nOn two lines.", "A made-up answer 3.\nOn two lines.", "feedback")


def test_15_14_an_empty_answer_is_not_taken_and_a_press_out_of_turn_stores_nothing(tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [made_teaching.FEEDBACK_OK], held=True)
    cases = app.state.parts.teaching.cases
    for empty in ("", "  \n "):
        refused = answer(client, 1, empty)
        assert refused.status_code == 400 and refusal_on(refused.text, "answer-send") == "Type an answer, even a short one."
    too_long = answer(client, 1, "x" * 1501)
    assert refusal_on(too_long.text, "answer-send") == "This answer is too long. Shorten it to 1,500 characters or fewer."
    assert ">" + "x" * 1501 + "</textarea>" in too_long.text                           # the words are still in their box
    assert cases.get(1)["step"] == "question_1" and cases.get(1)["answer_differential"] is None
    # Question 2 answered before question 1, or question 1 a second time: nothing is stored, and the page says so.
    early = answer(client, 2, "An answer out of turn.")
    assert early.status_code == 200 and t.STALE + " You had typed: An answer out of turn." in text_of(early)
    assert answer(client, 1, "A first answer.").status_code == 303
    again = answer(client, 1, "A first answer, pressed again.")
    assert again.status_code == 200 and t.STALE in text_of(again) and cases.get(1)["answer_differential"] == "A first answer."
    assert cases.get(1)["step"] == "question_2" and works == []


def test_15_14_after_the_third_answer_the_feedback_is_made_once_by_frames_alone_and_the_page_says_that_it_is_being_made(tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [made_teaching.FEEDBACK_OK, {"never": "asked"}], held=True)
    p = app.state.parts
    answer_all(client)
    # Being made beside the page: the page says so and asks again by itself; there is no box and no press.
    raw = client.get("/teaching/cases/1").text
    # Restated by mail 2, the sentence's own words unchanged. OLD: '<p class="waiting" id="feedback-making" role="status">The
    # feedback is being made. ...'. NEW: the sentence also asks for the keyboard, so that the browser brings it into the
    # window at each ask, now that the address the page asks at names no place.
    assert ('<p class="waiting" id="feedback-making" role="status" tabindex="-1" autofocus>The feedback is being made. This usually takes a few '
            'seconds, at most 2 minutes.</p>') in raw
    # Restated by mail 2 (the owner's room check of 25 Nov 2026). OLD: the page asked again at ...?quiet#questions, an
    # address with a # part, which a browser asked a second time takes for a place in the page it has, and loads
    # nothing. NEW: an address with no # part, which says that it is the wait's own ask.
    assert '<meta http-equiv="refresh" content="2;url=/teaching/cases/1?quiet&amp;waits=feedback">' in raw
    assert 'id="answer-box"' not in raw and 'id="feedback-again"' not in raw and 'id="feedback-failed"' not in raw
    assert t.STALE in text_of(client.post("/teaching/cases/1/again"))                  # a press from an older page: nothing a second time
    assert len(works) == 1 and engine.calls_for("teaching_feedback") == []
    works.pop()()                                                                      # the app's own work, run now
    # One call, built by frames from the scenario, the numbered turns, what was asked at the examination and the answers.
    call, = engine.calls_for("teaching_feedback")
    assert call.system == loader.prompt("teaching_feedback")
    assert call.user == frames.feedback_message(SCENARIO, SAID, ["Made-up one."], THE_ANSWERS)
    row = p.teaching.cases.get(1)
    assert row["step"] == "done" and row["feedback"] == made_teaching.FEEDBACK_OK and row["finished_at"] and not p.teaching.making(1)
    assert p.calls.get(p.teaching.cases.calls(1)[-1])["job"] == "teaching_feedback"
    assert events(app)[0] == ("teaching.finished", "case 1: 1 lines, 1 examination requests, feedback made")
    # Once: no view, no press and no answer from an older page makes it again.
    raw = client.get("/teaching/cases/1").text
    assert "http-equiv=\"refresh\"" not in raw and 'id="feedback-making"' not in raw
    client.post("/teaching/cases/1/again")
    answer(client, 3, "A third answer again.")
    assert works == [] and len(engine.calls_for("teaching_feedback")) == 1 and p.teaching.cases.get(1)["answer_plan"] == "A made-up plan."


@pytest.mark.parametrize("failed, why", [(EngineTimeout("made-up: no answer"), "too slow"), ({"points": "not a list"}, "the reply did not fit its form")])
def test_R30_a_feedback_that_did_not_come_keeps_everything_says_why_and_is_made_again_by_a_press_alone(tmp_path, clock, machine, failed, why):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [failed, made_teaching.FEEDBACK_OK])
    p = app.state.parts
    answer_all(client)
    row = p.teaching.cases.get(1)
    assert row["step"] == "feedback" and row["feedback"] is None and row["failure"] in ("too_slow", "bad_form")
    for _ in range(3):                                                                 # nothing is asked a second time by itself
        raw = client.get("/teaching/cases/1").text
    assert len(engine.calls_for("teaching_feedback")) == 1 and "http-equiv=\"refresh\"" not in raw
    assert f"The feedback could not be made: {why}. Your lines and your three answers are kept." in text_of(client.get("/teaching/cases/1"))
    assert '<button class="primary" id="feedback-again">Make the feedback again</button>' in raw
    assert "A made-up line." in raw and "A made-up differential." in raw and "A made-up plan." in raw      # all the learner did is there
    assert p.teaching.cases.answers(row) == THE_ANSWERS and len(p.teaching.cases.turns(1)) == 2
    assert events(app)[0][0] == "teaching.started"                                     # not finished: no such line yet
    again = client.post("/teaching/cases/1/again")
    assert again.status_code == 303 and again.headers["location"] == "/teaching/cases/1#questions"
    assert p.teaching.cases.get(1)["step"] == "done" and p.teaching.cases.get(1)["failure"] is None
    assert len(engine.calls_for("teaching_feedback")) == 2 and events(app)[0][0] == "teaching.finished"


def test_R30_a_making_that_the_apps_stop_cut_short_is_said_plainly_and_made_again_by_a_press(tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [made_teaching.FEEDBACK_OK], held=True)
    teaching = app.state.parts.teaching
    answer_all(client)
    works.clear()                                                                      # the app was closed: the work is gone,
    teaching._making.clear()                                                           # and the next run knows of none being made
    page = text_of(client.get("/teaching/cases/1"))
    assert "The feedback could not be made: OpenConsult was closed before the answer came. Your lines and your three answers are kept." in page
    assert engine.calls_for("teaching_feedback") == []
    assert client.post("/teaching/cases/1/again").status_code == 303 and len(works) == 1
    works.pop()()
    assert teaching.cases.get(1)["step"] == "done"


WAIT = "/teaching/cases/1?quiet&waits=feedback"       # the address a page that waits for its feedback asks again at


def asks_again_at(raw: str) -> str | None:
    """The address a page moves to by itself, or None where it does not."""
    import html
    import re
    found = re.search(r'<meta http-equiv="refresh" content="\d+;url=([^"]+)">', raw)
    return html.unescape(found.group(1)) if found else None


def test_room_check_of_25_nov_a_page_that_waits_for_its_feedback_asks_at_an_address_with_no_hash_part_and_is_sent_on_to_the_feedback(
        tmp_path, clock, machine):
    # The owner's room check of 25 Nov 2026: the feedback was made after 3.6 s and the page went on saying, for more
    # than two minutes, that it was being made. The page asked again at an address with a # part; asked a second time,
    # a browser takes that for a place inside the page it has and loads nothing (measured in Chrome, mail 2).
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [made_teaching.FEEDBACK_OK], held=True)
    answer_all(client)
    first = client.get("/teaching/cases/1").text                                       # the page after the third answer
    assert asks_again_at(first) == WAIT and "#" not in WAIT
    # The sentence asks for the keyboard, so that a browser brings it into the window at each ask, with no # part.
    assert '<p class="waiting" id="feedback-making" role="status" tabindex="-1" autofocus>' in first
    # While the feedback is made every ask is answered with the page, which asks again at that same address.
    for _ in range(3):
        asked = client.get(WAIT)
        assert asked.status_code == 200 and asks_again_at(asked.text) == WAIT and 'id="feedback-making"' in asked.text
    works.pop()()                                                                      # the feedback is made
    # The next ask of the waiting page is sent on to the feedback's own place in the page: with no press and no reload
    # the learner is looking at it. That address is another address, so the browser loads it.
    sent_on = client.get(WAIT)
    assert sent_on.status_code == 303 and sent_on.headers["location"] == "/teaching/cases/1#feedback"
    shown = client.get("/teaching/cases/1").text
    assert '<section class="pane" id="feedback">' in shown and asks_again_at(shown) is None and 'id="feedback-making"' not in shown
    assert client.get(WAIT).status_code == 303                                         # an older waiting page, asking late, is sent on too
    # The page's ordinary timed check, which names no wait, is never sent anywhere: a learner reading is left where they read.
    assert client.get("/teaching/cases/1?quiet").status_code == 200
    assert len(engine.calls_for("teaching_feedback")) == 1                             # asking made nothing a second time


def test_room_check_of_25_nov_a_waiting_page_is_sent_on_to_the_sentence_of_a_feedback_that_did_not_come(tmp_path, clock, machine):
    app, client, engine, works = at_the_questions(tmp_path, clock, machine, [EngineTimeout("made-up: no answer")], held=True)
    answer_all(client)
    assert client.get(WAIT).status_code == 200                                         # still being made
    works.pop()()                                                                      # it fails
    sent_on = client.get(WAIT)
    assert sent_on.status_code == 303 and sent_on.headers["location"] == "/teaching/cases/1#feedback-failed"
    shown = client.get("/teaching/cases/1").text
    assert 'id="feedback-failed"' in shown and 'id="feedback-again"' in shown and asks_again_at(shown) is None
    assert len(engine.calls_for("teaching_feedback")) == 1                             # nothing is asked again by itself (R30)
    # Made again by the press: the page waits again, at the same address with no # part.
    engine.script["teaching_feedback"].append(made_teaching.FEEDBACK_OK)
    client.post("/teaching/cases/1/again")
    assert asks_again_at(client.get("/teaching/cases/1").text) == WAIT and client.get(WAIT).status_code == 200
    works.pop()()
    assert client.get(WAIT).headers["location"] == "/teaching/cases/1#feedback"


def test_room_check_of_25_nov_no_waiting_page_asks_again_at_an_address_with_a_hash_part_and_a_wait_that_is_not_one_changes_nothing(
        tmp_path, clock, machine):
    # The writing of a fresh scenario waits the same way; its address never had a # part (proven in Chrome, mail 2).
    from tests.test_teaching_fresh import fresh_app, write
    app, client, engine, works = fresh_app(tmp_path / "fresh", clock, machine, [SCENARIO], held=True)
    write(client)
    again = asks_again_at(client.get("/teaching/cases/1").text)
    assert again == "/teaching/cases/1?quiet" and "#" not in again
    assert client.get(again).status_code == 200 and asks_again_at(client.get(again).text) == again
    # The wait's address asked of a case that is not waiting for its feedback: the page where the case stands, no more.
    assert client.get(WAIT).status_code == 200 and 'id="case-writing"' in client.get(WAIT).text
    works.pop()()
    assert client.get(WAIT).status_code == 200 and 'id="say-box"' in client.get(WAIT).text
    assert client.get("/teaching/cases/9?quiet&waits=feedback").headers["location"] == "/teaching"
