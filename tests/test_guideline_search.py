"""The search in ordinary code (spec 15.12, ruling 6 and the detail The
passages and the search; 6.3; R3; ruling 25 of 15.9): cosine over every
passage, the nearest 12 a name, merged to 6 with at most 2 from one
source, the floor, the index's model. Made-up vectors in a made-up
corpus; nothing here is what a model gave."""

from openconsult.db import open_database
from openconsult.guidelines import search as search_module
from openconsult.guidelines.search import GUIDELINE_FLOOR, INDEX_MODEL_DIFFERS, Index, cut, merge, search, unit
from openconsult.guidelines.sources import VECTOR_SIZE, Passage, SourceRow, Sources
from openconsult.guidelines.texts import search_text
from openconsult.patients.audit import Audit
from tests.fakes import MadeUpEmbedder


def axis(k: int, weight: float = 1.0) -> list:
    """A vector along one axis of the 768."""
    found = [0.0] * VECTOR_SIZE
    found[k] = weight
    return found


def mix(*parts) -> list:
    found = [0.0] * VECTOR_SIZE
    for k, weight in parts:
        found[k] += weight
    return found


def corpus(tmp_path, clock, model="made-up/embedder@0"):
    """Three sources: A with passages on axes 0 to 4, B on 5 to 9, C on 10 to 14; passage i of a source on its axis."""
    db = open_database(tmp_path / "openconsult.db")
    sources = Sources(db, Audit(db, clock), clock)
    for name, first in (("A", 0), ("B", 5), ("C", 10)):
        passages = [Passage(i, f"Heading {name}{i}", f"text of {name} {i} " * 10, 40, axis(first + i)) for i in range(5)]
        sources.add_source(SourceRow(f"Title {name}", "Made-up publisher", f"{name}.html", "html", "h" * 64, 1, "command", model), passages)
    return db, sources


def test_6_3_the_search_is_cosine_over_every_passage_the_nearest_12_merged_to_6_with_at_most_2_from_one_source(tmp_path, clock):
    db, sources = corpus(tmp_path, clock)
    index = Index(sources)
    assert len(index.rows) == 15 and index.models == {"made-up/embedder@0"}
    # Name one leans on A's axes 0, 1, 2 and B's 5; name two on C's 10, 11, 12 and A's 2 again, less.
    vectors = {search_text("Made-up one"): mix((0, 0.9), (1, 0.8), (2, 0.7), (5, 0.6), (3, 0.5), (4, 0.4), (6, 0.3)),
               search_text("Made-up two"): mix((10, 0.9), (11, 0.8), (12, 0.7), (2, 0.5))}
    embedder = MadeUpEmbedder(vector_for=lambda t: vectors[t])
    found = search(index, embedder, ["Made-up one", "Made-up two"])
    assert found.failure is None and found.query == "Made-up one; Made-up two" and embedder.embedded == [[search_text("Made-up one"), search_text("Made-up two")]]
    # Merged by passage id at the higher similarity, sorted; the nearest 12 a name, so up to 24 candidates.
    assert [c.passage_id for c in found.candidates][:4] == [11, 12, 1, 2]        # C's axes 10 and 11, then A's 0 and 1, by cosine
    axis2 = next(c for c in found.candidates if c.passage_id == 3)           # A's passage on axis 2, found by both names
    assert axis2.similarity == unit(vectors[search_text("Made-up one")])[2].__round__(4) and 12 <= len(found.candidates) <= 24     # the two names' nearest 12, merged
    # The cut: at most 2 from one source, 6 in all, in order; numbered from 1; the top similarity reported.
    sent = found.sent
    assert [p["n"] for p in sent] == [1, 2, 3, 4, 5, 6]
    assert all(sum(1 for p in sent if p["source_id"] == s) <= 2 for s in {p["source_id"] for p in sent})
    assert {p["source_id"] for p in sent} == {1, 2, 3} and sent[0]["similarity"] == found.top_similarity
    assert sent[0]["title"] in ("Title A", "Title C") and sent[0]["trail"].startswith("Heading") and sent[0]["text"].startswith("text of")
    assert found.search_ms >= 0 and not found.below_floor and not found.reranker_ran and found.floor == GUIDELINE_FLOOR
    # merge and cut on their own.
    a = search_module.Hit(1, 1, "t", "p", "h", "x", 0.5)
    b = search_module.Hit(1, 1, "t", "p", "h", "x", 0.7)
    c = search_module.Hit(2, 1, "t", "p", "h", "x", 0.6)
    d = search_module.Hit(3, 1, "t", "p", "h", "x", 0.55)
    e = search_module.Hit(4, 2, "t", "p", "h", "x", 0.4)
    assert [h.passage_id for h in merge([[a, c], [b, d, e]])] == [1, 2, 3, 4]
    assert [h.passage_id for h in cut([b, c, d, e])] == [1, 2, 4]           # the third of source 1 skipped
    assert search_module.NEAREST_PER_NAME == 12 and search_module.PER_SOURCE == 2 and search_module.SENT == 6
    db.close()


def test_R3_the_floor_sends_nothing_and_the_constant_is_v1s(tmp_path, clock):
    db, sources = corpus(tmp_path, clock)
    index = Index(sources)
    assert GUIDELINE_FLOOR == 0.45
    low = MadeUpEmbedder(vector_for=lambda t: mix((0, 0.44), (700, 1.0)))     # cosine with axis 0 is 0.44 / |v|: under the floor
    found = search(index, low, ["Made-up far"])
    assert found.below_floor and found.sent == [] and found.top_similarity < GUIDELINE_FLOOR and found.candidates
    exact = MadeUpEmbedder(vector_for=lambda t: mix((0, 0.45), (700, (1 - 0.45 ** 2) ** 0.5)))
    found = search(index, exact, ["Made-up near"])
    assert not found.below_floor and found.top_similarity == 0.45 and len(found.sent) == 6
    # A worker failure is a failed search with its reason, nothing sent, no raise.
    failed = search(index, MadeUpEmbedder(fail="made-up: the worker died"), ["Made-up x"])
    assert failed.failure == "made-up: the worker died" and failed.sent == [] and failed.candidates == []
    # An empty corpus: nothing to merge, the floor refuses.
    for s in sources.loaded():
        sources.remove_source(s["id"])
    index.refresh()
    assert index.rows == [] and search(index, exact, ["Made-up near"]).below_floor
    db.close()


def test_ruling_25_an_index_records_its_model_and_is_never_searched_with_another(tmp_path, clock):
    db, sources = corpus(tmp_path, clock, model="made-up/embedder@0")
    index = Index(sources)
    other = MadeUpEmbedder(model_id="made-up/embedder@1", vector_for=lambda t: axis(0))
    found = search(index, other, ["Made-up a"])
    assert found.failure == INDEX_MODEL_DIFFERS and found.sent == [] and other.embedded == []     # nothing asked of the worker
    same = MadeUpEmbedder(model_id="made-up/embedder@0", vector_for=lambda t: axis(0))
    assert search(index, same, ["Made-up a"]).failure is None
    assert sources.loaded()[0]["model"] == "made-up/embedder@0" and sources.index_rows()[0]["model"] == "made-up/embedder@0"
    db.close()
