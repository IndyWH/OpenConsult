"""The one audit recorder (spec 6.5, 15.6)."""

from datetime import datetime, timedelta, timezone

from openconsult.db import open_database
from openconsult.patients.audit import Audit


def test_6_5_the_recorder_adds_the_time_itself_and_lists_newest_first(tmp_path):
    # Pins spec 6.5: in v1 the time was typed out at every one of 97
    # call sites. Here the recorder stamps it from its own clock.
    times = iter([datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=n) for n in range(3)])
    audit = Audit(open_database(tmp_path / "openconsult.db"), clock=lambda: next(times))
    audit.record("statement.accepted")
    audit.record("user.set_up", "Dr Example")
    audit.record("login")
    lines = audit.lines()
    assert [line.event for line in lines] == ["login", "user.set_up", "statement.accepted"]
    assert lines[0].at == "2026-10-04T09:02:00+00:00"
    assert lines[1].detail == "Dr Example"
