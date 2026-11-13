"""The lines a model reads, and the turns (spec 15.9, the details of part
two of 5c; ruling 22). The speech choices cut a page very differently, so
the bench makes its lines by one rule for every choice, from the smallest
timed pieces of the page at Stop. A piece is never split, and no word is
changed, added or lost. The label check, the voice method and the call for
doubtful drug names work on these lines; the note is given turns, as v1
gives them. The words placed around a transcript are exactly those the
details give: the heading, the numbers in square brackets, and the three
role words."""

from __future__ import annotations

from openconsult.bench.speech.reference import Reference
# v1's two role words and the word for a turn with no speaker (ruling 22,
# the owner's word) live in the app's note module since 6b, where the app
# sends them too (spec 5.1; 15.10 ruling 5).
from openconsult.consult.note import DOCTOR, PATIENT, UNKNOWN
# The rule for the lines lives where the app reads it too since 6c (spec 5.1; 15.10, the details of step 6c).
from openconsult.consult.joined import JOIN_GAP_S, SENTENCE_END, ends_sentence, lines_of  # noqa: F401 - the bench's names

HEADING = "TRANSCRIPT:"
ROLE_OF = {"DOCTOR": DOCTOR, "PATIENT": PATIENT}


def turns_of(lines: list[dict]) -> list[dict]:
    """Turns {n, speaker, text, lines} from neighbouring lines of the same
    label, numbered from 0 as v1 numbers them."""
    turns: list[dict] = []
    for line in lines:
        if turns and turns[-1]["speaker"] == line["speaker"]:
            turns[-1]["text"] += " " + line["text"]
            turns[-1]["lines"].append(line["n"])
        else:
            turns.append({"n": len(turns), "speaker": line["speaker"], "text": line["text"], "lines": [line["n"]]})
    return turns


def script_turns(reference: Reference) -> list[dict]:
    """For a note from the script itself: each speech of the reference as cut
    is one turn, with the script's speaker."""
    return [{"n": index, "speaker": speech.speaker, "text": speech.text, "lines": [speech.number]}
            for index, speech in enumerate(reference.speeches)]


def lines_text(lines: list[dict]) -> str:
    """The user text of the label check and the doubtful drug names: the
    heading, then one line for each line of the page, its number in square
    brackets, a space and the words. No speaker is shown (ruling 17)."""
    return "\n".join([HEADING] + [f"[{line['n']}] {line['text']}" for line in lines])


def turns_text(turns: list[dict], roles: dict[str, str]) -> str:
    """The user text of the note, as v1 sends it: the heading, then one line
    for each turn, its number in square brackets, a space, the role, a colon,
    a space and the words. roles maps a choice's label to DOCTOR or PATIENT
    (the best fit to the script); any other label, and none, is Unknown."""
    return "\n".join([HEADING] + [f"[{turn['n']}] {role_word(turn['speaker'], roles)}: {turn['text']}" for turn in turns])


def role_word(speaker: str | None, roles: dict[str, str]) -> str:
    """A script's speaker is its own role; a choice's label goes through
    the best-fit mapping; anything else is Unknown."""
    if speaker is None:
        return UNKNOWN
    return ROLE_OF.get(roles.get(str(speaker), str(speaker)), UNKNOWN)
