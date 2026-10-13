"""This machine's line about the language model (spec 15.7; 15.8, rulings
36 and 37): the engine chosen at start, held for the run, said in one
sentence from the file of words; only on a machine with a suitable card,
and never asked at a page view. Two made-up engines stand in."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from tests.conftest import PORT, browser, log_in, set_up, text_of
from tests.fakes import FakeEngine

SUITABLE = describe("Linux", "x86_64", [Card("Made-up card", 24564)])
SUITABLE_WINDOWS = describe("Windows", "AMD64", [Card("Made-up card", 24564)])
SMALLER = describe("Windows", "AMD64", [Card("Made-up card", 8188)])
MAC = describe("Darwin", "arm64", [])

ABSENT = dict(version=None)
VLLM = dict(version="0.31-made-up", present=True, context=16384)
OLLAMA = dict(version="9.9", present=True)


def sentence(key, **fill):
    return words.REASONS[key].format(**fill)


CASES = [
    # (vllm, ollama, the sentence)
    (VLLM, OLLAMA, sentence("engine_running", engine="vLLM", version="0.31-made-up", model=words.MODEL_PRESENT)),
    (ABSENT, OLLAMA, sentence("engine_fallback", engine="Ollama", version="9.9", model=words.MODEL_PRESENT,
                              reason=words.UNFIT["no_answer"].format(engine="vLLM"))),
    (dict(version="0.31-made-up", present=False), OLLAMA,
     sentence("engine_fallback", engine="Ollama", version="9.9", model=words.MODEL_PRESENT,
              reason=words.UNFIT["no_model"].format(engine="vLLM"))),
    (ABSENT, dict(version="9.9", present=False),
     sentence("engine_none", why="; ".join([words.UNFIT["no_answer"].format(engine="vLLM"),
                                            words.UNFIT["no_model"].format(engine="Ollama")]))),
    (ABSENT, ABSENT, sentence("engine_none", why="; ".join([words.UNFIT["no_answer"].format(engine="vLLM"),
                                                            words.UNFIT["no_answer"].format(engine="Ollama")]))),
]


def pages_of(tmp_path, clock, machine, vllm, ollama):
    engines = {"vllm": FakeEngine(**vllm), "ollama": FakeEngine(**ollama)}
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, engines=engines)
    client = browser(app)
    client.post("/first-run/statement", data={"agree": "yes"})
    first_run = text_of(client.get("/first-run"))
    set_up(client)
    log_in(client)
    settings = text_of(client.get("/settings"))
    return engines, first_run, settings


@pytest.mark.parametrize("vllm, ollama, line", CASES)
def test_ruling_36_this_machine_says_the_engine_the_model_and_the_reason(tmp_path, clock, vllm, ollama, line):
    engines, first_run, settings = pages_of(tmp_path, clock, SUITABLE, vllm, ollama)
    for page in (first_run, settings):
        assert f"<th>{words.ROW_MODEL}</th>" in page and line in page


def test_ruling_36_the_decisions_are_read_at_start_and_never_at_a_view(tmp_path, clock):
    engines, first_run, settings = pages_of(tmp_path, clock, SUITABLE, ABSENT, OLLAMA)
    assert engines["vllm"].status_calls == 1 and engines["ollama"].status_calls == 1
    # On Windows with a suitable card vLLM is never asked (ruling 30), and the line names Ollama alone.
    engines, first_run, settings = pages_of(tmp_path / "w", clock, SUITABLE_WINDOWS, VLLM, OLLAMA)
    assert engines["vllm"].status_calls == 0 and engines["ollama"].status_calls == 1
    assert sentence("engine_running", engine="Ollama", version="9.9", model=words.MODEL_PRESENT) in settings
    assert "vLLM" not in settings


@pytest.mark.parametrize("machine", [SMALLER, MAC])
def test_15_7_on_any_other_machine_nothing_about_an_engine_is_shown_and_none_is_asked(tmp_path, clock, machine):
    engines, first_run, settings = pages_of(tmp_path, clock, machine, VLLM, OLLAMA)
    for page in (first_run, settings):
        assert f"<th>{words.ROW_MODEL}</th>" not in page
        assert words.MODEL_PRESENT not in page and "vLLM" not in page and "Ollama" not in page
        assert words.REASONS["engine_none"].split("{")[0] not in page
    assert engines["vllm"].status_calls == 0 and engines["ollama"].status_calls == 0
