"""Session-wide test-data cleanup.

The suite runs against the real dev database (heavy tests self-skip when
it's absent), and several tests exercise the front-desk flow by creating
real patients, queue entries, and consultations — which used to
accumulate in the owner's Today view and worklist after every run.

Strategy: snapshot the max id of each littered table before the session,
delete everything above the watermark afterwards. This covers every test
file with one mechanism and no per-test bookkeeping. CAVEAT, documented
deliberately: rows created in the app by a human DURING a pytest run
would fall above the watermark and be deleted too — don't use the app
while the suite runs. Audit rows and app_user rows are never touched
(append-only log; accounts are governance-managed, see HANDOVER).
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

_TABLES = ("consultation", "queue_entry", "patient")  # delete in this order


def _connect():
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_rows():
    try:
        with _connect() as conn:
            marks = {
                t: conn.execute(f"SELECT COALESCE(max(id), 0) FROM {t}").fetchone()[0]
                for t in _TABLES
            }
    except Exception:  # no database: nothing to clean either
        yield
        return

    yield

    with _connect() as conn:
        deleted = {}
        for table in _TABLES:  # consultations first (turns/notes cascade)
            deleted[table] = len(
                conn.execute(
                    f"DELETE FROM {table} WHERE id > %s RETURNING id",
                    (marks[table],),
                ).fetchall()
            )
    if any(deleted.values()):
        print(f"\n[conftest] cleaned up test rows: {deleted}")
