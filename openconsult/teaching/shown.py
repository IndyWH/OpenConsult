"""What a learner is shown of a feedback (spec 15.14; the owner's rule of
24 Nov 2026, mail 3 of run 10a): no learner's line, no credit. The model
matches what the learner did against the scenario and answers with
numbers; this is the rule by code that stands between that answer and
the page, so that credit never rests on a turn of the patient's or on a
line that is not there. The bench counts by it, and the page of run 10b
will show by it.

It only ever takes credit away: nothing is turned from not met to met.
It writes no word a person reads."""

from __future__ import annotations

BY_TURNS, BY_NONE = "turns", "none"      # two of the form's four words for where a point is shown


def doctors_turns(conversation: list[tuple[str, str]]) -> set[int]:
    """The numbers of the doctor's turns, numbered from 1 as the frame numbers them, doctor and patient alike."""
    return {n for n, (speaker, _) in enumerate(conversation, 1) if speaker == "doctor"}


def _entry(point: dict, doctors: set[int]) -> dict:
    """One entry as it came back, with only the doctor's turns left; met stays met only where it is shown by an
    examination or an answer, or by a turn of the doctor's that is left."""
    turns = [turn for turn in point["turns"] if turn in doctors]
    met = bool(point["met"]) and point["shown_by"] != BY_NONE and (point["shown_by"] != BY_TURNS or bool(turns))
    return {**point, "met": met, "turns": turns}


def shown(answer: dict, conversation: list[tuple[str, str]], points: int) -> dict:
    """The model's answer as a learner would be shown it: one entry for each of the case's marking points, in
    their order. A point that did not come back is not met; one that came back more than once is met only if
    every one of its entries is. A number the case does not have is dropped. Signposting stands only on a turn of
    the doctor's. Every other part of the answer is given back as it came."""
    doctors, back = doctors_turns(conversation), {}
    for point in answer["points"]:
        back.setdefault(point["number"], []).append(_entry(point, doctors))
    listed = []
    for number in range(1, points + 1):
        entries = back.get(number)
        if not entries:
            listed.append({"number": number, "met": False, "shown_by": BY_NONE, "turns": []})
        elif len(entries) == 1:
            listed.append(entries[0])
        else:
            listed.append({**entries[0], "met": all(entry["met"] for entry in entries),
                           "turns": sorted({turn for entry in entries for turn in entry["turns"]})})
    signpost = [turn for turn in answer["signpost_turns"] if turn in doctors]
    return {**answer, "points": listed, "signposted": bool(answer["signposted"]) and bool(signpost), "signpost_turns": signpost}
