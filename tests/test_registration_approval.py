"""Approve-to-activate registration (2026-07-24 public-exposure work).

Public registration still works and still caps roles at doctor/
receptionist, but the account starts INACTIVE: no session cookie at
registration, a clear awaiting-approval message at login, activation
through the admin's existing reactivate path (audited user.activated,
distinct from user.reactivated), and a pending counter on the public
monitoring pulse so the hourly sentry can say someone is waiting.
"""

import asyncio
import os
import secrets

import psycopg
import pytest
from dotenv import load_dotenv
from conftest import approve_account
from fastapi.testclient import TestClient

from app import auth, monitor

load_dotenv()

PASSWORD = "test-password-123"


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _register(client, username, role="doctor"):
    return client.post(
        "/api/register",
        json={"username": username, "password": PASSWORD,
              "display_name": "Pending Person", "role": role},
    )


def _query_one(sql, params):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchone()


def _admin_client():
    from app.main import app

    admin = asyncio.run(auth.create_user(
        f"admin_{secrets.token_hex(4)}", PASSWORD, "Admin", "admin"
    ))
    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(admin["id"]))
    return client


def test_registration_creates_pending_inactive_account_without_session():
    from app.main import app

    auth.ensure_schema()
    client = TestClient(app)
    username = f"pending_{secrets.token_hex(4)}"
    response = _register(client, username)
    assert response.status_code == 200
    body = response.json()
    assert body["pending"] is True
    assert "approval" in body["message"]
    # No session cookie: registering must not grant access.
    assert auth.COOKIE_NAME not in response.cookies
    row = _query_one(
        "SELECT active, pending_approval FROM app_user WHERE username = %s",
        (username,),
    )
    assert row == (False, True)
    event = _query_one(
        "SELECT a.action FROM audit_event a JOIN app_user u ON u.id = a.user_id"
        " WHERE u.username = %s ORDER BY a.at DESC LIMIT 1",
        (username,),
    )
    assert event == ("user.registered_pending",)


def test_login_blocked_with_awaiting_message_until_approved():
    from app.main import app

    client = TestClient(app)
    username = f"pending_{secrets.token_hex(4)}"
    assert _register(client, username).status_code == 200

    blocked = client.post("/api/login", json={"username": username, "password": PASSWORD})
    assert blocked.status_code == 403
    assert "awaiting administrator approval" in blocked.json()["error"]
    # A WRONG password on a pending account must not reveal its status.
    probe = client.post("/api/login", json={"username": username, "password": "wrong-password"})
    assert probe.status_code == 401
    assert probe.json()["error"] == "invalid credentials"

    approve_account(username)
    ok = client.post("/api/login", json={"username": username, "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["user"]["username"] == username


def test_admin_approval_audits_user_activated_not_reactivated():
    from app.main import app

    client = TestClient(app)
    username = f"pending_{secrets.token_hex(4)}"
    assert _register(client, username, role="receptionist").status_code == 200
    uid = _query_one("SELECT id FROM app_user WHERE username = %s", (username,))[0]

    admin = _admin_client()
    assert admin.post(f"/api/admin/users/{uid}/reactivate").status_code == 200
    assert _query_one(
        "SELECT active, pending_approval FROM app_user WHERE id = %s", (uid,)
    ) == (True, False)
    assert _query_one(
        "SELECT count(*) FROM audit_event WHERE action = 'user.activated'"
        " AND subject_id = %s", (uid,),
    ) == (1,)

    # Deactivate + reactivate the SAME account: now it's governance, not
    # approval — the audit event must be user.reactivated.
    assert admin.post(f"/api/admin/users/{uid}/deactivate").status_code == 200
    assert admin.post(f"/api/admin/users/{uid}/reactivate").status_code == 200
    assert _query_one(
        "SELECT count(*) FROM audit_event WHERE action = 'user.reactivated'"
        " AND subject_id = %s", (uid,),
    ) == (1,)


def test_users_view_payload_carries_pending_flag():
    from app.main import app

    client = TestClient(app)
    username = f"pending_{secrets.token_hex(4)}"
    assert _register(client, username).status_code == 200

    listed = _admin_client().get("/api/admin/users").json()
    me = next(u for u in listed if u["username"] == username)
    assert me["pending_approval"] is True and me["active"] is False


def test_deactivated_account_login_stays_indistinguishable():
    """Governance deactivation must not advertise itself at login — only
    never-approved registrations get the awaiting-approval message."""
    from app.main import app

    user = asyncio.run(auth.create_user(
        f"gone_{secrets.token_hex(4)}", PASSWORD, "Gone", "doctor"
    ))
    asyncio.run(auth.set_user_active(user["id"], False))
    client = TestClient(app)
    response = client.post(
        "/api/login", json={"username": user["username"], "password": PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["error"] == "invalid credentials"


def test_pulse_counts_pending_registrations_and_drops_on_approval():
    from app.main import app

    client = TestClient(app)
    username = f"pending_{secrets.token_hex(4)}"
    assert _register(client, username).status_code == 200

    monitor.invalidate_cache()
    pulse = TestClient(app).get("/api/monitor/pulse").json()
    assert pulse["registrations_pending_activation_today"] >= 1
    assert pulse["registrations_pending_activation_last_hour"] >= 1
    # Registrations keep counting under the new event name.
    assert pulse["registrations_today"] >= 1
    before = pulse["registrations_pending_activation_today"]

    approve_account(username)
    monitor.invalidate_cache()
    after = TestClient(app).get("/api/monitor/pulse").json()
    assert after["registrations_pending_activation_today"] == before - 1
