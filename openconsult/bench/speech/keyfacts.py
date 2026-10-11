"""The key facts of a script, and how a note is checked against them (spec
15.9, ruling 20; 13.3 mark 6; the details of part two of 5c; V1_LESSONS
9.3, 9.8). Cowork writes the lists from the scripts themselves; code
applies them. A fact has a kind, the speeches it is said in, and a rule
made of groups of words: every group must be found in one and the same
entry of the note, with the right figures, and for a negative a word of
negation. The four outcomes for one entry are found, changed, part and
missing; over the entries the best counts. No model judges a note."""

from __future__ import annotations

import json
import re
from pathlib import Path

from openconsult.bench.speech.marks import NEGATIONS
from openconsult.speech.matching import normalise

OUTCOMES = ("found", "changed", "part", "missing")
SECTIONS = ("subjective", "objective", "assessment", "plan")
_FIGURE = re.compile(r"^\d+(\.\d+)?$")


class KeyFacts:
    """The file: the kinds in order, the words of negation, and each
    script's facts, every alternative normalised as the note's words are."""

    def __init__(self, data: dict):
        self.kinds = tuple(data["kinds_in_order"])
        self.negations = frozenset(NEGATIONS) | frozenset(_word(w)[0] for w in data.get("negation_words_added", []) if _word(w))
        self.scripts = {key: dict(script) for key, script in data["scripts"].items()}

    @classmethod
    def read(cls, path: Path) -> "KeyFacts":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def facts_of(self, script_key: str, last_speech: int | None = None, skipped: tuple[int, ...] = ()) -> list[dict]:
        """The facts of a script that count for a reading: at least one of
        a fact's speeches was read (the reading cut at last_speech, the
        skipped speeches left out)."""
        found = []
        for fact in self.scripts.get(script_key, {}).get("facts", []):
            said_in = [int(n) for n in fact["said_in"]]
            read = [n for n in said_in if (last_speech is None or n <= last_speech) and n not in skipped]
            if read:
                found.append(fact)
        return found


def _word(text: str) -> list[str]:
    return normalise(text)


def _holds(words: list[str], part: list[str]) -> bool:
    return bool(part) and any(words[i:i + len(part)] == part for i in range(len(words) - len(part) + 1))


def groups_met(entry_words: list[str], fact: dict) -> int:
    """How many of the fact's groups stand in the entry: a group is met when
    any of its alternatives stands there as whole words in order."""
    return sum(1 for group in fact["needs"] if any(_holds(entry_words, _word(alt)) for alt in group))


def outcome_for_entry(entry_words: list[str], fact: dict, negations: frozenset) -> str | None:
    """One entry: found, changed, part or missing; None when the entry is
    passed over (an unless phrase stands in it)."""
    if any(_holds(entry_words, _word(phrase)) for phrase in fact.get("unless", [])):
        return None
    if groups_met(entry_words, fact) < len(fact["needs"]):
        return "missing"
    figures = [w for w in entry_words if _FIGURE.match(w)]
    numbers_met = all(any(str(f) in figures for f in group) for group in fact.get("numbers", []))
    negated_ok = (not fact.get("negated")) or any(w in negations for w in entry_words)
    if numbers_met and negated_ok:
        return "found"
    if not numbers_met and not figures:
        return "part" if negated_ok else "changed"
    return "changed"


def best(outcomes: list[str]) -> str:
    for outcome in OUTCOMES:
        if outcome in outcomes:
            return outcome
    return "missing"


def check_note(note: dict, fact: dict, negations: frozenset) -> dict:
    """The fact against every entry of the note in the sections it names,
    the best outcome, the nearest entry (the one that holds the most of
    the fact's groups, none when no entry holds a single group), and
    whether a fact that is not a negative was found only beside a word of
    negation."""
    sections = fact.get("sections") or SECTIONS
    outcomes, nearest, most, found_with_negation, found_without = [], None, 0, False, False
    for section in sections:
        for entry in note.get(section, []):
            words = normalise(str(entry.get("text", "")))
            outcome = outcome_for_entry(words, fact, negations)
            if outcome is None:
                continue
            outcomes.append(outcome)
            met = groups_met(words, fact)
            if met > most:
                most, nearest = met, {"section": section, "text": entry.get("text", ""), "groups_met": met}
            if outcome == "found" and not fact.get("negated"):
                if any(w in negations for w in words):
                    found_with_negation = True
                else:
                    found_without = True
    return {"id": fact["id"], "kind": fact["kind"], "fact": fact["fact"], "outcome": best(outcomes),
            "nearest": nearest, "groups": len(fact["needs"]),
            "only_beside_negation": found_with_negation and not found_without}


def check_all(note: dict, facts: list[dict], negations: frozenset) -> list[dict]:
    return [check_note(note, fact, negations) for fact in facts]
