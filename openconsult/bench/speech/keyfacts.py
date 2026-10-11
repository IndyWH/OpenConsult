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
# A note is full of shorthand, and the matching of part one reads shorthand
# as one word (the check of part two, fix 1). Before the matching, a note's
# text, and every alternative, unless phrase and word of negation of a rule,
# go through the same reading: a turn citation dropped; a thousands comma
# removed; a sign of about, more than or less than before a figure dropped;
# a figure with x after it parted; a range of two figures parted; a slash
# between two words, or between a figure and a word, parted (a slash
# between two figures stays: 150/95 is 150 over 95). A hyphen between two
# words is read both ways, joined as the matching joins it (co-codamol) and
# parted, and a thing is met when it is met in either reading.
_CITATION = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_SIGN_BEFORE_FIGURE = re.compile(r"[~\u2248<>\u2265\u2264]+\s*(?=\d)")
_TIMES = re.compile(r"(?<=\d)x\b")
_RANGE = re.compile(r"(?<=\d)-(?=\d)")
_SLASH_WORDS = re.compile(r"(?<=[A-Za-z])/(?=[A-Za-z0-9])|(?<=\d)/(?=[A-Za-z])")
_HYPHEN_WORDS = re.compile(r"(?<=[A-Za-z])-(?=[A-Za-z])")


def read_shorthand(text: str) -> str:
    """A note's text with its shorthand read as words, before the matching."""
    text = _THOUSANDS.sub("", _CITATION.sub(" ", str(text)))
    text = _SIGN_BEFORE_FIGURE.sub("", text)
    text = _TIMES.sub(" x", text)
    text = _RANGE.sub(" to ", text)
    return _SLASH_WORDS.sub(" ", text)


def readings(text: str) -> list[list[str]]:
    """The words of a text in its one or two readings: hyphenated words
    joined, and, where that differs, parted."""
    plain = read_shorthand(text)
    joined = normalise(plain)
    parted = normalise(_HYPHEN_WORDS.sub(" ", plain))
    return [joined] if parted == joined else [joined, parted]


class KeyFacts:
    """The file: the kinds in order, the words of negation, and each
    script's facts, every alternative normalised as the note's words are."""

    def __init__(self, data: dict):
        self.kinds = tuple(data["kinds_in_order"])
        self.negations = frozenset(NEGATIONS) | frozenset(w for added in data.get("negation_words_added", [])
                                                          for reading in readings(added) for w in reading[:1])
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


def _holds(words: list[str], part: list[str]) -> bool:
    return bool(part) and any(words[i:i + len(part)] == part for i in range(len(words) - len(part) + 1))


def stands(entry: list[list[str]], phrase: str) -> bool:
    """Whether a phrase of a rule stands in an entry as whole words in
    order, in either reading of either side."""
    return any(_holds(words, part) for words in entry for part in readings(phrase))


def groups_met(entry: list[list[str]], fact: dict) -> int:
    """How many of the fact's groups stand in the entry: a group is met when
    any of its alternatives stands there as whole words in order."""
    return sum(1 for group in fact["needs"] if any(stands(entry, alt) for alt in group))


def outcome_for_entry(entry: list[list[str]], fact: dict, negations: frozenset) -> str | None:
    """One entry, in its readings: found, changed, part or missing; None
    when the entry is passed over (an unless phrase stands in it)."""
    if any(stands(entry, phrase) for phrase in fact.get("unless", [])):
        return None
    if groups_met(entry, fact) < len(fact["needs"]):
        return "missing"
    entry_words = [w for words in entry for w in words]
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
            words = readings(str(entry.get("text", "")))
            outcome = outcome_for_entry(words, fact, negations)
            if outcome is None:
                continue
            outcomes.append(outcome)
            met = groups_met(words, fact)
            if met > most:
                most, nearest = met, {"section": section, "text": entry.get("text", ""), "groups_met": met}
            if outcome == "found" and not fact.get("negated"):
                if any(w in negations for reading in words for w in reading):
                    found_with_negation = True
                else:
                    found_without = True
    return {"id": fact["id"], "kind": fact["kind"], "fact": fact["fact"], "outcome": best(outcomes),
            "nearest": nearest, "groups": len(fact["needs"]),
            "only_beside_negation": found_with_negation and not found_without}


def check_all(note: dict, facts: list[dict], negations: frozenset) -> list[dict]:
    return [check_note(note, fact, negations) for fact in facts]
