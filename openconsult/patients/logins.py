"""Logins, kept in the app's own memory (spec 15.6).

A login is a long random value in a session cookie. It ends at logout,
when the browser closes, when the app stops, after 30 minutes with no
use, or when the password changes. No secret is stored, so nothing can
leak or outlive the app (V1_LESSONS 10.2).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from openconsult.patients.audit import Audit, Clock, now_local

# The app locks itself after this long with no use, and asks for the
# password again. Source: the owner's ruling of 4 Oct 2026 (spec 15.6
# ruling 5). It is not a setting.
LOCK_AFTER = timedelta(minutes=30)

# Each wrong password makes the next try wait longer: this long after the
# first, doubling each time, never more than the cap. A right password or
# a restart clears it. The user is never locked out for good; the reset
# command is the way back. Source: the stage 2 plan review of 4 Oct 2026
# (answer c). A design choice, not a measurement.
FIRST_WAIT = timedelta(seconds=1)
LONGEST_WAIT = timedelta(minutes=5)


@dataclass
class Login:
    token: str
    generation: int
    last_used: datetime


@dataclass(frozen=True)
class Found:
    """What the guard learns about a cookie: a live login, or why not."""
    login: Login | None
    reason: str | None  # None, "locked", "password_changed" or "unknown"


class Logins:
    def __init__(self, audit: Audit, clock: Clock = now_local):
        self._audit = audit
        self._clock = clock
        self._logins: dict[str, Login] = {}
        self._wrong_tries = 0
        self._next_try_at: datetime | None = None
        # Stage 6 sets this while a consultation runs, so the doctor is
        # never shut out in front of a patient (15.6 ruling 5).
        self.consultation_running = False

    def start(self, generation: int) -> str:
        token = secrets.token_urlsafe(32)
        self._logins[token] = Login(token, generation, self._clock())
        return token

    def find(self, token: str | None, generation: int, touch: bool = True) -> Found:
        """The login for a cookie, if it is still live. A request that is
        use touches it; the page's own timed check does not (plan review,
        change 2), so two open tabs cannot keep each other alive."""
        login = self._logins.get(token or "")
        if login is None:
            return Found(None, "unknown")
        now = self._clock()
        if login.generation != generation:
            del self._logins[token]
            return Found(None, "password_changed")
        if not self.consultation_running and now - login.last_used >= LOCK_AFTER:
            del self._logins[token]
            self._audit.record("lock")
            return Found(None, "locked")
        if touch:
            login.last_used = now
        return Found(login, None)

    def seconds_left(self, login: Login) -> int:
        """How long until this login locks with no further use."""
        left = login.last_used + LOCK_AFTER - self._clock()
        return max(0, int(left.total_seconds()))

    def tokens(self) -> list[str]:
        return list(self._logins)

    def end(self, token: str | None) -> None:
        self._logins.pop(token or "", None)

    def end_all_except(self, token: str | None) -> None:
        self._logins = {t: login for t, login in self._logins.items() if t == token}

    def wait_left(self) -> int:
        """Seconds before the next password may be tried; 0 means now."""
        if self._next_try_at is None:
            return 0
        left = self._next_try_at - self._clock()
        return max(0, int(-(-left.total_seconds() // 1)))

    def wrong_password(self) -> int:
        """Record a wrong password and return the wait before the next try."""
        self._wrong_tries += 1
        wait = min(FIRST_WAIT * 2 ** (self._wrong_tries - 1), LONGEST_WAIT)
        self._next_try_at = self._clock() + wait
        self._audit.record("login.wrong_password")
        return int(wait.total_seconds())

    def right_password(self) -> None:
        self._wrong_tries = 0
        self._next_try_at = None
