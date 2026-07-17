"""Smoke tests: does the app start and answer at all?

Run with: uv run pytest
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_redirects_anonymous_to_login():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


def test_root_redirects_valid_session_to_today():
    from app import auth

    cookies = {auth.COOKIE_NAME: auth.sign_session(1)}
    response = client.get("/", cookies=cookies, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/today"


def test_health_reports_database():
    """Requires PostgreSQL to be running with the app database created."""
    response = client.get("/health")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "ok"
    assert body["pgvector_available"] is True
