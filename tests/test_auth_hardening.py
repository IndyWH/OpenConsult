"""Auth hardening for public exposure (2026-07-24): per-IP rate limits
on login and registration, and source-IP forensics on auth audit events
(login success, login failure, registration).
"""

import os
import secrets
from types import SimpleNamespace

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.ratelimit import RateLimiter, client_ip, login_limiter, register_limiter

load_dotenv()

PASSWORD = "test-password-123"


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


# ------------------------------------------------------------- the limiter

def test_rate_limiter_allows_up_to_limit_then_blocks_with_retry_after():
    limiter = RateLimiter(3, 60)
    assert [limiter.retry_after("a", now=t) for t in (0, 1, 2)] == [None] * 3
    retry = limiter.retry_after("a", now=3)
    assert retry is not None and 55 <= retry <= 60
    # Another address is unaffected.
    assert limiter.retry_after("b", now=3) is None


def test_rate_limiter_window_slides_and_reset_clears():
    limiter = RateLimiter(2, 10)
    assert limiter.retry_after("a", now=0) is None
    assert limiter.retry_after("a", now=1) is None
    assert limiter.retry_after("a", now=2) is not None
    # The oldest attempt (t=0) leaves the 10 s window…
    assert limiter.retry_after("a", now=10.5) is None
    limiter.reset()
    assert limiter.retry_after("a", now=11) is None


def test_client_ip_trusts_forwarding_only_from_loopback():
    def req(host, headers=None):
        return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers or {})

    # Direct connection: the peer address, XFF ignored (spoofable).
    assert client_ip(req("100.64.1.2")) == "100.64.1.2"
    assert client_ip(req("100.64.1.2", {"x-forwarded-for": "8.8.8.8"})) == "100.64.1.2"
    # Via the local proxy (Tailscale Serve/Funnel): last XFF entry.
    assert client_ip(req("127.0.0.1", {"x-forwarded-for": "203.0.113.9"})) == "203.0.113.9"
    assert client_ip(req("127.0.0.1", {"x-forwarded-for": "spoofed, 203.0.113.9"})) == "203.0.113.9"
    # Loopback with no proxy header stays loopback; no client at all is safe.
    assert client_ip(req("127.0.0.1")) == "127.0.0.1"
    assert client_ip(SimpleNamespace(client=None, headers={})) == "unknown"


# ------------------------------------------------------------ the endpoints

@needs_db
def test_login_rate_limited_with_clear_error(monkeypatch):
    from app.main import app

    monkeypatch.setattr(login_limiter, "attempts", 3)
    client = TestClient(app)
    for _ in range(3):
        response = client.post(
            "/api/login", json={"username": "nobody", "password": "wrong-password"}
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/login", json={"username": "nobody", "password": "wrong-password"}
    )
    assert blocked.status_code == 429
    assert "too many login attempts" in blocked.json()["error"]
    assert int(blocked.headers["Retry-After"]) >= 1


@needs_db
def test_register_rate_limited_with_clear_error(monkeypatch):
    from app.main import app

    monkeypatch.setattr(register_limiter, "attempts", 2)
    client = TestClient(app)
    for _ in range(2):
        response = client.post(
            "/api/register",
            json={"username": f"rl_{secrets.token_hex(4)}", "password": PASSWORD,
                  "display_name": "RL", "role": "doctor"},
        )
        assert response.status_code == 200
    blocked = client.post(
        "/api/register",
        json={"username": f"rl_{secrets.token_hex(4)}", "password": PASSWORD,
              "display_name": "RL", "role": "doctor"},
    )
    assert blocked.status_code == 429
    assert "too many registration attempts" in blocked.json()["error"]
    assert int(blocked.headers["Retry-After"]) >= 1


@needs_db
def test_auth_audit_events_carry_source_ip():
    from conftest import approve_account
    from app.main import app

    client = TestClient(app)
    username = f"ip_{secrets.token_hex(4)}"
    assert client.post(
        "/api/register",
        json={"username": username, "password": PASSWORD,
              "display_name": "IP Test", "role": "doctor"},
    ).status_code == 200
    assert client.post(  # a failed login, audited with source + reason
        "/api/login", json={"username": username, "password": "wrong-password"}
    ).status_code == 401
    approve_account(username)
    assert client.post(
        "/api/login", json={"username": username, "password": PASSWORD}
    ).status_code == 200

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        registered_ip = conn.execute(
            "SELECT a.detail->>'ip' FROM audit_event a"
            " JOIN app_user u ON u.id = a.user_id"
            " WHERE a.action = 'user.registered_pending' AND u.username = %s",
            (username,),
        ).fetchone()[0]
        login_ip = conn.execute(
            "SELECT a.detail->>'ip' FROM audit_event a"
            " JOIN app_user u ON u.id = a.user_id"
            " WHERE a.action = 'user.login' AND u.username = %s",
            (username,),
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT detail->>'ip', detail->>'reason' FROM audit_event"
            " WHERE action = 'user.login_failed' AND detail->>'username' = %s",
            (username,),
        ).fetchone()
    # TestClient's synthetic peer address — the point is it was recorded.
    assert registered_ip == "testclient"
    assert login_ip == "testclient"
    assert failed == ("testclient", "bad_credentials")


# ------------------------------------ registration input bounds (2026-07-31)
#
# Defence at the source for the Critical XSS finding: registration is
# public, so display_name and username are where an unauthenticated
# stranger writes text that later renders in an administrator's browser.
# The escaping (tests/test_xss_escaping.py) is the other, independent half.

def test_display_name_with_markup_is_refused_not_stored():
    from app import auth

    with pytest.raises(auth.InvalidUserInput):
        auth.validate_display_name('<img src=x onerror=alert(1)>')
    # The payload from the audit's Finding 1, in the form it was reported.
    with pytest.raises(auth.InvalidUserInput):
        auth.validate_display_name('Ada<script>alert(1)</script>')
    # Control characters too — a newline in a spoken name is not a name.
    with pytest.raises(auth.InvalidUserInput):
        auth.validate_display_name("Ada\nBad")


def test_over_long_display_name_and_username_are_refused():
    from app import auth

    with pytest.raises(auth.InvalidUserInput):
        auth.validate_display_name("A" * (auth.DISPLAY_NAME_MAX + 1))
    with pytest.raises(auth.InvalidUserInput):
        auth.validate_username("a" * (auth.USERNAME_MAX + 1))
    with pytest.raises(auth.InvalidUserInput):
        auth.validate_username("ab")            # under the minimum


def test_blank_display_name_is_refused_it_is_spoken_aloud():
    from app import auth

    with pytest.raises(auth.InvalidUserInput):
        auth.validate_display_name("   ")


def test_legitimate_names_still_pass():
    """The bound must not reject real people. Apostrophes, hyphens and
    non-Latin scripts are somebody's actual name — the sink escapes them."""
    from app import auth

    for name in ("Wajira Herath", "O'Brien", "Anne-Marie", "Dr Vicky",
                 " Næss", "Herath  ", "李伟"):
        assert auth.validate_display_name(name) == name.strip()
    for username in ("doctor", "someone_else", "rl_9f3a2b1c", "a.b-c"):
        assert auth.validate_username(username) == username


def test_username_rejects_characters_outside_the_identifier_set():
    from app import auth

    for bad in ("has space", "<script>", "quote\"mark", "semi;colon"):
        with pytest.raises(auth.InvalidUserInput):
            auth.validate_username(bad)


@needs_db
def test_register_endpoint_refuses_markup_display_name_with_400():
    """End to end: the public form cannot store the payload, and says why
    rather than reporting the generic "username already taken"."""
    from app.main import app

    client = TestClient(app)
    username = f"xss_{secrets.token_hex(4)}"
    response = client.post(
        "/api/register",
        json={"username": username, "password": PASSWORD,
              "display_name": "<img src=x onerror=alert(1)>", "role": "doctor"},
    )
    assert response.status_code == 400
    assert "markup" in response.json()["error"]

    # Nothing was written: the account does not exist to be approved.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute(
            "SELECT count(*) FROM app_user WHERE username = %s", (username,)
        ).fetchone()[0] == 0
