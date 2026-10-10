"""This machine's two lines about the local model (spec 15.7; HANDOVER,
stage 3): only on a machine with a suitable card."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import FakeEngine

SUITABLE = describe("Linux", "x86_64", [Card("Made-up card", 24564)])
SMALLER = describe("Windows", "AMD64", [Card("Made-up card", 8188)])
MAC = describe("Darwin", "arm64", [])

CASES = [
    (FakeEngine(version="9.9", present=True), words.OLLAMA_RUNNING.format(version="9.9"), words.MODEL_PRESENT),
    (FakeEngine(version="9.9", present=False), words.OLLAMA_RUNNING.format(version="9.9"), words.MODEL_ABSENT),
    (FakeEngine(version=None), words.OLLAMA_NOT_RUNNING, words.MODEL_UNKNOWN),
]


@pytest.mark.parametrize("engine, ollama_line, model_line", CASES)
def test_15_7_this_machine_says_whether_ollama_runs_and_gemma_is_present(tmp_path, clock, engine, ollama_line, model_line):
    app = build_app(store.build(tmp_path, PORT), machine=SUITABLE, clock=clock, engine=engine)
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    assert ollama_line in first_run and model_line in first_run
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    assert ollama_line in settings and model_line in settings
    assert engine.status_calls == 2


@pytest.mark.parametrize("machine", [SMALLER, MAC])
def test_15_7_on_any_other_machine_nothing_about_ollama_is_shown_and_it_is_not_asked(tmp_path, clock, machine):
    engine = FakeEngine(version="9.9", present=True)
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, engine=engine)
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    for page in (first_run, settings):
        assert words.ROW_OLLAMA not in page and words.ROW_MODEL not in page
        assert words.MODEL_PRESENT not in page and words.OLLAMA_NOT_RUNNING not in page
    assert engine.status_calls == 0
