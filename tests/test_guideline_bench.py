"""The guideline bench (spec 15.12, rulings 9, 10 and 19; R18): each query
once through the app's own search and 13 chains through its call, the
right passage by file and heading, the queries file's hash, the writer
that never writes over, the patient line from the command. A made-up
corpus, a made-up embedder, made-up replies."""

import hashlib
import json

import pytest

from openconsult.bench import guideline
from openconsult.bench.cli import main
from openconsult.bench.replay import CHAINS
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult.messages import Patient
from openconsult.guidelines.search import Index
from openconsult.llm.door import Door
from openconsult.llm.record import ModelCalls
from openconsult.settings import paths
from tests.fakes import FakeEngine, MadeUpEmbedder
from tests.test_guideline_search import axis, corpus

QUERIES = {"queries": [{"id": "Q01", "file": "A.html", "heading": "Heading A1", "query": "Made-up query one"},
                       {"id": "M01", "file": "", "heading": "", "query": "Made-up nothing"}]}
NUMBERED = {"id": "Q02", "file": "B.html", "heading": "Section B", "query": "Made-up query two"}


def queries_file(tmp_path):
    path = tmp_path / "queries.json"
    data = json.dumps(QUERIES).encode()
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def test_ruling_10_the_bench_runs_each_query_once_through_the_apps_search_and_13_chains_through_its_call(tmp_path, clock, monkeypatch):
    path, sha = queries_file(tmp_path)
    with pytest.raises(guideline.QueriesChanged):
        guideline.read_queries(path, "0" * 64)
    queries = guideline.read_queries(path, sha)
    assert [q["id"] for q in queries] == ["Q01", "M01"] and queries[1]["file"] is None
    db, sources = corpus(tmp_path / "data", clock)
    index = Index(sources)
    vectors = {"task: search result | query: Made-up query one": axis(1), "task: search result | query: Made-up nothing": axis(700)}
    embedder = MadeUpEmbedder(vector_for=lambda t: vectors[t])
    engine = FakeEngine({"guideline": [{"covered": True, "summary": f"made {i} [1].", "passages_cited": [1]} for i in range(14)]})
    door = Door(engine, ModelCalls(db, clock))
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "owner")
    writer = ResultWriter(tmp_path / "out", forbidden=[tmp_path / "data"])
    with pytest.raises(Refused):
        ResultWriter(tmp_path / "data" / "out", forbidden=[tmp_path / "data"])       # R18: never under the corpus's data folder
    patient = Patient(50, "F")
    first = guideline.first_call(door, guideline.run_search(index, embedder, queries[0], False), patient, queries[0]["query"])
    assert first.ok and first.answer["summary"] == "made 0 [1]."
    summary = guideline.run(door, index, embedder, queries, writer, patient, reranker=False, queries_sha256=sha, log=lambda line: None)
    assert summary == {"run": 2 + 2 * CHAINS.__len__(), "kept": 0}
    results = writer.read_all()
    searched = results[("Q01", "search")]
    right = [r["id"] for r in index.rows if r["file_name"] == "A.html" and r["trail"] == "Heading A1"]
    assert searched["right_passages"] == right and searched["rank_merged"] == 1 and searched["rank_sent"] == 1 and searched["real"]
    # A numbered section whose passages sit under its subsections: every passage whose trail passes through it is right.
    from openconsult.bench.guideline import under_heading, unnumbered
    assert unnumbered("1.3 Section B") == "section b" and unnumbered("1.3.2") == "" and unnumbered("Plain") == "plain"
    assert under_heading("Recommendations \u203a 1.3 Section B \u203a 1.3.2", "Section B") and under_heading("1.3 Section B", "section b")
    assert not under_heading("Recommendations \u203a 1.4 Section C \u203a 1.3.2", "Section B") and not under_heading("", "Section B")
    assert guideline.right_passages(index, NUMBERED) == []                         # the made corpus has no such heading
    assert searched["top_similarity"] == 1.0 and not searched["below_floor"] and len(searched["sent"]) == 6 and searched["search_ms"] >= 0
    assert searched["reranker"] is False and searched["queries_sha256"] == sha and searched["embedding_model"] == "made-up/embedder@0"
    assert searched["prompts"]["guideline"] == "7e07e0170f2f38ac06551fabd8cb67d66d9a0e21a2e4a507d82c20629975d94f" and searched["floor"] == 0.45
    chains = [results[("Q01", c.name)] for c in CHAINS]
    assert [c["chain"] for c in chains] == [c.name for c in CHAINS] and all(c["outcome"] == "covered" and c["cited"] == [1] for c in chains)
    assert chains[0]["words"] == 3 and chains[0]["summary"] == "made 1 [1]." and chains[0]["call"]["call_id"] and chains[0]["sent_count"] == 6
    assert chains[3]["temperature"] == 0.5 and chains[3]["seed"] == 1 and chains[0]["patient"] == {"age": 50, "sex": "F"}
    made = results[("M01", "search")]
    assert made["below_floor"] and made["real"] is False and made["right_passages"] == [] and made["rank_merged"] is None
    made_chains = [results[("M01", c.name)] for c in CHAINS]
    assert all(c["outcome"] == "below_floor" and c["no_call"] and c["call"] is None for c in made_chains)
    assert len(engine.calls_for("guideline")) == 14                                           # the first call and Q01's 13; none for M01
    assert all(call.user.startswith("The patient is a 50-year-old woman.\n\nQUERY: Made-up query one\n\nPASSAGES:\n[1] Title A: Heading A1\n")
               for call in engine.calls_for("guideline"))
    # Run again: every result kept, nothing written over, no call.
    again = guideline.run(door, index, embedder, queries, writer, patient, reranker=False, queries_sha256=sha, log=lambda line: None)
    assert again == {"run": 0, "kept": 2 + 2 * len(CHAINS)} and len(engine.calls_for("guideline")) == 14
    # Another arm in the same folder is refused by its stamp.
    assert guideline.arm_differs(searched, door, embedder, True, sha) is not None and guideline.arm_differs(searched, door, embedder, False, sha) is None
    # The searches alone: a timing pass writes the search and no chain.
    timing = ResultWriter(tmp_path / "timing", forbidden=[tmp_path / "data"])
    assert guideline.run(door, index, embedder, queries, timing, patient, reranker=True, search_only=True, log=lambda line: None) == {"run": 2, "kept": 0}
    assert set(timing.read_all()) == {("Q01", "search"), ("M01", "search")} and timing.read_all()[("Q01", "search")]["reranker_ran"]
    assert embedder.reranked and embedder.reranked[-1][0] == "Made-up nothing"
    db.close()
    # The command line refuses a wrong hash, and results under the data folder (R18).
    assert main(["guideline", "--queries", str(path), "--queries-sha256", "0" * 64, "--out", str(tmp_path / "x"),
                 "--data-folder", str(tmp_path / "data"), "--age", "50", "--sex", "F"]) == 3
    assert main(["guideline", "--queries", str(path), "--queries-sha256", sha, "--out", str(tmp_path / "data" / "x"),
                 "--data-folder", str(tmp_path / "data"), "--age", "50", "--sex", "F"]) == 6
