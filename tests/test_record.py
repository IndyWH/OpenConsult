"""The record of model calls and table version 2 (spec 6.3, 6.5, 15.7;
R20; V1_LESSONS 3.12, 3.13, 6.2)."""

import sqlite3

import pytest

from openconsult import schema
from openconsult.app import build_app
from openconsult.db import Database, _statements, open_database
from openconsult.llm.record import CallRow, ModelCalls
from openconsult.patients.audit import Audit
from openconsult.patients.users import Users
from openconsult.settings import store
from tests.conftest import PASSWORD, PORT, browser, log_in


def version_1_database(path):
    """A data folder as stage 2's code left it: its tables only, with a user."""
    raw = sqlite3.connect(path, isolation_level=None)
    raw.row_factory = sqlite3.Row
    for statement in _statements(schema.MIGRATIONS[1]):
        raw.execute(statement)
    db = Database(raw)
    Users(db, Audit(db)).set_up("Dr", "Made-up", PASSWORD)
    db.execute("INSERT INTO first_run (step, done_at) VALUES ('statement', 't'), ('machine', 't')")
    assert db.version() == 1 and "model_call" not in db.tables()
    db.close()


def test_6_5_a_version_1_database_with_its_user_comes_forward_with_nothing_lost(tmp_path, machine, clock):
    path = tmp_path / "openconsult.db"
    version_1_database(path)
    db = open_database(path)
    assert db.version() == schema.VERSION and "model_call" in db.tables()
    user = db.query_one("SELECT title, name FROM app_user")
    assert (user["title"], user["name"]) == ("Dr", "Made-up")
    assert db.query_one("SELECT event FROM audit_log")["event"] == "user.set_up"
    assert len(db.query("SELECT step FROM first_run")) == 2
    db.close()
    # And the user logs in through the app, with no first run asked again.
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock)
    client = browser(app)
    assert log_in(client).headers["location"] == "/"
    assert client.get("/").status_code == 200


def a_row(**changes) -> CallRow:
    base = dict(job="alarm", engine="made-up", engine_version="0.0", model_tag="made-up:tag",
                model_digest="abc", prompt_sha256="p" * 64, request='{"made": "up"}',
                reply='{"ok": true}', prompt_tokens=10, output_tokens=5, wall_ms=12,
                total_ms=11, load_ms=1, read_ms=2, write_ms=8, outcome="ok", detail=None)
    base.update(changes)
    return CallRow(**base)


def test_R20_the_store_keeps_every_field_of_a_call_and_stamps_the_time(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    calls = ModelCalls(db, clock)
    first = calls.add(a_row())
    second = calls.add(a_row(outcome="too_long", detail="cut at 1000 tokens", reply=None))
    rows = calls.rows(newest_first=False)
    assert [r["id"] for r in rows] == [first, second]
    assert rows[0]["at"].startswith("2026-10-04T09:00")
    assert rows[0]["request"] == '{"made": "up"}' and rows[0]["model_digest"] == "abc"
    assert rows[1]["outcome"] == "too_long" and rows[1]["detail"] == "cut at 1000 tokens"
    assert calls.get(second)["reply"] is None
    with pytest.raises(ValueError):
        calls.add(a_row(outcome="not-a-kind"))
    db.close()
