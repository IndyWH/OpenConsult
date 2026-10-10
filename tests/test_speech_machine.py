"""This machine's two lines about the speech choice (spec 15.9): on a
suitable card only, read from the data folder and the stored result,
with no worker started and no model loaded."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.speech.choices import WHISPERX_PYANNOTE
from openconsult.speech.door import Door
from openconsult.speech.selftest import Outcome, SelfTests
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import MadeUpWorker
from tests.test_machine_status import MAC, SMALLER, SUITABLE

STATES = ["not_installed", "not_run", "passed", "failed"]
EXPECTED = {
    "not_installed": (words.SPEECH_NOT_INSTALLED, words.SELF_TEST_NOT_POSSIBLE),
    "not_run": (words.SPEECH_INSTALLED, words.SELF_TEST_NOT_RUN),
    "passed": (words.SPEECH_INSTALLED, words.SELF_TEST_PASSED.format(date="4 Oct 2026", time="09:00")),
    "failed": (words.SPEECH_INSTALLED, words.SELF_TEST_FAILED.format(date="4 Oct 2026", time="09:00",
                                                                     reason="made-up reason")),
}


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
    installed_line, self_test_line = EXPECTED[state]
    for page in (first_run, settings):
        assert words.ROW_SPEECH in page and installed_line in page and self_test_line in page
    assert worker.starts == 0 and worker.requests == []        # nothing started, nothing loaded


def test_15_9_the_newest_self_test_is_the_one_shown(tmp_path, clock):
    app = app_in(tmp_path, clock, SUITABLE, "failed", MadeUpWorker())
    clock.advance(hours=1)
    SelfTests(app.state.parts.db, clock).add("whisperx_pyannote", Outcome(True, None, [], [], {}))
    client = browser(app)
    set_up(client)
    log_in(client)
    page = text_of(client.get("/settings"))
    assert words.SELF_TEST_PASSED.format(date="4 Oct 2026", time="10:00") in page
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


# ------------------------------------------- one line for each choice (5b)

from openconsult.speech.choices import ASSEMBLYAI, NEMOTRON, SPEECHMATICS  # noqa: E402

CLOUD_STATES = {
    "no_key": words.CLOUD_NO_KEY,
    "not_run": words.CLOUD_NOT_RUN,
    "passed": words.CLOUD_PASSED.format(date="4 Oct 2026", time="09:00"),
    "failed": words.CLOUD_FAILED.format(date="4 Oct 2026", time="09:00", reason="made-up reason"),
}
NEMOTRON_STATES = {
    "not_installed": words.NEMOTRON_NOT_INSTALLED,
    "not_run": words.NEMOTRON_NOT_RUN,
    "passed": words.NEMOTRON_PASSED.format(date="4 Oct 2026", time="09:00"),
    "failed": words.NEMOTRON_FAILED.format(date="4 Oct 2026", time="09:00", reason="made-up reason"),
}


def doors_in(tmp_path, clock, machine, nemotron_state, cloud_state):
    workers = {name: MadeUpWorker() for name in ("whisperx_pyannote", "nemotron", "speechmatics", "assemblyai")}
    doors = {
        "nemotron": Door(NEMOTRON, make_worker=lambda: workers["nemotron"], installed=lambda: nemotron_state != "not_installed"),
        "speechmatics": Door(SPEECHMATICS, make_worker=lambda: workers["speechmatics"], installed=lambda: True,
                             key_present=lambda: cloud_state != "no_key"),
        "assemblyai": Door(ASSEMBLYAI, make_worker=lambda: workers["assemblyai"], installed=lambda: True,
                           key_present=lambda: cloud_state != "no_key"),
    }
    whisperx = Door(WHISPERX_PYANNOTE, make_worker=lambda: workers["whisperx_pyannote"], installed=lambda: False)
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, speech=whisperx, doors=doors)
    for name, state in (("nemotron", nemotron_state), ("speechmatics", cloud_state), ("assemblyai", cloud_state)):
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
@pytest.mark.parametrize("cloud_state", list(CLOUD_STATES))
def test_15_9_this_machine_has_one_line_for_each_choice_on_a_suitable_card(tmp_path, clock, nemotron_state, cloud_state):
    app, workers = doors_in(tmp_path, clock, SUITABLE, nemotron_state, cloud_state)
    for page in pages_of(app):
        assert f"<th>{words.ROW_NEMOTRON}</th><td>{NEMOTRON_STATES[nemotron_state]}</td>" in page
        for row in (words.ROW_SPEECHMATICS, words.ROW_ASSEMBLYAI):
            assert f"<th>{row}</th><td>{CLOUD_STATES[cloud_state]}</td>" in page
    assert all(w.starts == 0 and w.requests == [] for w in workers.values())    # nothing started, nothing loaded


@pytest.mark.parametrize("machine", [SMALLER, MAC])
def test_15_9_a_machine_with_no_suitable_card_shows_the_cloud_lines_and_nothing_local(tmp_path, clock, machine):
    app, workers = doors_in(tmp_path, clock, machine, "passed", "passed")
    for page in pages_of(app):
        assert f"<th>{words.ROW_NEMOTRON}</th>" not in page and words.NEMOTRON_PASSED[:10] not in page
        for row in (words.ROW_SPEECHMATICS, words.ROW_ASSEMBLYAI):
            assert f"<th>{row}</th><td>{CLOUD_STATES['passed']}</td>" in page
    assert all(w.starts == 0 for w in workers.values())


def test_10_4_a_failure_on_one_door_leaves_the_others_untouched(tmp_path, clock):
    app, workers = doors_in(tmp_path, clock, SUITABLE, "not_run", "not_run")
    workers["nemotron"].ready_ok = False
    failed = app.state.parts.doors["nemotron"].open(16000, speakers=2)
    assert failed.failure == "died"
    assert workers["nemotron"].starts == 1
    assert all(workers[name].starts == 0 for name in ("whisperx_pyannote", "speechmatics", "assemblyai"))
    assert set(app.state.parts.doors) == {"whisperx_pyannote", "nemotron", "speechmatics", "assemblyai"}
