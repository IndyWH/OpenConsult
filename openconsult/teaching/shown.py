"""What a learner is shown of a feedback (spec 15.14; the owner's rule of
24 Nov 2026, mails 3 and 4 of run 10a): no learner's line that is not
the learner's. The model matches what the learner did against the
scenario and answers with numbers; this is the rule by code that stands
between that answer and the page. The bench counts by it, and the page
of run 10b will show by it.

A number that is not a turn of the doctor's never reaches a learner, as
a quoted line or as signposting. Dropping a turn never changes whether
a point is met: the form cannot tell a point shown by an examination or
an answer from one shown in the consultation, so a point that came back
met stays met with whatever turns of the doctor's are left. A marking
point that did not come back is not met. Nothing is ever turned from
not met to met. It writes no word a person reads."""

from __future__ import annotations


def doctors_turns(conversation: list[tuple[str, str]]) -> set[int]:
    """The numbers of the doctor's turns, numbered from 1 as the frame numbers them, doctor and patient alike."""
    return {n for n, (speaker, _) in enumerate(conversation, 1) if speaker == "doctor"}


def shown(answer: dict, conversation: list[tuple[str, str]], points: int) -> dict:
    """The model's answer as a learner would be shown it: one entry for each of the case's marking points, in
    their order, with only the doctor's turns left in its list. A point that did not come back is not met; one
    that came back more than once is met only if every one of its entries is. A number the case does not have is
    dropped. Signposting stands only on a turn of the doctor's. Every other part of the answer is given back as
    it came."""
    doctors, back = doctors_turns(conversation), {}
    for point in answer["points"]:
        back.setdefault(point["number"], []).append({**point, "turns": [turn for turn in point["turns"] if turn in doctors]})
    listed = []
    for number in range(1, points + 1):
        entries = back.get(number)
        if not entries:
            listed.append({"number": number, "met": False, "turns": []})
        elif len(entries) == 1:
            listed.append(entries[0])
        else:
            listed.append({**entries[0], "met": all(entry["met"] for entry in entries),
                           "turns": sorted({turn for entry in entries for turn in entry["turns"]})})
    signpost = [turn for turn in answer["signpost_turns"] if turn in doctors]
    return {**answer, "points": listed, "signposted": bool(answer["signposted"]) and bool(signpost), "signpost_turns": signpost}
