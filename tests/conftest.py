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
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

# The suite drives the app over http://testserver, and a `Secure` cookie is
# not sent over plaintext HTTP — so with the production default every
# authenticated test would lose its session. Turned off HERE and only here;
# app/main.py defaults it to secure, so a forgotten variable in production
# fails safe (2026-07-31 audit, Finding 6). Set — not setdefault — before
# any app import: load_dotenv() above has already read .env, and since
# 2026-09-10 .env.example documents SESSION_COOKIE_SECURE=true explicitly,
# so a fresh clone's .env would otherwise carry the production value into
# the suite and fail 33 cookie-bearing tests (the launch-day fresh-clone
# run found exactly that). The suite's outcome must not depend on .env.
os.environ["SESSION_COOKIE_SECURE"] = "false"

# app/auth.py refuses to start without a real SECRET_KEY (import-time
# fail-fast, 2026-08-04). The suite must pass on a box with no .env, and
# must never sign test cookies with this machine's production key — so the
# whole session runs on a fresh random valid key. Set (not setdefault)
# before any app import; the guard itself is exercised by
# tests/test_secret_key_guard.py, never weakened here.
os.environ["SECRET_KEY"] = secrets.token_hex(32)

# The suite must not read the live .env's AUTO_MODE_ENABLED (pilot fix
# slice 5, 2026-09-10): app/main.py binds the gate at import, and the
# pre-7c tests pin the app's behaviour with the gate DOWN. Pinned off here
# for the whole session — set, not setdefault, so neither the shell's
# environment nor .env can raise it — and again per test by the autouse
# fixture below, so the count and the outcome are the same with
# AUTO_MODE_ENABLED=true in the environment as without. A test that wants
# the machine opts in with monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED",
# True) (tests/auto_harness.py's gate fixture does).
os.environ["AUTO_MODE_ENABLED"] = "false"

# The suite must never write into the owner's recordings (Task 16,
# 2026-10-04). app/main.py (and scripts/manage_consultations.py,
# scripts/reset_demo.py) bind RECORDINGS_DIR at import, and .env names the
# real data/recordings. Until now each test had to opt out with its own
# monkeypatch; tests/test_live.py never did, so every run wrote the 11 s
# JFK fixture over consultation_<cid>.wav — and since the suite moved to a
# fresh test database (2026-07-24), whose consultation ids restart at 1,
# that cid was a LIVE consultation's number. Consultations 68 and 161 lost
# their audio that way. Set — not setdefault — after load_dotenv(), for the
# whole session, so no test, present or future, can reach the real folder
# by forgetting; the per-test monkeypatches stay and still give each test
# its own directory. Removed at session end (fixture below).
_RECORDINGS_TMP = tempfile.mkdtemp(prefix="consultation_ai_test_recordings_")
os.environ["RECORDINGS_DIR"] = _RECORDINGS_TMP

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

    # Sentinel admin. Predates the deletion of auth's count==0 auto-admin
    # bootstrap (2026-08-04) and deliberately kept: the suite's admin
    # presence stays deterministic rather than resting on collection
    # order, and if the deleted bootstrap ever came back, it still could
    # not promote a test registration. Password is random and discarded.
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


@pytest.fixture(autouse=True)
def _auto_mode_gate_down(monkeypatch):
    """Every test starts with the Phase 7c gate down (see the module
    docstring's note on AUTO_MODE_ENABLED); a test that wants auto mode
    sets the attribute itself, after this fixture, and monkeypatch restores
    it either way."""
    if _DB_READY:  # app modules are only imported once the test DB exists
        from app import main as appmain

        monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", False)
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


@pytest.fixture(scope="session", autouse=True)
def _recordings_tmp_dir():
    """Removes the session's recordings directory (see RECORDINGS_DIR above)."""
    yield
    shutil.rmtree(_RECORDINGS_TMP, ignore_errors=True)


# The recordings guard (Task 16, 2026-10-04). RECORDINGS_DIR above keeps
# every test away from the owner's data/recordings; this proves it, every
# run. The folder is snapshotted when this conftest loads — before any test
# — and compared at session end: a file created, removed or changed there
# fails the run and is named. Size, inode, mtime and ctime are compared, so
# a rewrite with identical bytes (the JFK fixture over itself) is caught
# too. Recording a consultation in the running app during a suite run will
# also trip it; that is the honest result, not a false alarm to silence.
# Pinned by tests/test_recordings_guard.py.
_REPO_RECORDINGS = (Path(__file__).parent.parent / "data" / "recordings").resolve()


def recordings_snapshot(directory: Path) -> dict[str, tuple[int, int, int, int]]:
    """name -> (size, inode, mtime_ns, ctime_ns); {} if the folder is absent."""
    try:
        entries = list(os.scandir(directory))
    except FileNotFoundError:
        return {}
    snapshot = {}
    for entry in entries:
        st = entry.stat(follow_symlinks=False)
        snapshot[entry.name] = (st.st_size, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
    return snapshot


def recordings_changes(before: dict, after: dict) -> list[str]:
    return ([f"created {n}" for n in sorted(after.keys() - before.keys())]
            + [f"removed {n}" for n in sorted(before.keys() - after.keys())]
            + [f"changed {n}" for n in sorted(before.keys() & after.keys())
               if before[n] != after[n]])


def apply_recordings_guard(session, before: dict, directory: Path) -> list[str]:
    """Fail the session if `directory` moved since `before`; returns the changes."""
    changes = recordings_changes(before, recordings_snapshot(directory))
    if changes:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    return changes


_RECORDINGS_BEFORE = recordings_snapshot(_REPO_RECORDINGS)
_recordings_guard_report: list[str] = []


def pytest_sessionfinish(session, exitstatus):
    _recordings_guard_report[:] = apply_recordings_guard(
        session, _RECORDINGS_BEFORE, _REPO_RECORDINGS)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if _recordings_guard_report:
        terminalreporter.section("RECORDINGS GUARD FAILED", sep="!", red=True, bold=True)
        terminalreporter.write_line(
            f"This run touched the owner's recordings in {_REPO_RECORDINGS}:")
        for change in _recordings_guard_report:
            terminalreporter.write_line(f"  {change}", red=True)
        terminalreporter.write_line(
            "Tests must write recordings only to RECORDINGS_DIR (a temp dir,"
            " set in tests/conftest.py). Check the backup before anything else.")
