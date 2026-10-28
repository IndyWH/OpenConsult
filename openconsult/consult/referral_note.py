"""The approved note as the two letter calls read it (spec 15.12, rulings
2, 3 and 8; the detail The two letter frames; R5, R11; D24). The text
is note_approval's alone, never a draft's. It is numbered from 1 in
reading order, the four headings numbered too and never citable, one
line per entry; the list call sees every line, the letter call sees each
Assessment entry's words replaced by the withheld file's words, the
numbers the same in both, so a citation reads the same line. The patient
line opens both messages; the background block reaches neither (D24):
there is no slot for it here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from openconsult import words
from openconsult.consult.messages import Patient, with_patient
from openconsult.consult.note import SECTIONS
from openconsult.prompts import loader

HEADINGS = tuple(words.SECTION_WORDS[s] for s in SECTIONS)


@dataclass(frozen=True)
class NoteLine:
    n: int
    section: str | None
    heading: bool
    text: str

    @property
    def citable(self) -> bool:
        """A heading and an Assessment line are never citable (ruling 4)."""
        return not self.heading and self.section != "assessment"


def numbered_lines(approved_text: str) -> list[NoteLine]:
    """The approved text line by line, blank lines skipped; a line equal
    to the next heading word in order opens that section; every other
    line is an entry of the section it is in."""
    found: list[NoteLine] = []
    section, expected = None, 0
    for raw in (approved_text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if expected < len(HEADINGS) and line == HEADINGS[expected]:
            section = SECTIONS[expected]
            expected += 1
            found.append(NoteLine(len(found) + 1, section, True, line))
        else:
            found.append(NoteLine(len(found) + 1, section, False, line))
    return found


def citable(lines: list[NoteLine]) -> set[int]:
    return {line.n for line in lines if line.citable}


def words_of(lines: list[NoteLine]) -> dict[int, str]:
    """Each line's words by its number, for the check and the page."""
    return {line.n: line.text for line in lines}


def list_text(lines: list[NoteLine]) -> str:
    """The note as the list call reads it: every line shown."""
    return "\n".join(f"[{line.n}] {line.text}" for line in lines)


def letter_text(lines: list[NoteLine]) -> str:
    """The note as the letter call reads it: an Assessment entry's words
    replaced by the withheld file's words, the numbers unchanged."""
    withheld = loader.file_text("letter.withheld")
    return "\n".join(f"[{line.n}] {withheld if line.section == 'assessment' and not line.heading else line.text}"
                     for line in lines)


def list_message(approved_text: str, patient: Patient) -> str:
    """The list call's user text: the patient line, a blank line, the frame around the numbered note."""
    return with_patient(loader.fill(loader.frame("referrals"), note=list_text(numbered_lines(approved_text))), patient)


def letter_message(approved_text: str, specialty: str, patient: Patient) -> str:
    """The letter call's user text: the patient line, a blank line, the
    specialty, a blank line, the frame around the masked numbered note."""
    note = letter_text(numbered_lines(approved_text))
    return with_patient(loader.fill(loader.frame("letter"), specialty=specialty, note=note), patient)


def patient_of(row: dict) -> Patient:
    """The patient line's age and sex for a letter call: from the details
    the consultation ran with (15.11 ruling 2), the age on the day it
    started, which is the age the live calls read."""
    born = date.fromisoformat(row["patient_date_of_birth"])
    day = datetime.fromisoformat(row["started_at"]).date()
    before_birthday = (day.month, day.day) < (born.month, born.day)
    return Patient(day.year - born.year - (1 if before_birthday else 0), row["patient_sex"])
