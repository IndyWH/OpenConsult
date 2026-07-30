"""The retrieval-composition harness's selectors, on synthetic hits.

REPORT-ONLY harness (docket item 12): the strategies live in the harness
and nothing ships — these tests pin the selector semantics so the
comparison the owner reads means what it says, and pin that production
retrieval is untouched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "evaluate_retrieval_composition.py"


def _load():
    spec = importlib.util.spec_from_file_location("evaluate_composition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load()


def hit(source, sim, text):
    return {"source": source, "similarity": sim, "text": text}


# The 450 shape: one big source's vocabulary dominating the ranking, the
# specific topic crowded below it.
ANAEMIA = {"Anaemia": [
    hit("NG203 CKD", 0.80, "a1"), hit("NG203 CKD", 0.79, "a2"),
    hit("NG203 CKD", 0.78, "a3"), hit("NG203 CKD", 0.77, "a4"),
    hit("CKS iron", 0.76, "b1"), hit("CKS iron", 0.75, "b2"),
    hit("NG8 anaemia mgmt", 0.74, "c1")]}


def test_production_mirror_caps_symmetrically():
    """The baseline reproduces the finding: the cap of 2 holds the wrong
    guideline to two slots — and the right one to two slots as well."""
    selected = harness.select_production(ANAEMIA)
    assert harness.composition(selected) == [
        ("NG203 CKD", 2), ("CKS iron", 2), ("NG8 anaemia mgmt", 1)]


def test_citation_diversity_widens_the_cited_source_set():
    selected = harness.select_citation_diversity(ANAEMIA)
    assert {h["source"] for h in selected} == {
        "NG203 CKD", "CKS iron", "NG8 anaemia mgmt"}
    # Breadth first, then depth by similarity — six slots still filled.
    assert len(selected) == 6


def test_slot_budget_protects_a_weak_condition_from_a_strong_ones_vocabulary():
    per = {"Strong": [hit("S", 0.9, f"s{i}") for i in range(8)],
           "Weak": [hit("W", 0.55, "w1"), hit("W", 0.54, "w2"),
                    hit("W2", 0.53, "w3")]}
    production = harness.select_production(per)
    assert sum(1 for h in production if h["source"].startswith("W")) <= 4
    budget = harness.select_slot_budget(per)
    weak = [h for h in budget if h["source"].startswith("W")]
    assert len(weak) == 3, "the weak condition's budget is its own"
    assert len(budget) == harness.SLOTS


def test_specific_naming_changes_the_query_not_the_selection():
    assert harness.STRATEGIES["specific_naming"] is harness.select_production
    assert harness.SPECIFIC_NAMES == {"Anaemia": "Iron deficiency anaemia"}


def test_every_strategy_dedups_and_never_exceeds_the_slots():
    duplicated = {"A": [hit("S1", 0.9, "same text " * 20)],
                  "B": [hit("S1", 0.8, "same text " * 20),
                        hit("S2", 0.7, "other")]}
    for name, select in harness.STRATEGIES.items():
        selected = select(duplicated)
        assert len(selected) <= harness.SLOTS
        texts = [h["text"][:120] for h in selected]
        assert len(texts) == len(set(texts)), f"{name} kept a duplicate"


def test_production_retrieval_is_untouched():
    """The strategies exist in the harness ONLY. app/rag.py keeps its
    shipped selection — same cap, same slots, no strategy hook."""
    rag_src = (REPO / "app" / "rag.py").read_text()
    assert "strategy" not in rag_src.lower()
    assert "select_production" not in rag_src
    for token in ("slot_budget", "citation_diversity", "specific_naming"):
        assert token not in rag_src
