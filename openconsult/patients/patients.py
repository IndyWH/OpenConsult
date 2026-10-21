"""The patients (spec 8; 15.10 ruling 9; 15.11 ruling 1; R11; R17; D22):
a name, a date of birth and a sex, all three required, and the age
worked out on the day; the list, last seen first, and the one search
box, matching part of a name with case and accents folded, a date of
birth typed as a date, or the patient's number exactly. The number is
the row's own id, given by the app and never typed. Every patient here
is acted (R1); the row holds no more than the three."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

from openconsult.db import Database
from openconsult.patients.audit import Audit, Clock, now_local

SEXES = ("F", "M")
FIELDS = ("name", "date_of_birth", "sex")
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


# The forms a date of birth may be typed in the search box: the form's own
# (1990-10-21), and the two a British hand writes (21/10/1990, 21.10.1990).
DATE_FORMS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y")


def parse_typed_date(text: str) -> date | None:
    for form in DATE_FORMS:
        try:
            return datetime.strptime((text or "").strip(), form).date()
        except ValueError:
            continue
    return None


def fold(text: str) -> str:
    """Case and accents folded, so Zoë matches zoe (ruling 1)."""
    plain = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in plain if not unicodedata.combining(ch)).casefold()


@dataclass(frozen=True)
class Listed:
    """One row of the Patients page: the patient and the date last seen,
    None for one never seen."""
    patient: PatientRow
    last_seen: datetime | None


def search(rows: list[Listed], query: str) -> list[Listed]:
    """The one search (ruling 1): digits alone are the number exactly, and
    failing that part of a name, so a name with digits in it is still found
    (the plan review, point 6); a date typed as a date is the date of
    birth; anything else is part of the name, folded on both sides."""
    query = (query or "").strip()
    if not query:
        return list(rows)
    if query.isdigit():
        by_number = [r for r in rows if r.patient.id == int(query)]
        if by_number:
            return by_number
    typed = parse_typed_date(query)
    if typed is not None:
        return [r for r in rows if r.patient.date_of_birth == typed]
    wanted = fold(query)
    return [r for r in rows if wanted in fold(r.patient.name)]


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

    def listed(self) -> list[Listed]:
        """Every patient, last seen first; those never seen after, the newest
        made first. Read from the tables every time (ruling 1)."""
        rows = self._db.query(
            "SELECT p.id, p.name, p.date_of_birth, p.sex, "
            "(SELECT MAX(c.started_at) FROM consultation c WHERE c.patient_id = p.id) AS last_seen "
            "FROM patient p ORDER BY last_seen IS NULL, last_seen DESC, p.id DESC")
        return [Listed(PatientRow(r["id"], r["name"], date.fromisoformat(r["date_of_birth"]), r["sex"]),
                       datetime.fromisoformat(r["last_seen"]) if r["last_seen"] else None) for r in rows]

    def get(self, patient_id: int) -> PatientRow | None:
        found = self._db.query_one("SELECT id, name, date_of_birth, sex FROM patient WHERE id = ?", (patient_id,))
        if found is None:
            return None
        return PatientRow(found["id"], found["name"], date.fromisoformat(found["date_of_birth"]), found["sex"])

    # ----------------------------------------------- corrections (ruling 2)

    def correct(self, patient_id: int, field: str, value: str, by_whom: str) -> bool:
        """One corrected detail: the current row changes, patient_change
        keeps what stood before, when and by whom, and the audit log says
        so (R2). The value is checked by the caller as the form checks it.
        False when nothing changed. No consultation row is touched."""
        if field not in FIELDS:
            raise ValueError(f"not a detail: {field}")
        current = self._db.query_one(f"SELECT {field} AS value FROM patient WHERE id = ?", (patient_id,))
        if current is None:
            raise ValueError(f"no patient {patient_id}")
        before = current["value"]
        if value == before:
            return False
        at = self._clock().isoformat(timespec="seconds")
        with self._db.transaction() as con:
            con.execute(f"UPDATE patient SET {field} = ? WHERE id = ?", (value, patient_id))
            con.execute("INSERT INTO patient_change (patient_id, field, before, after, at, by_whom) VALUES (?, ?, ?, ?, ?, ?)",
                        (patient_id, field, before, value, at, by_whom))
        self._audit.record("patient.changed", f"patient {patient_id}: {field} from {before} to {value}")
        return True

    def changes(self, patient_id: int) -> list[dict]:
        rows = self._db.query("SELECT * FROM patient_change WHERE patient_id = ? ORDER BY id", (patient_id,))
        return [dict(r) for r in rows]

    def changed_after(self, patient_id: int, moment: str) -> str | None:
        """The time of the latest correction made after the moment given
        (a consultation's start), or None: the one line of ruling 2."""
        found = self._db.query_one("SELECT MAX(at) AS at FROM patient_change WHERE patient_id = ? AND at > ?",
                                   (patient_id, moment))
        return found["at"] if found and found["at"] else None

    def today(self) -> date:
        when = self._clock()
        return when.date() if isinstance(when, datetime) else when
