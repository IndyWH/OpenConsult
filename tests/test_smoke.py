"""Smoke tests: does the app start and answer at all?

Run with: uv run pytest
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_answers():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "Consultation AI"


def test_health_reports_database():
    """Requires PostgreSQL to be running with the app database created."""
    response = client.get("/health")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "ok"
    assert body["pgvector_available"] is True
