"""Users, sessions, and role-based access (Phase 6).

Sessions are HMAC-signed cookies (stdlib only): "uid.expiry.signature".
The cookie carries identity; the role is looked up fresh per request so a
role change takes effect immediately. Passwords are scrypt-hashed.

Roles: doctor, receptionist, admin. Server-side enforcement lives in the
dependencies below — the receptionist must never reach transcripts,
notes, or review pages (plan §2), and the UI merely reflects what the
server already enforces.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

import psycopg
from dotenv import load_dotenv
from fastapi import Cookie, HTTPException

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
SESSION_TTL_S = 12 * 3600
COOKIE_NAME = "session"

ROLES = ("doctor", "receptionist", "admin")
CLINICAL_ROLES = ("doctor", "admin")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_user (
    id serial PRIMARY KEY,
    username text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    display_name text NOT NULL,
    role text NOT NULL CHECK (role IN ('doctor', 'receptionist', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now()
);
-- Governance: accounts are deactivated, never deleted — audit rows and
-- consultations reference them and the names must survive for the record.
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS last_login_at timestamptz;
-- Approve-to-activate (2026-07-24, public exposure): public registrations
-- start inactive with this flag set; the admin's approval activates them.
-- Distinguishes "never approved" from "deactivated by governance".
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS pending_approval boolean NOT NULL DEFAULT false;
"""


def ensure_schema() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(SCHEMA_SQL)


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------------- sessions

def sign_session(user_id: int) -> str:
    expiry = int(time.time()) + SESSION_TTL_S
    message = f"{user_id}.{expiry}"
    signature = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256)
    return f"{message}.{signature.hexdigest()}"


def verify_session(token: str | None) -> int | None:
    if not token:
        return None
    try:
        uid, expiry, signature = token.split(".")
        message = f"{uid}.{expiry}"
        expected = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256)
        if not hmac.compare_digest(signature, expected.hexdigest()):
            return None
        if int(expiry) < time.time():
            return None
        return int(uid)
    except (ValueError, TypeError):
        return None


# -------------------------------------------------------------------- users

async def _conn() -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(DATABASE_URL)


def _row_to_user(row) -> dict:
    return {"id": row[0], "username": row[1], "display_name": row[2], "role": row[3]}


async def list_users() -> list[dict]:
    """The admin Users view: every account, active or not."""
    async with await _conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT id, username, display_name, role, created_at,"
                " last_login_at, active, pending_approval FROM app_user ORDER BY id"
            )
        ).fetchall()
    return [
        {"id": r[0], "username": r[1], "display_name": r[2], "role": r[3],
         "created_at": str(r[4])[:16], "last_login_at": str(r[5])[:16] if r[5] else None,
         "active": r[6], "pending_approval": r[7]}
        for r in rows
    ]


async def set_user_active(user_id: int, active: bool, conn=None) -> bool:
    """Deactivate/reactivate an account. Deactivation is refused (returns
    False) when it would leave no active admin — the guard is inside the
    UPDATE so a concurrent deactivation can't slip past it. The optional
    conn lets tests exercise the last-admin guard inside a rolled-back
    transaction instead of touching real accounts."""
    sql = (
        "UPDATE app_user SET active = %s,"
        " pending_approval = pending_approval AND NOT %s"  # activation = approval
        " WHERE id = %s AND (%s OR"
        " role != 'admin' OR EXISTS (SELECT 1 FROM app_user"
        "   WHERE role = 'admin' AND active AND id != %s)) RETURNING id"
    )
    params = (active, active, user_id, active, user_id)
    if conn is not None:
        return await (await conn.execute(sql, params)).fetchone() is not None
    async with await _conn() as conn:
        return await (await conn.execute(sql, params)).fetchone() is not None


async def is_pending_approval(user_id: int) -> bool:
    """Lets the activation endpoint tell a first approval (audit
    user.activated) from reactivating a governance-deactivated account
    (audit user.reactivated)."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT pending_approval FROM app_user WHERE id = %s", (user_id,)
            )
        ).fetchone()
    return bool(row and row[0])


async def create_user(
    username: str, password: str, display_name: str, role: str, *, pending: bool = False
) -> dict:
    """pending=True is the public-registration path: the account is created
    inactive and awaits the admin's approval. Direct callers (CLI, tests)
    keep the default and get an active account."""
    if role not in ROLES:
        raise ValueError(f"invalid role {role!r}")
    async with await _conn() as conn:
        count = (await (await conn.execute("SELECT count(*) FROM app_user")).fetchone())[0]
        if count == 0:
            role = "admin"  # bootstrap: the first account administers the rest
            pending = False  # …so it must be able to log in
        row = await (
            await conn.execute(
                "INSERT INTO app_user"
                " (username, password_hash, display_name, role, active, pending_approval)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " RETURNING id, username, display_name, role, pending_approval",
                (username, hash_password(password), display_name, role,
                 not pending, pending),
            )
        ).fetchone()
    return {**_row_to_user(row), "pending_approval": row[4]}


async def get_user(user_id: int) -> dict | None:
    """Active accounts only: a deactivated user's (still-signed) session
    cookies stop resolving to a user, which is what invalidates them."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, username, display_name, role FROM app_user"
                " WHERE id = %s AND active", (user_id,),
            )
        ).fetchone()
    return _row_to_user(row) if row else None


async def authenticate(username: str, password: str) -> tuple[dict | None, str | None]:
    """(user, None) on success; (None, reason) otherwise. The reason is
    'awaiting_approval' only when the password is CORRECT on a pending
    account — the applicant may learn their own status. A governance-
    deactivated account stays indistinguishable from bad credentials."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, username, display_name, role, password_hash,"
                " active, pending_approval"
                " FROM app_user WHERE username = %s", (username,),
            )
        ).fetchone()
        if row is None or not verify_password(password, row[4]):
            return None, "bad_credentials"
        if not row[5]:
            return None, "awaiting_approval" if row[6] else "bad_credentials"
        await conn.execute(
            "UPDATE app_user SET last_login_at = now() WHERE id = %s", (row[0],)
        )
        return _row_to_user(row), None


async def change_password(user_id: int, current: str, new: str) -> bool:
    """Self-service change: the current password must verify first."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT password_hash FROM app_user WHERE id = %s AND active",
                (user_id,),
            )
        ).fetchone()
        if row is None or not verify_password(current, row[0]):
            return False
        await conn.execute(
            "UPDATE app_user SET password_hash = %s WHERE id = %s",
            (hash_password(new), user_id),
        )
    return True


async def reset_password(username: str, new: str) -> bool:
    """Break-glass reset, no current password — server-shell CLI only
    (scripts/manage_users.py). Never exposed over HTTP."""
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE app_user SET password_hash = %s WHERE username = %s"
                " RETURNING id",
                (hash_password(new), username),
            )
        ).fetchone()
    return row is not None


async def set_display_name(username: str, display_name: str) -> dict | None:
    """Break-glass display-name change — server-shell CLI only, never over
    HTTP. Returns the id and the previous name so the caller can audit what
    actually changed, or None if there is no such user.

    Why this exists (2026-07-28): the display name is spoken aloud to a
    patient. The disclosure interpolates it server-side, and consultation
    448 ran on the admin account whose display name is "Doctor", so the room
    heard "Dr Doctor". The owner's decision was to fix the names rather than
    add a guard in code — no title is ever invented from a name, and that
    convention stays (`app/speech.py`).

    Trimmed, and refused if empty: a blank name would make the disclosure say
    "Dr " and a name is not the place to discover that.
    """
    display_name = display_name.strip()
    if not display_name:
        raise ValueError("display name cannot be blank")
    async with await _conn() as conn:
        # The old name comes from a CTE rather than a sub-SELECT in
        # RETURNING: a sub-SELECT there reads the statement's own snapshot
        # and it is not obvious which side of the UPDATE it lands on. The CTE
        # is unambiguous.
        row = await (
            await conn.execute(
                "WITH before AS ("
                "  SELECT id, display_name FROM app_user WHERE username = %s)"
                " UPDATE app_user SET display_name = %s FROM before"
                " WHERE app_user.id = before.id"
                " RETURNING app_user.id, before.display_name",
                (username, display_name),
            )
        ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "from": row[1], "to": display_name}


async def set_role(username: str, role: str) -> bool:
    """Promote/demote — server-shell CLI only. Refuses to demote the last
    active admin, same invariant as deactivation."""
    if role not in ROLES:
        raise ValueError(f"invalid role {role!r}")
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "UPDATE app_user SET role = %s WHERE username = %s AND"
                " (%s = 'admin' OR role != 'admin' OR EXISTS"
                "  (SELECT 1 FROM app_user WHERE role = 'admin' AND active"
                "   AND username != %s)) RETURNING id",
                (role, username, role, username),
            )
        ).fetchone()
    return row is not None


# ------------------------------------------------------------- dependencies

async def _user_from_cookie(token: str | None) -> dict | None:
    uid = verify_session(token)
    return await get_user(uid) if uid else None


def api_user(*roles: str):
    """API dependency: 401 without a session, 403 outside the role list."""
    allowed = roles or ROLES

    async def dep(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict:
        user = await _user_from_cookie(session)
        if user is None:
            raise HTTPException(status_code=401, detail="login required")
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="forbidden for this role")
        return user

    return dep


def page_user(*roles: str):
    """Page dependency: redirect anonymous users to /login; 403 wrong role."""
    allowed = roles or ROLES

    async def dep(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict:
        user = await _user_from_cookie(session)
        if user is None:
            raise HTTPException(status_code=307, headers={"Location": "/login"})
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="forbidden for this role")
        return user

    return dep
