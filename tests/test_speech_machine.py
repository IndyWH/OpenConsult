"""What This machine says about the speech choices (spec 15.9): on a
suitable card only, read from the data folder and the stored result,
with no worker started and no model loaded. Until run 9c these facts
stood as rows of a table; since the control panel (15.13, rulings 6 and
56) each stands in its box, or on its control in Settings, and is not
said a second time in the small table. Each test here proves the same
fact where it now stands."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.speech.choices import WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from openconsult.speech.selftest import Outcome, SelfTests
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import MadeUpWorker
from tests.test_machine_status import MAC, SMALLER, SUITABLE, box_of

STATES = ["not_installed", "not_run", "passed", "failed"]
WHISPERX = "WhisperX with pyannote"
# What the box Transcription, This computer says for each state of the choice it would run.
EXPECTED = {
    "not_run": ("Not set up", f"{WHISPERX} is installed. Its self-test has not been run yet."),
    "passed": ("Ready", f"{WHISPERX} is installed and its self-test passed on 4 Oct 2026 at 09:00."),
    "failed": ("Not set up", f"{WHISPERX} is installed. Its self-test failed on 4 Oct 2026 at 09:00: made-up reason"),
}
ROWS_GONE = (words.ROW_SPEECH, words.ROW_SELF_TEST, words.ROW_NEMOTRON, words.ROW_SPEECHMATICS, words.ROW_SPEECH_CHOICE)


def no_row(page: str) -> bool:
    """None of the rows of the table that the boxes now say."""
    return not any(f"<th>{row}</th>" in page for row in ROWS_GONE)


def app_in(tmp_path, clock, machine, state, worker):
    installed = state != "not_installed"
    door = Door(WHISPERX_PYANNOTE, make_worker=lambda: worker, installed=lambda: installed)
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, speech=door)
    if state in ("passed", "failed"):
        outcome = Outcome(state == "passed", None if state == "passed" else "made-up reason", [], [], {})
        SelfTests(app.state.parts.db, clock).add("whisperx_pyannote", outcome)
    return app


@pytest.mark.parametrize("state", STATES)
def test_15_9_this_machine_says_whether_the_choice_is_installed_and_the_last_self_test(tmp_path, clock, state):
    worker = MadeUpWorker()
    app = app_in(tmp_path, clock, SUITABLE, state, worker)
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    for page in (first_run, settings):
        box = box_of(page, "speech_local")
        if state == "not_installed":
            # Neither model is installed: the box names Nemotron, the choice until the doctor changes it, with its command.
            assert "Not set up" in box and "Nemotron is not installed. Install it with: uv run openconsult install-speech --choice nemotron" in box
        else:
            state_words, sentence = EXPECTED[state]
            assert WHISPERX in box and state_words in box and sentence in box                # the model it would run, its state, and why
        assert no_row(page)
    if state == "not_installed":
        # That the WhisperX choice is not installed stands on its own control, in Settings.
        assert ('id="speech-model-whisperx_pyannote-reason">Not installed. Install it with: uv run openconsult install-speech '
                "--choice whisperx_pyannote</p>") in settings
    assert worker.starts == 0 and worker.requests == []        # nothing started, nothing loaded


def test_15_9_the_newest_self_test_is_the_one_shown(tmp_path, clock):
    app = app_in(tmp_path, clock, SUITABLE, "failed", MadeUpWorker())
    clock.advance(hours=1)
    SelfTests(app.state.parts.db, clock).add("whisperx_pyannote", Outcome(True, None, [], [], {}))
    client = browser(app)
    set_up(client)
    log_in(client)
    page = text_of(client.get("/settings"))
    assert f"{WHISPERX} is installed and its self-test passed on 4 Oct 2026 at 10:00." in box_of(page, "speech_local")
    assert "made-up reason" not in page


@pytest.mark.parametrize("machine", [SMALLER, MAC])
def test_15_9_on_any_other_machine_nothing_about_speech_is_shown(tmp_path, clock, machine):
    app = app_in(tmp_path, clock, machine, "passed", MadeUpWorker())
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    for page in (first_run, settings):
        # The row headers exactly: 5b's Speechmatics row, shown on every machine, holds the word Speech.
        assert f"<th>{words.ROW_SPEECH}</th>" not in page and f"<th>{words.ROW_SELF_TEST}</th>" not in page
        assert words.SPEECH_INSTALLED not in page and words.SELF_TEST_PASSED[:6] not in page


# ------------------------------------------- each choice in its box (5b; 9c)

from openconsult.speech.choices import NEMOTRON, SPEECHMATICS  # noqa: E402

CLOUD_STATES = ["no_key", "not_run", "passed", "failed"]
NEMOTRON_STATES = {
    "not_installed": ("Not set up", "Nemotron is not installed. Install it with: uv run openconsult install-speech --choice nemotron"),
    "not_run": ("Not set up", "Nemotron is installed. Its self-test has not been run yet."),
    "passed": ("Ready", "Nemotron is installed and its self-test passed on 4 Oct 2026 at 09:00."),
    "failed": ("Not set up", "Nemotron is installed. Its self-test failed on 4 Oct 2026 at 09:00: made-up reason"),
}


def doors_in(tmp_path, clock, machine, nemotron_state, cloud_state):
    workers = {name: MadeUpWorker() for name in ("whisperx_pyannote", "nemotron", "speechmatics")}
    doors = {
        "nemotron": Door(NEMOTRON, make_worker=lambda: workers["nemotron"], installed=lambda: nemotron_state != "not_installed"),
        "speechmatics": Door(SPEECHMATICS, make_worker=lambda: workers["speechmatics"], installed=lambda: True,
                             key_present=lambda: cloud_state != "no_key"),
    }
    whisperx = Door(WHISPERX_PYANNOTE, make_worker=lambda: workers["whisperx_pyannote"], installed=lambda: False)
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, speech=whisperx, doors=doors)
    for name, state in (("nemotron", nemotron_state), ("speechmatics", cloud_state)):
        if state in ("passed", "failed"):
            outcome = Outcome(state == "passed", None if state == "passed" else "made-up reason", [], [], {})
            SelfTests(app.state.parts.db, clock).add(name, outcome)
    return app, workers


def pages_of(app):
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    return first_run, text_of(client.get("/settings"))


@pytest.mark.parametrize("nemotron_state", list(NEMOTRON_STATES))
@pytest.mark.parametrize("cloud_state", CLOUD_STATES)
def test_15_9_this_machine_says_each_choice_in_its_box_on_a_suitable_card(tmp_path, clock, nemotron_state, cloud_state):
    app, workers = doors_in(tmp_path, clock, SUITABLE, nemotron_state, cloud_state)
    state_words, sentence = NEMOTRON_STATES[nemotron_state]
    for page in pages_of(app):
        local = box_of(page, "speech_local")
        assert "Nemotron" in local and state_words in local and sentence in local             # what its row said, in its box
        # The cloud service's box says its connection as the app holds it (7.2): no key is connected here, whatever
        # a self-test of the clip once gave. That self-test is no longer on This machine; it stands on its step's page.
        cloud = box_of(page, "speechmatics")
        assert "Not set up" in cloud and "Speechmatics is not connected." in cloud and words.NOT_CONNECTED in cloud
        assert no_row(page) and words.CLOUD_PASSED[:16] not in page
        assert words.ROW_ASSEMBLYAI not in page                                   # 15.13 ruling 28: no page of the app names it
    assert all(w.starts == 0 and w.requests == [] for w in workers.values())    # nothing started, nothing loaded


@pytest.mark.parametrize("machine", [SMALLER, MAC])
def test_15_9_a_machine_with_no_suitable_card_shows_the_cloud_box_and_nothing_local(tmp_path, clock, machine):
    app, workers = doors_in(tmp_path, clock, machine, "passed", "passed")
    for page in pages_of(app):
        local = box_of(page, "speech_local")
        assert "Cannot run here" in local and machine.sentence in local and "self-test passed" not in page   # nothing local is said to work
        assert "Speechmatics, cloud" in box_of(page, "speechmatics") and no_row(page)
        assert words.ROW_ASSEMBLYAI not in page                                   # 15.13 ruling 28
    assert all(w.starts == 0 for w in workers.values())


def test_10_4_a_failure_on_one_door_leaves_the_others_untouched(tmp_path, clock):
    app, workers = doors_in(tmp_path, clock, SUITABLE, "not_run", "not_run")
    workers["nemotron"].ready_ok = False
    failed = app.state.parts.doors["nemotron"].open(16000, speakers=2)
    assert failed.failure == "died"
    assert workers["nemotron"].starts == 1
    assert all(workers[name].starts == 0 for name in ("whisperx_pyannote", "speechmatics"))
    assert set(app.state.parts.doors) == {"whisperx_pyannote", "nemotron", "speechmatics"}      # no door for the second cloud service (15.13 ruling 28)
