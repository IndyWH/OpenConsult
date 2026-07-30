"""The shared schema entry point (app/schema.py).

Scope note, deliberately: these tests run against the disposable
`consultation_ai_test` database like everything else in the suite. They
say nothing about the live database — checking that one is
`scripts/migrate.py --check`'s job, run by an operator. Testing against
live would break the isolation the suite was built to have.

They are also self-referential in one specific way worth stating plainly:
`check_drift()` compares the database against the same `SCHEMA_SQL`
strings `ensure_all()` applied to build it, so "no drift" here is
evidence that the two agree with each other, not that either matches
what the app queries at runtime.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from app import schema

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")


def _db():
    return psycopg.connect(os.environ["DATABASE_URL"])


def test_ensure_all_covers_every_module_in_one_order():
    """The point of the module: one ordering, not five call sites."""
    names = [name for name, _ in schema.statements()]
    assert names == list(schema.MODULE_NAMES)
    # raw_segments added 2026-07-30 (the raw-transcript view); it sits
    # after consultations because its table references consultation(id).
    assert set(names) == {"auth", "frontdesk", "consultations", "letters",
                          "system_utterances", "raw_segments", "audit"}


def test_ensure_all_is_idempotent():
    schema.ensure_all()
    schema.ensure_all()  # would raise on a non-guarded statement


def test_no_drift_after_ensure_all():
    schema.ensure_all()
    assert schema.check_drift() == []


def test_check_drift_reports_a_missing_column_without_creating_it():
    """Drop a column, confirm the check names it, confirm the check did not
    put it back — then restore it ourselves."""
    schema.ensure_all()
    with _db() as conn:
        conn.execute("ALTER TABLE consultation DROP COLUMN quality_outcome")
        conn.commit()
    try:
        drift = schema.check_drift()
        assert "missing column: consultation.quality_outcome" in drift

        # The check rolls back: the column must still be absent afterwards.
        with _db() as conn:
            present = conn.execute(
                "SELECT 1 FROM information_schema.columns"
                " WHERE table_name = 'consultation'"
                "   AND column_name = 'quality_outcome'").fetchone()
        assert present is None, "check_drift() mutated the database"
    finally:
        schema.ensure_all()

    assert schema.check_drift() == []


def test_check_drift_reports_a_missing_table():
    schema.ensure_all()
    with _db() as conn:
        conn.execute("DROP TABLE letter_suggestion")
        conn.commit()
    try:
        drift = schema.check_drift()
        assert any(line.startswith("missing table: letter_suggestion")
                   for line in drift), drift
    finally:
        schema.ensure_all()

    assert schema.check_drift() == []


def test_migrate_check_exit_codes():
    """--check exits 0 clean, 1 on drift, and never writes."""
    import scripts.migrate as migrate

    schema.ensure_all()
    assert migrate.main(["--check"]) == 0

    with _db() as conn:
        conn.execute("ALTER TABLE consultation DROP COLUMN quality_signals")
        conn.commit()
    try:
        assert migrate.main(["--check"]) == 1
        with _db() as conn:
            present = conn.execute(
                "SELECT 1 FROM information_schema.columns"
                " WHERE table_name = 'consultation'"
                "   AND column_name = 'quality_signals'").fetchone()
        assert present is None, "--check applied the schema"
        assert migrate.main([]) == 0  # apply
        with _db() as conn:
            present = conn.execute(
                "SELECT 1 FROM information_schema.columns"
                " WHERE table_name = 'consultation'"
                "   AND column_name = 'quality_signals'").fetchone()
        assert present is not None
    finally:
        schema.ensure_all()
