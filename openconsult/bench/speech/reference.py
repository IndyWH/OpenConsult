"""The reference (spec 13.4; 15.9, the details of 5c). The script, read by
the parser the bench already has, gives the speeches in order with their
speakers; the list's notes on speeches read differently change it, and a
reading that is not whole is cut after its last speech. Drug names, test
names and safety-net speeches are counted from the reference as cut.
Where every arm with a model of its own wrote the same word against the
script, and at least three did, the place is taken as spoken that way and
counts against no arm (13.4 rule 5); a word every arm left out is not
agreement and still counts."""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.bench.cases import parse_script
from openconsult.speech.matching import Pair, hyphenated, normalise

LEAST_ARMS_TO_AGREE = 3


@dataclass(frozen=True)
class Speech:
    number: int           # from 1, as the bench parser gives them
    speaker: str          # DOCTOR or PATIENT
    text: str


@dataclass(frozen=True)
class RefWord:
    norm: str
    speaker: str
    speech: int


@dataclass(frozen=True)
class Reference:
    speeches: tuple[Speech, ...]
    words: tuple[RefWord, ...]
    joinable: frozenset[str]        # the hyphenated words, for joining split page words
    last_speech: int | None         # where a reading that is not whole was cut

    @property
    def norms(self) -> list[str]:
        return [w.norm for w in self.words]

    def speech_of(self, number: int) -> Speech:
        return self.speeches[number - 1]


def build(script_text: str, last_speech: int | None = None, read_differently=()) -> Reference:
    """The speeches as spoken: the parser's turns numbered from 1, the
    notes applied, the cut made, then the words."""
    turns = parse_script(script_text)
    changed = {int(note["speech"]): note for note in read_differently}
    speeches = []
    for number, turn in enumerate(turns, start=1):
        if last_speech is not None and number > last_speech:
            break
        note = changed.get(number)
        if note and note.get("skipped"):
            continue
        speeches.append(Speech(number, turn.speaker, str(note["said"]) if note else turn.text))
    joinable = frozenset().union(*(hyphenated(s.text) for s in speeches)) if speeches else frozenset()
    words = tuple(RefWord(norm, s.speaker, s.number) for s in speeches for norm in normalise(s.text))
    return Reference(tuple(speeches), words, joinable, last_speech)


def occurrences(reference: Reference, name: str) -> list[tuple[int, int]]:
    """Where a name is spoken, as whole words: (first index, last index) of
    each occurrence in the reference as cut. A name of several words is a
    run of words."""
    target = normalise(name)
    norms = reference.norms
    found = []
    for i in range(len(norms) - len(target) + 1):
        if norms[i:i + len(target)] == target:
            found.append((i, i + len(target) - 1))
    return found


def names_as_cut(reference: Reference, names: dict[str, int]) -> dict[str, list[tuple[int, int]]]:
    """Each name of the marks file with its occurrences in the reference as cut."""
    return {name: occurrences(reference, name) for name in names}


def safety_nets_as_cut(reference: Reference, numbers: list[int]) -> list[int]:
    present = {s.number for s in reference.speeches}
    return [n for n in numbers if n in present]


@dataclass(frozen=True)
class Agreed:
    """One place of the reference where every arm that counts wrote the
    same word against the script (agreed), or every arm left it out
    (missing_everywhere, which is not agreement and still counts)."""
    index: int
    spoken: str
    written: str | None
    kind: str             # agreed or missing_everywhere
    arms: tuple[str, ...]


def outcomes(pairs: list[Pair], page: list[str]) -> dict[int, str | None]:
    """For each reference index: the page word standing there when it was
    replaced, None when missing; a heard word is left out."""
    found: dict[int, str | None] = {}
    for pair in pairs:
        if pair.kind == "replaced":
            found[pair.spoken] = page[pair.page]
        elif pair.kind == "missing":
            found[pair.spoken] = None
    return found


def agreement(reference: Reference, pages: dict[str, tuple[list[Pair], list[str]]],
              least: int = LEAST_ARMS_TO_AGREE) -> list[Agreed]:
    """pages: for each arm that counts, its alignment and its page words.
    Fewer than least arms: nothing is agreed."""
    if len(pages) < least:
        return []
    by_arm = {arm: outcomes(pairs, page) for arm, (pairs, page) in sorted(pages.items())}
    found = []
    for index, word in enumerate(reference.words):
        seen = [by_arm[arm].get(index, "heard") for arm in by_arm]
        if any(s == "heard" for s in seen):
            continue
        if all(s is None for s in seen):
            found.append(Agreed(index, word.norm, None, "missing_everywhere", tuple(by_arm)))
        elif len(set(seen)) == 1:
            found.append(Agreed(index, word.norm, seen[0], "agreed", tuple(by_arm)))
    return found
