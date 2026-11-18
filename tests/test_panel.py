"""The control panel of This machine (spec 15.13, rulings 5, 6 and 56 and
the details of run 9c; 15.8, ruling 38; 7.1; 7.3; R15; R31; Cowork's
review of the plan, points 1 and 2). One picture, made by one piece of
code from what the app holds, shown at step 2 of the first run and at
the top of Settings. Made engines, made speech doors, a made store and
made tests of each connection: nothing is asked of a real one."""

from __future__ import annotations

import re

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store as settings_store
from openconsult.settings.machine import Card, describe
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import statement_for
from openconsult.speech.choices import NEMOTRON, SPEECHMATICS as SPEECHMATICS_CHOICE, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor
from openconsult.speech.selftest import Outcome
from openconsult.web import panel
from openconsult.web.consult import start_state
from tests.conftest import PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.made_up_store import MadeStore
from tests.test_connect_screens import GOOD, NO_CARD, SUITABLE, MadeTesters
from tests.test_machine_status import box_of

SMALLER = describe("Windows", "AMD64", [Card("Made-up card", 8188)])
ROOMY = describe("Linux", "x86_64", [Card("Made-up roomy card", 49140)])
BOTH_KEYS = {"ANTHROPIC_API_KEY": GOOD, "SPEECHMATICS_API_KEY": GOOD}
PATHS = {"L": ChosenPath(THIS_COMPUTER, THIS_COMPUTER), "R": ChosenPath(THIS_COMPUTER, THIS_COMPUTER, True),
         "S": ChosenPath(THIS_COMPUTER, SPEECHMATICS), "C": ChosenPath(CLAUDE, THIS_COMPUTER),
         "CR": ChosenPath(CLAUDE, THIS_COMPUTER, True), "CS": ChosenPath(CLAUDE, SPEECHMATICS)}


def made(tmp_path, clock, machine=SUITABLE, held=None, nemotron=True, whisperx=False, ollama=None, environ=None, path=None, tick=True,
         user=True):
    """An app with made everything: which keys the made store holds, which speech models are installed, whether the
    local engine holds the model; the path as chosen, its statement ticked."""
    store, testers = MadeStore(held or {}), MadeTesters()
    installed = {NEMOTRON.name: nemotron, WHISPERX_PYANNOTE.name: whisperx}
    workers = {name: MadeUpWorker() for name in (NEMOTRON.name, WHISPERX_PYANNOTE.name, SPEECHMATICS_CHOICE.name)}
    doors = {choice.name: SpeechDoor(choice, make_worker=lambda name=choice.name: workers[name], installed=lambda name=choice.name: installed[name])
             for choice in (NEMOTRON, WHISPERX_PYANNOTE)}
    doors[SPEECHMATICS_CHOICE.name] = SpeechDoor(SPEECHMATICS_CHOICE, make_worker=lambda: workers[SPEECHMATICS_CHOICE.name], installed=lambda: True,
                                                 key_present=lambda: store.held.get("SPEECHMATICS_API_KEY") is not None)
    engines = {"vllm": FakeEngine(version=None), "ollama": ollama or FakeEngine()}
    app = build_app(settings_store.build(tmp_path, PORT), machine=machine, clock=clock, engines=engines, doors=doors, secure_store=store,
                    testers=testers.both())
    p = app.state.parts
    if path is not None:
        p.stored.set_path(machine.case, path)
        if tick and statement_for(path) is not None:
            p.stored.tick_statement(statement_for(path).sha256, path, statement_for(path))
    client = browser(app)
    if user:
        set_up(client)
        log_in(client)
    return app, client, testers, engines, workers


def state_of(box) -> tuple:
    return box.state, box.sentence


# --------------------------------------------------- each state of each box

def test_15_13_ruling_56_the_microphone_box_is_ready_when_the_test_has_seen_the_level_move_and_says_when(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, user=False)
    p = app.state.parts
    box = panel.build(p).box("microphone")
    assert state_of(box) == ("not_set_up", "The microphone has not been tested on this computer yet.") and box.when == ()
    assert (box.action.kind, box.action.address) == ("test", "/first-run/microphone")
    p.first_run.mark_done("microphone")
    box = panel.build(p).box("microphone")
    assert state_of(box) == ("ready", "The microphone was tested on 4 Oct 2026 at 09:00: the level moved.")
    assert box.when == ("tested on 4 Oct 2026 at 09:00",) and box.on_path and not box.chosen and box.action.kind == "test"


@pytest.mark.parametrize("case, kwargs, state, sentence, action", [
    ("installed, self-test passed", dict(), "ready", "Nemotron is installed and its self-test passed on 4 Oct 2026 at 09:00.", "test"),
    ("installed, self-test never run", dict(), "not_set_up", "Nemotron is installed. Its self-test has not been run yet.", "test"),
    ("installed, self-test failed", dict(), "not_set_up", "Nemotron is installed. Its self-test failed on 4 Oct 2026 at 09:00: made-up reason", "test"),
    ("not installed", dict(nemotron=False), "not_set_up",
     "Nemotron is not installed. Install it with: uv run openconsult install-speech --choice nemotron", None),
    ("no suitable card", dict(machine=SMALLER), "cannot_run", SMALLER.sentence, None),
])
def test_15_13_ruling_56_the_box_transcription_this_computer_for_each_state(tmp_path, clock, case, kwargs, state, sentence, action):
    app, client, *_ = made(tmp_path, clock, **kwargs)
    p = app.state.parts
    if "passed" in case or "failed" in case:
        p.self_tests.add("nemotron", Outcome("passed" in case, None if "passed" in case else "made-up reason", [], [], {}))
    box = panel.build(p).box("speech_local")
    assert state_of(box) == (state, sentence) and box.model == "Nemotron" and not box.cloud
    assert (box.action.kind if box.action else None) == action
    assert box.action is None or box.action.address == "/first-run/self-test"
    assert box.when == (("tested on 4 Oct 2026 at 09:00",) if state == "ready" else ())      # a time only where the app has one


def test_15_13_ruling_56_the_whisperx_choice_as_the_model_of_the_box_and_the_room_checks_own_sentence(tmp_path, clock):
    app, client, *_ = made(tmp_path / "roomy", clock, machine=ROOMY, whisperx=True)
    p = app.state.parts
    p.stored.set_speech_model("whisperx_pyannote", was="nemotron")
    assert panel.build(p).box("speech_local").model == "WhisperX with pyannote"
    # Chosen, on a card with no room for its pass at Stop: cannot run here, in the room check's own sentence.
    app, client, *_ = made(tmp_path / "small", clock, whisperx=True)
    p = app.state.parts
    p.stored.set_speech_model("whisperx_pyannote", was="nemotron")
    assert state_of(panel.build(p).box("speech_local")) == ("cannot_run", words.REASONS["whisperx_no_room"])


def test_15_13_ruling_56_the_box_language_model_this_computer_for_each_state(tmp_path, clock):
    app, client, *_ = made(tmp_path / "held", clock)
    p = app.state.parts
    box = panel.build(p).box("model_local")
    assert state_of(box) == ("ready", p.decisions.language_model.sentence) and box.model == "Gemma 4 QAT" and box.chosen
    assert box.when == ("The engine was asked when OpenConsult started.",) and box.action is None       # chosen already: nothing to choose
    app, client, *_ = made(tmp_path / "none", clock, ollama=FakeEngine(version=None))
    p = app.state.parts
    box = panel.build(p).box("model_local")
    assert box.state == "not_set_up" and box.sentence == (
        p.decisions.language_model.sentence + " The engine is set up by hand until the installers arrive. The README says how.")
    assert box.action is None and box.when == ()
    app, client, *_ = made(tmp_path / "smaller", clock, machine=SMALLER)
    assert state_of(panel.build(app.state.parts).box("model_local")) == ("cannot_run", SMALLER.sentence)


def test_15_13_ruling_56_a_cloud_box_for_each_state_and_a_key_not_tested_since_the_start_says_so_on_its_face(tmp_path, clock, monkeypatch):
    # No key: not set up, the sketch's sentence, and Connect.
    app, client, testers, *_ = made(tmp_path / "none", clock)
    p = app.state.parts
    box = panel.build(p).box("claude")
    assert state_of(box) == ("not_set_up", "Claude is not connected. It is the cloud language model, for a computer that cannot run its own.")
    assert (box.action.kind, box.action.address, box.when, box.cloud, box.model) == ("connect", "/connect/claude", ("Not connected.",), True, "Claude Haiku 5.5")
    box = panel.build(p).box("speechmatics")
    assert box.sentence == "Speechmatics is not connected. It is the cloud transcription service, for a computer that cannot run its own."
    # A key in the secure store, not on the path at start, so not tested in this run: ready, for it passed its test when it
    # was saved, and the face says in the app's own words that it was not tested since the start. Never a time.
    app, client, testers, *_ = made(tmp_path / "stored", clock, held=BOTH_KEYS)
    p = app.state.parts
    assert testers.asked == []
    for name, sentence in (("claude", "Claude is connected. It is the cloud language model."),
                           ("speechmatics", "Speechmatics is connected. It is the cloud transcription service.")):
        box = panel.build(p).box(name)
        assert state_of(box) == ("ready", sentence) and box.when == ("Not tested since OpenConsult started.",) and box.action.kind == "choose"
        assert not re.search(r"\d\d:\d\d", " ".join(box.when))
    # Tested, and it answered: the time of the test. Tested, and it failed: cannot run here, with the reason, and Test.
    p.connections.test(CLAUDE)
    box = panel.build(p).box("claude")
    assert box.state == "ready" and box.when == ("Connected, tested at 09:00.",)
    testers.fail[CLAUDE] = "no_credit"
    p.connections.test(CLAUDE)
    box = panel.build(p).box("claude")
    assert state_of(box) == ("cannot_run", "Claude cannot be used now. It is the cloud language model.")
    assert box.when == ("The last test failed at 09:00: Claude refused to start: the account has no credit left.",)
    assert (box.action.kind, box.action.address, box.action.fields) == ("test", "/connect/claude", (("key", ""),))
    # A key that is not from the store and never passed a test in this run: not set up, and Test.
    monkeypatch.setenv("SPEECHMATICS_API_KEY", GOOD)
    app, client, testers, *_ = made(tmp_path / "environment", clock)
    box = panel.build(app.state.parts).box("speechmatics")
    assert state_of(box) == ("not_set_up", "Speechmatics has a key that has not been tested since OpenConsult started. It is the cloud transcription service.")
    assert box.when == ("Not tested since OpenConsult started.",) and box.action.kind == "test"


# ------------------------------------------ the chosen path, and what goes

@pytest.mark.parametrize("name, speech_row, model_row, by", [
    ("L", 0, 0, "transcription on this computer, then the language model on this computer."),
    ("S", 1, 0, "transcription by Speechmatics, then the language model on this computer."),
    ("C", 0, 1, "transcription on this computer, then the language model by Claude."),
    ("CS", 1, 1, "transcription by Speechmatics, then the language model by Claude."),
])
def test_15_13_ruling_56_the_chosen_path_is_marked_for_each_path_by_the_border_the_word_and_the_arrows(tmp_path, clock, name, speech_row, model_row, by):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    made_panel = panel.build(app.state.parts)
    chosen = {box.name for box in made_panel.boxes if box.chosen}
    assert chosen == {("speechmatics" if speech_row else "speech_local"), ("claude" if model_row else "model_local")}
    assert {box.name for box in made_panel.boxes if box.on_path} == chosen | {"microphone", "consultation"}
    assert [(a.gutter, a.from_row, a.to_row) for a in made_panel.arrows] == [(1, 0, speech_row), (2, speech_row, model_row), (3, model_row, 0)]
    assert made_panel.path_line == "The path you chose: the microphone, then " + by
    # On the page: the word Chosen in the two chosen boxes and in no other, the heavier border by its class, the arrows hidden from a reader.
    page = text_of(client.get("/settings"))
    for box in made_panel.boxes:
        in_page = box_of(page, box.name)
        assert ("data-chosen" in in_page.split(">", 1)[0]) is box.chosen and (f'<b class="box-chosen">{words.PANEL_CHOSEN}</b>' in in_page) is box.chosen
        assert (" on-path" in page.split(f'id="box-{box.name}"', 1)[0].rsplit("<details", 1)[1]) is box.on_path
    assert page.count('class="panel-arrow ') == 3 and page.count('class="panel-arrow ') == page.count('aria-hidden="true"><svg viewBox="0 0 24 12"')
    assert f'<p class="sentence" id="panel-path">{made_panel.path_line}</p>' in page


@pytest.mark.parametrize("name, speechmatics, claude", [
    ("L", "nothing", "nothing"), ("R", "after_stop", "nothing"), ("S", "live", "nothing"),
    ("C", "nothing", "live"), ("CR", "after_stop", "live"), ("CS", "live", "live"),
])
def test_review_point_1_a_cloud_box_says_what_goes_to_it_on_the_path_as_chosen_and_nothing_else(tmp_path, clock, name, speechmatics, claude):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    made_panel = panel.build(app.state.parts)
    says = {"live": "On the path you chose, the sound of the consultation goes to Speechmatics as it is spoken.",
            "after_stop": "On the path you chose, the recording goes to Speechmatics once, after Stop. No sound goes to it during the consultation.",
            "nothing": "On the path you chose, nothing goes to Speechmatics."}
    assert made_panel.box("speechmatics").goes == says[speechmatics]
    assert made_panel.box("claude").goes == {"live": "On the path you chose, the words of the consultation go to Claude.",
                                             "nothing": "On the path you chose, nothing goes to Claude."}[claude]
    # Connected and not chosen, as on the owner's own machine: the box is ready and does not say that sound goes to it.
    page = text_of(client.get("/settings"))
    assert ("goes to Speechmatics as it is spoken" in box_of(page, "speechmatics")) is (speechmatics == "live")
    assert ("go to Claude" in box_of(page, "claude")) is (claude == "live")
    # With the tick for better accuracy the Speechmatics box says Used after Stop, and the line of the path adds the owner's own.
    assert (made_panel.box("speechmatics").also == "Used after Stop") is (speechmatics == "after_stop")
    assert (words.CLOUD_MARK_RECORDING in made_panel.path_line) is (speechmatics == "after_stop")
    assert panel.goes_to(PATHS[name], SPEECHMATICS) == speechmatics and panel.goes_to(PATHS[name], CLAUDE) == claude


# ------------------------------------------------------- the Consultation box

def facts(tmp_path, clock):
    """Made facts for the Consultation box, each with the app it gives."""
    yield "all on this computer, ready", made(tmp_path / "a", clock)
    yield "no local model", made(tmp_path / "b", clock, ollama=FakeEngine(version=None))
    yield "no speech model installed", made(tmp_path / "c", clock, nemotron=False)
    yield "Claude chosen, no key", made(tmp_path / "d", clock, path=PATHS["C"], tick=False)
    yield "both in the cloud, the statement not ticked", made(tmp_path / "e", clock, machine=NO_CARD, held=BOTH_KEYS, tick=False)
    yield "the cloud, ticked and tested at start", made(tmp_path / "f", clock, machine=NO_CARD, held=BOTH_KEYS, path=PATHS["CS"])
    yield "a set-up step not done", made(tmp_path / "g", clock, user=False)


def test_15_13_ruling_56_the_consultation_box_and_the_start_control_give_the_same_reason_from_the_same_facts(tmp_path, clock):
    seen = set()
    for case, (app, client, testers, engines, workers) in facts(tmp_path, clock):
        p = app.state.parts
        if case.startswith("the cloud, ticked"):
            p.connections.test_all((CLAUDE, SPEECHMATICS))                              # a path set after the start: tested since
        box = panel.build(p).box("consultation")
        at_start = start_state(p, ask_engine=False)
        assert box.sentence == (at_start.problem or "Ready to start."), case
        assert box.state == ("ready" if at_start.problem is None else "not_set_up" if at_start.lead else "cannot_run"), case
        assert box.link == at_start.lead and box.on_path and not box.chosen, case
        seen.add(box.state)
    assert seen == {"ready", "not_set_up", "cannot_run"}
    # A connection that fails its test: the same sentence as the Start control, and the box says when it was tested.
    app, client, testers, *_ = made(tmp_path / "h", clock, machine=NO_CARD, held=BOTH_KEYS, path=PATHS["CS"])
    p = app.state.parts
    testers.fail[SPEECHMATICS] = "no_internet"
    p.connections.test_all((CLAUDE, SPEECHMATICS))
    box = panel.build(p).box("consultation")
    assert box.sentence == start_state(p, ask_engine=False).problem == (
        "Start is not offered: Speechmatics could not be reached. Check the internet connection and try again.")
    assert box.when == ("Speechmatics was tested at 09:00.", "Claude was tested at 09:00.") and box.link == ("/connect/speechmatics", "Speechmatics")


def test_review_point_2_the_consultation_box_rests_only_on_tests_that_were_made(tmp_path, clock):
    # Keys in the store, the path moved to the cloud after the start: neither service was tested since the start.
    app, client, testers, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS["CS"])
    p = app.state.parts
    assert testers.asked == [] and start_state(p, ask_engine=False).problem is None       # nothing is known against it, and nothing was tested
    box = panel.build(p).box("consultation")
    assert state_of(box) == ("not_set_up", "Speechmatics has not been tested since OpenConsult started. The Start screen tests it.")
    assert box.when == () and box.link == ("/connect/speechmatics", "Speechmatics")
    p.connections.test_all((CLAUDE, SPEECHMATICS))
    box = panel.build(p).box("consultation")
    assert state_of(box) == ("ready", "Ready to start.") and box.when == ("Speechmatics was tested at 09:00.", "Claude was tested at 09:00.")
    # Its face says what it is ready for, as the owner's sketch has it; every other box says Ready.
    assert box.state_words == "Ready to start" and panel.build(p).box("microphone").state_words == "Ready"
    assert '<span class="box-sign" aria-hidden="true">✓</span> Ready to start</span>' in box_of(text_of(client.get("/settings")), "consultation")
    # On this computer the box says that the engine was asked at the start; it is not asked again for a view.
    app, client, *_ = made(tmp_path / "local", clock)
    assert panel.build(app.state.parts).box("consultation").when == ("The engine was asked when OpenConsult started.",)


# ------------------------------------------------------------ on the pages

def test_15_13_ruling_56_no_test_is_made_and_no_engine_asked_at_a_view_of_the_picture_on_either_page(tmp_path, clock):
    app, client, testers, engines, workers = made(tmp_path, clock, machine=NO_CARD, held=BOTH_KEYS, user=False)
    asked, status = len(testers.asked), {name: engine.status_calls for name, engine in engines.items()}
    store_calls = len(app.state.parts.store.calls)
    client.post("/first-run/statement", data={"agree": "yes"})
    first = client.get("/first-run")
    assert 'id="control-panel"' in first.text
    set_up(client)
    log_in(client)
    for _ in range(3):
        assert 'id="control-panel"' in client.get("/settings").text
    assert len(testers.asked) == asked and {name: engine.status_calls for name, engine in engines.items()} == status
    assert all(worker.starts == 0 and worker.requests == [] for worker in workers.values())
    assert all(what == "get" for what, _ in app.state.parts.store.calls[store_calls:])       # the store is read for a key's presence, never written


def test_15_13_ruling_56_the_picture_on_the_page_columns_in_the_order_of_the_path_states_by_sign_and_word_boxes_that_open_with_no_script(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held={"ANTHROPIC_API_KEY": GOOD})
    page = text_of(client.get("/settings"))
    picture = page.split('id="control-panel"', 1)[1].split('<table class="plain facts">', 1)[0]
    # The order a screen reader meets: the line of the path, then the four columns, this computer before its cloud service.
    order = [picture.index(mark) for mark in ('id="panel-path"', 'id="panel-microphone">Microphone<', 'id="box-microphone"', 'id="panel-transcription">Transcription<',
                                              'id="box-speech_local"', 'id="box-speechmatics"', 'id="panel-language_model">Language model<',
                                              'id="box-model_local"', 'id="box-claude"', 'id="panel-consultation">Consultation<', 'id="box-consultation"')]
    assert order == sorted(order)
    # Each box is the browser's own disclosure: a press opens it with no script. None is open as served.
    assert picture.count("<details ") == 6 == picture.count("<summary ") and "<details open" not in picture and " open>" not in picture
    assert "<script" not in picture
    # A state is told by a sign and a word, never by colour alone (R15); the sign is hidden from a reader, the word is not.
    for name, sign, said in (("microphone", "\u2713", "Ready"), ("claude", "\u2713", "Ready"), ("speechmatics", "\u2013", "Not set up")):
        assert f'<span class="box-state"><span class="box-sign" aria-hidden="true">{sign}</span> {said}</span>' in box_of(page, name)
    assert words.PANEL_SIGNS == {"ready": "\u2713", "not_set_up": "\u2013", "cannot_run": "\u2715"}
    # A cloud box carries the drawn cloud of the cloud mark; a box of this computer does not.
    assert 'class="cloud-shape"' in box_of(page, "claude") and 'class="cloud-shape"' in box_of(page, "speechmatics")
    assert 'class="cloud-shape"' not in box_of(page, "model_local") and 'class="cloud-shape"' not in box_of(page, "microphone")
    # The small table under it holds what the boxes do not say, and nothing a box says.
    table = page.split('<table class="plain facts">', 1)[1].split("</table>", 1)[0]
    assert re.findall(r"<th>([^<]+)</th>", table) == [words.ROW_SYSTEM, words.ROW_CARD, words.ROW_GUIDELINE_SEARCH, words.ROW_CONVERTER]
    assert SUITABLE.sentence in page.split("</table>", 1)[1].split("</section>", 1)[0]
    # R31: no action Download and no box for Alba; the actions are the three, or the Consultation box's own link.
    assert "Download" not in picture and "Alba" not in picture
    assert set(re.findall(r'data-action="([a-z]+)"', picture)) <= {"connect", "test", "choose", "link"}


def test_15_13_ruling_56_each_action_leads_where_it_says_and_choose_follows_rulings_47_and_48(tmp_path, clock):
    app, client, testers, *_ = made(tmp_path, clock, held={"ANTHROPIC_API_KEY": GOOD})
    p = app.state.parts
    page = client.get("/settings").text
    assert '<a class="button" id="act-microphone" data-action="test" href="/first-run/microphone">Test</a>' in page
    assert '<a class="button" id="act-speechmatics" data-action="connect" href="/connect/speechmatics">Connect</a>' in page
    # Choose on the Claude box: the section's own address, so it follows ruling 47. The statement waits: nothing is saved,
    # and the page that comes back goes to the statement by itself, with no script and without loading again.
    choose = box_of(page, "claude").split("<form", 1)[1].split("</form>", 1)[0]
    assert 'method="post" action="/settings/path/language-model"' in choose and 'name="language_model" value="claude"' in choose
    assert 'name="from" value="panel"' in choose and '<button id="act-claude" data-action="choose">Choose</button>' in choose
    waits = client.post("/settings/path/language-model", data={"language_model": CLAUDE, "from": "panel"})
    assert waits.status_code == 200 and words.PATH_NOT_SAVED_YET in text_of(waits) and p.stored.path("suitable") == PATHS["L"]
    assert '<meta http-equiv="refresh" content="0;url=#not-saved-language-model">' in waits.text
    assert 'http-equiv="refresh" content="0;url=#' not in client.post("/settings/path/language-model", data={"language_model": CLAUDE}).text
    made_statement = statement_for(PATHS["C"])
    client.post("/settings/path/language-model", data={"language_model": CLAUDE, "understand": "yes", "sha256": made_statement.sha256})
    assert p.stored.path("suitable") == PATHS["C"]
    # Now the box This computer is ready and not chosen: its Choose sends less than was ticked, so it saves with no tick (ruling 48).
    page = client.get("/settings").text
    assert '<button id="act-model_local" data-action="choose">Choose</button>' in box_of(page, "model_local")
    saved = client.post("/settings/path/language-model", data={"language_model": THIS_COMPUTER, "from": "panel"})
    assert saved.status_code == 303 and p.stored.path("suitable") == PATHS["L"]
    # Test on a cloud box: the connect screen's own test of the key in use, which answers on that screen.
    test = box_of(client.get("/settings").text, "claude")
    assert 'data-action="choose"' in test                                                # ready and not chosen: its one action is Choose
    client.post("/settings/path/language-model", data={"language_model": CLAUDE})        # covered by its own tick: saved
    test = box_of(client.get("/settings").text, "claude").split("<form", 1)[1].split("</form>", 1)[0]
    assert 'method="post" action="/connect/claude"' in test and 'name="key" value=""' in test and 'data-action="test">Test</button>' in test
    before = len(testers.asked)
    tested = client.post("/connect/claude", data={"key": ""})
    assert tested.status_code == 303 and tested.headers["location"] == "/connect/claude?done=tested" and len(testers.asked) == before + 1
    # A box that cannot be chosen offers no Choose, and a post made anyway is refused on the section's control.
    assert 'data-action="choose"' not in box_of(client.get("/settings").text, "speechmatics")
    refused = client.post("/settings/path/transcription", data={"transcription": SPEECHMATICS, "from": "panel"})
    assert refused.status_code == 400 and refusal_on(refused.text, "save-transcription") == "Connect Speechmatics first."


def test_7_1_and_ruling_56_the_same_picture_at_step_2_of_the_first_run_with_no_choose_and_where_to_choose(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, user=False)
    client.post("/first-run/statement", data={"agree": "yes"})
    first = client.get("/first-run")
    page = text_of(first)
    assert 'id="control-panel"' in page and page.count("<details ") == 6
    assert 'data-action="choose"' not in page                                              # no user yet: no change of path here
    for name in ("claude", "speechmatics"):                                               # ready, and not on the path
        assert "You can choose it in Settings once OpenConsult is set up." in box_of(page, name)
    assert "You can choose it" not in box_of(page, "model_local")                         # on the path already
    # The picture stands outside the step's own form: a box's form is never inside another.
    form = first.text.split('action="/first-run/machine"', 1)[1].split("</form>", 1)[0]
    assert "<form" not in form and 'id="continue"' in form and first.text.index('id="control-panel"') < first.text.index('action="/first-run/machine"')
    assert 'class="wrap"' in first.text and "wrap narrow" not in first.text               # wide enough for four columns
    assert client.post("/first-run/machine", data={}).status_code == 303
    # The same boxes in Settings, where Choose is offered.
    set_up(client)
    log_in(client)
    assert 'data-action="choose"' in box_of(client.get("/settings").text, "claude")


def test_15_8_ruling_38_the_boxes_are_written_to_the_audit_log_once_at_start_with_their_figures(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held={"ANTHROPIC_API_KEY": GOOD})
    p = app.state.parts
    lines = {line.event: line.detail for line in p.audit.lines() if line.event.startswith("panel.")}
    assert sorted(lines) == ["panel.claude", "panel.consultation", "panel.microphone", "panel.model_local", "panel.speech_local", "panel.speechmatics"]
    assert lines["panel.claude"] == "Ready. Claude is connected. It is the cloud language model. Figures: key store, last test none."
    assert lines["panel.speechmatics"].startswith("Not set up. Speechmatics is not connected.") and "key none" in lines["panel.speechmatics"]
    assert all(words.EVENTS[event] for event in lines) and GOOD not in " ".join(lines.values())       # never a key
    for _ in range(2):
        client.get("/settings")
    assert len([line for line in p.audit.lines() if line.event.startswith("panel.")]) == 6            # a view writes nothing
