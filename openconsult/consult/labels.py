"""The label check, as a job of the language model door (spec 15.9,
rulings 4 and 17; 15.10 rulings 7 and 14). The model reads the lines
with their numbers and no labels, and gives back numbers and labels
only: the form admits nothing else, so it cannot change a word. Code
refuses a reply that misses, repeats or invents a line, and takes no
label from it. The bench reads the same prompt file and uses the same
check (spec 5.1)."""

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


def check_labels(answer: dict | None, n_lines: int) -> tuple[dict[int, str] | None, dict | None]:
    """The labels by line number, or None with the reason the reply was
    refused: a line missed, repeated or not there (ruling 17). From a
    refused reply no label is taken."""
    if answer is None:
        return None, {"reason": "no answer"}
    seen: dict[int, str] = {}
    repeated, unknown = [], []
    for entry in answer.get("lines", []):
        number = entry["line"]
        if not isinstance(number, int) or number < 1 or number > n_lines:
            unknown.append(number)
        elif number in seen:
            repeated.append(number)
        else:
            seen[number] = str(entry["label"])
    missing = [n for n in range(1, n_lines + 1) if n not in seen]
    if missing or repeated or unknown:
        return None, {"reason": "refused", "missing": missing, "repeated": repeated, "unknown": unknown}
    return seen, None


def refusal_words(refusal: dict) -> str:
    parts = []
    for key in ("missing", "repeated", "unknown"):
        if refusal.get(key):
            parts.append(f"{key} {', '.join(str(n) for n in refusal[key])}")
    return "; ".join(parts) or refusal.get("reason", "")


def run(door: Door, rows: list[dict], consultation_id: int) -> tuple[dict[int, str] | None, dict]:
    """One call for the whole transcript. Returns the labels by line number,
    or None, and an outcome: ok, refused with its detail, or failed with
    the door's failure and detail. The words are proven unchanged."""
    numbered = [row for row in rows if row.get("n") is not None]
    before = texts_hash(numbered)
    result: Result = door.ask("label_check", lines_text(numbered), consultation_id=consultation_id)
    if before != texts_hash(numbered):
        raise RuntimeError("a word of the transcript changed during the label check")
    if not result.ok:
        return None, {"outcome": "failed", "failure": result.failure, "detail": result.detail, "call_id": result.call_id}
    labels, refusal = check_labels(result.answer, len(numbered))
    if labels is None:
        return None, {"outcome": "refused", "detail": refusal_words(refusal), "call_id": result.call_id}
    return labels, {"outcome": "ok", "call_id": result.call_id}
