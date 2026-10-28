"""The rows of the corpus and of the panel (spec 15.12, The passages and
the search; rulings 5 and 11; ruling 25 of 15.9; R2, R20): a source and
its passages added in one transaction and removed in one, every add and
remove audited with counts and never a title; the vectors as bytes at
unit length; each guideline search of a live consultation kept with the
passages it sent, its outcome and its seconds. Nothing here talks to a
model or a worker."""

from __future__ import annotations

import json
import math
from array import array
from dataclasses import dataclass

from openconsult.db import Database
from openconsult.patients.audit import Audit, Clock, now_local

KINDS = ("html", "pdf", "text")
ADDED_BY = ("page", "command")
OUTCOMES = ("covered", "not_covered", "below_floor", "no_citation", "failed")
VECTOR_SIZE = 768                      # EmbeddingGemma 2 (15.9 ruling 25)


@dataclass(frozen=True)
class SourceRow:
    title: str
    publisher: str
    file_name: str
    kind: str
    sha256: str
    bytes: int
    added_by: str
    model: str                         # the embedding model and revision that built its passages


@dataclass(frozen=True)
class Passage:
    position: int
    trail: str                         # the heading trail; empty when the source has none
    text: str
    words: int
    vector: list                       # 768 numbers, made unit length when stored


@dataclass(frozen=True)
class AnswerRow:
    consultation_id: int
    pass_n: int
    names: list
    query: str
    passages: list                     # each: n, passage_id, source_id, title, publisher, trail, text, similarity, rerank_score, cited
    candidates: int
    top_similarity: float | None
    floor: float
    reranker_ran: bool
    outcome: str
    call_id: int | None
    covered: bool | None
    summary: str | None
    passages_cited: list | None
    invalid_cites: int
    failure: str | None
    search_ms: int
    wall_ms: int
    shown: bool


def pack(vector: list) -> bytes:
    """768 float32 little-endian at unit length; a vector of another size
    or with a value that is not a number is refused."""
    if len(vector) != VECTOR_SIZE:
        raise ValueError(f"a vector of {len(vector)} numbers, not {VECTOR_SIZE}")
    values = [float(x) for x in vector]
    if any(math.isnan(x) or math.isinf(x) for x in values):
        raise ValueError("a vector holds a value that is not a number")
    length = math.sqrt(sum(x * x for x in values)) or 1.0
    packed = array("f", [x / length for x in values])
    if packed.itemsize != 4:
        raise ValueError("float32 is not 4 bytes on this machine")
    return packed.tobytes()


def unpack(blob: bytes) -> array:
    found = array("f")
    found.frombytes(blob)
    return found


class Sources:
    def __init__(self, db: Database, audit: Audit, clock: Clock = now_local):
        self._db = db
        self._audit = audit
        self._clock = clock

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    # --------------------------------------------------------- the corpus

    def add_source(self, row: SourceRow, passages: list[Passage], seconds: float = 0.0) -> int:
        """The source and its passages together or not at all; then the
        audit line of counts."""
        if row.kind not in KINDS:
            raise ValueError(f"not a kind of document: {row.kind}")
        if row.added_by not in ADDED_BY:
            raise ValueError(f"not a way of adding: {row.added_by}")
        if not passages:
            raise ValueError("a source needs at least one passage")
        with self._db.transaction() as con:
            cursor = con.execute(
                "INSERT INTO guideline_source (title, publisher, file_name, kind, sha256, bytes, added_at, added_by, "
                "statement_accepted, passage_count, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (row.title, row.publisher, row.file_name, row.kind, row.sha256, row.bytes, self._now(), row.added_by,
                 len(passages), row.model))
            source_id = int(cursor.lastrowid)
            con.executemany(
                "INSERT INTO guideline_passage (source_id, position, trail, text, words, vector, model) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(source_id, p.position, p.trail, p.text, p.words, pack(p.vector), row.model) for p in passages])
        self._audit.record("guideline.added", f"source {source_id}: {row.kind}, {len(passages)} passages, {row.bytes} bytes, "
                                              f"{seconds:.1f} s, by the {row.added_by}, the statement accepted")
        return source_id

    def remove_source(self, source_id: int) -> int:
        """The passages deleted and the source marked removed, in one
        transaction; the row stays with its count. The passages removed."""
        found = self.source(source_id)
        if found is None or found["removed_at"] is not None:
            raise KeyError(f"no loaded source {source_id}")
        with self._db.transaction() as con:
            removed = con.execute("DELETE FROM guideline_passage WHERE source_id = ?", (source_id,)).rowcount
            con.execute("UPDATE guideline_source SET removed_at = ? WHERE id = ?", (self._now(), source_id))
        self._audit.record("guideline.removed", f"source {source_id}: {removed} passages")
        return removed

    def source(self, source_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM guideline_source WHERE id = ?", (source_id,))
        return dict(found) if found else None

    def loaded(self) -> list[dict]:
        """The sources that stand, newest first."""
        rows = self._db.query("SELECT * FROM guideline_source WHERE removed_at IS NULL ORDER BY id DESC")
        return [dict(r) for r in rows]

    def counts(self) -> dict:
        """Sources, passages and the latest date added, for the provenance line."""
        row = self._db.query_one("SELECT COUNT(*) AS sources, COALESCE(SUM(passage_count), 0) AS passages, MAX(added_at) AS latest "
                                 "FROM guideline_source WHERE removed_at IS NULL")
        return {"sources": int(row["sources"]), "passages": int(row["passages"]), "latest": row["latest"]}

    def passages_of(self, source_id: int) -> list[dict]:
        rows = self._db.query("SELECT id, source_id, position, trail, text, words, model FROM guideline_passage "
                              "WHERE source_id = ? ORDER BY position", (source_id,))
        return [dict(r) for r in rows]

    def passage(self, passage_id: int) -> dict | None:
        found = self._db.query_one("SELECT p.*, s.title, s.publisher FROM guideline_passage p JOIN guideline_source s "
                                   "ON s.id = p.source_id WHERE p.id = ?", (passage_id,))
        return {**dict(found), "vector": unpack(found["vector"])} if found else None

    def index_rows(self) -> list[dict]:
        """Every loaded passage with its vector, for the index in memory."""
        rows = self._db.query("SELECT p.id, p.source_id, p.trail, p.text, p.model, p.vector, s.title, s.publisher "
                              "FROM guideline_passage p JOIN guideline_source s ON s.id = p.source_id "
                              "WHERE s.removed_at IS NULL ORDER BY p.id")
        return [{**dict(r), "vector": unpack(r["vector"])} for r in rows]

    # ---------------------------------------------------------- the panel

    def add_answer(self, row: AnswerRow) -> int:
        if row.outcome not in OUTCOMES:
            raise ValueError(f"not an outcome: {row.outcome}")
        cursor = self._db.execute(
            "INSERT INTO guideline_answer (consultation_id, pass_n, at, names, query, passages, candidates, top_similarity, "
            "floor, reranker_ran, outcome, call_id, covered, summary, passages_cited, invalid_cites, failure, search_ms, "
            "wall_ms, shown) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row.consultation_id, row.pass_n, self._clock().isoformat(timespec="milliseconds"),
             json.dumps(list(row.names), ensure_ascii=False), row.query, json.dumps(list(row.passages), ensure_ascii=False),
             row.candidates, row.top_similarity, row.floor, int(bool(row.reranker_ran)), row.outcome, row.call_id,
             None if row.covered is None else int(bool(row.covered)), row.summary,
             json.dumps(list(row.passages_cited)) if row.passages_cited is not None else None, row.invalid_cites,
             row.failure, row.search_ms, row.wall_ms, int(bool(row.shown))))
        return int(cursor.lastrowid)

    def answers(self, consultation_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM guideline_answer WHERE consultation_id = ? ORDER BY id", (consultation_id,))
        return [self._answer(r) for r in rows]

    def answer(self, answer_id: int) -> dict | None:
        found = self._db.query_one("SELECT * FROM guideline_answer WHERE id = ?", (answer_id,))
        return self._answer(found) if found else None

    @staticmethod
    def _answer(row) -> dict:
        return {**dict(row), "names": json.loads(row["names"]), "passages": json.loads(row["passages"]),
                "passages_cited": json.loads(row["passages_cited"]) if row["passages_cited"] else None}
