"""The notes and their five counts (spec 15.9, rulings 15, 19 and 20; 13.3
mark 6; 13.4 rule 6; 15.8 ruling 16; the details of part two of 5c). From
each page a note is written twice, and twice from the script itself. For
each note the bench counts: each key fact's outcome; every figure that was
not spoken in the transcript the note was written from; a reasoning that
does not end as a sentence ends; an entry whose turns are empty or name no
turn that exists; and the drug names, right, not spoken, or said to be
unclear. The chance between the two notes of one page is how many facts
differ in outcome. No model judges a note."""

from __future__ import annotations

import re

from openconsult.bench.speech import keyfacts
from openconsult.bench.speech.druglist import DrugList
from openconsult.speech.matching import UNITS, normalise

SECTIONS = keyfacts.SECTIONS
_FIGURE = re.compile(r"^\d+(\.\d+)?$")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
# A GP's short form for a length of time: a figure, a slash and 7, 52 or 12
# is days, weeks or months, when the figure is 24 or less (the plan review of
# part two, change 3); otherwise the slash is the word over, as 110/52 is.
_SHORT_FORM = re.compile(r"\b(\d+)/(7|52|12)\b")
# A note cites its turns inside its text as well, [12, 13]: those numbers
# are turns, not figures. And a hyphen between two figures is a range,
# 5-10 mins: two figures, not one (found by reading the rehearsal's tables).
_CITATION = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_RANGE = re.compile(r"(?<=\d)-(?=\d)")
SHORT_FORM_LIMIT = 24
SHORT_FORM_WORDS = {"7": "days", "52": "weeks", "12": "months"}
# A dose in other units counts as spoken: the units of mass, in milligrams.
MASS_MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}
SENTENCE_END = (".", "?", "!")
CLOSERS = "\"')]}’”"
UNCLEAR = "unclear"


def read_short_forms(text: str) -> str:
    """The note's side, read before the matching: turn citations dropped, a
    thousands comma removed, a range split, the short forms for time read."""
    def replace(match):
        if int(match.group(1)) <= SHORT_FORM_LIMIT:
            return f"{match.group(1)} {SHORT_FORM_WORDS[match.group(2)]}"
        return match.group(0)
    text = _RANGE.sub(" to ", _THOUSANDS.sub("", _CITATION.sub(" ", text)))
    return _SHORT_FORM.sub(replace, text)


def figures_with_units(words: list[str]) -> list[tuple[str, str | None]]:
    """Each figure of a normalised text, with the unit that follows it when
    one does (the matching's short form)."""
    found = []
    for index, word in enumerate(words):
        if _FIGURE.match(word):
            unit = words[index + 1] if index + 1 < len(words) and words[index + 1] in set(UNITS.values()) else None
            found.append((word, unit))
    return found


def _mg(figure: str, unit: str | None) -> float | None:
    return float(figure) * MASS_MG[unit] if unit in MASS_MG else None


def figures_not_spoken(note: dict, transcript_words: list[str]) -> list[dict]:
    """Every figure in the note's entries and reasoning that the transcript
    does not hold, as a figure or as the same amount in another unit of
    mass (ruling 19)."""
    spoken = figures_with_units(transcript_words)
    spoken_figures = {f for f, _ in spoken}
    spoken_mg = {_mg(f, u) for f, u in spoken if _mg(f, u) is not None}
    found = []
    for section, text in _texts(note):
        words = normalise(read_short_forms(text))
        for figure, unit in figures_with_units(words):
            if figure in spoken_figures or (_mg(figure, unit) in spoken_mg):
                continue
            found.append({"figure": figure, "unit": unit, "section": section, "text": text})
    return found


def _texts(note: dict) -> list[tuple[str, str]]:
    found = [("reasoning", str(note.get("reasoning", "")))]
    for section in SECTIONS:
        found += [(section, str(entry.get("text", ""))) for entry in note.get(section, [])]
    return found


def reasoning_cut(reasoning: str) -> bool:
    """A reasoning that does not end as a sentence ends: the mark of the
    stray double quote (15.8 ruling 16). A closing quote or bracket may
    follow the full stop."""
    text = str(reasoning or "").rstrip().rstrip(CLOSERS).rstrip()
    return not text or text[-1] not in SENTENCE_END


def bad_turns(note: dict, n_turns: int) -> list[dict]:
    """Entries whose turns are empty or name no turn that exists (0 to the
    last turn sent), as v1's citation check counts them."""
    found = []
    for section in SECTIONS:
        for entry in note.get(section, []):
            turns = entry.get("turns") or []
            if not any(isinstance(t, int) and 0 <= t < n_turns for t in turns):
                found.append({"section": section, "text": entry.get("text", ""), "turns": list(turns)})
    return found


def drug_names_in_note(note: dict, drugs: DrugList, spoken_names: list[str], never_right: list[str]) -> dict:
    """For each drug the page never once wrote rightly, whether the note has
    the right name; every whole name of the list in the note that was not
    spoken in the reading, with its entry; and whether an entry says a name
    is unclear (ruling 19)."""
    spoken = {" ".join(normalise(n)) for n in spoken_names}
    right = {}
    not_spoken, unclear = [], 0
    all_words = []
    for section, text in _texts(note):
        words = normalise(text)
        all_words += words
        if UNCLEAR in words and section != "reasoning":
            unclear += 1
        seen = set()
        for index in range(len(words)):
            whole = drugs.in_list_at(words, index)
            if whole and whole not in spoken and whole not in seen:
                seen.add(whole)
                not_spoken.append({"name": whole, "section": section, "text": text})
    for name in never_right:
        target = normalise(name)
        right[name] = any(all_words[i:i + len(target)] == target for i in range(len(all_words) - len(target) + 1))
    return {"right_name_present": right, "names_not_spoken": not_spoken, "unclear_entries": unclear}


def five_counts(note: dict, transcript_words: list[str], n_turns: int, facts: list[dict], negations: frozenset,
                drugs: DrugList | None, spoken_names: list[str], never_right: list[str]) -> dict:
    return {"key_facts": keyfacts.check_all(note, facts, negations),
            "figures_not_spoken": figures_not_spoken(note, transcript_words),
            "reasoning_cut": reasoning_cut(note.get("reasoning", "")),
            "bad_turns": bad_turns(note, n_turns),
            "drugs": drug_names_in_note(note, drugs, spoken_names, never_right) if drugs else None,
            "entries": sum(len(note.get(s, [])) for s in SECTIONS)}


def chance(first: list[dict], second: list[dict]) -> dict:
    """How often the two notes of one page differ in the outcome of a key fact."""
    by_id = {f["id"]: f["outcome"] for f in second}
    differ = [f["id"] for f in first if by_id.get(f["id"]) != f["outcome"]]
    return {"facts": len(first), "differ": len(differ), "ids": differ}
