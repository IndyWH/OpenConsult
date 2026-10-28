"""The guideline searches of the test of 5d (spec 15.9, the details of
5d; 15.8 ruling 29). v2 has no guideline search yet (stage 8), so the
test sends what v1 sends: one call to the embedding model for each
condition on the list of differentials, the words task: search result |
query: before the name. The names are those of the public engine bench,
consultation 495, chain A1 of the arm ollama-google-file, kept here as
data, so no new word is written for a model to read (15.8 ruling 1). A
vector is checked: 768 numbers, none a not-a-number."""

from __future__ import annotations

import json
import math
from pathlib import Path

# v1's forms, kept in the app since 8b (openconsult/guidelines/texts.py) and read from there.
from openconsult.guidelines.texts import PASSAGE_FORM, QUERY_PREFIX  # noqa: F401

VECTOR_SIZE = 768
LISTS_FILE = Path(__file__).with_name("searches.json")


def search_text(name: str) -> str:
    return QUERY_PREFIX + name


def passage_text(title: str, text: str) -> str:
    return PASSAGE_FORM.format(title=title, text=text)


def read_lists(path: Path = LISTS_FILE) -> list[list[str]]:
    """The 11 lists, as the file holds them."""
    return [list(names) for names in json.loads(Path(path).read_bytes().decode("utf-8"))["lists"]]


def list_for(k: int, lists: list[list[str]]) -> list[str]:
    """Search k takes list k; after the last list it starts again from the first."""
    return lists[k % len(lists)]


def vector_fault(vector) -> str | None:
    """Why a vector fails its check, or None: exactly VECTOR_SIZE numbers,
    none a not-a-number. An infinite value is counted with the
    not-a-number, as not a usable number, and named apart."""
    if not isinstance(vector, list):
        return "not a list of numbers"
    if len(vector) != VECTOR_SIZE:
        return f"{len(vector)} numbers, not {VECTOR_SIZE}"
    for i, value in enumerate(vector):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"number {i} is not a number"
        if math.isnan(value):
            return f"number {i} is a not-a-number"
        if math.isinf(value):
            return f"number {i} is infinite"
    return None


def lists_from_replies(rows: list[dict]) -> list[list[str]]:
    """The lists of differentials of one chain from the public replies, one
    for each pass in order: the reply's own names, or, where the reply's
    list was empty and the pass kept the earlier list (15.8 ruling 5),
    the earlier names."""
    lists, earlier = [], []
    for row in sorted((r for r in rows if r["job"] == "assessment"), key=lambda r: r["point"]):
        own = [d.get("condition") for d in (json.loads(row["text"]).get("differentials") or [])
               if isinstance(d, dict) and d.get("condition")]
        names = earlier if not own and row.get("kept") else own
        lists.append(list(names))
        earlier = list(names)
    return lists
