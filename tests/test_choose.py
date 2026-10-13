"""The engine chosen at start (spec 15.8, rulings 30, 37, 40; 10.4; R20):
vLLM first on Linux with a suitable card, then Ollama; the choice held
for the run; a failed call fails and says so with no switch. Two made-up
engines and a made-up card stand in; nothing here is what a model said."""

import pytest

from openconsult.llm.profile import GEMMA_4_QAT


def test_15_7_the_profile_names_the_model_for_each_engine_in_one_place():
    on_vllm = GEMMA_4_QAT.for_engine("vllm")
    assert (on_vllm.engine, on_vllm.tag) == ("vllm", GEMMA_4_QAT.tags["vllm"])
    assert on_vllm.tag != GEMMA_4_QAT.tag and on_vllm.context == GEMMA_4_QAT.context
    on_ollama = GEMMA_4_QAT.for_engine("ollama")
    assert (on_ollama.engine, on_ollama.tag) == ("ollama", GEMMA_4_QAT.tag)   # the default is Ollama's, the fallback everywhere
    assert (GEMMA_4_QAT.engine, GEMMA_4_QAT.think, GEMMA_4_QAT.sampling.temperature) == ("ollama", False, 0.0)
    with pytest.raises(KeyError):
        GEMMA_4_QAT.for_engine("made-up")
