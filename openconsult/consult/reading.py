"""The reading view's one rule: what a turn is (spec 15.10 rulings 14, 35
and 42; the details of step 6e, What a turn is). The speech choices cut a
page into lines, some of one word, and a doctor who reads the transcript
to check a note should read a conversation: doctor, patient, doctor,
patient. This gives the entries of the reading view from the page's
numbered lines. It is how the page is shown and nothing more: no line is
joined in the record, moved or given a new number, nothing is stored, and
no model reads a turn (the lines a model reads are joined.py's)."""

from __future__ import annotations

# An unsure run sits inside a turn only when it holds no more than this many words in all (ruling 42 and the details
# of step 6e: on six recordings with two people every such word between two lines of one speaker was that speaker's).
FOLD_WORDS = 3
UNSURE = "unsure"


def shown(line: dict) -> str:
    """The speaker a line is shown with. A line shown as unsure counts as
    unsure whatever label the check gave it (ruling 14)."""
    return UNSURE if line.get("unsure") or line.get("label") == UNSURE else line["label"]


def entries_of(lines: list[dict]) -> list[dict]:
    """The entries of the reading view, in order, each {speaker, lines}.
    Neighbouring lines shown under one speaker are one turn. A run of
    neighbouring unsure lines that together hold no more than FOLD_WORDS
    words, with a line before it and a line after it shown under the same
    speaker, sits inside that turn, and the turn runs on through it. Every
    other unsure run is an entry of its own, shown as unsure. A line with
    no words counts by its speaker like any line and adds no words. Every
    line is in exactly one entry."""
    under = [shown(line) for line in lines]
    first = 0
    while first < len(lines):
        if under[first] != UNSURE:
            first += 1
            continue
        after = first
        while after < len(lines) and under[after] == UNSURE:
            after += 1
        held = sum(len(str(line.get("text") or "").split()) for line in lines[first:after])
        if 0 < first and after < len(lines) and under[first - 1] == under[after] and held <= FOLD_WORDS:
            under[first:after] = [under[after]] * (after - first)
        first = after
    entries: list[dict] = []
    for line, speaker in zip(lines, under):
        if entries and entries[-1]["speaker"] == speaker:
            entries[-1]["lines"].append(line)
        else:
            entries.append({"speaker": speaker, "lines": [line]})
    return entries


def numbers_of(entries: list[dict]) -> dict[int, int]:
    """The number of the turn that holds each line (15.13, the details of
    step 9f, The number of a turn): the entries of the reading view are
    numbered from 1, in order, as the page shows them, and an entry of
    its own with no sure speaker is numbered like any turn. It is how
    the page is shown: the number is not stored and no model reads it
    (the turns a model cites are note.py's, numbered from 0 by another
    rule)."""
    return {line["n"]: number for number, entry in enumerate(entries, start=1) for line in entry["lines"]}


def chips_of(cited: list[int], numbers: dict[int, int]) -> list[int]:
    """The chips of a note entry (15.13, ruling 71): the number of each
    turn that holds at least one of the lines the entry cites, in order,
    each number once; none is dropped or gathered into a range. An entry
    that cites no line has none, and a cited line that is not on the
    page gives none."""
    return sorted({numbers[n] for n in cited if n in numbers})
