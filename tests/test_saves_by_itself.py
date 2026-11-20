"""A tick or a choice in Settings saves by itself (spec 15.13, ruling 47;
the details of run 9c; 7.3, rules 2 and 4; R15). The owner's idea, from
the room check of 17 Nov 2026: a doctor ticks, forgets Save, and wonders
in a consultation why the setting was not applied. The page's script
sends the form of the control that changed, as it stands; these tests
send what it sends. A choice that needs a cloud statement is not saved
until the statement is ticked, and that tick saves it. A field that is
typed keeps its Save. Where the script has not run, every form still
has a Save control that works."""

from __future__ import annotations

import re

from openconsult import words
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from tests.conftest import refusal_on, text_of
from tests.made_up_store import MadeStore
from tests.test_connect_screens import GOOD, NO_CARD, SUITABLE, made_app

BOTH_KEYS = {"ANTHROPIC_API_KEY": GOOD, "SPEECHMATICS_API_KEY": GOOD}
NOT_SAVED = "This choice is not saved yet. Read the statement below and tick it. The tick saves the choice."
NO_SCRIPT = "This page's script did not run. Press Save after you change a choice or a tick."
LOCAL = ChosenPath(THIS_COMPUTER, THIS_COMPUTER)


def changes(p) -> list[str]:
    return [l.detail for l in reversed(p.audit.lines()) if l.event == "setting.changed"]


def forms_that_save(page: str) -> list[str]:
    return re.findall(r'<form method="post" action="([^"]+)"[^>]* data-saves', page)


def test_15_13_ruling_47_each_control_saves_on_its_own_change_with_no_save_press_and_is_audited_from_what_to_what(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    for_claude, for_speech = ChosenPath(CLAUDE, THIS_COMPUTER), ChosenPath(THIS_COMPUTER, SPEECHMATICS)
    # What the script sends when a choice changes: the form as it stands, and that it keeps the page's place. The
    # statement of each path stands ticked here, so nothing waits.
    p.stored.tick_statement(statement_for(for_claude).sha256, for_claude)
    saved = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "place": "keep"})
    assert saved.status_code == 303 and saved.headers["location"] == "/settings?done=path&at=language-model"   # no anchor: the page stays where it was
    assert p.stored.path("suitable") == for_claude
    saved = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER})
    assert saved.headers["location"] == "/settings?done=path&at=language-model#language-model"                 # with no script: back at the section
    p.stored.tick_statement(statement_for(for_speech).sha256, for_speech)
    saved = client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "place": "keep"})
    assert saved.headers["location"] == "/settings?done=path&at=transcription" and p.stored.path("suitable") == for_speech
    client.post("/settings/path/transcription", data={"transcription": THIS_COMPUTER, "place": "keep"})
    assert p.stored.path("suitable") == LOCAL
    # The tick for better accuracy, taken off: saved at once, and said beside the tick and nowhere else.
    p.stored.set_path("suitable", ChosenPath(THIS_COMPUTER, THIS_COMPUTER, True))
    off = client.post("/settings/better-accuracy", data={"place": "keep"})
    assert off.headers["location"] == "/settings?done=path&at=better-accuracy" and p.stored.path("suitable") == LOCAL
    page = client.get(off.headers["location"]).text
    assert f'id="saved-better-accuracy" role="status">{words.PATH_SAVED}</p>' in page and page.count(words.PATH_SAVED) == 1
    assert changes(p) == ["language_model from this_computer to claude", "language_model from claude to this_computer",
                          "transcription from this_computer to speechmatics", "transcription from speechmatics to this_computer",
                          "better_accuracy from off to on", "better_accuracy from on to off"]                  # 7.3 rule 4


def test_15_13_ruling_47_nothing_is_saved_while_a_statement_waits_and_the_page_loaded_again_shows_the_choice_that_is_saved(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    made = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    shown = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "place": "keep"})
    assert shown.status_code == 200 and NOT_SAVED == words.PATH_NOT_SAVED_YET
    assert f'<p class="waiting" id="not-saved-language-model" role="status">{NOT_SAVED}</p>' in shown.text
    # The statement stands under the control, inside the control's own form, with its tick; the choice asked for is shown picked.
    form = shown.text.split('id="form-language-model"', 1)[1].split("</form>", 1)[0]
    assert form.index("not-saved-language-model") < form.index('id="statement-language-model" data-statement')
    assert f'name="sha256" value="{made.sha256}"' in form and f'name="understand" value="yes"> {made.tick}' in form
    assert '<input type="radio" name="language_model" value="claude" checked>' in form
    assert p.stored.path("suitable") == LOCAL and changes(p) == [] and p.stored.ticked_sha256 is None       # nothing saved, nothing ticked
    assert not any(l.event == "statement.ticked" for l in p.audit.lines())
    # Nothing of the waiting choice is kept: the page loaded again shows the choice that is saved, and no statement.
    again = client.get("/settings").text
    assert '<input type="radio" name="language_model" value="this_computer" checked>' in again and "not-saved-" not in again
    assert 'data-statement' not in again and NOT_SAVED not in again
    # The tick, as the script sends it: the choice, the tick and the checksum of the text shown. It saves both together.
    saved = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": made.sha256, "place": "keep"})
    assert saved.status_code == 303 and p.stored.path("suitable") == ChosenPath(CLAUDE, THIS_COMPUTER) and p.stored.ticked(made)
    assert [l.event for l in p.audit.lines()][:2] == ["statement.ticked", "setting.changed"]


def test_15_13_ruling_47_mail_6_after_the_tick_of_a_long_statement_the_line_saved_is_one_the_places_script_moves_into_the_window(tmp_path, clock):
    # Seen in the browser at mail 5 of run 9c and mended at mail 6 (Cowork's detail, in the sense of ruling 47): after
    # the tick of a long statement the form is short again and its line Saved. stood above the window. The suite has no
    # browser: this pins what the script rests on; the window itself is measured in the look of mail 6.
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    made = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    shown = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "place": "keep"}).text
    long_form = shown.split('id="form-language-model"', 1)[1].split("</form>", 1)[0]
    assert long_form.count("<li>") >= 8                                                 # a long statement: the tick stands far under the control
    saved = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": made.sha256, "place": "keep"})
    after = client.get(saved.headers["location"]).text
    form = after.split('id="form-language-model"', 1)[1].split("</form>", 1)[0]
    # The line is in the form that was used, which is short again, a status line of the class the script looks for.
    assert f'<p class="notice" id="saved-language-model" role="status">{words.PATH_SAVED}</p>' in form and "<li>" not in form
    assert after.count('class="notice"') == 1 and '<div id="settings" data-keeps-place data-path="/settings">' in after
    script = client.get("/static/place.js").text
    assert "page.querySelector('.notice[role=status], .where-lines[role=status]')" in script     # the line of a save, and his line of a path that sends less
    assert script.count("scrollIntoView({block: 'nearest'})") == 2                               # the form that was used, then the line: the least move
    assert "function inWindow(box, under, height) { return box.top >= under && box.bottom <= height; }" in script   # only when the line is not whole in the window
    style = client.get("/static/theme.css").text
    assert ".notice[role=status], .where-lines[role=status], #settings form[data-stay] { scroll-margin: 4.2rem 0 1rem; }" in style   # clear of the app's bar
    # The line of a path that sends less is of the second class, when it says a save.
    wide = statement_for(ChosenPath(CLAUDE, SPEECHMATICS))
    client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "understand": "yes", "sha256": wide.sha256})
    less = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER, "place": "keep"})
    assert less.headers["location"] == "/settings?done=less&at=language-model"
    assert '<div class="waiting where-lines" role="status">' in client.get(less.headers["location"]).text


def test_15_13_ruling_47_a_changed_choice_is_never_saved_by_the_tick_of_another_choices_statement(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    for_claude = statement_for(ChosenPath(CLAUDE, THIS_COMPUTER))
    # The statement for Claude stands on the page; the transcription is sent with that statement's tick and checksum.
    wrong = client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "understand": "yes", "sha256": for_claude.sha256})
    assert wrong.status_code == 400 and refusal_on(wrong.text, "save-transcription") == words.STATEMENT_CHANGED
    assert p.stored.path("suitable") == LOCAL and p.stored.ticked_sha256 is None


def test_15_13_ruling_47_the_statement_that_stands_apart_is_saved_by_its_own_tick(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=NO_CARD, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    made = statement_for(ChosenPath(CLAUDE, SPEECHMATICS))
    page = client.get("/settings").text
    apart = page.split('id="cloud-statement"', 1)[1].split("</section>", 1)[0]
    assert '<form method="post" action="/statement/tick" id="form-statement" data-saves data-stay>' in apart
    assert 'id="tick-statement" aria-describedby="tick-statement-refusal" data-save>' in apart          # its Save, for a page with no script
    ticked = client.post("/statement/tick", data={"sha256": made.sha256, "understand": "yes", "back": "/settings", "place": "keep"})
    assert ticked.status_code == 303 and p.stored.ticked(made)
    after = client.get(ticked.headers["location"]).text
    assert f'id="statement-saved" role="status">{words.SAVED}</p>' in after and 'id="cloud-statement"' not in after
    # On a connect screen the statement stands apart too, with the script and the line for a page where it did not run.
    app, client, store, testers = made_app(tmp_path / "connect", clock, machine=NO_CARD, store=MadeStore(BOTH_KEYS))
    screen = client.get("/connect/claude").text
    assert "/static/settings.js?v=" in screen and NO_SCRIPT in text_of(client.get("/connect/claude")) and "data-saves" in screen


def test_15_13_ruling_47_a_typed_field_keeps_its_save_and_is_not_saved_by_the_change_of_another_control(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    p = app.state.parts
    page = client.get("/settings").text
    # The forms that save by themselves, and no other: the two choices, the speech model of this computer and the
    # tick for better accuracy.
    assert forms_that_save(page) == ["/settings/path/language-model", "/settings/path/transcription", "/settings/speech-model",
                                     "/settings/better-accuracy"]
    for action, save in (("/settings/retention", "save-retention"), ("/settings/you", "save-you"), ("/settings/password", "change-password"),
                         ("/settings/guidelines/add", "add-guideline")):
        form = page.split(f'action="{action}"', 1)[1].split("</form>", 1)[0]
        assert "data-saves" not in page.split(f'action="{action}"', 1)[0].rsplit("<form", 1)[1] and "data-saves" not in form.split(">", 1)[0]
        assert f'id="{save}"' in form and "data-save" not in form                              # its own control, never taken away
    # A half-typed value that travels with another control's change is not saved by it.
    client.post("/settings/path/transcription", data={"transcription": THIS_COMPUTER, "days": "7", "name": "Half typed", "new_password": "half-typed"})
    assert p.stored.audio_retention_days == 90 and p.users.get().name != "Half typed" and changes(p) == []
    assert client.post("/settings/retention", data={"days": "30"}).status_code == 303 and p.stored.audio_retention_days == 30


def test_15_13_ruling_47_the_page_as_served_works_with_no_script_a_save_control_for_each_form_and_one_line_that_says_so(tmp_path, clock):
    app, client, store, testers = made_app(tmp_path, clock, machine=SUITABLE, store=MadeStore(BOTH_KEYS))
    page = client.get("/settings")
    assert f'<p class="mark" id="no-script" data-no-script>{NO_SCRIPT}</p>' in text_of(page) and NO_SCRIPT == words.SETTINGS_NO_SCRIPT
    for save in ("save-language-model", "save-transcription", "save-better-accuracy"):
        assert f'id="{save}" aria-describedby="{save}-refusal" data-save>{words.SAVE}</button>' in page.text   # served, and taken away by the script alone
    # The refusal's slot is named by the control that is used, too (R15): the group of choices, and the tick.
    assert '<div role="radiogroup" aria-label="Language model" aria-describedby="save-language-model-refusal">' in page.text
    assert '<div role="group" aria-describedby="save-better-accuracy-refusal"><label class="tick"><input type="checkbox" name="better_accuracy"' in page.text
    # The page names its two scripts, marked; the review page's script for the place is the same file.
    assert re.search(r'<script src="/static/settings\.js\?v=[0-9a-f]{12}"></script>\s*<script src="/static/place\.js\?v=[0-9a-f]{12}"></script>', page.text)
    assert '<div id="settings" data-keeps-place data-path="/settings">' in page.text
    assert all(f'id="{form}" data-saves data-stay' in page.text or f'id="{form}" data-saves data-stay>' in page.text
               for form in ("form-language-model", "form-transcription", "better-accuracy"))
    # A choice refused on the control, with no script and with it: a cloud choice with no connection.
    app, client, store, testers = made_app(tmp_path / "bare", clock, machine=SUITABLE)
    refused = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "place": "keep"})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-language-model") == "Connect Claude first."
