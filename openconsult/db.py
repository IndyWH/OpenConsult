"""The one place that opens the database (spec 6.5).

SQLite, from Python's own library: one file in the data folder, nothing
to install or start (spec 6.3). The tables come from schema.py and are
applied by version number.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from openconsult import schema


class NewerDatabase(Exception):
    """The data folder was made by a newer OpenConsult than this one."""


class Database:
    """A thin door to one SQLite connection, opened in autocommit mode.
    One user, one writer, so one lock is enough."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._connection.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._connection.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(sql, params).fetchone()

    def version(self) -> int:
        return stored_version(self._connection)

    def tables(self) -> list[str]:
        rows = self.query("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        return [row["name"] for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def open_database(path: Path) -> Database:
    """Open the file, creating it if absent, and bring its tables up to
    the current version."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return Database(connection)


def stored_version(connection: sqlite3.Connection) -> int:
    has_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    if not has_table:
        return 0
    row = connection.execute("SELECT version FROM schema_version").fetchone()
    return int(row[0]) if row else 0


def migrate(connection: sqlite3.Connection) -> None:
    """Apply every version above the stored one, each in its own
    transaction, so a failure leaves the file at a whole version."""
    stored = stored_version(connection)
    if stored > schema.VERSION:
        raise NewerDatabase(stored)
    for version in range(stored + 1, schema.VERSION + 1):
        try:
            connection.execute("BEGIN")
            for statement in _statements(schema.MIGRATIONS[version]):
                connection.execute(statement)
            if version > 1:
                connection.execute("UPDATE schema_version SET version = ?", (version,))
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise


def _statements(script: str) -> list[str]:
    """Split a script into statements. Triggers hold semicolons inside
    BEGIN ... END, so the split waits for the END."""
    statements, current, in_trigger = [], [], False
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True
        if in_trigger and stripped.upper() == "END;":
            in_trigger = False
        if stripped.endswith(";") and not in_trigger:
            statements.append("\n".join(current))
            current = []
    return statements
