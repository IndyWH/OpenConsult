"""The label check, as a job of the language model door (spec 15.9,
rulings 4 and 17; 15.10 rulings 7, 14 and 24). The model reads the lines
with their numbers and no labels, and gives back numbers and labels
only: the form admits nothing else, so it cannot change a word. Code
refuses a reply that misses a line, and takes no label from it. A line
named twice with two labels is unsure, and a number that is not on the
page is dropped (ruling 24). The bench reads the same prompt file and
uses the same check (spec 5.1)."""

from __future__ import annotations

import hashlib

from openconsult.llm.door import Door, Result
from openconsult.prompts import loader

LABELS = ("doctor", "patient", "unsure")


def lines_text(rows: list[dict]) -> str:
    """The user text: the heading, then one line for each line, its number
    in square brackets, a space and the words; no speaker shown (the
    details of part two of 5c). The words around the lines come from the
    frame file, never from here."""
    numbered = "\n".join(f"[{row['n']}] {row['text']}" for row in rows)
    return loader.fill(loader.frame("label_check"), transcript=numbered)


def texts_hash(rows: list[dict]) -> str:
    """The proof that no word changed: the words of the lines, hashed, to
    be compared before and after the check."""
    joined = "\n".join(f"{row['n']}\t{row['text']}" for row in rows)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def check_labels(answer: dict | None, n_lines: int) -> tuple[dict[int, str] | None, dict | None, dict]:
    """The labels by line number, or None with the reason the reply was
    refused: a line not named, whose label would have to be guessed
    (ruling 17). From a refused reply no label is taken. By ruling 24 a
    line on a page can hold both speakers, so a line named more than once
    takes its label when every naming gives the same one and is unsure
    when they differ, and a number that is not a line of the page sent is
    dropped. The third thing given back is the counts of the reply: the
    lines named more than once, the numbers dropped, and the lines made
    unsure by this rule."""
    counts: dict = {"named_twice": 0, "dropped": 0, "made_unsure": []}
    if answer is None:
        return None, {"reason": "no answer"}, counts
    named: dict[int, list[str]] = {}
    for entry in answer.get("lines", []):
        number = entry["line"]
        if not isinstance(number, int) or isinstance(number, bool) or number < 1 or number > n_lines:
            counts["dropped"] += 1
        else:
            named.setdefault(number, []).append(str(entry["label"]))
    counts["named_twice"] = sum(1 for given in named.values() if len(given) > 1)
    counts["made_unsure"] = sorted(n for n, given in named.items() if len(set(given)) > 1)
    missing = [n for n in range(1, n_lines + 1) if n not in named]
    if missing:
        return None, {"reason": "refused", "missing": missing}, counts
    return {n: named[n][0] if len(set(named[n])) == 1 else "unsure" for n in sorted(named)}, None, counts


def refusal_words(refusal: dict) -> str:
    if refusal.get("missing"):
        return f"missing {', '.join(str(n) for n in refusal['missing'])}"
    return refusal.get("reason", "")


def run(door: Door, rows: list[dict], consultation_id: int) -> tuple[dict[int, str] | None, dict]:
    """One call for the whole transcript. Returns the labels by line number,
    or None, and an outcome: ok, refused with its detail, or failed with
    the door's failure and detail; with a reply that came back, the two
    counts of ruling 24. The words are proven unchanged."""
    numbered = [row for row in rows if row.get("n") is not None]
    before = texts_hash(numbered)
    result: Result = door.ask("label_check", lines_text(numbered), consultation_id=consultation_id)
    if before != texts_hash(numbered):
        raise RuntimeError("a word of the transcript changed during the label check")
    if not result.ok:
        return None, {"outcome": "failed", "failure": result.failure, "detail": result.detail, "call_id": result.call_id}
    labels, refusal, counts = check_labels(result.answer, len(numbered))
    kept = {"call_id": result.call_id, "named_twice": counts["named_twice"], "dropped": counts["dropped"]}
    if labels is None:
        return None, {"outcome": "refused", "detail": refusal_words(refusal), **kept}
    return labels, {"outcome": "ok", **kept}
