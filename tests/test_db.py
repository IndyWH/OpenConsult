"""The one database module and its versioned tables (spec 6.5, 15.6)."""

import sqlite3

import pytest

from openconsult import schema
from openconsult.db import NewerDatabase, open_database


def test_6_5_a_fresh_database_has_every_table_at_the_current_version(tmp_path):
    db = open_database(tmp_path / "data" / "openconsult.db")
    assert db.version() == schema.VERSION
    assert {"app_user", "audit_log", "first_run", "schema_version"} <= set(db.tables())
    db.close()


def test_6_5_opening_the_database_again_changes_nothing(tmp_path):
    path = tmp_path / "openconsult.db"
    first = open_database(path)
    first.execute("INSERT INTO first_run (step, done_at) VALUES (?, ?)", ("statement", "t"))
    first.close()
    second = open_database(path)
    assert second.version() == schema.VERSION
    assert second.query_one("SELECT step FROM first_run")["step"] == "statement"
    second.close()


def test_6_5_a_database_from_a_newer_version_is_refused(tmp_path):
    # Pins V1_LESSONS 6.2: tables change by version number, never by
    # guesswork against whatever file is there.
    path = tmp_path / "openconsult.db"
    open_database(path).close()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE schema_version SET version = ?", (schema.VERSION + 1,))
    raw.commit()
    raw.close()
    with pytest.raises(NewerDatabase):
        open_database(path)


def test_15_6_an_audit_line_can_never_be_changed_or_removed(tmp_path):
    db = open_database(tmp_path / "openconsult.db")
    db.execute("INSERT INTO audit_log (at, event) VALUES (?, ?)", ("t", "login"))
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE audit_log SET event = 'logout'")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("DELETE FROM audit_log")
    assert db.query_one("SELECT event FROM audit_log")["event"] == "login"
    db.close()
