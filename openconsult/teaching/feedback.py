"""The feedback as a learner is shown it (spec 12.4; 12.3, rule 4; D5;
D36; 15.14, rulings 13 and 20, and the details of run 10b: The
feedback, What did not come back, The known fault on the page).

The model writes no feedback in words: it answers with numbers and yes
or no. This module builds the five parts of 12.4 from that answer, and
never from the answer as it came: the rule of
openconsult/teaching/shown.py is applied first, so a line that is not
the learner's is never quoted. Every word it gives is the scenario's
own, and every quoted line is the learner's own, by its number.

A learner who is taught something wrong is harmed, and on the local
model the feedback credits a red flag that was not asked about in about
one feedback in five (ruling 20). So nothing here smooths the answer
over. A point that came back met is shown with the learner's own lines,
or plainly with none. A point, a diagnosis, an investigation or a step
that the answer left out is not judged, and is never shown as not met
or not named. The most important thing missed is shown only when it
names a point that is shown as not met. No grade, no pass or fail and
no count is built (D5)."""

from __future__ import annotations

from openconsult.teaching import frames
from openconsult.teaching.cases import ANSWERS
from openconsult.teaching.shown import shown

MET, NOT_MET, NOT_JUDGED = "met", "not_met", "not_judged"
NAMED, NOT_NAMED = "named", "not_named"
# What the most important thing missed is, when it is not a point's words: one of two sentences of the page.
NONE_MISSED, NO_SINGLE_POINT = "none_missed", "no_single_point"
DONE_WELL_MOST = 3
# The words of an item of each list, by the name its field has in the scenario.
ITEM_WORDS = {"differential": "diagnosis", "investigations": "investigation", "plan": "step"}


def marking_points(scenario: dict) -> list[tuple[str, str]]:
    """The marking points as (heading, words), in the order the frames number them from 1 across the three headings."""
    return [(heading, words) for heading in frames.HEADINGS for words in scenario["marking_points"][heading]]


def _lines(turns: list[int], conversation: list[tuple[str, str]]) -> list[dict]:
    """The learner's own lines for these turns, each with the learner's own number: turn 2k-1 is line k."""
    return [{"line": (turn + 1) // 2, "text": conversation[turn - 1][1]} for turn in sorted(set(turns))]


def _points(scenario: dict, conversation: list, answer: dict, ruled: dict) -> list[dict]:
    came = {point["number"] for point in answer["points"]}
    found = []
    for n, (heading, words) in enumerate(marking_points(scenario), 1):
        entry = ruled["points"][n - 1]
        state = NOT_JUDGED if n not in came else MET if entry["met"] else NOT_MET
        found.append({"n": n, "heading": heading, "words": words, "state": state,
                      "lines": _lines(entry["turns"], conversation) if state == MET else []})
    return found


def _missed(points: list[dict], number: int) -> dict:
    """The most important thing missed: the words of the point the model
    named, only when the page shows that point as not met. Where the
    model names none and no point is shown as not met, the page says
    that none was marked as missed; in every other case, that the
    feedback named no single point."""
    named = next((point for point in points if point["n"] == number), None)
    if named is not None and named["state"] == NOT_MET:
        return {"words": named["words"]}
    if number < 1 and not any(point["state"] == NOT_MET for point in points):
        return {"sentence": NONE_MISSED}
    return {"sentence": NO_SINGLE_POINT}


def _done_well(points: list[dict], numbers: list[int]) -> list[str]:
    """Up to three, each only when the page shows that point as met; the others are dropped."""
    by_number = {point["n"]: point for point in points}
    return [by_number[n]["words"] for n in dict.fromkeys(numbers) if n in by_number and by_number[n]["state"] == MET][:DONE_WELL_MOST]


def _own_words(typed: str, entries: list) -> list[str]:
    """What the learner named beyond the scenario: an entry only when its
    words stand in the learner's answer, letter for letter but for
    capitals, and then as the learner typed them."""
    own = []
    for entry in (str(entry).strip() for entry in entries):
        at = typed.lower().find(entry.lower()) if entry else -1
        if at >= 0:
            own.append(typed[at:at + len(entry)])
    return list(dict.fromkeys(own))


def _list(scenario: dict, name: str, answer: dict, typed: str) -> dict:
    """One of the three lists set against the case: each item of the
    scenario in its own words with named, not named, or not judged where
    its number did not come back; an item that came back more than once
    is named only if every entry says so."""
    said: dict[int, list[bool]] = {}
    for entry in answer[name]:
        said.setdefault(entry["number"], []).append(bool(entry["named"]))
    items = []
    for n, held in enumerate(scenario[name], 1):
        state = NOT_JUDGED if n not in said else NAMED if all(said[n]) else NOT_NAMED
        urgency = held.get("urgency")
        items.append({"words": held[ITEM_WORDS[name]], "state": state, "must_not_miss": bool(held.get("must_not_miss")),
                      "urgency": urgency if urgency and urgency != frames.NO_URGENCY else None})
    return {"name": name, "items": items, "answer": typed, "also_named": _own_words(typed, answer[f"{name}_extra"])}


def built(scenario: dict, conversation: list[tuple[str, str]], answers: dict, answer: dict) -> dict:
    """The five parts of 12.4, in their order: the most important thing
    missed; done well; the differential, the investigations and the plan
    set against the case; the marking points under their three
    headings; whether the learner signposted. answers: the learner's
    three answers by name. answer: the model's, as the door held it to
    its form."""
    ruled = shown(answer, conversation, len(marking_points(scenario)))
    points = _points(scenario, conversation, answer, ruled)
    return {
        "missed": _missed(points, answer["most_important_missed"]),
        "done_well": _done_well(points, answer["done_well"]),
        "lists": [_list(scenario, name, answer, answers[name]) for name in ANSWERS],
        "headings": [{"heading": heading, "points": [point for point in points if point["heading"] == heading]} for heading in frames.HEADINGS],
        "any_not_judged": any(point["state"] == NOT_JUDGED for point in points),
        "signposted": ruled["signposted"],
        "signpost_lines": _lines(ruled["signpost_turns"], conversation) if ruled["signposted"] else [],
    }
