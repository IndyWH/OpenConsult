"""The room check at start (spec 15.8, rulings 32, 33, 36 and 38; the
details of 3c): the two sums at the free memory 5d measured, at less,
and with no language model on the card; the app's own engines told
apart from other programs; each element's state, reason and figures. A
made-up card stands in; every program here is made up."""

import subprocess
from types import SimpleNamespace

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import room
from openconsult.settings.decisions import CONVERTER, GUIDELINE_SEARCH, LANGUAGE_MODEL, WHISPERX_CHOICE
from openconsult.settings.machine import Card, describe
from openconsult.settings.room import Program, check, others_mib, parse_programs, read_programs
from openconsult.settings import store
from tests.conftest import PORT
from tests.fakes import FakeEngine

# This card (24,564 MiB), and what the desktop held at 5d's start (829 MiB).
CARD = describe("Linux", "x86_64", [Card("Made-up card", 24564)])
NO_CARD = describe("Linux", "x86_64", [])
UNREADABLE = describe("Linux", "x86_64", None)
MAC = describe("Darwin", "arm64", [])
SMALL = describe("Windows", "AMD64", [Card("Made-up card", 12288)])
DESKTOP = [Program(1, "/usr/lib/made-up-desktop --type=gpu-process", 829)]


def test_ruling_32_embeddinggemma_2_lands_on_the_card_at_5ds_free_memory():
    found = check(CARD, "vllm", DESKTOP)
    guideline = found[GUIDELINE_SEARCH]
    assert guideline.green and guideline.reason == "guideline_card"
    assert guideline.figures["sum"] == 829 + 18316 + 3384 + 1010 + 1000 == 24539
    assert guideline.figures["spare"] == 24564 - 24539 and guideline.figures["free"] == 24564 - 829
    assert guideline.sentence == words.REASONS["guideline_card"]
    on_ollama = check(CARD, "ollama", DESKTOP)[GUIDELINE_SEARCH]
    assert on_ollama.green and on_ollama.figures["sum"] == 829 + 16568 + 3384 + 1010 + 1000


def test_ruling_32_with_less_room_it_lands_on_the_processor():
    crowded = DESKTOP + [Program(2, "/usr/lib/made-up-game", 1500)]
    guideline = check(CARD, "vllm", crowded)[GUIDELINE_SEARCH]
    assert not guideline.green and guideline.reason == "guideline_processor"
    assert guideline.figures["other programs"] == 2329 and guideline.figures["spare"] < 0
    assert guideline.sentence == words.REASONS["guideline_processor"]
    # The twin on Ollama, which needs less: still on the card.
    assert check(CARD, "ollama", crowded)[GUIDELINE_SEARCH].green


@pytest.mark.parametrize("engine", ["vllm", "ollama"])
def test_ruling_33_the_whisperx_choice_is_offered_only_when_its_pass_at_stop_fits(engine):
    choice = check(CARD, engine, DESKTOP)[WHISPERX_CHOICE]
    assert not choice.green and choice.reason == "whisperx_no_room"
    assert choice.figures["sum"] == 829 + room.LANGUAGE_MODEL_MIB[engine] + 1010 + 9464 + 1000
    assert choice.figures["WhisperX live"] == 2452 and choice.sentence == words.REASONS["whisperx_no_room"]
    # With no language model on the card (the cloud, or no local engine) the choice fits.
    cloud = check(CARD, None, DESKTOP)[WHISPERX_CHOICE]
    assert cloud.green and cloud.reason == "whisperx_available" and cloud.figures["sum"] == 829 + 1010 + 9464 + 1000


def test_ruling_33_where_embeddinggemma_sits_enters_the_second_sum():
    # A made-up card just large enough: with no language model the first sum puts the embedding on the
    # card (1010 + 3384 + 1000 = 5394 fits in 12288), and the second sum then counts it.
    on_card = check(SMALL, None, [])
    assert on_card[GUIDELINE_SEARCH].green
    assert on_card[WHISPERX_CHOICE].figures["EmbeddingGemma 2 on the card"] == 1010
    assert on_card[WHISPERX_CHOICE].green and on_card[WHISPERX_CHOICE].figures["sum"] == 1010 + 9464 + 1000
    # Fill the card so the first sum fails: the embedding goes to the processor and leaves the second sum.
    crowded = [Program(3, "/usr/lib/made-up-game", 12288 - 5394 + 1)]
    off_card = check(SMALL, None, crowded)
    assert not off_card[GUIDELINE_SEARCH].green
    assert off_card[WHISPERX_CHOICE].figures["EmbeddingGemma 2 on the card"] == 0
    assert off_card[WHISPERX_CHOICE].figures["sum"] == crowded[0].mib + 9464 + 1000


def test_ruling_36_the_engines_own_process_is_not_counted_as_another_program():
    programs = DESKTOP + [Program(2, "VLLM::EngineCore", 18212), Program(3, "/usr/lib/ollama/llama-server", 16526),
                          Program(4, r"C:\Users\made-up\AppData\Local\Programs\Ollama\lib\ollama\llama-server.exe", 16526)]
    assert others_mib(programs) == 829
    assert others_mib(None) == 0 and others_mib([]) == 0
    # The twin: a program that is not the app's own counts.
    assert others_mib([Program(5, "/opt/made-up/llama-server", 500)]) == 500


@pytest.mark.parametrize("machine", [NO_CARD, UNREADABLE, MAC])
def test_ruling_36_a_machine_with_no_card_or_one_that_cannot_be_read_still_decides(machine):
    found = check(machine, None, None)
    assert found[GUIDELINE_SEARCH].reason == "guideline_no_card" and not found[GUIDELINE_SEARCH].green
    assert found[WHISPERX_CHOICE].reason == "whisperx_no_card" and not found[WHISPERX_CHOICE].green
    assert found[GUIDELINE_SEARCH].figures["card total"] == 0


def test_ruling_36_the_programs_on_the_card_are_read_once_with_the_drivers_tool(tmp_path, clock):
    def two_programs(command, **kwargs):
        assert "nvidia-smi" in command[0] and "--query-compute-apps=pid,process_name,used_memory" in command
        return SimpleNamespace(returncode=0, stdout="5467, /usr/lib/made-up-desktop --type=gpu-process, 40\n"
                                                    "1050, /usr/lib/made-up-browser --type=gpu-process, 221\n"
                                                    "[No data]\n")

    found = read_programs(which=lambda name: "/usr/bin/" + name, run=two_programs)
    assert found == [Program(5467, "/usr/lib/made-up-desktop --type=gpu-process", 40),
                     Program(1050, "/usr/lib/made-up-browser --type=gpu-process", 221)]
    assert parse_programs("") == [] and parse_programs("No running processes found\n") == []
    # A tool that is absent, fails, hangs or answers oddly: nothing is counted, and the check still decides.
    def hangs(*a, **k):
        raise subprocess.TimeoutExpired(a[0], 1)

    def fails(*a, **k):
        return SimpleNamespace(returncode=1, stdout="")

    assert read_programs(which=lambda name: None, run=two_programs) is None
    for run in (hangs, fails):
        assert read_programs(which=lambda name: "/usr/bin/" + name, run=run) is None
    assert check(CARD, "vllm", None)[GUIDELINE_SEARCH].figures["other programs"] == 0
    # In the app it is read once at start, on a machine with a card only, and never at a page view.
    reads = []
    app = build_app(store.build(tmp_path, PORT), machine=CARD, clock=clock,
                    engines={"vllm": FakeEngine(version="0.31-made-up", context=16384), "ollama": FakeEngine()},
                    card_programs=lambda: reads.append(1) or DESKTOP)
    assert reads == [1] and app.state.parts.decisions.guideline_search.green
    mac = build_app(store.build(tmp_path / "mac", PORT), machine=MAC, clock=clock, card_programs=lambda: reads.append(2))
    assert reads == [1] and not mac.state.parts.decisions.whisperx_choice.green


def test_ruling_38_each_element_has_a_name_a_state_a_reason_and_its_figures(tmp_path, clock):
    app = build_app(store.build(tmp_path, PORT), machine=CARD, clock=clock,
                    engines={"vllm": FakeEngine(version="0.31-made-up", context=16384), "ollama": FakeEngine()},
                    card_programs=lambda: DESKTOP)
    decisions = app.state.parts.decisions
    assert sorted(decisions.elements) == sorted([LANGUAGE_MODEL, GUIDELINE_SEARCH, WHISPERX_CHOICE, CONVERTER])   # the converter joins in 7a
    for element in decisions.elements.values():
        assert element.name in decisions.elements and isinstance(element.green, bool)
        assert element.reason in words.REASONS and element.sentence and element.figures
        # No figure in MiB on the page: the sentence names neither the card's total nor a sum.
        assert "MiB" not in element.sentence and "24564" not in element.sentence
        assert str(element.figures.get("sum", "no sum")) not in element.sentence
    assert (decisions.language_model.green, decisions.guideline_search.green, decisions.whisperx_choice.green) == (True, True, False)
    assert decisions.start_offered
    # One audit line for each, with the figures.
    lines = {line.event: line.detail for line in app.state.parts.audit.lines() if line.event.startswith("decision.")}
    assert sorted(lines) == ["decision.converter", "decision.guideline_search", "decision.language_model", "decision.whisperx_choice"]
    assert "sum 24539" in lines["decision.guideline_search"] and "free 23735" in lines["decision.guideline_search"]
    assert "WhisperX at Stop 9464" in lines["decision.whisperx_choice"]
    assert all(words.EVENTS[event] for event in lines)


def test_5_1_the_needs_are_the_figures_of_5d():
    # Each a measured source (STAGE5D_REPORT, 13 Oct 2026), so that a silent change to a need fails here.
    assert room.LANGUAGE_MODEL_MIB == {"vllm": 18316, "ollama": 16568, None: 0}
    assert (room.NEMOTRON_MIB, room.WHISPERX_LIVE_MIB, room.WHISPERX_STOP_MIB) == (3384, 2452, 9464)
    assert (room.EMBEDDING_2_MIB, room.MARGIN_MIB) == (1010, 1000)
    assert room.MARGIN_MIB < 1313
