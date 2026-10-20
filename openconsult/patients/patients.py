"""The patients (spec 8; 15.10 ruling 9; R11; D22): a name, a date of
birth and a sex, all three required, and the age worked out on the day.
Every patient here is acted (R1); the row holds no more than the three."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from openconsult.db import Database
from openconsult.patients.audit import Audit, Clock, now_local

SEXES = ("F", "M")
# A date of birth further back than this is a slip, not a patient: the
# patient line of R11 takes an age of 120 at most (consult/messages.py).
OLDEST_YEARS = 120


@dataclass(frozen=True)
class PatientRow:
    id: int
    name: str
    date_of_birth: date
    sex: str

    def age_on(self, day: date) -> int:
        """Whole years lived on that day."""
        before_birthday = (day.month, day.day) < (self.date_of_birth.month, self.date_of_birth.day)
        return day.year - self.date_of_birth.year - (1 if before_birthday else 0)


def parse_date(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def problem(name: str, date_of_birth: str, sex: str, today: date) -> str | None:
    """None when the three can be saved, else name, date_missing, date_bad
    or sex (R11: a patient cannot be saved without a date of birth and a sex)."""
    if not (name or "").strip():
        return "name"
    if not (date_of_birth or "").strip():
        return "date_missing"
    born = parse_date(date_of_birth)
    if born is None or born > today or born.year < today.year - OLDEST_YEARS:
        return "date_bad"
    if sex not in SEXES:
        return "sex"
    return None


class Patients:
    def __init__(self, db: Database, audit: Audit, clock: Clock = now_local):
        self._db = db
        self._audit = audit
        self._clock = clock

    def add(self, name: str, date_of_birth: date, sex: str) -> PatientRow:
        if sex not in SEXES:
            raise ValueError("the sex is F or M")
        cursor = self._db.execute(
            "INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), date_of_birth.isoformat(), sex, self._clock().isoformat(timespec="seconds")))
        row = PatientRow(int(cursor.lastrowid), name.strip(), date_of_birth, sex)
        self._audit.record("patient.saved", f"patient {row.id}")
        return row

    def get(self, patient_id: int) -> PatientRow | None:
        found = self._db.query_one("SELECT id, name, date_of_birth, sex FROM patient WHERE id = ?", (patient_id,))
        if found is None:
            return None
        return PatientRow(found["id"], found["name"], date.fromisoformat(found["date_of_birth"]), found["sex"])

    def today(self) -> date:
        when = self._clock()
        return when.date() if isinstance(when, datetime) else when
