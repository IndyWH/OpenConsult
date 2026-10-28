"""The two forms a text takes on its way to the embedding model (spec
15.12, The passages and the search; 15.9, A guideline search): the query
as v1 sent it and Google's page gives it, and the document form with the
heading trail before the text. v1's forms, byte for byte (V1/app/rag.py
and scripts/ingest_guidelines.py); the bench of 5d read them from here
under their old home."""

from __future__ import annotations

QUERY_PREFIX = "task: search result | query: "
PASSAGE_FORM = "title: {title} | text: {text}"
# The heading trail's joint, as v1 kept it (app/chunking.py).
TRAIL_JOINT = " › "
# The title and the trail on one line, for the embedding and for the citation.
SOURCE_JOINT = ": "


def search_text(name: str) -> str:
    return QUERY_PREFIX + name


def source_line(title: str, trail: str) -> str:
    """The title, or the title, a colon, a space and the trail."""
    return f"{title}{SOURCE_JOINT}{trail}" if trail else title


def passage_text(title: str, trail: str, text: str) -> str:
    """What is embedded: the source line as the title part, the passage as the text part."""
    return PASSAGE_FORM.format(title=source_line(title, trail), text=text)
