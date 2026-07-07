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


async def create_user(username: str, password: str, display_name: str, role: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"invalid role {role!r}")
    async with await _conn() as conn:
        count = (await (await conn.execute("SELECT count(*) FROM app_user")).fetchone())[0]
        if count == 0:
            role = "admin"  # bootstrap: the first account administers the rest
        row = await (
            await conn.execute(
                "INSERT INTO app_user (username, password_hash, display_name, role)"
                " VALUES (%s, %s, %s, %s) RETURNING id, username, display_name, role",
                (username, hash_password(password), display_name, role),
            )
        ).fetchone()
    return _row_to_user(row)


async def get_user(user_id: int) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, username, display_name, role FROM app_user WHERE id = %s",
                (user_id,),
            )
        ).fetchone()
    return _row_to_user(row) if row else None


async def authenticate(username: str, password: str) -> dict | None:
    async with await _conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, username, display_name, role, password_hash"
                " FROM app_user WHERE username = %s", (username,),
            )
        ).fetchone()
    if row and verify_password(password, row[4]):
        return _row_to_user(row)
    return None


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
