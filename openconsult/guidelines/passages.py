"""A document into passages (spec 15.12, ruling 5 and the detail The
passages and the search; 6.5): HTML by its headings, one passage per leaf
section with its heading trail, as v1's chunker did; a PDF by its text in
reading order, split at blank lines; plain text by blank lines. A passage
holds at most 350 words and at least 40: a smaller section joins the next
under the same heading, a longer one is split at a paragraph end, then a
sentence end, never inside a sentence. The standard library reads the
HTML; pypdf reads the PDF. Nothing here embeds or stores."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from openconsult.guidelines.texts import TRAIL_JOINT

MAX_WORDS = 350      # v1 app/chunking.py
MIN_WORDS = 40
KINDS = {".html": "html", ".htm": "html", ".pdf": "pdf", ".txt": "text", ".md": "text"}
HEADINGS = {"h2": 0, "h3": 1, "h4": 2}
DROPPED = ("nav", "header", "footer", "aside", "script", "style")
SKIPPED_HEADINGS = ("on this page", "contents")
# v1's sentence end: a full stop, question or exclamation mark, a space, a capital or a digit.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
TITLE_SEPARATOR = "|"


class Unreadable(Exception):
    """A file of no known kind, or one that cannot be read as its kind."""


@dataclass
class Section:
    trail: list
    blocks: list = field(default_factory=list)

    @property
    def words(self) -> int:
        return sum(len(b.split()) for b in self.blocks)

    @property
    def parent(self) -> tuple:
        return tuple(self.trail[:-1])


@dataclass(frozen=True)
class Cut:
    """One passage as the loader made it, before its vector."""
    trail: str
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class Document:
    kind: str
    title_line: str        # the file's own title line, for the loader command
    sections: list         # of Section, in reading order


def sniff_kind(name: str, data: bytes) -> str:
    """By the name's suffix, then by the bytes: a PDF begins %PDF-, an
    HTML file holds a doctype or an html tag in its first bytes."""
    head = data[:1024].lower()
    if head.startswith(b"%pdf-"):
        return "pdf"
    if b"<!doctype" in head or b"<html" in head:
        return "html"
    suffix = name.lower().rsplit(".", 1)
    kind = KINDS.get("." + suffix[1]) if len(suffix) == 2 else None
    if kind is None:
        raise Unreadable("not HTML, PDF or plain text")
    return kind


def title_from_line(title_line: str, kind: str) -> str:
    """The guideline's name from the file's own title line: for HTML the
    part between the first and the second separator; otherwise the line."""
    if kind == "html" and title_line.count(TITLE_SEPARATOR) >= 2:
        return title_line.split(TITLE_SEPARATOR)[1].strip()
    return title_line.strip()


# ------------------------------------------------------------------ HTML

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _Scan(HTMLParser):
    """Which region the page has: a chapter element, a main, or the body."""

    def __init__(self):
        super().__init__()
        self.found = set()

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if "chapter" in classes:
            self.found.add("chapter")
        if tag in ("main", "body"):
            self.found.add(tag)


class _Reader(HTMLParser):
    """Walks the page in order, within the region, dropping nav and the
    like, and attaches paragraphs and lists to the heading trail in force."""

    def __init__(self, region: str):
        super().__init__()
        self.region = region
        self.title = ""
        self.sections = [Section([])]
        self._stack: list[str] = []
        self._in_region = 0          # depth at which the region opened, or 0
        self._dropped = 0
        self._in_title = False
        self._heading: list | None = None
        self._block: list | None = None
        self._items: list | None = None
        self._item: list | None = None
        self._list_depth = 0
        self._trail: list = []

    def _opens_region(self, tag, attrs) -> bool:
        if self.region == "chapter":
            return "chapter" in (attrs.get("class") or "").split()
        return tag == self.region

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self._stack.append(tag)
        if tag == "title":
            self._in_title = True
        if not self._in_region and self._opens_region(tag, attrs):
            self._in_region = len(self._stack)
            return
        if not self._in_region:
            return
        if tag in DROPPED:
            self._dropped += 1
        if self._dropped:
            return
        self._space()
        if tag in HEADINGS:
            self._heading = []
        elif tag in ("ul", "ol"):
            self._list_depth += 1
            if self._list_depth == 1:
                self._items = []
        elif tag == "li" and self._list_depth == 1:
            self._item = []
        elif tag == "p" and self._list_depth == 0:
            self._block = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if self._in_region and self._dropped and tag in DROPPED:
            self._dropped -= 1
        elif self._in_region and not self._dropped:
            self._close(tag)
        if self._stack and self._in_region == len(self._stack) and self._stack[-1] == tag:
            self._in_region = -1         # the region has ended: nothing after it counts
        if self._stack:
            self._stack.pop()

    def _space(self):
        """A space where a tag opens or closes inside a buffer, so words of
        two elements never run together; the clean-up folds the extra."""
        for buffer in (self._heading, self._item, self._block):
            if buffer is not None:
                buffer.append(" ")

    def _close(self, tag):
        self._space()
        if tag in HEADINGS and self._heading is not None:
            self._open_section(HEADINGS[tag], _clean("".join(self._heading)))
            self._heading = None
        elif tag == "p" and self._block is not None:
            self._add_block(_clean("".join(self._block)))
            self._block = None
        elif tag == "li" and self._item is not None and self._list_depth == 1:
            text = _clean("".join(self._item))
            if text:
                self._items.append(text)
            self._item = None
        elif tag in ("ul", "ol") and self._list_depth:
            self._list_depth -= 1
            if self._list_depth == 0 and self._items is not None:
                self._add_list(self._items)
                self._items = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_region <= 0 or self._dropped:
            return
        if self._heading is not None:
            self._heading.append(data)
        elif self._item is not None:
            self._item.append(data)
        elif self._block is not None:
            self._block.append(data)

    def _open_section(self, level: int, heading: str):
        if not heading or heading.lower() in SKIPPED_HEADINGS:
            return
        trail = self._trail[:level]
        while len(trail) < level:
            trail.append("")             # a skipped heading level, tolerated
        trail.append(heading)
        self._trail = trail
        self.sections.append(Section([t for t in trail if t]))

    def _add_block(self, text: str):
        if text:
            self.sections[-1].blocks.append(text)

    def _add_list(self, items: list):
        if not items:
            return
        bullets = "\n".join(f"- {item}" for item in items)
        blocks = self.sections[-1].blocks
        if blocks:
            blocks[-1] += "\n" + bullets      # a stem and its bullets are one unit
        else:
            blocks.append(bullets)


def read_html(data: bytes) -> Document:
    text = data.decode("utf-8", errors="replace")
    scan = _Scan()
    scan.feed(text)
    region = "chapter" if "chapter" in scan.found else ("main" if "main" in scan.found else "body")
    reader = _Reader(region)
    reader.feed(text)
    reader.close()
    return Document("html", _clean(reader.title), [s for s in reader.sections if s.blocks])


# ------------------------------------------------------------ PDF, text

def _blocks(text: str) -> list[str]:
    found = []
    for raw in re.split(r"\n\s*\n", text):
        block = _clean(raw)
        if block:
            found.append(block)
    return found


def read_text(data: bytes) -> Document:
    text = data.decode("utf-8", errors="replace")
    blocks = _blocks(text)
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return Document("text", first, [Section([], blocks)] if blocks else [])


def read_pdf(data: bytes) -> Document:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - a bad file is one plain refusal
        raise Unreadable(f"the PDF could not be read: {type(exc).__name__}") from None
    blocks = [b for page in pages for b in _blocks(page)]
    first = next((line.strip() for page in pages for line in page.splitlines() if line.strip()), "")
    return Document("pdf", first, [Section([], blocks)] if blocks else [])


READERS = {"html": read_html, "pdf": read_pdf, "text": read_text}


def read_document(name: str, data: bytes) -> Document:
    kind = sniff_kind(name, data)
    return READERS[kind](data)


# ------------------------------------------------------------ the sizes

def _merge_small(sections: list[Section]) -> list[Section]:
    """A section under MIN_WORDS joins the next under the same parent; a
    last one joins the one before it under the same parent."""
    merged: list[Section] = []
    for section in sections:
        if merged and merged[-1].words < MIN_WORDS and merged[-1].parent == section.parent:
            merged[-1].blocks.extend(section.blocks)
            merged[-1].trail = section.trail
        else:
            merged.append(Section(list(section.trail), list(section.blocks)))
    if len(merged) >= 2 and merged[-1].words < MIN_WORDS and _beside(merged[-2], merged[-1]):
        last = merged.pop()
        merged[-1].blocks.extend(last.blocks)
    return merged


def _beside(earlier: Section, last: Section) -> bool:
    """The one before a last small section: under the same parent, or the
    section it is a subsection of."""
    return earlier.parent == last.parent or tuple(earlier.trail) == last.parent


def _split_sentences(block: str) -> list[str]:
    pieces, piece, count = [], [], 0
    for sentence in SENTENCE_END.split(block):
        piece.append(sentence)
        count += len(sentence.split())
        if count >= MAX_WORDS:
            pieces.append(" ".join(piece))
            piece, count = [], 0
    if piece:
        pieces.append(" ".join(piece))
    return pieces


def _split_long(blocks: list[str]) -> list[str]:
    """Runs of at most MAX_WORDS at paragraph ends; one paragraph over the
    limit at sentence ends."""
    passages, current, count = [], [], 0

    def flush():
        nonlocal current, count
        if current:
            passages.append("\n".join(current))
            current, count = [], 0

    for block in blocks:
        words = len(block.split())
        if words > MAX_WORDS:
            flush()
            passages.extend(_split_sentences(block))
            continue
        if count + words > MAX_WORDS:
            flush()
        current.append(block)
        count += words
    flush()
    return passages


def cut(document: Document) -> list[Cut]:
    found = []
    for section in _merge_small([s for s in document.sections if s.blocks]):
        trail = TRAIL_JOINT.join(section.trail)
        for text in _split_long(section.blocks):
            found.append(Cut(trail, text))
    return found
