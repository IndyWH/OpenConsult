"""Who spoke: four readings, side by side (spec 15.9, ruling 4; rulings
17 and 22; the details of part two of 5c). For each page: the labels of the
speech choice (part one's best fit), the label check, the voice method,
and the two together, where the label stands only when the voice and the
words agree and the line is unsure anywhere else. Each reading is counted
in the same way, word by word against the script: right, wrong and unsure.
A page word standing where nothing was spoken has no speaker to be right
or wrong about, and is counted apart."""

from __future__ import annotations

from openconsult.bench.speech import marks
from openconsult.bench.speech.pages import Page, build_page
from openconsult.bench.speech.reference import Reference

READINGS = ("choice", "label_check", "voice", "together")
ROLE_TO_LABEL = {"DOCTOR": "doctor", "PATIENT": "patient"}


def line_page(lines: list[dict], reference: Reference) -> Page:
    """The lines a model reads, as the pieces of a page against the reference."""
    return build_page("lines", [{"start": ln["start"], "end": ln["end"], "text": ln["text"], "speaker": ln["speaker"]}
                                for ln in lines], reference)


def choice_labels(lines: list[dict], page: Page, reference: Reference) -> dict[int, str]:
    """The choice's own labels as doctor, patient or unsure, by the best
    fit to the script (part one's who_spoke); a label beyond the two of the
    fit is wrong wherever it stands, so it is given the word other."""
    mapping = marks.who_spoke(page, reference)["mapping"]
    found = {}
    for line in lines:
        if line["speaker"] is None:
            found[line["n"]] = "unsure"
        else:
            found[line["n"]] = ROLE_TO_LABEL.get(mapping.get(str(line["speaker"]), ""), "other")
    return found


def voice_labels(readings: dict[int, str] | None) -> dict[int, str] | None:
    """The voice's reading as a label: not doctor counts as the patient."""
    if readings is None:
        return None
    return {n: {"doctor": "doctor", "not_doctor": "patient"}.get(r, "unsure") for n, r in readings.items()}


def together(words_labels: dict[int, str] | None, voice: dict[int, str] | None) -> dict[int, str] | None:
    """Where the voice and the words agree the label stands; anywhere else
    the line is unsure (ruling 4). Without the voice there is no reading."""
    if voice is None:
        return None
    joined = {}
    for n, by_voice in voice.items():
        by_words = (words_labels or {}).get(n, "unsure")
        joined[n] = by_voice if by_voice in ("doctor", "patient") and by_voice == by_words else "unsure"
    return joined


def count(page: Page, reference: Reference, labels: dict[int, str] | None, lines: list[dict]) -> dict:
    """Word by word: right, wrong and unsure against the script; a word from
    nowhere apart. No labels (a refused or failed reading) is all unsure."""
    number_of_line = {index: line["n"] for index, line in enumerate(lines)}
    right = wrong = unsure = nowhere = 0
    for word in range(len(page.words)):
        spoken = page.spoken_of.get(word)
        if spoken is None:
            nowhere += 1
            continue
        label = (labels or {}).get(number_of_line[page.word_piece[word]], "unsure")
        if label == "unsure":
            unsure += 1
        elif label == ROLE_TO_LABEL[reference.words[spoken].speaker]:
            right += 1
        else:
            wrong += 1
    return {"right": right, "wrong": wrong, "unsure": unsure, "nowhere": nowhere}


def four_readings(lines: list[dict], reference: Reference, label_check: dict[int, str] | None,
                  voice: dict[int, str] | None) -> dict:
    """The four readings of one page, each counted the same way, with the
    labels of every line kept for reading. label_check is the labels by line
    number, or None when the reply was refused or the call failed; voice is
    the voice method's reading by line number, or None when it was not run."""
    page = line_page(lines, reference)
    by_choice = choice_labels(lines, page, reference)
    by_voice = voice_labels(voice)
    readings = {"choice": by_choice, "label_check": label_check, "voice": by_voice,
                "together": together(label_check, by_voice)}
    counted = {}
    for name in READINGS:
        labels = readings[name]
        if labels is None and name in ("voice", "together"):
            counted[name] = {"not_run": True}
        else:
            counted[name] = count(page, reference, labels, lines)
    return {"counts": counted, "lines": [{"n": ln["n"], "words": len(ln["text"].split()),
                                         **{name: (readings[name] or {}).get(ln["n"]) for name in READINGS}}
                                        for ln in lines]}
