"""The patients (spec 15.10 ruling 9; R11; D22): name, date of birth and
sex, all three required, and the age on the day. Every patient here is
made up."""

from datetime import date

import pytest

from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.patients.patients import PatientRow, Patients, parse_date, problem

TODAY = date(2026, 10, 20)


def test_R11_a_patient_cannot_be_saved_without_a_date_of_birth_and_a_sex():
    assert problem("", "1990-01-01", "F", TODAY) == "name"
    assert problem("Made-up", "", "F", TODAY) == "date_missing"
    assert problem("Made-up", "not a date", "F", TODAY) == "date_bad"
    assert problem("Made-up", "2027-01-01", "F", TODAY) == "date_bad"     # in the future
    assert problem("Made-up", "1905-12-31", "F", TODAY) == "date_bad"     # more than 120 years ago (R11's line stops at 120)
    assert problem("Made-up", "1906-01-01", "F", TODAY) is None
    assert problem("Made-up", "1990-01-01", "", TODAY) == "sex"
    assert problem("Made-up", "1990-01-01", "female", TODAY) == "sex"
    assert problem("Made-up", "1990-01-01", "F", TODAY) is None           # the twin
    assert parse_date(" 1990-01-01 ") == date(1990, 1, 1) and parse_date("1990-13-01") is None


def test_R11_the_table_itself_refuses_a_patient_with_no_sex_or_date(tmp_path):
    import sqlite3
    db = open_database(tmp_path / "openconsult.db")
    patients = Patients(db, Audit(db))
    with pytest.raises(ValueError):
        patients.add("Made-up", date(1990, 1, 1), "X")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('a', '1990-01-01', 'X', 't')")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('a', NULL, 'F', 't')")
    saved = patients.add("  Made-up  ", date(1990, 1, 1), "F")
    assert patients.get(saved.id) == PatientRow(saved.id, "Made-up", date(1990, 1, 1), "F")
    assert patients.get(saved.id + 1) is None
    assert Audit(db).lines()[0].event == "patient.saved"
    db.close()


@pytest.mark.parametrize("born, day, age", [
    (date(1990, 10, 20), date(2026, 10, 20), 36),    # the birthday itself
    (date(1990, 10, 21), date(2026, 10, 20), 35),    # the birthday is tomorrow
    (date(1990, 10, 19), date(2026, 10, 20), 36),
    (date(2026, 3, 1), date(2026, 10, 20), 0),       # a baby
    (date(2008, 10, 21), date(2026, 10, 20), 17),    # still a girl or boy for the patient line
])
def test_D22_the_age_is_worked_out_on_the_day(born, day, age):
    assert PatientRow(1, "Made-up", born, "F").age_on(day) == age
