"""The one user (spec 7.1, 15.6): a title, a name and a password.

The password is stored only as a hash, with the method ported from v1
app/auth.py (spec 6.1): scrypt with a 16 byte salt, in the same stored
form, so the port is pinned by a hash v1 made.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from openconsult.db import Database
from openconsult.patients.audit import Audit, Clock, now_local

# At least 8 characters, as in v1 (spec 15.6).
MIN_PASSWORD = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def password_problem(password: str, again: str) -> str | None:
    """None when the new password may be used, else "short" or "differ"."""
    if len(password) < MIN_PASSWORD:
        return "short"
    if password != again:
        return "differ"
    return None


def name_problem(name: str) -> str | None:
    return "missing" if not name.strip() else None


class AlreadySetUp(Exception):
    pass


class NoUser(Exception):
    pass


@dataclass(frozen=True)
class User:
    title: str
    name: str
    generation: int

    @property
    def full_name(self) -> str:
        return f"{self.title} {self.name}".strip()


class Users:
    def __init__(self, db: Database, audit: Audit, clock: Clock = now_local):
        self._db = db
        self._audit = audit
        self._clock = clock

    def get(self) -> User | None:
        row = self._db.query_one("SELECT title, name, password_generation FROM app_user")
        return User(row["title"], row["name"], row["password_generation"]) if row else None

    def exists(self) -> bool:
        return self.get() is not None

    def set_up(self, title: str, name: str, password: str) -> User:
        """The first run's last step. Fields are checked by the caller
        with name_problem and password_problem; this refuses a second user."""
        if self.exists():
            raise AlreadySetUp()
        self._db.execute(
            "INSERT INTO app_user (id, title, name, password_hash, created_at)"
            " VALUES (1, ?, ?, ?, ?)",
            (title.strip(), name.strip(), hash_password(password),
             self._clock().isoformat(timespec="seconds")),
        )
        user = self.get()
        self._audit.record("user.set_up", user.full_name)
        return user

    def verify(self, password: str) -> bool:
        row = self._db.query_one("SELECT password_hash FROM app_user")
        return bool(row) and verify_password(password, row["password_hash"])

    def change_details(self, title: str, name: str) -> User:
        """Title and name, each change audited from what to what
        (15.6 ruling 7)."""
        before = self._require()
        title, name = title.strip(), name.strip()
        self._db.execute("UPDATE app_user SET title = ?, name = ?", (title, name))
        if title != before.title:
            self._audit.record("title.changed", f"from {before.title or '(none)'} to {title or '(none)'}")
        if name != before.name:
            self._audit.record("name.changed", f"from {before.name} to {name}")
        return self.get()

    def change_password(self, new_password: str) -> User:
        return self._set_password(new_password, "password.changed")

    def reset_password(self, new_password: str) -> User:
        """The reset command's way in (D26). Changes the password and
        nothing else."""
        return self._set_password(new_password, "password.reset")

    def _set_password(self, new_password: str, event: str) -> User:
        self._require()
        self._db.execute(
            "UPDATE app_user SET password_hash = ?,"
            " password_generation = password_generation + 1",
            (hash_password(new_password),),
        )
        self._audit.record(event)
        return self.get()

    def _require(self) -> User:
        user = self.get()
        if user is None:
            raise NoUser()
        return user
