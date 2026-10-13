"""The four lines of ruling 23 as code judges them, the steadiness rule
(15.8 ruling 21), the third word, the way round kept apart and the
pointer of ruling 24 (spec 15.9, the details of 5d). Every result here
is made up by tests/made_up_run.py; nothing is what a model, an engine or
a speech worker said."""

import json

import pytest

from openconsult.bench.shared import judge
from tests import made_up_run as made

T0 = made.T0


def a_run(tmp_path, **base):
    run = tmp_path / "run"
    made.write_base(run, "base-before", **base)
    made.write_base(run, "base-after", **base)
    return run


def judged(run, name):
    found = judge.judge_run(run)
    return next(s for s in found["setups"] + found["wayrounds"] if s["name"] == name)


def test_ruling_23_a_setup_that_meets_every_line_works(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "ollama-one-nemotron-first-card")
    s = judged(run, "ollama-one-nemotron-first-card")
    assert s["word"] == "works" and s["works"] is True and s["first_missed"] is None
    assert all(s["lines"][n]["met"] is True for n in "1234")
    assert s["lines"]["3"]["typical_s"] == 4.0 and s["lines"]["3"]["base_s"] == 4.0
    assert s["measured"]["typical_pass_s"] == 4.0 and s["measured"]["alarm_answer_s"] == 1.2
    assert s["measured"]["stop_s"] == 0.5 and s["measured"]["after_stop_typical_s"] == 4.0
    assert s["measured"]["search_median_s"] == 0.3 and s["measured"]["words_differ_from_alone"] == 0


@pytest.mark.parametrize("name, kwargs, reason", [
    ("embedding-moved", {"watch_kwargs": {"odd": {120.0: {"emb_where": "processor"}}}},
     "the embedding model was processor at 120 s, not on the card"),
    ("language-gone", {"watch_kwargs": {"odd": {95.0: {"lm_where": "gone"}}}}, "the language model was unloaded at 95 s"),
    ("language-split", {"watch_kwargs": {"odd": {40.0: {"lm_where": "split"}}}},
     "the language model was split between the card and the processor at 40 s"),
    ("speech-oom-at-stop", {"speech_failure": {"at": "stop", "piece": None, "failure": "worker_error",
                                                "detail": "OutOfMemoryError: CUDA out of memory. Tried to allocate"}},
     "the speech worker ran out of memory at stop"),
    ("speech-oom-at-stop-ctranslate2", {"speech_failure": {"at": "stop", "piece": None, "failure": "worker_error",
                                                            "detail": "MemoryError: batch_size ( 32) is probably too large. Try with a smaller value"}},
     "the speech worker ran out of memory at stop"),
    ("speech-would-not-start", {"speech_failure": {"at": "open", "piece": None, "failure": "died",
                                                    "detail": "The speech worker stopped with exit code 1."}},
     "the speech worker would not start: The speech worker stopped with exit code 1."),
    ("speech-off-card", {"watch_kwargs": {"odd": {200.0: {"speech_on": False}}}}, "the speech worker was not on the card at 200 s"),
    ("embedding-oom", {"search_kwargs": {"fail_at": 3, "error": "made-up: CUDA out of memory"}},
     "the embedding model ran out of memory at search 3"),
])
def test_ruling_23_line_one_missed_with_its_reason(tmp_path, name, kwargs, reason):
    run = a_run(tmp_path)
    made.write_setup(run, name, **kwargs)
    s = judged(run, name)
    assert s["lines"]["1"]["met"] is False and reason in s["lines"]["1"]["reason"]
    assert s["word"] == "not working" and s["first_missed"] == 1


def test_ruling_23_line_one_on_vllm_and_the_private_ollama_and_version_2(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "vllm-one-nemotron-second-card", way="vllm-one", embedding="second")
    made.write_setup(run, "vllm-down", way="vllm-one", embedding="second", watch_kwargs={"odd": {50.0: {"vllm_up": False}}})
    made.write_setup(run, "ollama-together-nemotron-second-processor", way="ollama-together", embedding="second",
                     where="processor", search_kwargs={"device": "cpu"})
    made.write_setup(run, "second-wrong-device", way="ollama-together", embedding="second", where="processor",
                     search_kwargs={"device": "cuda"})
    made.write_setup(run, "second-left-card", embedding="second", where="card", watch_kwargs={"odd": {60.0: {"second_on_card": False}}})
    # The worker lives only while its searches run (made up: 15 s to 175.3 s); gone at 200 s is no miss. The run of
    # 13 Oct read four setups that work as not working before this was so.
    made.write_setup(run, "second-gone-after-its-searches", embedding="second", where="card",
                     watch_kwargs={"odd": {200.0: {"second_on_card": False}}})
    assert judged(run, "vllm-one-nemotron-second-card")["works"] is True
    assert "the language model was unloaded at 50 s" in judged(run, "vllm-down")["lines"]["1"]["reason"]
    assert judged(run, "ollama-together-nemotron-second-processor")["works"] is True
    assert "ran on cuda, not where the setup asked (processor)" in judged(run, "second-wrong-device")["lines"]["1"]["reason"]
    assert judged(run, "second-left-card")["lines"]["1"]["reason"] == "the worker of EmbeddingGemma 2 was not on the card at 60 s"
    assert judged(run, "second-gone-after-its-searches")["works"] is True


def test_ruling_23_line_two_met_and_missed(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "call-failed", chain_kwargs={"fail_at": ("A2", 7)})
    made.write_setup(run, "no-test", chain_kwargs={"test": False})
    made.write_setup(run, "no-ectopic", chain_kwargs={"ectopic": False})
    made.write_setup(run, "search-failed", search_kwargs={"fail_at": 12})
    made.write_setup(run, "after-stop-failed", after_kwargs={"fail_at": ("A1", 2)})
    made.write_setup(run, "chain-failed", chain_kwargs={"chain_failed": "the engine was unreachable 2 times in a row"})
    assert "a call failed: alarm at point 7 of chain A2 (too_slow)" in judged(run, "call-failed")["lines"]["2"]["reason"]
    assert "the hard mark H2 was missed in chain A1" in judged(run, "no-test")["lines"]["2"]["reason"]
    assert "the hard mark H1 was missed in chain A1" in judged(run, "no-ectopic")["lines"]["2"]["reason"]
    assert "search 12 failed for Made-up condition: made-up: refused" in judged(run, "search-failed")["lines"]["2"]["reason"]
    assert "a call failed: alarm at point 2 of chain A1" in judged(run, "after-stop-failed")["lines"]["2"]["reason"]
    assert "chain A1 failed: the engine was unreachable" in judged(run, "chain-failed")["lines"]["2"]["reason"]
    for name in ("call-failed", "no-test", "no-ectopic", "search-failed", "after-stop-failed", "chain-failed"):
        assert judged(run, name)["first_missed"] == 2 and judged(run, name)["lines"]["1"]["met"] is True


@pytest.mark.parametrize("wall_ms, met", [(4490, True), (4500, False)])
def test_ruling_23_line_three_on_the_line_and_just_under_it(tmp_path, wall_ms, met):
    run = a_run(tmp_path)
    made.write_setup(run, "s", wall_ms=wall_ms)
    s = judged(run, "s")
    assert s["lines"]["3"]["met"] is met and s["lines"]["3"]["base_s"] == 4.0
    if not met:
        assert s["lines"]["3"]["reason"] == "the typical pass was 4.50 s, 0.50 s longer than 4.00 s with the card to itself"
        assert s["word"] == "not working" and s["first_missed"] == 3


def test_15_8_ruling_21_the_steadiness_rule(tmp_path):
    run = tmp_path / "run"
    made.write_base(run, "base-before", lm_ms={"ollama-one": 4000, "vllm-one": 3000})
    made.write_base(run, "base-after", lm_ms={"ollama-one": 4250, "vllm-one": 3260})
    made.write_setup(run, "steady", way="ollama-one", wall_ms=4600)
    made.write_setup(run, "unsteady", way="vllm-one", wall_ms=3100)
    found = judge.judge_run(run)
    assert found["steadiness"]["ollama-one"]["judged"] and found["steadiness"]["ollama-one"]["mean"] == 4.125
    assert found["steadiness"]["vllm-one"]["judged"] is False
    assert found["steadiness"]["vllm-one"]["reason"] == "the two base lines of vllm-one differ by 0.26 s, more than 0.25 s: the day was not steady"
    assert judged(run, "steady")["lines"]["3"]["met"] is True
    unsteady = judged(run, "unsteady")
    assert unsteady["lines"]["3"]["met"] is None and unsteady["word"] == "not judged" and unsteady["not_judged"] == [3]
    assert found["counts"]["vllm"] == {"works": 0, "not working": 0, "not judged": 1}


def test_ruling_23_line_three_and_four_not_judged_for_a_missing_base_line(tmp_path):
    run = tmp_path / "run"
    made.write_base(run, "base-before", lm_missing=("ollama-together",), speech_missing=("whisperx",))
    made.write_base(run, "base-after")
    made.write_setup(run, "no-lm-base", way="ollama-together")
    made.write_setup(run, "no-speech-base", speech="whisperx")
    a, b = judged(run, "no-lm-base"), judged(run, "no-speech-base")
    assert a["lines"]["3"]["met"] is None and "the base line before is missing for ollama-together" in a["lines"]["3"]["reason"]
    assert b["lines"]["4"]["met"] is None and b["lines"]["4"]["reason"] == "the speech choice lacks one of its two base lines"
    assert a["word"] == b["word"] == "not judged" and a["not_judged"] == [3] and b["not_judged"] == [4]


def test_ruling_23_line_four_the_stretch_and_the_same_field_for_both_choices(tmp_path):
    run = a_run(tmp_path)
    # The chains run from 15 s to 15 + 33 * 4 = 147 s of the recording.
    made.write_setup(run, "keeps-up", lines=made.default_lines(wait=2.9))
    made.write_setup(run, "behind", speech="whisperx", lines=made.default_lines(wait=3.0))
    kept, behind = judged(run, "keeps-up"), judged(run, "behind")
    assert kept["lines"]["4"]["stretch_s"] == [15.0, 147.0]
    assert kept["lines"]["4"]["setup"]["lines"] == 44 and kept["lines"]["4"]["base"]["lines"] == 88    # 44 in each base line
    assert kept["lines"]["4"]["setup"]["typical_s"] == 2.9 and kept["lines"]["4"]["base"]["typical_s"] == 2.0
    assert kept["lines"]["4"]["met"] is True and kept["works"] is True
    assert behind["lines"]["4"]["met"] is False and behind["first_missed"] == 4
    assert behind["lines"]["4"]["reason"] == "the typical wait was 3.00 s, 1.00 s longer than 2.00 s alone"
    assert behind["lines"]["4"]["setup"]["first_half_lines"] == 22 and behind["lines"]["4"]["setup"]["second_half_lines"] == 22


def test_ruling_23_line_four_the_two_halves(tmp_path):
    run = a_run(tmp_path)
    # The base line's wait does not grow; a setup whose wait grows by 1.0 s across the stretch misses, by 0.9 keeps up.
    made.write_setup(run, "grows", lines=[(end, 2.0 + (0.0 if end < 81 else 1.0)) for end, _ in made.default_lines()])
    made.write_setup(run, "grows-little", lines=[(end, 2.0 + (0.0 if end < 81 else 0.9)) for end, _ in made.default_lines()])
    grows, little = judged(run, "grows"), judged(run, "grows-little")
    assert grows["lines"]["4"]["setup"]["growth_s"] == 1.0 and grows["lines"]["4"]["base"]["growth_s"] == 0.0
    assert grows["lines"]["4"]["met"] is False and "the wait grew by 1.00 s" in grows["lines"]["4"]["reason"]
    assert little["lines"]["4"]["met"] is True


def test_ruling_23_line_four_no_line_in_the_stretch_misses_it_when_the_base_line_has_some(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "silent", lines=[(200.0, 2.0), (250.0, 2.0)])      # lines only after the stretch
    s = judged(run, "silent")
    assert s["lines"]["4"]["met"] is False and s["lines"]["4"]["reason"] == "no line reached the page while the language model was busy"
    assert s["lines"]["4"]["setup"]["lines"] == 0 and s["lines"]["4"]["base"]["lines"] == 88
    quiet = tmp_path / "quiet"
    made.write_base(quiet, "base-before", speech_lines={"nemotron": [(200.0, 2.0)]})
    made.write_base(quiet, "base-after", speech_lines={"nemotron": [(200.0, 2.0)]})
    made.write_setup(quiet, "silent-too", lines=[(200.0, 2.0)])
    assert judged(quiet, "silent-too")["lines"]["4"]["met"] is None
    assert judged(quiet, "silent-too")["lines"]["4"]["reason"] == "the speech choice alone gave no line in the stretch"


def test_ruling_23_line_four_a_stop_with_no_transcript_for_another_reason_misses_it(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "stop-failed", speech_failure={"at": "stop", "piece": None, "failure": "worker_error",
                                                        "detail": "ValueError: made-up"})
    s = judged(run, "stop-failed")
    assert s["lines"]["1"]["met"] is True and s["lines"]["4"]["met"] is False
    assert s["lines"]["4"]["reason"] == "Stop gave no transcript: ValueError: made-up" and s["first_missed"] == 4


def test_ruling_23_the_three_words_and_the_first_line_missed(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "both", wall_ms=4600, chain_kwargs={"test": False})
    s = judged(run, "both")
    assert s["word"] == "not working" and s["first_missed"] == 2
    assert s["lines"]["3"]["met"] is False and s["lines"]["3"]["typical_s"] == 4.6      # still reported


def test_ruling_23_a_way_round_is_never_counted_as_a_setup(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "ollama-one-whisperx-first-card", speech="whisperx",
                     speech_failure={"at": "stop", "piece": None, "failure": "worker_error", "detail": "CUDA out of memory"})
    made.write_setup(run, "ollama-one-whisperx-first-processor", speech="whisperx", where="processor",
                     speech_failure={"at": "stop", "piece": None, "failure": "worker_error", "detail": "CUDA out of memory"})
    # The way round: the language model off the card from stop.wanted until it is back after Stop.
    off = {"wanted_epoch": T0 + 314.5, "back_epoch": T0 + 325.0}
    made.write_setup(run, "ollama-whisperx-first-processor", speech="whisperx", where="processor", kind="wayround",
                     setup_extra={"wayround": off}, watch_kwargs={"odd": {315.0: {"lm_where": "gone"}, 320.0: {"lm_where": "gone"}}},
                     pause={"wanted_epoch": T0 + 314.5, "waited_s": 3.0, "went_ahead": False})
    made.write_setup(run, "wayround-wrong", speech="whisperx", where="processor", kind="wayround",
                     setup_extra={"wayround": off}, watch_kwargs={"odd": {100.0: {"lm_where": "gone"}}})
    found = judge.judge_run(run)
    assert found["counts"]["ollama"] == {"works": 0, "not working": 2, "not judged": 0}
    assert [w["name"] for w in found["wayrounds"]] == ["ollama-whisperx-first-processor", "wayround-wrong"]
    assert all(w["kind"] == "way round" for w in found["wayrounds"])
    good = judged(run, "ollama-whisperx-first-processor")
    assert good["lines"]["1"]["met"] is True and good["measured"]["stop_pause"]["waited_s"] == 3.0
    assert "the language model was unloaded at 100 s" in judged(run, "wayround-wrong")["lines"]["1"]["reason"]
    assert found["pointers"] == {"ollama-one-whisperx-first-card": {"twin": "ollama-one-whisperx-first-processor", "word": "not working"}}


def test_ruling_24_the_pointer_from_a_card_setup_to_its_processor_twin(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "vllm-one-nemotron-first-card", way="vllm-one", chain_kwargs={"test": False})
    made.write_setup(run, "vllm-one-nemotron-first-processor", way="vllm-one", where="processor")
    made.write_setup(run, "vllm-one-nemotron-second-card", way="vllm-one", embedding="second", chain_kwargs={"test": False})
    found = judge.judge_run(run)
    assert found["pointers"] == {"vllm-one-nemotron-first-card": {"twin": "vllm-one-nemotron-first-processor", "word": "works"},
                                 "vllm-one-nemotron-second-card": None}
    assert found["counts"]["vllm"] == {"works": 1, "not working": 2, "not judged": 0}


def test_15_9_5d_the_cards_memory_at_each_step_in_mib_and_the_base_lines_summary(tmp_path):
    run = a_run(tmp_path)
    made.write_setup(run, "s")
    found = judge.judge_run(run, card=made.card_samples(T0))
    card = found["setups"][0]["measured"]["card"]
    assert card["load_language"]["used_mib_max"] == 18_000 and card["recording"]["samples"] > 100
    assert card["recording"]["programs_mib_max"][made.ENV["nemotron"]] == 4_000 and card["stop"]["samples"] == 0
    assert found["base_before"]["lm"]["ollama-one"] == 4.0 and found["base_before"]["index"]["first-card"]["seconds"] == 12.5
    assert found["base_before"]["speech"]["nemotron"]["lines"] == 103 and found["base_after"]["embed"]["second-processor"]["median_s"] == 0.3
    assert json.dumps(found)                                                                  # plain JSON throughout


def test_15_9_5d_words_that_differ_between_two_pages():
    a = [{"text": "No chest pain at rest"}, {"text": "I take metformin"}]
    b = [{"text": "No chest pain at rest"}, {"text": "I take met formin today"}]
    assert judge.words_that_differ(a, a) == 0 and judge.words_that_differ(a, b) == 3
    assert judge.says_memory("torch.OutOfMemoryError: CUDA out of memory") and not judge.says_memory("ValueError: x")


def test_ruling_23_a_stop_that_gave_nothing_ends_the_window_where_the_feed_ended_and_the_proof_runs_one_chain(tmp_path):
    """When Stop gave no transcript the worker is usually gone from the card
    just after; the window of line one ends where the sound ended, not at
    the last reading. And a setup that says it ran one chain is judged on
    that chain (the proof of item 9)."""
    run = a_run(tmp_path)
    made.write_setup(run, "died-at-stop", speech="whisperx", watch_kwargs={"odd": {320.0: {"speech_on": False}}},
                     speech_failure={"at": "stop", "piece": None, "failure": "worker_error", "detail": "MemoryError: batch_size"})
    s = judged(run, "died-at-stop")
    assert s["lines"]["1"]["reason"] == "the speech worker ran out of memory at stop"
    assert judge.fed_seconds({"stop": None, "loudness": {"window_s": 0.1, "dbfs": [None] * 567}}) == 56.7
    made.write_setup(run, "one-chain", chain_kwargs={"chains": ("A1",)}, setup_extra={"chains": ["A1"]})
    assert judged(run, "one-chain")["lines"]["2"]["met"] is True
    made.write_setup(run, "one-chain-of-three", chain_kwargs={"chains": ("A1",)})
    assert "chain A2 is missing" in judged(run, "one-chain-of-three")["lines"]["2"]["reason"]
