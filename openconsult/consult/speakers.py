"""Who spoke (spec 15.9 ruling 4; 15.10 rulings 7 and 14; V1_LESSONS 2.1,
2.2): the question asked at Stop, the labels its answer sets, and the
label check's labels applied with their marks. The answer sets the
chosen speaker's lines to doctor and every other speaker's to patient; a
line the choice gave no speaker is unsure. The check changes labels
only, each change marked; a line it calls unsure is shown unsure; a
line with no first reading takes the check's label and stays shown
unsure, because there was nothing for the check to agree with."""

from __future__ import annotations

from openconsult.speech.matching import normalise

CANNOT_TELL = "none"
FIRST_WORDS = 8


def options(rows: list[dict]) -> list[dict]:
    """One option for each speaker label the choice gave, in order of first
    appearance, with the first words of its first line."""
    found: dict[str, dict] = {}
    for row in rows:
        speaker = row.get("raw_speaker")
        if speaker is None or speaker in found or row.get("refused"):
            continue
        words = row["text"].split()
        found[speaker] = {"speaker": speaker, "n": len(found) + 1,
                          "words": " ".join(words[:FIRST_WORDS]) + ("..." if len(words) > FIRST_WORDS else "")}
    return list(found.values())


def labels_from_answer(rows: list[dict], doctor_speaker: str) -> dict[int, dict]:
    """By line number: the label and whether the line is unsure. I cannot
    tell (CANNOT_TELL) sets every line unsure."""
    labels = {}
    for row in rows:
        if row.get("n") is None:
            continue
        speaker = row.get("raw_speaker")
        if doctor_speaker == CANNOT_TELL or speaker is None:
            labels[row["n"]] = {"label": "unsure", "changed_by_check": False, "unsure": True}
        else:
            labels[row["n"]] = {"label": "doctor" if speaker == doctor_speaker else "patient",
                                "changed_by_check": False, "unsure": False}
    return labels


def apply_check(rows: list[dict], check: dict[int, str]) -> dict[int, dict]:
    """The check's labels over the lines as they stand after the answer
    (rulings 7 and 14). Returns the lines whose label, mark or unsure
    changed, by number."""
    changed = {}
    for row in rows:
        n = row.get("n")
        if n is None or n not in check:
            continue
        said = check[n]
        current, no_first_reading = row["label"], row.get("raw_speaker") is None
        if said == "unsure":
            if not row.get("unsure"):
                changed[n] = {"label": current, "changed_by_check": False, "unsure": True}
        elif no_first_reading:
            changed[n] = {"label": said, "changed_by_check": False, "unsure": True}
        elif said != current:
            changed[n] = {"label": said, "changed_by_check": True, "unsure": False}
    return changed


def words_of(text: str) -> list[str]:
    return normalise(text)
