"""The delete of a kept case (spec 15.14, ruling 22 and the details of
run 10b: Kept cases; R15). One question that says what goes and that it
cannot be undone; then the case with every line, reply, finding shown,
answer and feedback, and every stored model call of it, in one go; and
one audit line of counts. A made bank and a made engine."""

from openconsult.teaching import play, words as t
from tests.conftest import refusal_on, text_of
from tests.test_teaching_kept import finish, rows, scripted
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import events, start

QUESTION = ("Delete this case of 4 Oct 2026? Its lines, the patient's replies, the findings shown, your answers, the feedback and "
            "the stored model calls of the case all go. This cannot be undone.")
TYPED = ("A made-up line.", "Made-up one.", "A made-up answer 1.", "A made-up answer 3.")


def two_cases(tmp_path, clock, machine):
    """Case 1 finished, case 2 one line in."""
    app, client = teaching_app(tmp_path, clock, machine, scripted())
    app.state.parts.teaching.run = lambda work: work()
    start(client, 1)
    finish(client, 1)
    start(client, 2)
    client.post("/teaching/cases/2/say", data={"line": "1", "text": "A line of the case that stays."})
    return app, client


def test_15_14_ruling_22_the_press_first_asks_one_question_that_says_what_goes_and_that_it_cannot_be_undone(tmp_path, clock, machine):
    app, client = two_cases(tmp_path, clock, machine)
    p = app.state.parts
    raw = client.get("/teaching").text
    assert '<button id="delete-1" aria-describedby="delete-1-refusal">Delete</button>' in raw and 'id="delete-question-1"' not in raw
    asked = client.post("/teaching/cases/1/delete")
    assert asked.status_code == 200 and f'<p class="statement" id="delete-question-1">{QUESTION.replace(chr(39), "&#39;")}</p>' in asked.text
    row = asked.text.split('<tr data-kept="1">', 1)[1].split("</tr>", 1)[0]
    assert '<input type="hidden" name="confirm" value="yes">' in row and '<button class="primary danger" id="confirm-delete-1"' in row
    assert f'<a class="button" id="keep-1" href="/teaching#your-cases">' in row and 'id="delete-question-2"' not in asked.text
    # Nothing has gone: the question alone removes nothing, and Keep leaves the case as it was.
    assert p.teaching.cases.get(1)["step"] == "done" and len(p.teaching.cases.turns(1)) == 2 and len(rows(client.get("/teaching").text)) == 2
    assert "teaching.deleted" not in [event for event, _ in events(app)]


def test_15_14_ruling_22_yes_removes_the_case_with_every_line_and_stored_call_in_one_go_and_leaves_every_other_case(tmp_path, clock, machine):
    app, client = two_cases(tmp_path, clock, machine)
    p = app.state.parts
    calls_of_1, calls_of_2 = p.teaching.cases.calls(1), p.teaching.cases.calls(2)
    assert len(calls_of_1) == 3 and len(calls_of_2) == 1
    done = client.post("/teaching/cases/1/delete", data={"confirm": "yes"})
    assert done.status_code == 303 and done.headers["location"] == "/teaching?deleted=yes#your-cases"
    cases = p.teaching.cases
    assert cases.get(1) is None and cases.turns(1) == [] and cases.examined(1) == [] and cases.calls(1) == []
    assert [row["id"] for row in p.calls.rows(newest_first=False)] == calls_of_2      # its model calls are gone from the record, the other case's are not
    assert cases.get(2)["step"] == "history" and [turn["text"] for turn in cases.turns(2)] == ["A line of the case that stays.", "A made-up reply."]
    # The audit line: counts, and never a word that was typed.
    assert events(app)[0] == ("teaching.deleted", "case 1 of 2026-10-04: 2 turns, 1 examination requests, 3 answers, 1 feedback, 3 model calls")
    log = client.get("/log").text
    assert "Teaching case deleted" in log and not [words for words in TYPED if words in log]
    # The page says so, and lists the case no longer; the case has no page.
    page = client.get("/teaching?deleted=yes").text
    assert '<p class="notice" id="case-deleted" role="status">The case was deleted.</p>' in page and len(rows(page)) == 1
    assert 'id="case-deleted"' not in client.get("/teaching").text
    assert client.get("/teaching/cases/1").headers["location"] == "/teaching"
    # A second press, from an older page: nothing more is removed, and the page says where things stand.
    again = client.post("/teaching/cases/1/delete", data={"confirm": "yes"})
    assert again.status_code == 200 and t.STALE in text_of(again) and len(events(app)) == 4      # two started, one finished, one deleted
    assert cases.get(2) is not None


def test_15_14_ruling_22_a_case_that_is_not_finished_is_deleted_as_well_with_its_failed_calls(tmp_path, clock, machine):
    from openconsult.llm.engine import EngineTimeout
    from tests.fakes import FakeEngine
    engine = FakeEngine(script={"teaching_case": [EngineTimeout("made-up: no answer")]})
    app, client = teaching_app(tmp_path, clock, machine, engine)
    p = app.state.parts
    p.teaching.run = lambda work: work()
    press = client.get("/teaching").text.split('id="start-fresh-form"', 1)[1].split('name="press" value="', 1)[1].split('"', 1)[0]
    client.post("/teaching/cases", data={"topic": "A made-up topic", "level": "noisy", "press": press})
    assert p.teaching.cases.get(1)["step"] == "writing" and len(p.teaching.cases.calls(1)) == 1
    assert rows(client.get("/teaching").text)[0][3:] == ["AI-written, not reviewed by a clinician", "Not finished", "Go on"]
    assert client.post("/teaching/cases/1/delete", data={"confirm": "yes"}).status_code == 303
    assert p.teaching.cases.get(1) is None and p.calls.rows() == []
    assert events(app)[0] == ("teaching.deleted", "case 1 of 2026-10-04: 0 turns, 0 examination requests, 0 answers, 0 feedback, 1 model calls")


def test_R15_a_case_whose_answer_from_the_model_is_awaited_is_not_deleted_under_it_and_the_press_says_so(tmp_path, clock, machine, monkeypatch):
    app, client = two_cases(tmp_path, clock, machine)
    teaching = app.state.parts.teaching
    monkeypatch.setattr(play, "DELETE_WAITS_S", 0.05)
    held = teaching._lock(2)
    held.acquire()                                                                     # as while a call of case 2 is in flight
    try:
        refused = client.post("/teaching/cases/2/delete", data={"confirm": "yes"})
    finally:
        held.release()
    assert refused.status_code == 400
    assert refusal_on(refused.text, "delete-2") == "This case is waiting for the language model. Delete it when the answer has come."
    assert teaching.cases.get(2) is not None and len(teaching.cases.turns(2)) == 2
    assert client.post("/teaching/cases/2/delete", data={"confirm": "yes"}).status_code == 303 and teaching.cases.get(2) is None


def test_15_14_the_audit_lines_of_a_case_hold_counts_and_never_a_word_that_was_typed(tmp_path, clock, machine):
    app, client = two_cases(tmp_path, clock, machine)
    client.post("/teaching/cases/1/delete", data={"confirm": "yes"})
    lines = events(app)
    assert [event for event, _ in lines] == ["teaching.deleted", "teaching.started", "teaching.finished", "teaching.started"]
    assert lines[2] == ("teaching.finished", "case 1: 1 lines, 1 examination requests, feedback made")
    everything = " ".join(detail for _, detail in lines)
    for words in (*TYPED, "A line of the case that stays.", "A made-up reply.", "Made Up", "made-up ache", "Qexamone", "A made-up topic"):
        assert words not in everything, words
