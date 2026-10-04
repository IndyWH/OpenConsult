"""The message builders and the patient line, ported from v1 as plain
functions (spec 6.1, 15.7). The fixed words come from the prompts
folder; only the patient line is built by code (R11)."""

from __future__ import annotations

from dataclasses import dataclass

from openconsult.prompts import loader

ADULT_AGE = 18


class NoPatient(Exception):
    """Every model call about the patient carries the line (R11), so a
    pass with no usable patient is refused before any call."""


@dataclass(frozen=True)
class Patient:
    age: int
    sex: str  # F or M


def patient_line(age, sex) -> str | None:
    """The one line about the patient, or None when age or sex is not
    usable. Woman or man from 18, girl or boy under, a baby at 0."""
    if sex not in ("F", "M"):
        return None
    if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 120:
        return None
    child = "girl" if sex == "F" else "boy"
    if age == 0:
        return f"The patient is a baby {child}, under 1 year old."
    noun = ("woman" if sex == "F" else "man") if age >= ADULT_AGE else child
    return f"The patient is a {age}-year-old {noun}."


def with_patient(message: str, patient: Patient | None) -> str:
    line = patient_line(patient.age, patient.sex) if patient else None
    if line is None:
        raise NoPatient("a model call about the patient needs a usable age and sex")
    return f"{line}\n\n{message}"


def assessment_message(transcript: str, previous_names) -> str:
    """The transcript alone on the first pass, or when the earlier list
    was empty. Later, the earlier differentials' names, as a stale list
    before the transcript, so the evidence is read last (R12)."""
    names = [name for name in (previous_names or ()) if isinstance(name, str) and name]
    if not names:
        return loader.fill(loader.frame("assessment.first"), transcript=transcript)
    return loader.fill(loader.frame("assessment.later"), stale="\n".join(names),
                       transcript=transcript)


def alarm_message(transcript: str) -> str:
    return loader.fill(loader.frame("alarm"), transcript=transcript)


def names_of(differentials) -> tuple[str, ...]:
    """The condition names of an assessment's differentials, in order."""
    return tuple(d["condition"] for d in (differentials or [])
                 if isinstance(d, dict) and d.get("condition"))
