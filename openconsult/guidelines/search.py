"""The search, in ordinary code (spec 15.12, ruling 6 and the detail The
passages and the search; 6.3; ruling 25 of 15.9; R3): the names' vectors
from the worker, cosine against every loaded passage, the nearest 12 for
each name, merged, at most 2 from one source, 6 in all, as v1 did; a
floor under which nothing is sent; the reranker's reordering, when it is
wired and on, before the floor and the cut. The index is read once into
memory and again after a change; the rows stay the record. An index built
with another model is never searched."""

from __future__ import annotations

import operator
import time
from array import array
from dataclasses import dataclass, field

from openconsult.guidelines.embedder import Embedder
from openconsult.guidelines.sources import Sources
from openconsult.guidelines.texts import search_text

# v1 app/rag.py: MIN_SIMILARITY 0.45, calibrated in v1's evaluation of 7 Jul
# 2026; set again by the owner's ruling after the bench of 8b.
GUIDELINE_FLOOR = 0.45
# v1 app/rag.py, answer_for_conditions: 12 nearest a condition, 2 a source, 6 in all.
NEAREST_PER_NAME = 12
PER_SOURCE = 2
SENT = 6
NAMES_JOINT = "; "
INDEX_MODEL_DIFFERS = "index_model_differs"


def query_of(names: list[str]) -> str:
    return NAMES_JOINT.join(names)


def dot(a: array, b: array) -> float:
    return sum(map(operator.mul, a, b))


def unit(vector: list) -> array:
    found = array("f", [float(x) for x in vector])
    length = dot(found, found) ** 0.5 or 1.0
    return array("f", [x / length for x in found])


@dataclass(frozen=True)
class Hit:
    passage_id: int
    source_id: int
    title: str
    publisher: str
    trail: str
    text: str
    similarity: float
    rerank_score: float | None = None

    def as_sent(self, n: int) -> dict:
        return {"n": n, "passage_id": self.passage_id, "source_id": self.source_id, "title": self.title,
                "publisher": self.publisher, "trail": self.trail, "text": self.text, "similarity": self.similarity,
                "rerank_score": self.rerank_score, "cited": False}


@dataclass
class Search:
    """One search's result: what was merged, what is sent, and why not."""
    names: list
    query: str
    candidates: list = field(default_factory=list)   # the merged set in its final order
    sent: list = field(default_factory=list)         # after the floor and the cut, as dicts with n
    top_similarity: float | None = None
    below_floor: bool = False
    reranker_ran: bool = False
    rerank_failure: str | None = None
    failure: str | None = None                       # the worker's, or INDEX_MODEL_DIFFERS
    search_ms: int = 0
    floor: float = GUIDELINE_FLOOR


class Index:
    """Every loaded passage's vector in memory, refreshed after an add or a remove."""

    def __init__(self, sources: Sources):
        self._sources = sources
        self.rows: list[dict] = []
        self.refresh()

    def refresh(self) -> None:
        self.rows = self._sources.index_rows()

    @property
    def models(self) -> set:
        return {row["model"] for row in self.rows}

    def nearest(self, vector: array, k: int = NEAREST_PER_NAME) -> list[Hit]:
        scored = sorted(((dot(vector, row["vector"]), row) for row in self.rows), key=lambda s: -s[0])
        return [Hit(r["id"], r["source_id"], r["title"], r["publisher"], r["trail"], r["text"], round(float(s), 4))
                for s, r in scored[:k]]


def merge(per_name: list[list[Hit]]) -> list[Hit]:
    """By passage id, the higher similarity kept; sorted by similarity."""
    best: dict[int, Hit] = {}
    for hits in per_name:
        for hit in hits:
            if hit.passage_id not in best or hit.similarity > best[hit.passage_id].similarity:
                best[hit.passage_id] = hit
    return sorted(best.values(), key=lambda h: -h.similarity)


def cut(hits: list[Hit], per_source: int = PER_SOURCE, sent: int = SENT) -> list[Hit]:
    """In the order given: at most per_source from one source, sent in all."""
    counts: dict[int, int] = {}
    found = []
    for hit in hits:
        if counts.get(hit.source_id, 0) >= per_source:
            continue
        counts[hit.source_id] = counts.get(hit.source_id, 0) + 1
        found.append(hit)
        if len(found) >= sent:
            break
    return found


def rerank_text(hit: Hit) -> str:
    """What the reranker reads of a passage: its trail, a line break, its text."""
    return f"{hit.trail}\n{hit.text}" if hit.trail else hit.text


def _reranked(embedder: Embedder, query: str, merged: list[Hit], search: Search) -> list[Hit]:
    scores = embedder.rerank(query, [rerank_text(h) for h in merged])
    if not scores.ok or len(scores.scores) != len(merged):
        search.rerank_failure = scores.error or f"{len(scores.scores)} scores came back for {len(merged)} passages"
        return merged
    search.reranker_ran = True
    scored = [Hit(h.passage_id, h.source_id, h.title, h.publisher, h.trail, h.text, h.similarity, round(float(s), 4))
              for h, s in zip(merged, scores.scores)]
    return sorted(scored, key=lambda h: -h.rerank_score)


def search(index: Index, embedder: Embedder, names: list[str], reranker: bool = False,
           floor: float = GUIDELINE_FLOOR, clock=time.perf_counter) -> Search:
    """One search for the one or two names: nothing is sent when the index
    was built with another model, the worker failed, or the highest
    similarity is under the floor."""
    started = clock()
    found = Search(list(names), query_of(names), floor=floor)
    others = index.models - {embedder.model_id}
    if others:
        found.failure = INDEX_MODEL_DIFFERS
        found.search_ms = round(1000 * (clock() - started))
        return found
    vectors = embedder.embed([search_text(name) for name in names])
    if not vectors.ok or len(vectors.vectors) != len(names):
        found.failure = vectors.error or f"{len(vectors.vectors)} vectors came back for {len(names)} names"
        found.search_ms = round(1000 * (clock() - started))
        return found
    merged = merge([index.nearest(unit(v)) for v in vectors.vectors])
    if reranker and merged:
        merged = _reranked(embedder, found.query, merged, found)
    found.candidates = merged
    found.top_similarity = max((h.similarity for h in merged), default=None)
    if found.top_similarity is None or found.top_similarity < floor:
        found.below_floor = True
    else:
        found.sent = [h.as_sent(i + 1) for i, h in enumerate(cut(merged))]
    found.search_ms = round(1000 * (clock() - started))
    return found
