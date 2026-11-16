"""The first-run steps of run 9b (spec 7.1; 15.13, ruling 7 and the details
of the run; 15.8 ruling 37; D46; R15): connect the language model and
connect transcription only when their path is the cloud, the self-test
from the page, the microphone test, then the user; each of the middle
steps can be left, and Start names what is missing. Made doors, a made
store, made tests of a connection; no microphone and no browser."""

from __future__ import annotations

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store as settings_store
from openconsult.settings.path import CLAUDE, SPEECHMATICS, ChosenPath
from openconsult.settings.statement import statement_for
from openconsult.speech.choices import NEMOTRON
from openconsult.speech.door import Door as SpeechDoor
from openconsult.speech.selftest import SelfTests
from openconsult.web import steps
from tests.conftest import PASSWORD, PORT, browser, log_in, refusal_on, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.made_up_store import MadeStore
from tests.test_connect_screens import GOOD, NO_CARD, SUITABLE, MadeTesters
from tests.test_start import PATIENT, TICKS
from tests.test_stop import until

USER = {"title": "Dr", "name": "Example", "password": PASSWORD, "password_again": PASSWORD}
CLIP_WORDS = ("and so my fellow americans ask not what your country can do for you ask what you can do for your country")


def clip_worker(heard: str = CLIP_WORDS):
    """A made worker that hears the clip's words on its first piece, as one line of one speaker."""
    line = {"id": 1, "start": 0.0, "end": 0.2, "text": heard, "speaker": "S1", "confidence": None}
    return MadeUpWorker(live=[[line]])


def fresh(tmp_path, clock, machine, worker=None, store=None, testers=None):
    testers = testers or MadeTesters()
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: worker is not None)}
    app = build_app(settings_store.build(tmp_path, PORT), machine=machine, clock=clock, engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()},
                    doors=doors, secure_store=store if store is not None else MadeStore(), testers=testers.both())
    return app, browser(app), testers


def through_machine(client):
    client.post("/first-run/statement", data={"agree": "yes"})
    client.post("/first-run/machine", data={})


def test_7_1_the_steps_come_in_their_order_and_a_connect_step_only_when_its_path_is_the_cloud(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(steps, "pace", lambda s: None)
    # A suitable card: both paths begin on this computer, so no connect step; the self-test, the microphone test, the user.
    app, client, testers = fresh(tmp_path / "card", clock, SUITABLE, worker=clip_worker())
    p = app.state.parts
    through_machine(client)
    page = text_of(client.get("/first-run"))
    assert words.FIRST_RUN_SELF_TEST_INTRO in page and words.CONNECT_CLAUDE_TITLE not in page and words.FIRST_RUN_NEW_STEPS not in page
    assert client.post("/first-run/self-test").headers["location"] == "/first-run/self-test"
    assert until(lambda: steps.self_testing(p).state == "passed")
    done = text_of(client.get("/first-run/self-test"))
    assert words.SELF_TEST_STEP_PASSED in done and 'id="continue" href="/first-run"' in client.get("/first-run/self-test").text
    assert SelfTests(p.db, clock).last("nemotron")["passed"]                                 # stored as the command stores it
    assert steps.is_done(p, "self_test") and words.MIC_INTRO in text_of(client.get("/first-run"))
    assert client.post("/first-run/microphone", data={"moved": "yes"}).headers["location"] == "/first-run"
    assert words.FIRST_RUN_USER_INTRO in client.get("/first-run").text
    events = [l.event for l in p.audit.lines()]
    assert "self_test.passed" in events and "microphone.tested" in events
    # No suitable card: both paths begin in the cloud, so the two connect steps come first, in their order.
    app, client, testers = fresh(tmp_path / "none", clock, NO_CARD)
    p = app.state.parts
    through_machine(client)
    first = client.get("/first-run")
    assert f'<h1 class="page">{words.CONNECT_CLAUDE_TITLE}</h1>' in first.text and words.FIRST_RUN_CONNECT_MODEL_TITLE in text_of(first)
    assert 'data-step="connect_language_model"' in first.text and 'id="not-now"' in first.text
    client.post("/connect/claude", data={"key": GOOD})
    assert 'id="cloud-statement"' in client.get("/first-run").text and 'id="not-now"' in client.get("/first-run").text   # connected, not ticked: not done yet
    client.post("/connect/speechmatics", data={"key": GOOD})
    made = statement_for(ChosenPath(CLAUDE, SPEECHMATICS))
    client.post("/statement/tick", data={"sha256": made.sha256, "understand": "yes", "back": "/first-run"})
    assert steps.is_done(p, "connect_language_model") and steps.is_done(p, "connect_transcription")
    assert words.FIRST_RUN_SELF_TEST_INTRO in text_of(client.get("/first-run"))               # both connect steps done: the self-test is next
    assert words.SELF_TEST_RUNNING_CLOUD.format(service="Speechmatics") in text_of(client.get("/first-run"))   # the clip leaves: said before the press


def test_7_1_a_failed_self_test_leaves_the_step_not_done_and_says_why_and_each_middle_step_can_be_left(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(steps, "pace", lambda s: None)
    app, client, testers = fresh(tmp_path / "wrong", clock, SUITABLE, worker=clip_worker("made up words that are not the clip"))
    p = app.state.parts
    through_machine(client)
    client.post("/first-run/self-test")
    assert until(lambda: steps.self_testing(p).state == "failed")
    page = client.get("/first-run/self-test")
    assert words.SELF_TEST_STEP_FAILED.format(reason=steps.self_testing(p).reason) in text_of(page) and "expected words were heard" in text_of(page)
    assert not steps.is_done(p, "self_test") and 'id="continue"' not in page.text and 'id="not-now"' in page.text
    assert words.FIRST_RUN_SELF_TEST_INTRO in text_of(client.get("/first-run"))               # the walk stays at the step
    # Nothing installed on this computer: the control is disabled with the reason on it, and the step can still be left.
    app, client, testers = fresh(tmp_path / "bare", clock, SUITABLE, worker=None)
    p = app.state.parts
    through_machine(client)
    page = client.get("/first-run")
    assert 'id="run-self-test" aria-describedby="run-self-test-refusal" disabled' in page.text
    assert refusal_on(page.text, "run-self-test").startswith(words.SPEECH_REASONS["nemotron_not_installed"])
    refused = client.post("/first-run/self-test")
    assert refused.status_code == 400 and steps.self_testing(p).state == "idle"
    assert client.post("/first-run/leave", data={"step": "self_test"}).headers["location"] == "/first-run"
    assert words.MIC_INTRO in text_of(client.get("/first-run"))
    no_sound = client.post("/first-run/microphone", data={})                                 # the level was never seen to move
    assert no_sound.status_code == 400 and refusal_on(no_sound.text, "continue") == words.MIC_NO_SOUND and not steps.is_done(p, "microphone")
    client.post("/first-run/leave", data={"step": "microphone"})
    assert words.FIRST_RUN_USER_INTRO in client.get("/first-run").text                        # so a bare computer still reaches the user step
    assert client.post("/first-run/leave", data={"step": "statement"}).headers["location"] == "/first-run" and p.first_run.left() == {
        "self_test", "microphone"}


def test_R15_start_names_the_missing_step_on_its_control_with_the_way_to_it(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(steps, "pace", lambda s: None)
    app, client, testers = fresh(tmp_path, clock, SUITABLE, worker=clip_worker())
    p = app.state.parts
    through_machine(client)
    for step in ("self_test", "microphone"):
        client.post("/first-run/leave", data={"step": step})
    client.post("/first-run/user", data=USER)
    assert log_in(client).headers["location"] == "/"                                          # both were met and left: nothing is asked again
    client.post("/patients", data=PATIENT)
    page = client.get("/consultations/start/1")
    assert 'id="start" aria-describedby="start-refusal" disabled' in page.text
    assert refusal_on(page.text, "start") == "Start is not offered: the self-test has not passed. Open the set-up steps."
    assert 'id="start-lead"><a href="/first-run/self-test">' in page.text
    refused = client.post("/consultations/start/1", data=TICKS)
    assert refused.status_code == 400 and p.consultations.get(1) is None
    client.post("/first-run/self-test")                                                       # a step left can be done later, at its own address
    assert until(lambda: steps.self_testing(p).state == "passed")
    page = client.get("/consultations/start/1")
    assert refusal_on(page.text, "start") == "Start is not offered: the microphone has not been tested. Open the set-up steps."
    assert 'id="start-lead"><a href="/first-run/microphone">' in page.text
    client.post("/first-run/microphone", data={"moved": "yes"})
    assert refusal_on(client.get("/consultations/start/1").text, "start") == ""
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303 and p.consultations.get(1) is not None
    # While a consultation runs the self-test is refused on its control: the speech choice has one session.
    busy = client.post("/first-run/self-test")
    assert busy.status_code == 400 and refusal_on(busy.text, "run-self-test") == words.SELF_TEST_BUSY


def test_details_of_9b_a_folder_that_finished_its_first_run_before_meets_the_new_steps_once_at_its_next_login(tmp_path, clock):
    app, client, testers = fresh(tmp_path, clock, SUITABLE, worker=clip_worker())
    p = app.state.parts
    through_machine(client)
    client.post("/first-run/user", data=USER)              # as stage 2 left a folder: the statement, This machine, the user
    assert steps.walk_step(p) == "self_test"
    assert browser(app).get("/first-run/self-test").headers["location"] == "/login"           # a set-up folder: behind the login
    assert log_in(client).headers["location"] == "/first-run"
    page = text_of(client.get("/first-run"))
    assert words.FIRST_RUN_NEW_STEPS in page and words.FIRST_RUN_SELF_TEST_INTRO in page       # said on the page, once
    assert client.get("/").status_code == 200                                                # nothing is locked: every page still answers
    client.post("/first-run/leave", data={"step": "self_test"})
    assert words.FIRST_RUN_NEW_STEPS in text_of(client.get("/first-run")) and words.MIC_INTRO in text_of(client.get("/first-run"))
    client.post("/first-run/microphone", data={"moved": "yes"})
    assert client.get("/first-run").headers["location"] == "/" and log_in(client).headers["location"] == "/"   # met once, not again


def test_15_8_ruling_37_where_no_local_model_runs_and_claude_is_not_connected_this_machine_and_start_lead_to_the_connect_screen(tmp_path, clock):
    absent = {"vllm": FakeEngine(version=None), "ollama": FakeEngine(version=None)}
    app = build_app(settings_store.build(tmp_path, PORT), machine=SUITABLE, clock=clock, engines=absent, secure_store=MadeStore(),
                    testers=MadeTesters().both())
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    machine_page = client.get("/first-run")
    assert words.POINTER_TO_CONNECT in text_of(machine_page) and 'id="pointer"' in machine_page.text and 'href="/connect/claude"' in machine_page.text
    from tests.conftest import set_up
    set_up(client)
    log_in(client)
    assert words.POINTER_TO_CONNECT in text_of(client.get("/settings"))
    client.post("/patients", data=PATIENT)
    start = client.get("/consultations/start/1")
    assert refusal_on(start.text, "start").startswith("Start is not offered:") and 'id="start-lead"><a href="/connect/claude">' in start.text
    client.post("/connect/claude", data={"key": GOOD})
    assert words.POINTER_TO_CONNECT not in text_of(client.get("/settings"))                   # connected: nothing to point to


def test_7_1_the_microphone_page_asks_as_the_live_page_asks_and_sends_no_sound(tmp_path, clock):
    app, client, testers = fresh(tmp_path, clock, SUITABLE, worker=clip_worker())
    through_machine(client)
    client.post("/first-run/leave", data={"step": "self_test"})
    page = client.get("/first-run")
    said = text_of(page)
    assert words.MIC_INTRO in said and words.MIC_NOT_SENT in said and words.MIC_NEEDS_SCRIPT in said and "<meter" in page.text
    assert 'id="continue" aria-describedby="continue-refusal" disabled' in page.text          # until the level has been seen to move
    form = page.text.split('id="mic-form"', 1)[1].split("</form>", 1)[0]
    assert form.count("<input") == 1 and 'name="moved"' in form                               # the form carries one word, never sound
    script = client.get("/static/mictest.js").text
    live = client.get("/static/live.js").text
    asked = "channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false"
    assert asked in script and asked in live and "sampleRate: ASKED_RATE" in script and "ASKED_RATE = 48000" in script
    for way_out in ("WebSocket", "fetch(", "XMLHttpRequest", "sendBeacon", "EventSource", ".submit("):
        assert way_out not in script                                                          # the script opens no connection of any kind
    assert "/static/mictest.js?v=" in page.text
