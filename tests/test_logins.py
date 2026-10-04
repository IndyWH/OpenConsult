"""Logins in memory, the 30 minute lock and the growing wait
(spec 15.6; ruling 5; V1_LESSONS 10.2)."""

from datetime import datetime, timedelta, timezone

import pytest

from openconsult.db import open_database
from openconsult.patients.audit import Audit
from openconsult.patients.logins import LOCK_AFTER, LONGEST_WAIT, Logins


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def logins(tmp_path):
    clock = FakeClock()
    audit = Audit(open_database(tmp_path / "openconsult.db"), clock=clock)
    return Logins(audit, clock=clock), clock, audit


def test_ruling_5_a_login_locks_after_30_minutes_with_no_use(logins):
    logins, clock, audit = logins
    token = logins.start(generation=1)
    clock.advance(seconds=LOCK_AFTER.total_seconds())
    found = logins.find(token, generation=1)
    assert found.login is None and found.reason == "locked"
    assert audit.lines()[0].event == "lock"
    assert logins.find(token, generation=1).reason == "unknown"


def test_ruling_5_use_inside_30_minutes_keeps_the_login(logins):
    logins, clock, _ = logins
    token = logins.start(generation=1)
    for _ in range(3):
        clock.advance(minutes=29)
        assert logins.find(token, generation=1).login is not None
    # The page's own timed check is not use, so it does not push the lock back.
    clock.advance(minutes=29)
    assert logins.find(token, generation=1, touch=False).login is not None
    clock.advance(minutes=1)
    assert logins.find(token, generation=1, touch=False).reason == "locked"


def test_ruling_5_a_running_consultation_never_locks(logins):
    logins, clock, _ = logins
    token = logins.start(generation=1)
    logins.consultation_running = True
    clock.advance(hours=3)
    assert logins.find(token, generation=1, touch=False).login is not None
    logins.consultation_running = False
    assert logins.find(token, generation=1, touch=False).reason == "locked"


def test_15_6_each_wrong_password_makes_the_next_try_wait_longer_and_never_for_good(logins):
    logins, clock, audit = logins
    assert logins.wait_left() == 0
    waits = [logins.wrong_password() for _ in range(4)]
    assert waits == sorted(waits) and len(set(waits)) == 4
    assert logins.wait_left() == waits[-1]
    for _ in range(20):
        logins.wrong_password()
    assert logins.wait_left() <= LONGEST_WAIT.total_seconds()
    clock.advance(seconds=LONGEST_WAIT.total_seconds())
    assert logins.wait_left() == 0
    logins.right_password()
    assert logins.wrong_password() == waits[0]
    assert audit.lines()[0].event == "login.wrong_password"


def test_15_6_a_change_of_password_ends_every_other_login(logins):
    logins, _, _ = logins
    mine = logins.start(generation=1)
    other = logins.start(generation=1)
    logins.end_all_except(mine)
    assert logins.find(other, generation=1).reason == "unknown"
    assert logins.find(mine, generation=1).login is not None
    # A reset in another process raises the generation; the app sees it.
    assert logins.find(mine, generation=2).reason == "password_changed"


def test_10_2_a_login_cannot_outlive_the_app(logins, tmp_path):
    # Pins V1_LESSONS 10.2: v1's signed cookie survived a restart and a
    # reset. Here a token means nothing to a fresh app, and the data
    # folder holds no secret that could make it mean something.
    logins, clock, audit = logins
    token = logins.start(generation=1)
    fresh = Logins(audit, clock=clock)
    assert fresh.find(token, generation=1).reason == "unknown"
    assert [p.name for p in tmp_path.iterdir()] == ["openconsult.db"]
