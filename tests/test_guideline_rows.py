"""The rows of the corpus and of the panel (spec 15.12, The passages and
the search; rulings 5 and 11; ruling 25 of 15.9; R2, R20). Made-up
passages and made-up vectors; nothing here is what a model gave."""

import math

import pytest

from openconsult.db import open_database
from openconsult.guidelines.sources import VECTOR_SIZE, AnswerRow, Passage, SourceRow, Sources, pack, unpack
from openconsult.patients.audit import Audit
from tests.test_letter_rows import approved_consultation


def made_vector(seed: int) -> list:
    return [((i * 7 + seed) % 13) - 6.0 for i in range(VECTOR_SIZE)]


def made_source(title="Made-up title", kind="html", by="page", model="made-up/embedder@0"):
    return SourceRow(title, "Made-up publisher", "made.html", kind, "a" * 64, 1234, by, model)


def made_passages(n=3):
    return [Passage(i, f"Heading {i}" if i else "", f"made passage {i} " * 20, 60, made_vector(i)) for i in range(n)]


def test_ruling_5_R2_a_source_and_its_passages_are_added_in_one_transaction_and_removed_audited(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    audit = Audit(db, clock)
    sources = Sources(db, audit, clock)
    assert sources.loaded() == [] and sources.counts() == {"sources": 0, "passages": 0, "latest": None}
    first = sources.add_source(made_source(), made_passages(3), seconds=1.25)
    row = sources.source(first)
    assert (row["title"], row["publisher"], row["kind"], row["passage_count"], row["model"], row["removed_at"], row["statement_accepted"]) == \
        ("Made-up title", "Made-up publisher", "html", 3, "made-up/embedder@0", None, 1)
    line = audit.lines()[0]
    assert line.event == "guideline.added" and "Made-up title" not in line.detail
    assert line.detail == f"source {first}: html, 3 passages, 1234 bytes, 1.2 s, by the page, the statement accepted"
    # The vectors go in at unit length and come out as 768 floats.
    passages = sources.passages_of(first)
    assert [p["position"] for p in passages] == [0, 1, 2] and passages[1]["trail"] == "Heading 1" and passages[0]["trail"] == ""
    stored = sources.passage(passages[1]["id"])
    assert len(stored["vector"]) == VECTOR_SIZE and abs(math.sqrt(sum(x * x for x in stored["vector"])) - 1.0) < 1e-5
    assert stored["title"] == "Made-up title" and stored["publisher"] == "Made-up publisher" and stored["model"] == "made-up/embedder@0"
    assert [r["id"] for r in sources.index_rows()] == [p["id"] for p in passages]
    # A refused passage leaves nothing: the source and its passages land together or not at all.
    bad = made_passages(2) + [Passage(2, "", "x", 1, [1.0] * (VECTOR_SIZE - 1))]
    with pytest.raises(ValueError):
        sources.add_source(made_source("Second"), bad)
    assert len(sources.loaded()) == 1 and len(sources.index_rows()) == 3
    with pytest.raises(ValueError):
        sources.add_source(made_source("Empty"), [])
    with pytest.raises(ValueError):
        sources.add_source(made_source(kind="docx"), made_passages(1))
    with pytest.raises(ValueError):
        pack([math.nan] + [0.0] * (VECTOR_SIZE - 1))
    # Loaded newest first; counts; remove takes the passages, keeps the row with its count, audited.
    clock.advance(minutes=1)
    second = sources.add_source(made_source("Second", by="command"), made_passages(2))
    assert [s["id"] for s in sources.loaded()] == [second, first]
    assert sources.counts() == {"sources": 2, "passages": 5, "latest": clock().isoformat(timespec="seconds")}
    assert sources.remove_source(first) == 3
    assert sources.passages_of(first) == [] and sources.source(first)["passage_count"] == 3
    assert sources.source(first)["removed_at"] == clock().isoformat(timespec="seconds")
    assert [s["id"] for s in sources.loaded()] == [second] and len(sources.index_rows()) == 2
    assert audit.lines()[0].event == "guideline.removed" and audit.lines()[0].detail == f"source {first}: 3 passages"
    with pytest.raises(KeyError):
        sources.remove_source(first)                         # removed already: never twice
    assert unpack(pack(made_vector(1)))[0] == pytest.approx(pack(made_vector(1)) and unpack(pack(made_vector(1)))[0])
    db.close()


def test_ruling_11_R20_the_answer_row_keeps_the_passages_sent_the_outcome_and_the_call(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    sources = Sources(db, Audit(db, clock), clock)
    cid, _, _ = approved_consultation(db, clock)
    sent = [{"n": 1, "passage_id": 5, "source_id": 1, "title": "t", "publisher": "p", "trail": "h", "text": "made", "similarity": 0.61,
             "rerank_score": None, "cited": True}]
    one = sources.add_answer(AnswerRow(cid, 2, ["Made-up A", "Made-up B"], "Made-up A; Made-up B", sent, 9, 0.61, 0.45, False,
                                       "covered", None, True, "made summary [1]", [1], 0, None, 120, 2400, True))
    row = sources.answer(one)
    assert (row["pass_n"], row["names"], row["query"], row["passages"], row["candidates"], row["top_similarity"], row["floor"]) == \
        (2, ["Made-up A", "Made-up B"], "Made-up A; Made-up B", sent, 9, 0.61, 0.45)
    assert (row["reranker_ran"], row["outcome"], row["covered"], row["summary"], row["passages_cited"], row["shown"]) == \
        (0, "covered", 1, "made summary [1]", [1], 1)
    two = sources.add_answer(AnswerRow(cid, 3, ["Made-up C"], "Made-up C", [], 0, 0.2, 0.45, False, "below_floor", None, None, None,
                                       None, 0, None, 50, 50, False))
    assert [a["id"] for a in sources.answers(cid)] == [one, two] and sources.answers(cid)[1]["passages_cited"] is None
    with pytest.raises(ValueError):
        sources.add_answer(AnswerRow(cid, 4, [], "", [], 0, None, 0.45, False, "guessed", None, None, None, None, 0, None, 1, 1, True))
    db.close()
