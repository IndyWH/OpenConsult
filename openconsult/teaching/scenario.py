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
