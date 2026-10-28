"""One document into the corpus (spec 15.12, ruling 5; the detail The
passages and the search): the kind sniffed, the passages cut, each
embedded in the document form, the rows written together or not at all.
The page and the loader command both come here, so the bench tests the
loader the doctor uses (ruling 18). A refusal is one named reason; nothing
is half-added."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from openconsult.guidelines import passages as cutter
from openconsult.guidelines.sources import Passage, SourceRow, Sources
from openconsult.guidelines.texts import passage_text

BATCH = 16            # texts in one request to the worker, as v1 sent them
# A document a doctor saves for their own use is a few hundred kB; this is far above it.
UPLOAD_LIMIT_BYTES = 50_000_000


@dataclass(frozen=True)
class Added:
    source_id: int
    passages: int
    outside: int          # passages under 40 or over 350 words, for the report
    seconds: float
    kind: str
    title: str


@dataclass(frozen=True)
class Refused:
    reason: str           # kind, too_big, no_passages, worker, embed_failed
    detail: str | None = None


def add_document(sources: Sources, embedder, name: str, data: bytes, publisher: str, added_by: str,
                 title: str | None = None, clock=time.perf_counter) -> Added | Refused:
    """title None takes the guideline's name from the file's own title line (the loader command)."""
    started = clock()
    if len(data) > UPLOAD_LIMIT_BYTES:
        return Refused("too_big")
    not_ready = embedder.ready()
    if not_ready:
        return Refused("worker", not_ready)
    try:
        document = cutter.read_document(name, data)
    except cutter.Unreadable as why:
        return Refused("kind", str(why))
    cuts = cutter.cut(document)
    if not any(c.words >= cutter.MIN_WORDS for c in cuts):
        return Refused("no_passages")          # no passage of 40 words or more: nothing worth searching
    title = (title or cutter.title_from_line(document.title_line, document.kind) or name).strip()
    vectors = []
    for start in range(0, len(cuts), BATCH):
        found = embedder.embed([passage_text(title, c.trail, c.text) for c in cuts[start:start + BATCH]])
        if not found.ok or len(found.vectors) != len(cuts[start:start + BATCH]):
            return Refused("embed_failed", found.error or f"{len(found.vectors)} vectors came back for {len(cuts[start:start + BATCH])} texts")
        vectors.extend(found.vectors)
    rows = [Passage(i, c.trail, c.text, c.words, v) for i, (c, v) in enumerate(zip(cuts, vectors))]
    seconds = round(clock() - started, 2)
    source = SourceRow(title, publisher.strip(), name, document.kind, hashlib.sha256(data).hexdigest(), len(data), added_by,
                       embedder.model_id or "unknown")
    source_id = sources.add_source(source, rows, seconds)
    outside = sum(1 for c in cuts if not cutter.MIN_WORDS <= c.words <= cutter.MAX_WORDS)
    return Added(source_id, len(rows), outside, seconds, document.kind, title)
