"""Structure-aware chunking of guideline documents for retrieval.

Design decisions (and why):

1. A chunk is a SECTION, not a token window. Guideline advice is organised
   under headings; a fixed-size sliding window cuts recommendations in half
   and welds unrelated ones together. We build a heading tree (h2→h4) and
   emit one chunk per leaf section.
2. Every chunk knows its heading trail ("Recommendations › Managing stable
   angina › Drug treatment"). The trail is prepended to the text that gets
   EMBEDDED — headings carry the clinical topic words that make retrieval
   land — and stored for citation display.
3. List items stay with the paragraph that introduces them. "Offer aspirin
   if:" plus its bullets is one clinical unit; a bullet alone is noise.
4. Sections larger than MAX_WORDS split at paragraph boundaries first, then
   at sentence boundaries — never mid-sentence. Sections smaller than
   MIN_WORDS merge into the next section under the same parent instead of
   becoming context-free fragments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

MAX_WORDS = 350
MIN_WORDS = 40

_HEADING_TAGS = {"h2": 0, "h3": 1, "h4": 2}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass
class Chunk:
    section_path: str  # "Recommendations › Managing stable angina › Drugs"
    text: str          # the passage itself, without the path

    @property
    def embedding_text(self) -> str:
        """What gets embedded: heading trail + passage."""
        return f"{self.section_path}\n{self.text}"

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class _Section:
    path: list[str]
    blocks: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sections_from_html(html: str, root_heading: str) -> list[_Section]:
    """Walk the document in order, attaching paragraphs and lists to the
    heading trail currently in force."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find(class_="chapter") or soup.find("main") or soup.body or soup

    # Kill navigation/boilerplate that would pollute chunks.
    for tag in body.find_all(["nav", "header", "footer", "script", "style", "aside"]):
        tag.decompose()

    trail: list[str] = [root_heading]
    sections: list[_Section] = [_Section(path=list(trail))]

    for el in body.find_all(["h2", "h3", "h4", "p", "ul", "ol"]):
        if el.find_parent(["ul", "ol"]):  # nested list — handled with its top list
            continue
        name = el.name
        if name in _HEADING_TAGS:
            heading = _clean(el.get_text())
            if not heading or heading.lower() in ("on this page", "contents"):
                continue
            trail = trail[: _HEADING_TAGS[name] + 1]
            while len(trail) <= _HEADING_TAGS[name]:
                trail.append("")  # tolerate skipped heading levels
            trail.append(heading)
            sections.append(_Section(path=[t for t in trail if t]))
        elif name == "p":
            text = _clean(el.get_text())
            if text:
                sections[-1].blocks.append(text)
        else:  # ul / ol: keep items together, attached to the preceding stem
            items = [_clean(li.get_text()) for li in el.find_all("li", recursive=False)]
            items = [i for i in items if i]
            if not items:
                continue
            bullet_block = "\n".join(f"- {i}" for i in items)
            if sections[-1].blocks:
                # Recommendation stem ("Offer X if:") + its bullets = one unit.
                sections[-1].blocks[-1] += "\n" + bullet_block
            else:
                sections[-1].blocks.append(bullet_block)

    return [s for s in sections if s.blocks]


def _split_long(blocks: list[str]) -> list[str]:
    """Group blocks into passages of <= MAX_WORDS, splitting a single huge
    block at sentence boundaries only."""
    passages: list[str] = []
    current: list[str] = []
    count = 0

    def flush() -> None:
        nonlocal current, count
        if current:
            passages.append("\n".join(current))
            current, count = [], 0

    for block in blocks:
        words = len(block.split())
        if words > MAX_WORDS:
            flush()
            sentences = _SENTENCE_END.split(block)
            piece: list[str] = []
            piece_count = 0
            for sentence in sentences:
                piece_count += len(sentence.split())
                piece.append(sentence)
                if piece_count >= MAX_WORDS:
                    passages.append(" ".join(piece))
                    piece, piece_count = [], 0
            if piece:
                passages.append(" ".join(piece))
            continue
        if count + words > MAX_WORDS:
            flush()
        current.append(block)
        count += words
    flush()
    return passages


def chunk_html(html: str, root_heading: str) -> list[Chunk]:
    """Parse a guideline HTML page into retrieval chunks."""
    sections = _sections_from_html(html, root_heading)

    # Merge undersized sections into the next one under the same parent so a
    # lone heading with one line doesn't become a context-free fragment.
    merged: list[_Section] = []
    for section in sections:
        if (
            merged
            and sum(len(b.split()) for b in merged[-1].blocks) < MIN_WORDS
            and merged[-1].path[:-1] == section.path[:-1]
        ):
            merged[-1].blocks.extend(section.blocks)
            merged[-1].path = section.path
        else:
            merged.append(section)

    chunks: list[Chunk] = []
    for section in merged:
        path = " › ".join(section.path)
        for passage in _split_long(section.blocks):
            chunks.append(Chunk(section_path=path, text=passage))
    return chunks
