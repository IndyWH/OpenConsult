"""The engine chosen at start (spec 15.8, rulings 30, 37, 40; 10.4; R20):
vLLM first on Linux with a suitable card, then Ollama; the choice held
for the run; a failed call fails and says so with no switch. Two made-up
engines and a made-up card stand in; nothing here is what a model said."""

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.llm.choose import NO_ANSWER, NO_MODEL, SMALL_CONTEXT, NoEngine, choose
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineUnreachable
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.db import open_database
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from tests.conftest import PORT, browser
from tests.fakes import FakeEngine

LINUX = describe("Linux", "x86_64", [Card("Made-up card", 24564)])
WINDOWS = describe("Windows", "AMD64", [Card("Made-up card", 24564)])
MAC = describe("Darwin", "arm64", [])
SMALLER = describe("Linux", "x86_64", [Card("Made-up card", 8188)])
NONE = describe("Linux", "x86_64", [])


def engines(vllm=None, ollama=None):
    return {"vllm": vllm or FakeEngine(version="0.31-made-up", context=16384),
            "ollama": ollama or FakeEngine(version="9.9")}


def test_15_7_the_profile_names_the_model_for_each_engine_in_one_place():
    on_vllm = GEMMA_4_QAT.for_engine("vllm")
    assert (on_vllm.engine, on_vllm.tag) == ("vllm", GEMMA_4_QAT.tags["vllm"])
    assert on_vllm.tag != GEMMA_4_QAT.tag and on_vllm.context == GEMMA_4_QAT.context
    on_ollama = GEMMA_4_QAT.for_engine("ollama")
    assert (on_ollama.engine, on_ollama.tag) == ("ollama", GEMMA_4_QAT.tag)   # the default is Ollama's, the fallback everywhere
    assert (GEMMA_4_QAT.engine, GEMMA_4_QAT.think, GEMMA_4_QAT.sampling.temperature) == ("ollama", False, 0.0)
    with pytest.raises(KeyError):
        GEMMA_4_QAT.for_engine("made-up")


def test_ruling_37_vllm_is_asked_first_and_chosen_when_fit():
    both = engines()
    choice = choose(LINUX, both, GEMMA_4_QAT)
    assert choice.name == "vllm" and choice.passed_over == ()
    assert both["vllm"].status_calls == 1 and both["ollama"].status_calls == 0
    assert choice.chosen.status.context == 16384


def test_ruling_37_ollama_is_chosen_when_vllm_does_not_answer():
    both = engines(vllm=FakeEngine(version=None))
    choice = choose(LINUX, both, GEMMA_4_QAT)
    assert choice.name == "ollama"
    assert [(t.name, t.unfit) for t in choice.tried] == [("vllm", NO_ANSWER), ("ollama", None)]
    assert both["vllm"].status_calls == 1 and both["ollama"].status_calls == 1


@pytest.mark.parametrize("vllm, why", [
    (FakeEngine(version="0.31-made-up", present=False, context=16384), NO_MODEL),
    (FakeEngine(version="0.31-made-up", context=8192), SMALL_CONTEXT),
])
def test_ruling_37_a_vllm_that_is_not_fit_is_passed_over_with_its_reason(vllm, why):
    choice = choose(LINUX, engines(vllm=vllm), GEMMA_4_QAT)
    assert choice.name == "ollama" and choice.tried[0].unfit == why
    # The twin: a larger context is only more room, and vLLM is fit (the plan review of 3c).
    larger = choose(LINUX, engines(vllm=FakeEngine(version="0.31-made-up", context=32768)), GEMMA_4_QAT)
    assert larger.name == "vllm"


@pytest.mark.parametrize("machine, asked", [(WINDOWS, ["ollama"]), (MAC, []), (SMALLER, []), (NONE, [])])
def test_ruling_30_vllm_is_not_asked_on_windows_a_mac_or_without_a_suitable_card(machine, asked):
    both = engines()
    choice = choose(machine, both, GEMMA_4_QAT)
    assert [t.name for t in choice.tried] == asked
    assert both["vllm"].status_calls == 0
    assert choice.name == ("ollama" if asked else None)


def test_ruling_37_the_choice_is_made_once_and_held_for_the_run(tmp_path, clock):
    both = engines()
    app = build_app(store.build(tmp_path, PORT), machine=LINUX, clock=clock, engines=both)
    parts = app.state.parts
    assert parts.engine is both["vllm"] and parts.door.profile.tag == GEMMA_4_QAT.tags["vllm"]
    client = browser(app)
    client.get("/first-run")
    client.get("/first-run")
    parts.door.ask("alarm", "made-up words")
    assert both["vllm"].status_calls == 1 and both["ollama"].status_calls == 0   # never asked again
    assert parts.decisions.start_offered is True


def test_10_4_a_failed_call_fails_and_says_so_with_no_switch(tmp_path, clock):
    vllm = FakeEngine([EngineUnreachable("made-up: gone"), {"ok": True}], version="0.31-made-up", context=16384)
    both = engines(vllm=vllm)
    app = build_app(store.build(tmp_path, PORT), machine=LINUX, clock=clock, engines=both)
    door = app.state.parts.door
    gone = door.ask("alarm", "made-up words")
    assert not gone.ok and gone.failure == "unreachable" and "gone" in gone.detail
    assert both["ollama"].calls == []                       # nothing tried in its place
    rows = door._record.rows()
    assert len(rows) == 1 and rows[0]["engine"] == "made-up" and rows[0]["outcome"] == "unreachable"
    # The next call goes to the same engine; the next start would try vLLM first again.
    door.ask("alarm", "made-up words")
    assert len(vllm.calls) == 2 and both["ollama"].calls == []


def test_ruling_37_both_missing_every_call_fails_plainly_and_start_is_not_offered(tmp_path, clock):
    both = engines(vllm=FakeEngine(version=None), ollama=FakeEngine(version=None))
    app = build_app(store.build(tmp_path, PORT), machine=LINUX, clock=clock, engines=both)
    parts = app.state.parts
    assert isinstance(parts.engine, NoEngine) and parts.decisions.start_offered is False
    result = parts.door.ask("alarm", "made-up words")
    assert not result.ok and result.failure == "unreachable" and result.detail
    assert parts.door._record.rows()[0]["engine"] == "none"
    assert both["vllm"].calls == [] and both["ollama"].calls == []
    assert browser(app).get("/first-run").status_code == 200          # the app still answers


def test_R20_the_record_carries_the_engine_its_version_the_tag_and_the_digest_for_each_engine(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    for name, vllm in (("vllm", FakeEngine(version="0.31-made-up", digest="made-up-revision", context=16384)),
                       ("ollama", FakeEngine(version=None))):
        both = engines(vllm=vllm)
        choice = choose(LINUX, both, GEMMA_4_QAT)
        assert choice.name == name
        door = Door(both[name], ModelCalls(db, clock), GEMMA_4_QAT.for_engine(name))
        row = ModelCalls(db, clock).get(door.ask("alarm", "made-up words").call_id)
        assert (row["model_tag"], row["engine_version"]) == (GEMMA_4_QAT.tags[name], both[name].version())
        assert row["model_digest"] == both[name].model_digest(row["model_tag"])
    db.close()


def test_ruling_37_the_audit_log_holds_the_choice_with_its_reason(tmp_path, clock):
    both = engines(vllm=FakeEngine(version=None))
    app = build_app(store.build(tmp_path, PORT), machine=LINUX, clock=clock, engines=both)
    lines = [line for line in app.state.parts.audit.lines() if line.event == "decision.language_model"]
    assert len(lines) == 1
    detail = lines[0].detail
    assert words.UNFIT["no_answer"].format(engine="vLLM") in detail and "Ollama 9.9" in detail
    assert "engine ollama" in detail and "made-up-digest" in detail
    # Nothing was asked on a Mac, and the line says so plainly.
    mac = build_app(store.build(tmp_path / "mac", PORT), machine=MAC, clock=clock, engines=engines())
    detail = [line for line in mac.state.parts.audit.lines() if line.event == "decision.language_model"][0].detail
    assert words.NONE_ASKED in detail and "engine none" in detail
