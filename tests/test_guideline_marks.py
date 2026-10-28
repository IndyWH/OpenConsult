"""The marks of the guideline bench judged by code from made results
(spec 15.12, rulings 9 and 10; STAGE8B_PLAN item 6). Nothing a model
said is asserted; made results only."""

import pytest

from openconsult.bench import guideline_marks as marks
from openconsult.bench.replay import CHAINS

QUERIES = {"Q01": True, "Q02": True, "Q03": True, "M01": False}


def chain(name, outcome="covered", invalid=0, words=80, call=True):
    return {"chain": name, "outcome": outcome, "covered": outcome == "covered", "summary": "x", "cited": [1] if outcome == "covered" else [],
            "invalid": invalid, "words": words if outcome == "covered" else 0, "failure": "too_slow: x" if outcome == "failed" else None,
            "call": {"call_id": 1, "wall_ms": 2000} if call else None, "no_call": not call}


def arm(ranks: dict, search_ms: dict, chains_of=None, reranker=False):
    """A result folder's dict: a search and 13 chains for each query."""
    found = {}
    for qid, real in QUERIES.items():
        below = not real
        found[(qid, "search")] = {"real": real, "below_floor": below, "top_similarity": 0.2 if below else 0.7, "sent": [] if below else [1] * 6,
                                  "candidates": 12, "rank_merged": ranks.get(qid), "rank_sent": ranks.get(qid), "right_count": 1 if real else 0,
                                  "search_ms": search_ms.get(qid, 300), "reranker_ran": reranker}
        for c in CHAINS:
            made = chains_of(qid, c.name) if chains_of else None
            found[(qid, c.name)] = made or (chain(c.name) if real else chain(c.name, "below_floor", call=False))
    return found


def test_ruling_10_the_marks_are_judged_by_code_from_made_results(tmp_path):
    without = arm({"Q01": 1, "Q02": 2, "Q03": 1}, {})
    scored = marks.score(without)
    assert scored["panel_held"] and scored["held"] and scored["reranker_held"] is None and scored["reranker_marks"] is None
    assert {m["mark"] for m in scored["marks"]} == {"G1", "G2", "G3"} and len(scored["marks"]) == 7      # G1 and G2 for three real, G3 for one made
    t = scored["tables"]["without"]["Q01"]
    assert (t["chains"], t["covered"], t["cites_only_given"], t["under_150"], t["call_s"], t["rank_merged"]) == (13, 13, 13, 13, 2.0, 1)
    assert scored["tables"]["without"]["M01"]["refused"] == 13 and scored["tables"]["without"]["M01"]["no_call"] == 13
    # G1 fails on one chain citing a number it was not given; G2 on a 150-word summary and holds on 149; G3 on a covered chain.
    def bad(qid, name):
        if qid == "Q01" and name == "B4":
            return chain(name, invalid=1)
        if qid == "Q02" and name == "A1":
            return chain(name, words=150)
        if qid == "Q03" and name == "A2":
            return chain(name, words=149)
        if qid == "M01" and name == "B1":
            return chain(name, "covered")
        if qid == "M01" and name == "B2":
            return chain(name, "no_citation")
        if qid == "M01" and name == "B3":
            return chain(name, "not_covered")
        return None
    missed = marks.score(arm({"Q01": 1}, {}, bad))
    by = {(m["mark"], m["query"]): m for m in missed["marks"]}
    assert not by[("G1", "Q01")]["held"] and by[("G1", "Q01")]["figure"] == "12 of 13"
    assert not by[("G2", "Q02")]["held"] and by[("G2", "Q03")]["held"] and by[("G2", "Q01")]["held"]
    assert not by[("G3", "M01")]["held"] and by[("G3", "M01")]["figure"] == "12 of 13" and not missed["panel_held"]
    # A failed call misses G1 and G2; a chain short of 13 misses.
    failed = marks.score(arm({}, {}, lambda q, n: chain(n, "failed") if (q, n) == ("Q01", "A3") else None))
    assert not {(m["mark"], m["query"]): m for m in failed["marks"]}[("G1", "Q01")]["held"]
    short = {k: v for k, v in without.items() if k != ("Q01", "B10")}
    assert not {(m["mark"], m["query"]): m for m in marks.score(short)["marks"]}[("G1", "Q01")]["held"]
    # The reranker: R1 counts the firsts; R2 catches a fall from first to fourth; R3 catches 1,000 ms.
    with_ = arm({"Q01": 1, "Q02": 1, "Q03": 1}, {"Q01": 999}, reranker=True)
    both = marks.score(without, with_)
    r = {m["mark"]: m for m in both["reranker_marks"]}
    assert r["R1"]["held"] and r["R1"]["figure"] == "3 with, 2 without, of 3" and r["R2"]["held"] and r["R3"]["held"]
    assert both["reranker_held"] and both["held"] and set(both["tables"]) == {"without", "with"}
    lost = marks.score(without, arm({"Q01": 4, "Q02": 1, "Q03": 1}, {}, reranker=True))
    assert not {m["mark"]: m for m in lost["reranker_marks"]}["R2"]["held"] and "Q01" in {m["mark"]: m for m in lost["reranker_marks"]}["R2"]["figure"]
    slow = marks.score(without, arm({"Q01": 1, "Q02": 1, "Q03": 1}, {"M01": 1000}, reranker=True))
    assert not {m["mark"]: m for m in slow["reranker_marks"]}["R3"]["held"] and not slow["reranker_held"] and slow["panel_held"]
    same = marks.score(without, arm({"Q01": 1, "Q02": 2, "Q03": 1}, {}, reranker=True))
    assert not {m["mark"]: m for m in same["reranker_marks"]}["R1"]["held"]                 # no more firsts: not held
    # G1 to G3 on the arm with it count for the reranker, not the panel.
    g_with_missed = marks.score(without, arm({"Q01": 1, "Q02": 1, "Q03": 1}, {}, bad, reranker=True))
    assert g_with_missed["panel_held"] and not g_with_missed["reranker_held"] and not g_with_missed["held"]
    # The table is the same bytes twice; the files are never written over; nothing to score is refused.
    text = marks.as_markdown(both)
    assert text == marks.as_markdown(both) and "Arm with:" in text and "- Mark R3," in text
    marks.write(tmp_path / "marks", both)
    with pytest.raises(marks.MarksRefused):
        marks.write(tmp_path / "marks", both)
    with pytest.raises(marks.MarksRefused):
        marks.score({})


def test_ruling_19_the_right_passages_are_matched_again_from_the_stored_candidates_and_the_corpus():
    # The first scoring of 28 Oct matched the trail's last heading alone; the rule as it stands matches any heading of the trail,
    # its section number left out, so a numbered section's subsections count. Nothing stored changes but the ranks.
    rows = [{"id": 1, "file_name": "A.html", "trail": "Recommendations \u203a 1.3 Section B \u203a 1.3.2"},
            {"id": 2, "file_name": "A.html", "trail": "Recommendations \u203a 1.4 Other"},
            {"id": 3, "file_name": "C.html", "trail": "1.3 Section B"}]
    queries = [{"id": "Q01", "file": "A.html", "heading": "Section B", "query": "x"}, {"id": "M01", "file": None, "heading": None, "query": "y"}]
    results = {("Q01", "search"): {"real": True, "right_passages": [], "right_count": 0, "rank_merged": None, "rank_sent": None,
                                   "candidate_ranks": [{"passage_id": 2}, {"passage_id": 1}, {"passage_id": 3}], "sent": [{"passage_id": 2}, {"passage_id": 1}]},
               ("Q01", "A1"): chain("A1"), ("M01", "search"): {"real": False, "candidate_ranks": [], "sent": []}, ("M01", "A1"): chain("A1", "below_floor", call=False)}
    again = marks.rematch(results, rows, queries)
    assert again[("Q01", "search")]["right_passages"] == [1] and again[("Q01", "search")]["rank_merged"] == 2 and again[("Q01", "search")]["rank_sent"] == 2
    assert again[("Q01", "search")]["rematched"] and again[("Q01", "A1")] == chain("A1") and again[("M01", "search")]["right_passages"] == []
    assert results[("Q01", "search")]["rank_merged"] is None                       # the stored record is not changed
