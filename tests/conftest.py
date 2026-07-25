"""Test-database isolation: pytest never touches the live database.

At session start this conftest creates a fresh `consultation_ai_test`
database on the same Postgres server, points DATABASE_URL at it BEFORE
any app module is imported (they all bind the URL at import time), builds
the schema via the app's own `schema.ensure_all()` — the same entry point
and the same ordering the app lifespan uses, so the test database can
never be built from a different set of tables — copies the
guideline corpus tables from the live database (read-only) so the RAG
tests keep their coverage, and seeds a sentinel admin so auth's
"first account becomes admin" bootstrap can't promote a mid-suite test
registration. The whole database is dropped again at session end.

Requires two one-time grants (superuser, documented in HANDOVER):

    sudo -u postgres sh -c 'psql -c "ALTER ROLE consultation_app CREATEDB;" \
      && psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector;"'

(CREATEDB lets the test session create/drop its database; pgvector is an
untrusted extension, so it must live in template1 for new databases to
inherit it.) If the grants are missing the suite refuses to run rather
than fall back to the live database; if Postgres itself is absent,
DB-dependent tests self-skip exactly as before.
"""

import os
import secrets
import subprocess
import urllib.parse

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

TEST_DB_NAME = "consultation_ai_test"

_ONE_TIME_HELP = (
    "\n\nTest-database bootstrap failed: {reason}.\n"
    "Run the one-time setup (superuser, safe to re-run):\n\n"
    "  sudo -u postgres sh -c 'psql -c \"ALTER ROLE consultation_app CREATEDB;\""
    " && psql -d template1 -c \"CREATE EXTENSION IF NOT EXISTS vector;\"'\n\n"
    "The suite refuses to fall back to the live database.\n"
)


def _swap_db(url: str, dbname: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parts._replace(path="/" + dbname))


LIVE_URL = os.environ.get("DATABASE_URL", "")
TEST_URL = _swap_db(LIVE_URL, TEST_DB_NAME) if LIVE_URL else ""


def _copy_corpus_tables() -> None:
    """Guideline corpus, read-only from live → test, so RAG tests run.
    Best-effort: with no corpus (or no pg_dump) those tests self-skip."""
    try:
        dump = subprocess.run(
            ["pg_dump", LIVE_URL, "-t", "guideline_source", "-t", "guideline_chunk"],
            capture_output=True, timeout=120,
        )
        if dump.returncode != 0:
            return
        subprocess.run(
            ["psql", "-q", TEST_URL], input=dump.stdout,
            capture_output=True, timeout=120, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _bootstrap_test_database() -> bool:
    """Fresh test DB, schema, corpus copy, sentinel admin.
    Returns False when Postgres is absent (tests self-skip as before)."""
    if not LIVE_URL:
        return False
    try:
        admin = psycopg.connect(LIVE_URL, connect_timeout=2, autocommit=True)
    except Exception:
        return False
    with admin:
        try:
            admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
            admin.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        except psycopg.errors.InsufficientPrivilege:
            pytest.exit(_ONE_TIME_HELP.format(reason="CREATEDB not granted"), returncode=3)

    with psycopg.connect(TEST_URL) as conn:
        vector_installed = conn.execute(
            "SELECT installed_version FROM pg_available_extensions WHERE name = 'vector'"
        ).fetchone()[0]
        if not vector_installed:
            pytest.exit(
                _ONE_TIME_HELP.format(reason="pgvector missing from template1"),
                returncode=3,
            )

    # Every app module binds DATABASE_URL at import time — swap the env
    # first, then import; nothing imports the app before this conftest.
    os.environ["DATABASE_URL"] = TEST_URL
    from app import auth, schema

    # One entry point, one ordering — the same call the app lifespan makes,
    # so the test database can never be built from a different set of
    # tables than the running app has (app/schema.py).
    schema.ensure_all()

    _copy_corpus_tables()

    # Sentinel admin: with it in place, auth's count==0 bootstrap can never
    # promote a test registration to admin. Password is random and discarded.
    with psycopg.connect(TEST_URL) as conn:
        conn.execute(
            "INSERT INTO app_user (username, password_hash, display_name, role)"
            " VALUES ('bootstrap_admin', %s, 'Bootstrap Admin', 'admin')",
            (auth.hash_password(secrets.token_hex(16)),),
        )
    return True


_DB_READY = _bootstrap_test_database()


def approve_account(username: str) -> None:
    """Stand in for the admin's approval click: public registration is
    approve-to-activate (2026-07-24), so tests that register over HTTP
    approve the account here, then log in for their session cookie."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "UPDATE app_user SET active = true, pending_approval = false"
            " WHERE username = %s",
            (username,),
        )


@pytest.fixture(autouse=True)
def _reset_auth_rate_limits():
    """Every TestClient shares one synthetic address, so the suite's
    registrations/logins would trip the per-IP auth limits across test
    boundaries. Reset between tests; within a test the limits are real
    (that's what test_auth_hardening exercises)."""
    if _DB_READY:  # app modules are only imported once the test DB exists
        from app import ratelimit

        ratelimit.login_limiter.reset()
        ratelimit.register_limiter.reset()
    yield


@pytest.fixture(scope="session", autouse=True)
def test_database():
    yield
    if not _DB_READY:
        return
    try:
        with psycopg.connect(LIVE_URL, connect_timeout=2, autocommit=True) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
    except Exception as exc:  # leaving the test DB behind is harmless
        print(f"\n[conftest] could not drop {TEST_DB_NAME}: {exc}")
