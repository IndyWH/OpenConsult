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
    # Restated by mail 2 (the owner's room check of 25 Nov 2026: after the press the page went to its top, and the
    # question was out of sight). OLD: the press was answered with the page itself, status 200, at the address of the
    # press, and Keep led to the head of the list. NEW: the press leads to the teaching page at the row, where the
    # question stands; Keep leads back to the row.
    pressed = client.post("/teaching/cases/1/delete")
    assert pressed.status_code == 303 and pressed.headers["location"] == "/teaching?asking=1#kept-1"
    asked = client.get("/teaching?asking=1")
    assert asked.status_code == 200 and f'<p class="statement" id="delete-question-1">{QUESTION.replace(chr(39), "&#39;")}</p>' in asked.text
    row = asked.text.split('<tr data-kept="1" id="kept-1">', 1)[1].split("</tr>", 1)[0]
    assert '<input type="hidden" name="confirm" value="yes">' in row and '<button class="primary danger" id="confirm-delete-1"' in row
    assert f'<a class="button" id="keep-1" href="/teaching#kept-1">' in row and 'id="delete-question-2"' not in asked.text
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
    # Restated by mail 2. OLD: answered with the page, status 200. NEW: led to the list, which says so, in sight.
    again = client.post("/teaching/cases/1/delete", data={"confirm": "yes"})
    assert again.status_code == 303 and again.headers["location"] == "/teaching?gone=yes#your-cases"
    gone = client.get("/teaching?gone=yes")
    assert f'<p class="notice" id="cases-notice" role="status">{t.STALE}</p>' in text_of(gone) and len(events(app)) == 4      # two started, one finished, one deleted
    assert client.post("/teaching/cases/1/delete").headers["location"] == "/teaching?gone=yes#your-cases"       # and the first press on a case that is gone
    assert cases.get(2) is not None


def test_room_check_of_25_nov_after_delete_the_question_stands_at_its_row_with_the_script_and_with_none_and_keep_leads_back_to_the_row(
        tmp_path, clock, machine):
    # The owner's room check of 25 Nov 2026: after the press Delete on a row of Your cases the page went to its top; the
    # question and Yes, delete were out of sight. Measured in Chrome on a list of 30: the question stood 3,724 px down.
    import re
    app, client = two_cases(tmp_path, clock, machine)
    raw = client.get("/teaching").text
    # With the page's script: the page keeps its place over the load that the press makes (15.10, ruling 34). The page
    # is marked for place.js and names it; the row's form is marked data-stay; each row has a name of its own that
    # still stands after the press, for the window to be set by.
    assert '<div class="teaching" id="teaching-page" data-keeps-place data-path="/teaching">' in raw
    assert re.search(r'<script src="/static/place\.js\?v=[0-9a-f]{12}"></script>', raw)
    for case in (1, 2):
        assert f'<tr data-kept="{case}" id="kept-{case}">' in raw
        assert f'<form method="post" action="/teaching/cases/{case}/delete" data-stay><button id="delete-{case}"' in raw
    # The script asks the app for no place in the address, and the app names none: the window stays where it was.
    kept = client.post("/teaching/cases/2/delete", data={"place": "keep"})
    assert kept.status_code == 303 and kept.headers["location"] == "/teaching?asking=2"
    # With no script the app sends the browser to the row's own place.
    plain = client.post("/teaching/cases/2/delete")
    assert plain.headers["location"] == "/teaching?asking=2#kept-2"
    asked = client.get("/teaching?asking=2").text
    row = asked.split('<tr data-kept="2" id="kept-2">', 1)[1].split("</tr>", 1)[0]
    assert 'id="delete-question-2"' in row and 'id="confirm-delete-2"' in row and '<a class="button" id="keep-2" href="/teaching#kept-2">' in row
    assert 'id="delete-question-1"' not in asked and 'id="delete-2"' not in asked      # one question, at its own row; its Delete press is gone
    # A row named by an address stands clear of the app's bar, which stays at the window's top.
    sheet = client.get("/static/teaching.css").text
    assert re.search(r"\.teaching tr\[data-kept\][^{]*\{ scroll-margin-top: 5rem; \}", sheet)
    assert re.search(r'<link rel="stylesheet" href="/static/teaching\.css\?v=[0-9a-f]{12}">', raw)
    # Nothing is removed by any of it, and a question for a case that is not there asks nothing.
    assert len(rows(client.get("/teaching").text)) == 2 and app.state.parts.teaching.cases.get(2) is not None
    assert 'id="delete-question-' not in client.get("/teaching?asking=9").text and 'id="delete-question-' not in client.get("/teaching?asking=x").text


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
