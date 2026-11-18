"""The sections Language model and Transcription (spec 7.3, rules 1, 2
and 4; 10.3; 15.13, ruling 5 and the details of run 9b): two choices
each, a cloud choice saved only when its service is connected and the
statement of the path as it would then stand is ticked."""

from __future__ import annotations

from openconsult import words
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from tests.conftest import refusal_on, text_of
from tests.made_up_store import MadeStore
from tests.test_connect_screens import GOOD, NO_CARD, SUITABLE, made_app

BOTH_KEYS = {"ANTHROPIC_API_KEY": GOOD, "SPEECHMATICS_API_KEY": GOOD}


def setting_lines(p) -> list[str]:
    return [l.detail for l in reversed(p.audit.lines()) if l.event == "setting.changed"]


def test_7_3_rule_1_a_choice_this_machine_cannot_run_is_shown_disabled_with_the_reason_on_the_control(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=NO_CARD)
    p = app.state.parts
    page = client.get("/settings").text
    assert f"<h2>{words.SECTION_LANGUAGE_MODEL}</h2>" in page and f"<h2>{words.SECTION_TRANSCRIPTION}</h2>" in page
    for which, field in (("language-model", "language_model"), ("transcription", "transcription")):
        assert (f'<input type="radio" name="{field}" value="this_computer" disabled aria-describedby="{which}-this_computer-reason">'
                in page)
        assert f'id="{which}-this_computer-reason">{NO_CARD.sentence}</p>' in page
    assert '<input type="radio" name="language_model" value="claude" checked>' in page          # 10.3: no card, the cloud for both
    assert '<input type="radio" name="transcription" value="speechmatics" checked>' in page
    refused = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})   # a post made anyway
    assert refused.status_code == 400 and refusal_on(refused.text, "save-language-model") == NO_CARD.sentence
    assert setting_lines(p) == [] and p.stored.path("none") == ChosenPath(CLAUDE, SPEECHMATICS)
    assert refusal_on(client.post("/settings/path/transcription", data={"transcription": "made-up"}).text, "save-transcription") == words.PICK_ONE
    # With a suitable card both begin on this computer, and both choices of each section can be taken.
    app, client, store, testers = made_app(tmp_path / "card", clock, machine=SUITABLE)
    page = client.get("/settings").text
    assert '<input type="radio" name="language_model" value="this_computer" checked>' in page and " disabled aria-describedby=" not in page
    assert words.PATH_NEXT_CONSULTATION in text_of(client.get("/settings"))


def test_details_of_9b_a_cloud_choice_is_refused_without_the_connection_and_without_the_tick_and_saved_with_both(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE)
    p = app.state.parts
    refused = client.post("/settings/path/language-model", data={"language_model": CLAUDE})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-language-model") == "Connect Claude first."
    assert p.stored.path("suitable") == ChosenPath(THIS_COMPUTER, THIS_COMPUTER) and setting_lines(p) == []
    client.post("/connect/claude", data={"key": GOOD})
    # Connected, not ticked: the page shows the statement of the path as it would then stand, in that section, and saves nothing.
    # Since run 9c a choice saves by itself (15.13, ruling 47), so the choice sent alone is no press that is refused: the
    # page comes back with the statement and the line that the choice is not saved yet.
    shown = client.post("/settings/path/language-model", data={"language_model": CLAUDE})
    made = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    assert shown.status_code == 200 and refusal_on(shown.text, "save-language-model") == ""
    assert "This choice is not saved yet. Read the statement below and tick it. The tick saves the choice." in text_of(shown)
    # A Save pressed with the statement shown and no tick, on a page whose script has not run, is refused on the control.
    no_tick = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "sha256": made.sha256})
    assert no_tick.status_code == 400 and refusal_on(no_tick.text, "save-language-model") == words.STATEMENT_TICK_FIRST
    page = text_of(shown)
    assert 'id="statement-language-model"' in shown.text and made.heading == words.CLOUD_HEADING_MODEL and made.heading in page
    assert all(line in page for line in (*made.sent, *made.stays, made.tick)) and f'name="sha256" value="{made.sha256}"' in shown.text
    assert '<input type="radio" name="language_model" value="claude" checked>' in shown.text   # the choice asked for stays picked
    assert shown.text.count('name="sha256"') == 1 and p.stored.path("suitable").language_model == THIS_COMPUTER
    # A tick sent for another text is refused; the tick for the text shown saves the choice and the tick together.
    stale = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": "0" * 64})
    assert refusal_on(stale.text, "save-language-model") == words.STATEMENT_CHANGED and setting_lines(p) == []
    saved = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": made.sha256})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=path&at=language-model#language-model"
    assert p.stored.path("suitable") == ChosenPath(CLAUDE, THIS_COMPUTER) and p.stored.ticked(made)
    assert setting_lines(p) == ["language_model from this_computer to claude"]                 # 7.3 rule 4: from what to what
    assert (p.audit.lines()[0].event, p.audit.lines()[0].detail) == (
        "statement.ticked", f"language model claude, transcription this_computer, recording after Stop no; sha256 {made.sha256}")
    after = client.get("/settings?done=path&at=language-model").text                          # said beside the control changed, and only there
    assert f'id="saved-language-model" role="status">{words.PATH_SAVED}</p>' in after and after.count(words.PATH_SAVED) == 1
    assert 'id="cloud-statement"' not in client.get("/settings").text


def test_15_13_rulings_5_and_48_a_wider_path_asks_for_its_tick_one_that_sends_less_does_not_and_one_with_no_cloud_is_saved_at_once(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    first = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": first.sha256})
    # The second cloud choice: the statement is another text now, the one for both, and the earlier tick does not stand for it.
    both = statement_for(ChosenPath(CLAUDE, SPEECHMATICS))
    shown = client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS})
    assert words.PATH_NOT_SAVED_YET in text_of(shown) and words.CLOUD_HEADING_BOTH in text_of(shown)      # it waits for its tick (ruling 47)
    client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "understand": "yes", "sha256": both.sha256})
    assert p.stored.path("suitable") == ChosenPath(CLAUDE, SPEECHMATICS) and p.stored.ticked(both) and not p.stored.ticked(first)
    # Back to this computer for the language model, with the transcription still in the cloud. Until run 9c this path
    # asked for a tick of its own, and at the room check of 17 Nov 2026 the owner took that for a bug: less was leaving
    # than he had agreed to. Now it is saved with no tick (15.13, ruling 48), the tick that stands stays the wider
    # one, and the page shows that path's statement, with the owner's heading and no tick, under the line that says so.
    alone = statement_for(ChosenPath(THIS_COMPUTER, SPEECHMATICS))
    saved = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=less&at=language-model#language-model"
    assert p.stored.path("suitable") == ChosenPath(THIS_COMPUTER, SPEECHMATICS) and p.stored.ticked(both) and not p.stored.ticked(alone)
    shown = text_of(client.get(saved.headers["location"]))
    assert "Less leaves this computer than you agreed to, so no new tick is asked. This is what leaves now." in shown
    assert "Using a cloud transcription service" in shown and "I understand that this sound leaves this computer." not in shown
    # The last cloud choice given up: nothing leaves this computer, so nothing is asked.
    saved = client.post("/settings/path/transcription", data={"transcription": THIS_COMPUTER})
    assert saved.status_code == 303 and p.stored.path("suitable") == ChosenPath(THIS_COMPUTER, THIS_COMPUTER)
    assert setting_lines(p) == ["language_model from this_computer to claude", "transcription from this_computer to speechmatics",
                                "language_model from claude to this_computer", "transcription from speechmatics to this_computer"]
    assert len([l for l in p.audit.lines() if l.event == "statement.ticked"]) == 2             # three before ruling 48


def test_15_13_ruling_5_a_path_that_begins_in_the_cloud_shows_its_statement_on_the_settings_page_until_it_is_ticked(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=NO_CARD, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    made = statement_for(ChosenPath(CLAUDE, SPEECHMATICS))
    page = client.get("/settings")
    assert 'id="cloud-statement"' in page.text and f'name="sha256" value="{made.sha256}"' in page.text
    client.post("/statement/tick", data={"sha256": made.sha256, "understand": "yes", "back": "/settings"})
    assert p.stored.ticked(made) and 'id="cloud-statement"' not in client.get("/settings").text
