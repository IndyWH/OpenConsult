"""What code checks of a scenario a model has just written, before a
patient appears (spec 15.14, rulings 10, 14 and 23, and the details of
run 10b: A fresh scenario). Whether a fresh scenario is clinically
right cannot be checked by code, and its label says so. What can be
counted is counted here, by one function for the app and for the bench:
the bench's hard mark six reads plan_doses, so both count a dose in a
plan the same way.

A scenario made from a clinician's script keeps the dose the clinician
wrote and is not put through this (ruling 23)."""

from __future__ import annotations

import re

from openconsult.teaching import frames

NUMBER = r"(?<![\w.,])\d+(?:[.,]\d+)?\s*"
# Hard mark six as the bench's README writes it: a number followed by one of these six, as whole words.
DOSE = re.compile(NUMBER + r"(?:mg|microgram|g|ml|unit|units)\b", re.IGNORECASE)


def plan_doses(scenario: dict) -> list[int]:
    """The numbers, from 1, of the steps of the plan that hold a dose. A
    dose is where a small mistake by a model does most harm, so a fresh
    scenario whose plan holds one is not shown (ruling 10; mark six)."""
    return [n for n, step in enumerate(scenario["plan"], 1) if DOSE.search(step["step"])]


def incomplete(scenario: dict) -> bool:
    """A scenario that fits the form and cannot be played or marked: no
    fact, no marking point under any heading, or no diagnosis in its
    differential (the owner's okay of 25 Nov 2026). The form sets no
    least number, so this is checked here."""
    points = sum(len(scenario["marking_points"][heading]) for heading in frames.HEADINGS)
    return not scenario["facts"] or not points or not scenario["differential"]
