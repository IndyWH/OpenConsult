"""The label check, as a job of the language model door (spec 15.9,
rulings 4, 17 and 37; 15.10 rulings 7, 14 and 24). The model reads the
lines of joined.py, a long page in parts, with their numbers and no
labels, and gives back numbers and labels
only: the form admits nothing else, so it cannot change a word. Code
refuses a reply that misses a line, and takes no label from it. A line
named twice with two labels is unsure, and a number that is not on the
page is dropped (ruling 24). The bench reads the same prompt file and
uses the same check (spec 5.1)."""

from __future__ import annotations

import hashlib

from openconsult.consult import joined
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
    """The check of one page, as the calls it takes (joined.cut): its
    joined lines whole, or in parts one after another, each reply through
    check_labels. Returns the label of every numbered line by its number
    (a joined line's label goes to every line it holds), or None, and an
    outcome: ok, refused with its detail, or failed with the door's
    failure and detail; with the calls made, the parts, the joined lines
    and the two counts of ruling 24. All or nothing: a part that fails or
    is refused ends the run, no later part is asked and no label is
    taken. The words are proven unchanged, and the joined lines are
    proven to hold the words of the page and no other."""
    numbered = [row for row in rows if row.get("n") is not None]
    lines = joined.of_rows(numbered)
    before = texts_hash(numbered)
    worded = [{"n": row["n"], "text": str(row["text"]).strip()} for row in numbered if str(row["text"]).strip()]
    if texts_hash(joined.unjoined(lines, numbered)) != texts_hash(worded):
        raise RuntimeError("the joined lines do not hold the words of the transcript")
    parts = joined.cut(lines)
    outcome = {"call_ids": [], "parts": len(parts), "joined_lines": len(lines), "named_twice": 0, "dropped": 0}
    found = []
    for part in parts:
        result: Result = door.ask("label_check", lines_text(joined.numbered(part)), consultation_id=consultation_id)
        outcome["call_ids"].append(result.call_id)
        if before != texts_hash(numbered):
            raise RuntimeError("a word of the transcript changed during the label check")
        if not result.ok:
            return None, {**outcome, "outcome": "failed", "failure": result.failure, "detail": result.detail}
        labels, refusal, counts = check_labels(result.answer, len(part["lines"]))
        outcome["named_twice"] += counts["named_twice"]
        outcome["dropped"] += counts["dropped"]
        if labels is None:
            where = f"part {part['k']} of {len(parts)}: " if len(parts) > 1 else ""
            return None, {**outcome, "outcome": "refused", "detail": where + refusal_words(refusal)}
        found.append(labels)
    merged = joined.merge(parts, found) or {}
    return {n: merged[line["n"]] for line in lines for n in line["page_lines"]}, {**outcome, "outcome": "ok"}
