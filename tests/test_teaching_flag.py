"""The flag on a case, and the section Teaching of Settings (spec 12.3,
rule 7; 7.3; 15.13, rulings 47 and 55; 15.14, rulings 5, 6 and 8, and
the details of run 10b: After the feedback, Kept cases, Settings,
Teaching; the owner's okay of 25 Nov 2026). A made bank and a made
engine: no model is asked for real."""

from openconsult.settings import stored as stored_levels
from openconsult.teaching import cases as cases_module, words as t
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


# ------------------------------------------- the section Teaching of Settings

def section(raw: str) -> str:
    return raw.split('<section class="pane" id="teaching">', 1)[1].split("</section>", 1)[0]


def test_15_13_ruling_55_the_section_teaching_stands_between_guidelines_and_thresholds_with_the_default_level_and_no_timer(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine)
    raw = client.get("/settings").text
    found = [raw.find(f'<section class="pane" id="{name}">') for name in ("guidelines", "teaching", "thresholds")]
    assert all(f >= 0 for f in found) and found == sorted(found)                       # the order of 7.3
    part = section(raw)
    assert "<h2>Teaching</h2>" in part and '<p class="mark" id="teaching-level-legend">Default level</p>' in part
    # The three levels with their lines; straightforward until it is changed (ruling 5).
    assert stored_levels.TEACHING_LEVELS == cases_module.LEVELS and app.state.parts.stored.teaching_level == "straightforward"
    assert '<input type="radio" name="level" value="straightforward" checked> Straightforward: the story points to the diagnosis.</label>' in part
    assert part.count(" checked>") == 1 and 'value="hidden">' in part and 'value="noisy">' in part
    assert '<p class="mark" id="no-flags">No case is flagged.</p>' in part and "<h3>Flagged cases</h3>" in part
    assert "timer" not in part.lower() and "minutes" not in part.lower()               # ruling 6: the timer arrives with spoken teaching


def test_15_13_ruling_47_the_default_level_saves_by_itself_is_audited_from_what_to_what_and_a_new_case_begins_at_it(tmp_path, clock, machine):
    app, client = teaching_app(tmp_path, clock, machine)
    p = app.state.parts
    part = section(client.get("/settings").text)
    # A form that the page's script sends when the choice changes; its Save is served for a page whose script has not run.
    assert '<form method="post" action="/settings/teaching-level" id="teaching-level" data-saves data-stay>' in part
    assert '<button class="primary" id="save-teaching-level" aria-describedby="save-teaching-level-refusal" data-save>' in part
    saved = client.post("/settings/teaching-level", data={"level": "hidden"})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=teaching-level#teaching"
    assert client.post("/settings/teaching-level", data={"level": "hidden", "place": "keep"}).headers["location"] == "/settings?done=teaching-level"
    assert p.stored.teaching_level == "hidden"
    lines = [(line.event, line.detail) for line in p.audit.lines() if line.event == "setting.changed"]
    assert lines == [("setting.changed", "teaching_level from straightforward to hidden")]      # once: the same level again writes nothing
    raw = client.get("/settings?done=teaching-level").text
    assert '<p class="notice" id="saved-teaching-level" role="status">Saved.</p>' in raw
    assert '<input type="radio" name="level" value="hidden" checked>' in section(raw)
    # The level of a new case on the teaching page is the default; a case of the bank keeps its own.
    form = client.get("/teaching").text.split('id="start-fresh-form"', 1)[1].split("</form>", 1)[0]
    assert '<input type="radio" name="level" value="hidden" checked>' in form and form.count(" checked>") == 1
    refused = client.post("/settings/teaching-level", data={"level": "easy"})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-teaching-level") == "Pick a level."
    assert p.stored.teaching_level == "hidden"


def test_12_3_rule_7_settings_lists_each_flagged_case_shows_its_scenario_and_removes_the_flag(tmp_path, clock, machine):
    app, client = finished(tmp_path, clock, machine)
    p = app.state.parts
    client.post("/teaching/cases/1/flag", data={"note": NOTE})
    client.post("/teaching/cases/1/delete", data={"confirm": "yes"})                   # the flag outlives its case
    raw = client.get("/settings").text
    row = section(raw).split('<tr data-flag="1">', 1)[1].split("</tr>", 1)[0]
    assert [cell for cell in ("<td>4 Oct 2026</td>", "<td>A made-up topic</td>", "<td>Straightforward</td>", f"<td>{NOTE}</td>") if cell in row] == [
        "<td>4 Oct 2026</td>", "<td>A made-up topic</td>", "<td>Straightforward</td>", f"<td>{NOTE}</td>"]
    assert "Made from a clinician&#39;s script. The scenario is not yet reviewed." in row
    assert '<a class="button" id="show-flag-1" href="/teaching/flags/1">Show the scenario</a>' in row and ">Remove the flag</button>" in row
    assert "Qdiagone" not in raw and "Made Up" not in raw                               # the list holds nothing of the scenario itself
    # The press shows the scenario as it stood, whole, with the learner's note.
    page = client.get("/teaching/flags/1").text
    assert '<h1 class="page">A flagged case</h1>' in page and f'<td id="flag-note">{NOTE}</td>' in page
    assert 'id="whole-scenario"' in page and "zzreasoning zzmade zzup" in page and "Qdiagone" in page and "Made Up, 40, female" in page
    assert '<a class="button" id="back-to-settings" href="/settings#teaching">Back to Settings</a>' in page
    assert client.get("/teaching/flags/9").headers["location"] == "/settings#teaching"
    # Remove the flag: it goes with its copy of the scenario, the page says so, and the audit log names its number.
    removed = client.post("/teaching/flags/1/remove")
    assert removed.status_code == 303 and removed.headers["location"] == "/settings?done=flag-removed#teaching"
    assert p.teaching.cases.flags() == [] and events(app)[0] == ("teaching.flag_removed", "flag 1")
    raw = client.get("/settings?done=flag-removed").text
    assert '<p class="notice" id="flag-removed" role="status">The flag was removed.</p>' in raw and 'id="no-flags"' in raw
    assert client.post("/teaching/flags/1/remove").headers["location"] == "/settings#teaching"       # a second press removes nothing
    assert len([1 for event, _ in events(app) if event == "teaching.flag_removed"]) == 1
    # A flag with no note says so in the list.
    app2, client2 = finished(tmp_path / "second", clock, machine)
    client2.post("/teaching/cases/1/flag", data={"note": ""})
    assert "<td>No note was typed.</td>" in section(client2.get("/settings").text)
