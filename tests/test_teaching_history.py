"""The history of a teaching case (spec 12.3; 10.4; 15.14, rulings 10, 11
and 21, and the details of run 10b: The words a model reads, The
history, Words typed are never lost; R15; R30). A made scenario whose
second part holds words found nowhere in its first, and a made engine
that answers with made replies: nothing a model wrote is read."""

import re

import pytest

from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.settings.path import THIS_COMPUTER, ChosenPath
from openconsult.teaching import bank as bank_module, frames, room, words as t
from tests import made_teaching
from tests.conftest import refusal_on, text_of
from tests.fakes import FakeEngine
from tests.test_connect_screens import NO_CARD
from tests.test_teaching_frames import said_in, words_of
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import cloud_teaching, start

SCENARIO = made_teaching.SCENARIO
PART_TWO = {key: value for key, value in SCENARIO.items() if key not in frames.PART_ONE}


def reply(words: str, facts=(1,)) -> dict:
    return {"reply": words, "facts_used": list(facts)}


def playing(tmp_path, clock, machine, replies, **more):
    """A case of the made bank at its history, on a made engine that answers the patient's calls with these replies."""
    engine = FakeEngine(script={"teaching_patient": list(replies)})
    app, client = teaching_app(tmp_path, clock, machine, engine, **more)
    start(client, 1)
    return app, client, engine


def say(client, line: int, text: str, case: int = 1):
    return client.post(f"/teaching/cases/{case}/say", data={"line": str(line), "text": text})


def box_of(raw: str, box: str = "say-box") -> str:
    """What a box of the page holds, as the app sent it."""
    import html
    field = raw.split(f'id="{box}"', 1)[1].split(">", 1)[0]
    return html.unescape(re.search(r'value="([^"]*)"', field).group(1))


def test_15_14_rulings_10_and_21_a_line_is_sent_by_frames_alone_stored_with_its_reply_and_numbered_as_the_bench_numbered(tmp_path, clock, machine):
    app, client, engine = playing(tmp_path, clock, machine, [reply("A made-up first reply."), reply("A made-up second reply.", [1, 2])])
    cases = app.state.parts.teaching.cases
    sent = say(client, 1, "  Tell me about the made-up ache.  ")
    # To the page with no place named in the address: the box asks for the keyboard itself, and a browser gives it only then.
    assert sent.status_code == 303 and sent.headers["location"] == "/teaching/cases/1"
    assert say(client, 2, "Any made-up fever?").status_code == 303
    # Every request is built by frames and by nothing else: the job's prompt file, and the frame filled from part one.
    first, second = engine.calls_for("teaching_patient")
    assert first.system == second.system == loader.prompt("teaching_patient")
    assert first.user == frames.patient_message(SCENARIO, [], "Tell me about the made-up ache.")
    assert second.user == frames.patient_message(
        SCENARIO, [("doctor", "Tell me about the made-up ache."), ("patient", "A made-up first reply.")], "Any made-up fever?")
    # The actor is given part one alone: no word of the examiner's side is in a request (ruling 10).
    assert not words_of(said_in(PART_TWO)) & words_of(first.user + second.user)
    # The turns as the bench numbered them: the opening words are no turn, the learner's first line is turn 1.
    assert [(turn["n"], turn["speaker"], turn["text"]) for turn in cases.turns(1)] == [
        (1, "doctor", "Tell me about the made-up ache."), (2, "patient", "A made-up first reply."),
        (3, "doctor", "Any made-up fever?"), (4, "patient", "A made-up second reply.")]
    assert frames.turns(cases.conversation(1), loader.layout("teaching")).startswith("1. Doctor: Tell me about the made-up ache.\n2. Patient:")
    # On the page the learner's lines carry the learner's own count, as typed; the patient's replies carry none.
    raw = client.get("/teaching/cases/1").text
    turns = raw.split('data-part="turns"', 1)[1].split('data-part="step"', 1)[0]
    assert [int(n) for n in re.findall(r'<span class="line-number">(\d+)\.</span>', turns)] == [1, 2]
    assert '<p class="turn doctor" id="line-2"><span class="line-number">2.</span> <span class="speaker">You</span> <span class="said">Any made-up fever?</span></p>' in turns
    found = [turns.find(words) for words in ("I have a made-up ache.", "Tell me about the made-up ache.", "A made-up first reply.",
                                             "Any made-up fever?", "A made-up second reply.")]
    assert all(f >= 0 for f in found) and found == sorted(found)
    assert 'data-number="3"' in raw and 'name="line" value="3"' in raw and box_of(raw) == ""
    # The numbers of the facts a reply used are kept and never shown.
    assert [turn["facts_used"] for turn in cases.turns(1)] == [None, "[1]", None, "[1, 2]"] and "facts_used" not in raw
    # Each call is tied to its case, and belongs to no consultation of the clinic.
    rows = [app.state.parts.calls.get(call_id) for call_id in cases.calls(1)]
    assert [(row["job"], row["outcome"], row["consultation_id"]) for row in rows] == [("teaching_patient", "ok", None)] * 2


def test_15_14_an_empty_line_is_not_sent_and_the_page_says_so(tmp_path, clock, machine):
    app, client, engine = playing(tmp_path, clock, machine, [reply("never asked")])
    for empty in ("", "   "):
        refused = say(client, 1, empty)
        assert refused.status_code == 400 and refusal_on(refused.text, "say-send") == "Type a line first."
    assert engine.calls == [] and app.state.parts.teaching.cases.turns(1) == []


@pytest.mark.parametrize("answer, why", [(EngineTimeout("made-up: no answer"), "too slow"), ({"reply": "no list of facts"}, "the reply did not fit its form")])
def test_R30_a_failed_reply_stores_nothing_keeps_the_line_in_its_box_and_is_not_asked_a_second_time(tmp_path, clock, machine, answer, why):
    app, client, engine = playing(tmp_path, clock, machine, [answer, reply("A made-up reply at the second try.")])
    cases = app.state.parts.teaching.cases
    refused = say(client, 1, "A made-up line <typed> & kept.")
    assert refused.status_code == 400
    assert refusal_on(refused.text, "say-send") == (
        f"The patient's reply did not come: {why}. Your line is still in the box. Send it again when you are ready.")
    assert box_of(refused.text) == "A made-up line <typed> & kept."                    # as typed, in its box
    assert cases.turns(1) == [] and "A made-up line" not in refused.text.split('data-part="turns"', 1)[1].split('data-part="step"', 1)[0]
    assert len(engine.calls) == 1                                                     # nothing is asked again by itself
    # The failed call is in the record, tied to the case, so that it goes when the case goes.
    failed = app.state.parts.calls.get(cases.calls(1)[0])
    assert failed["job"] == "teaching_patient" and failed["outcome"] != "ok"
    # The learner sends it again, by the same number: now it is stored.
    assert say(client, 1, box_of(refused.text)).status_code == 303
    assert [turn["text"] for turn in cases.turns(1)] == ["A made-up line <typed> & kept.", "A made-up reply at the second try."]


def test_R15_a_second_press_and_a_press_on_a_stale_page_store_nothing_and_the_page_says_where_the_case_stands(tmp_path, clock, machine):
    app, client, engine = playing(tmp_path, clock, machine, [reply("A made-up first reply."), reply("never given")])
    cases = app.state.parts.teaching.cases
    assert say(client, 1, "A made-up first line.").status_code == 303
    again = say(client, 1, "A made-up first line.")                                    # the same press a second time
    assert again.status_code == 200 and 'id="case-notice"' in again.text
    assert "That press came from a page that was no longer up to date. This is where the case stands now." in text_of(again)
    assert len(cases.turns(1)) == 2 and len(engine.calls) == 1
    assert box_of(again.text) == "A made-up first line."                              # what was typed is in its box again
    late = say(client, 5, "A line from a page that never was.")
    assert late.status_code == 200 and t.STALE in text_of(late) and len(cases.turns(1)) == 2
    assert say(client, 1, "A line for a case that is not there.", case=99).headers["location"] == "/teaching"
    assert client.get("/teaching/cases/1").text.count('id="case-notice"') == 0         # an ordinary view says nothing of it


def test_15_14_the_history_ends_with_one_press_one_way_and_a_line_typed_and_not_sent_refuses_it(tmp_path, clock, machine):
    app, client, engine = playing(tmp_path, clock, machine, [reply("A made-up first reply."), reply("never given")])
    cases = app.state.parts.teaching.cases
    say(client, 1, "A made-up first line.")
    raw = client.get("/teaching/cases/1").text
    form = raw.split('<form method="post" action="/teaching/cases/1/say" id="say"', 1)[1].split("</form>", 1)[0]
    # Enter sends: the box is one line and Send is the form's first press; End the history goes to its own address.
    assert '<input type="text" id="say-box" name="text"' in form and "autofocus" in form and 'maxlength="1000"' in form
    assert 0 < form.find('id="say-send"') < form.find('id="end-history" formaction="/teaching/cases/1/end-history"')
    assert "<p class=\"mark\" id=\"end-history-line\">After this the patient cannot be asked more.</p>" in form
    assert ">End the history</button>" in form
    # A line typed and not sent travels with the press and refuses it: no typed word is lost.
    refused = client.post("/teaching/cases/1/end-history", data={"line": "2", "text": "A line typed and not sent."})
    assert refused.status_code == 400 and cases.get(1)["step"] == "history"
    assert refusal_on(refused.text, "end-history") == "You have typed a line and not sent it. Send it, or clear the box, before you end the history."
    assert box_of(refused.text) == "A line typed and not sent."
    # With the box empty: one press, and no way back.
    ended = client.post("/teaching/cases/1/end-history", data={"line": "2", "text": ""})
    assert ended.status_code == 303 and ended.headers["location"] == "/teaching/cases/1"
    assert cases.get(1)["step"] == "examination" and cases.get(1)["history_ended_at"]
    raw = client.get("/teaching/cases/1").text
    assert 'id="say-box"' not in raw and 'id="say-send"' not in raw and 'id="end-history"' not in raw      # no press that cannot act
    assert "A made-up first line." in raw and "A made-up first reply." in raw                              # what was said stays
    # A line or a second End from an older page: nothing stored, said plainly, and the words not lost.
    late = say(client, 2, "A line after the end.")
    assert late.status_code == 200 and len(cases.turns(1)) == 2 and len(engine.calls) == 1
    assert t.STALE + " You had typed: A line after the end." in text_of(late)
    assert t.STALE in text_of(client.post("/teaching/cases/1/end-history", data={"text": ""}))


def test_15_14_before_the_models_window_is_reached_the_page_says_so_and_at_the_bound_a_line_is_not_sent(tmp_path, clock, machine, monkeypatch):
    app, client, engine = playing(tmp_path, clock, machine, [reply("A made-up reply.")] * 3)
    start_chars = room.feedback_chars(SCENARIO, [])
    assert start_chars == len(loader.prompt("teaching_feedback")) + len(frames.feedback_message(SCENARIO, [], [], room.NO_ANSWERS))
    assert 'id="history-long"' not in client.get("/teaching/cases/1").text
    # A line over its most characters is not sent.
    long_line = say(client, 1, "x" * 1001)
    assert long_line.status_code == 400 and refusal_on(long_line.text, "say-send") == "This line is too long. Shorten it to 1,000 characters or fewer."
    # The bound brought down to this made case, so that two lines fit and a third does not.
    one = len("1. Doctor: A made-up line.\n2. Patient: A made-up reply.\n")
    monkeypatch.setattr(room, "FEEDBACK_BOUND", start_chars + room.AFTER_HISTORY + room.REPLY_ROOM + 2 * one + 20)
    assert say(client, 1, "A made-up line.").status_code == 303 and say(client, 2, "A made-up line.").status_code == 303
    raw = client.get("/teaching/cases/1").text
    assert '<p class="mark" id="history-long" role="status">This history is getting long. Only a few more lines fit. Then end the history.</p>' in raw
    full = say(client, 3, "A made-up line.")
    assert full.status_code == 400 and refusal_on(full.text, "say-send") == "This history is full: the language model cannot read more. End the history to go on."
    assert box_of(full.text) == "A made-up line." and len(engine.calls) == 2 and len(app.state.parts.teaching.cases.turns(1)) == 4
    assert client.post("/teaching/cases/1/end-history", data={"text": ""}).status_code == 303            # the way on is still there


def test_15_14_at_the_bound_the_feedbacks_request_still_fits_with_every_examination_and_answer_at_its_most():
    # The app's own longest scenario, a history filled to the bound with long lines, then all that may follow it.
    scenario = max((case.scenario for case in bank_module.read_bank().cases), key=lambda s: room.feedback_chars(s, []))
    said = []
    while room.line_fits(scenario, said, "d" * 300):
        said += [("doctor", "d" * 300), ("patient", "p" * room.REPLY_ROOM)]
    assert len(said) // 2 == 10                                                        # ten such lines; of the bench's mean length far more
    whole = frames.feedback_message(scenario, said, ["e" * 1000] * 3, {name: "a" * room.ANSWER_MOST for name in room.NO_ANSWERS})
    assert room.examination_fits(["e" * 1000] * 2, "e" * 1000) and not room.examination_fits(["e" * 1000] * 3, "e")
    assert len(loader.prompt("teaching_feedback")) + len(whole) <= room.FEEDBACK_BOUND == 33_000
    # By the figures of run 10a's stored calls that is within the window of 16,384 less the feedback's 2,500 tokens.
    assert 1106 + 0.349 * room.FEEDBACK_BOUND < 16384 - 2500 and 132 + 0.2372 * room.FEEDBACK_BOUND < 16384 - 2500
    typical = []
    while room.line_fits(scenario, typical, "d" * 54):
        typical += [("doctor", "d" * 54), ("patient", "p" * 43)]
    assert len(typical) // 2 == 129                                                    # about 130 lines of the bench's mean length


def test_15_6_typing_on_a_case_counts_as_use_and_the_page_names_its_script_and_its_own_style_sheet(tmp_path, clock, machine):
    app, client, engine = playing(tmp_path, clock, machine, [])
    raw = client.get("/teaching/cases/1").text
    assert re.search(r'<div class="teaching" id="teaching-case" data-case="1" data-use data-seconds-left="\d+" data-path="/teaching/cases/1">', raw)
    assert "http-equiv=\"refresh\"" not in raw                                         # timed by the script: no move while a box holds words
    for name in ("use.js", "teaching.js", "teaching.css"):
        assert re.search(rf'"/static/{re.escape(name)}\?v=[0-9a-f]{{12}}"', raw), name
    assert '<p class="mark" id="no-script" data-no-script>This page&#39;s script did not run. Send each line before you leave the page.</p>' in raw
    # The script holds no sentence of its own: what it says is on the form, in the app's words.
    form = text_of(client.get("/teaching/cases/1")).split('id="say"', 1)[1].split(">", 1)[0]
    for words in (t.PATIENT_ANSWERING, t.LOGIN_ENDED, t.NO_ANSWER):
        assert words in form
    script = client.get("/static/teaching.js").text
    assert not [words for words in (t.PATIENT_ANSWERING, t.LOGIN_ENDED, t.NO_ANSWER, t.YOU) if words in script]
    # Each rule of the teaching style sheet is scoped to the teaching pages (the rule of 21 Nov 2026).
    sheet = re.sub(r"/\*.*?\*/", "", client.get("/static/teaching.css").text, flags=re.S)
    selectors = [selector.strip() for rule in sheet.split("}") if "{" in rule for selector in rule.split("{")[0].split(",")]
    assert selectors and all(selector.startswith(".teaching ") for selector in selectors)
    assert "teaching.css" not in client.get("/").text and "teaching.css" not in client.get("/settings").text


def test_10_4_every_line_of_a_case_goes_by_the_model_the_case_started_with_whatever_settings_says_by_then(tmp_path, clock):
    claude = FakeEngine(script={"teaching_patient": [reply("A made-up reply from the made Claude.")]})
    app, client, claude, testers = cloud_teaching(tmp_path, clock, claude=claude)
    start(client, 1)
    p = app.state.parts
    p.stored.set_path(NO_CARD.case, ChosenPath(THIS_COMPUTER, THIS_COMPUTER))          # Settings moved after the start
    assert say(client, 1, "A made-up line.").status_code == 303
    assert len(claude.calls_for("teaching_patient")) == 1 and p.engine.name == "none"  # by Claude's door; nothing on this computer
    assert p.calls.get(p.teaching.cases.calls(1)[0])["engine"] == claude.name
    assert 'id="cloud-mark"' in client.get("/teaching/cases/1").text
