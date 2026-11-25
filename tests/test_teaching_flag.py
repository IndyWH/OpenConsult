"""The flag on a case, and the section Teaching of Settings (spec 12.3,
rule 7; 7.3; 15.13, rulings 47 and 55; 15.14, rulings 5, 6 and 8, and
the details of run 10b: After the feedback, Kept cases, Settings,
Teaching; the owner's okay of 25 Nov 2026). A made bank and a made
engine: no model is asked for real."""

from openconsult.teaching import words as t
from tests import made_teaching
from tests.conftest import refusal_on, text_of
from tests.test_teaching_kept import finish, scripted
from tests.test_teaching_page import teaching_app
from tests.test_teaching_start import events, start

NOTE = "The made-up finding contradicts the made-up history."


def finished(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine, scripted())
    app.state.parts.teaching.run = lambda work: work()
    start(client, 1)
    finish(client, 1)
    return app, client


def test_12_3_rule_7_after_the_feedback_a_case_is_flagged_as_wrong_once_with_a_note_that_may_be_empty(tmp_path, clock, machine):
    app, client = finished(tmp_path, clock, machine)
    cases = app.state.parts.teaching.cases
    raw = client.get("/teaching/cases/1").text
    row = raw.split('id="after-presses"', 1)[1].split("</section>", 1)[0]
    # Two presses side by side: the whole scenario, and the flag with its box.
    assert 0 < row.find('id="show-scenario"') < row.find('id="flag-form"') and ">Flag this case as wrong</button>" in row
    assert '<label for="flag-note">What is wrong? You may leave this empty.</label>' in row
    assert '<p class="mark" id="flag-note-stays">This note stays on this computer.</p>' in row
    too_long = client.post("/teaching/cases/1/flag", data={"note": "x" * 1001})
    assert too_long.status_code == 400 and refusal_on(too_long.text, "flag") == "This note is too long. Shorten it to 1,000 characters or fewer."
    assert cases.flags() == []
    sent = client.post("/teaching/cases/1/flag", data={"note": f"  {NOTE}  "})
    assert sent.status_code == 303 and sent.headers["location"] == "/teaching/cases/1#after-feedback"
    # Kept with the scenario as it stood, the topic, the level and the label, and the learner's note.
    flag, = cases.flags()
    held = cases.flag_row(flag["id"])
    assert (held["case_id"], held["note"], held["topic"], held["level"], held["label"], held["source"], held["bank_number"]) == (
        1, NOTE, "A made-up topic", "straightforward", "script", "bank", 1)
    assert held["scenario"] == made_teaching.SCENARIO
    # The audit line holds the note's length and never its words.
    assert events(app)[0] == ("teaching.flagged", f"case 1: a note of {len(NOTE)} characters")
    assert NOTE not in client.get("/log").text and "Teaching case flagged as wrong" in client.get("/log").text
    # The page says so, and the press is gone: a case is flagged once.
    raw = client.get("/teaching/cases/1").text
    assert '<p class="sentence" id="flagged">This case is flagged as wrong. The flag is listed in Settings.</p>' in raw
    assert 'id="flag-form"' not in raw and 'id="show-scenario"' in raw
    again = client.post("/teaching/cases/1/flag", data={"note": "A second flag."})
    assert again.status_code == 200 and t.STALE in text_of(again) and len(cases.flags()) == 1 and cases.flag_row(flag["id"])["note"] == NOTE


def test_12_3_rule_7_a_flag_with_no_note_and_no_flag_before_the_feedback(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine, scripted())
    app.state.parts.teaching.run = lambda work: work()
    cases = app.state.parts.teaching.cases
    start(client, 1)
    # A case can be judged only once it has been seen: before the feedback there is no press, and a press changes nothing.
    assert 'id="flag-form"' not in client.get("/teaching/cases/1").text
    early = client.post("/teaching/cases/1/flag", data={"note": "too early"})
    assert early.status_code == 200 and t.STALE in text_of(early) and cases.flags() == []
    finish(client, 1)
    assert client.post("/teaching/cases/1/flag", data={"note": "   "}).status_code == 303
    assert cases.flags()[0]["note"] == "" and events(app)[0] == ("teaching.flagged", "case 1: no note")


def test_15_14_ruling_22_a_flag_stays_with_its_scenario_and_its_note_when_its_case_is_deleted(tmp_path, clock, machine):
    app, client = finished(tmp_path, clock, machine)
    cases = app.state.parts.teaching.cases
    client.post("/teaching/cases/1/flag", data={"note": NOTE})
    assert client.post("/teaching/cases/1/delete", data={"confirm": "yes"}).status_code == 303
    assert cases.get(1) is None
    flag, = cases.flags()
    held = cases.flag_row(flag["id"])
    assert (held["case_id"], held["note"], held["scenario"]) == (None, NOTE, made_teaching.SCENARIO)
    assert events(app)[0] == ("teaching.deleted", "case 1 of 2026-10-04: 2 turns, 1 examination requests, 3 answers, 1 feedback, 3 model calls, 1 flag kept")
