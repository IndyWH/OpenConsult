"""One place that knows the whole schema, and one way to apply it.

Why this exists (HANDOVER carried work item 3, PHASE_7A_SPEC.md §3.4):
the schema lived in five module-level `SCHEMA_SQL` strings applied by five
separate `ensure_schema()` calls, and only the app's lifespan and
`tests/conftest.py` made all five. A script that imported one module got
that module's tables and nothing else, so a database could sit in a state
no single code path had ever produced. On 2026-07-25 that cost a
debugging session. Phase 7a adds a table, which is the cheapest possible
moment to pay for the fix.

The design deliberately does NOT change how the schema is expressed. The
per-module `SCHEMA_SQL` strings stay where they are, next to the code that
queries them — that locality is worth keeping. What changes is that there
is now exactly one **ordering** and one **entry point**:

    from app import schema
    schema.ensure_all()

Two things this is explicitly not, both decided in HANDOVER:

- **Not a startup refuse-to-start gate.** The app is what applies the
  schema; a gate would convert a self-healing restart into an outage.
  `ensure_all()` applies, it does not verify-then-refuse.
- **Not a check against the live database from the test suite.** That
  would break the deliberate test isolation (`tests/conftest.py`). The
  drift check is an operator tool run against whatever `DATABASE_URL`
  points at, by hand or from the after-reboot checklist.

Drift detection works by applying the DDL inside a transaction and rolling
it back, comparing an `information_schema` snapshot either side. It reports
what `ensure_all()` *would* create, without creating it. The same
rolled-back-transaction technique the admin tests already use for the
last-admin guard.
"""

from __future__ import annotations

import logging
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Application order matters: `letter` references `consultation`, `queue_entry`
# references `patient` and `app_user`. This tuple is the single ordering.
MODULE_NAMES = ("auth", "frontdesk", "consultations", "letters", "audit")


class _Rollback(Exception):
    """Raised to abandon the drift-check transaction. Never escapes."""


def _modules() -> list:
    """Imported lazily, never at module scope.

    Every app module binds DATABASE_URL at import time, and
    `tests/conftest.py` swaps the environment variable *before* importing
    anything. Importing them here at module scope would bind the live URL
    for any test run that happened to touch `app.schema` first.
    """
    import importlib

    return [importlib.import_module(f"app.{name}") for name in MODULE_NAMES]


def statements() -> list[tuple[str, str]]:
    """(module name, DDL) for every module, in application order."""
    return [(name, module.SCHEMA_SQL)
            for name, module in zip(MODULE_NAMES, _modules())]


def ensure_all() -> None:
    """Apply the whole schema. Idempotent — every statement is
    CREATE/ALTER ... IF NOT EXISTS or a guarded backfill."""
    for module in _modules():
        module.ensure_schema()


def _snapshot(conn: psycopg.Connection) -> dict[str, set[str]]:
    """Tables and columns in the public schema. Data is not compared: the
    backfill UPDATEs in SCHEMA_SQL touch rows, and rows are not drift."""
    snapshot: dict[str, set[str]] = {}
    for table, column in conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns"
        " WHERE table_schema = 'public'"
    ):
        snapshot.setdefault(table, set()).add(column)
    return snapshot


def check_drift(database_url: str | None = None) -> list[str]:
    """What `ensure_all()` would add to the target database, as a list of
    human-readable lines. Empty list means the database matches the code.

    Never mutates: the DDL runs inside a transaction that is always rolled
    back, including on success.
    """
    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    before: dict[str, set[str]] = {}
    after: dict[str, set[str]] = {}
    with psycopg.connect(url) as conn:
        try:
            before = _snapshot(conn)
            for name, sql in statements():
                conn.execute(sql)
            after = _snapshot(conn)
            raise _Rollback
        except _Rollback:
            conn.rollback()

    drift: list[str] = []
    for table in sorted(set(after) - set(before)):
        drift.append(f"missing table: {table} ({len(after[table])} columns)")
    for table in sorted(set(after) & set(before)):
        for column in sorted(after[table] - before[table]):
            drift.append(f"missing column: {table}.{column}")
    return drift
