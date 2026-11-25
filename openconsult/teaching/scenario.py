"""What the pages read off a scenario (spec 12.2; 15.14 and the details
of run 10b). A scenario is the form of teaching_case: part one is the
patient's side, part two the examiner's. Nothing here writes a word a
model reads: the frames do that (openconsult/teaching/frames.py), and
the numbers given here are the numbers the frames give."""

from __future__ import annotations

# A parent written as one of these, in any case of letters, counts as no parent (the details: The patient is presented).
NO_PARENT = ("", "nothing", "none", "no", "n/a")


def speaks_for(scenario: dict) -> str | None:
    """The parent who speaks for a child, as the scenario gives it, or None."""
    parent = str(scenario["patient"].get("parent") or "").strip()
    return None if parent.lower() in NO_PARENT else parent


# ------------------------------------------------------------ the examination

def findings(scenario: dict) -> list[str]:
    """The findings in the scenario's own words, in the order the frames
    number them from 1: the entries of examination, then of results."""
    return ([f"{found['examination']}: {found['finding']}" for found in scenario["examination"]]
            + [f"{found['test']}: {found['result']}" for found in scenario["results"]])


def _numbers(asked: list, most: int) -> list[int]:
    """The numbers that name a finding of the case, each once, in the order they came. Any other is dropped."""
    return list(dict.fromkeys(n for n in asked if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= most))


def _own_words(typed: str, entries: list) -> list[str]:
    """What the learner asked for that the case does not hold, in the
    learner's own words (ruling 12). The model gives each back as text.
    An entry is shown only when its words stand in what the learner
    typed, but for capitals, and then as the learner typed them; where
    one does not, the whole typed request stands in place of them all,
    so no word a model wrote is ever shown as the learner's."""
    own = []
    for entry in (str(entry).strip() for entry in entries):
        if not entry:
            continue
        at = typed.lower().find(entry.lower())
        if at < 0:
            return [typed]
        own.append(typed[at:at + len(entry)])
    return list(dict.fromkeys(own))


def examined_blocks(scenario: dict, examined: list[dict]) -> list[dict]:
    """Each examination request as the page shows it: the words as typed,
    the findings it brought, in the scenario's own words and once each,
    and what the case holds no finding for. no_examination: both lists
    came back empty. nothing: something came back and none of it can be
    shown, such as a number that is no finding of the case."""
    held = findings(scenario)
    blocks = []
    for request in examined:
        numbers = _numbers(request["asked"], len(held))
        not_held = _own_words(request["text"], request["not_in_case"])
        came_empty = not request["asked"] and not request["not_in_case"]
        blocks.append({"n": request["n"], "typed": request["text"], "found": [held[n - 1] for n in numbers], "not_held": not_held,
                       "no_examination": came_empty, "nothing": not came_empty and not numbers and not not_held})
    return blocks


def other_findings(scenario: dict, examined: list[dict]) -> list[str]:
    """The rest: every finding of the scenario that no request brought (D10)."""
    held = findings(scenario)
    shown = {n for request in examined for n in _numbers(request["asked"], len(held))}
    return [finding for n, finding in enumerate(held, 1) if n not in shown]
