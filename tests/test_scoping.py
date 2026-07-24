"""Strict own-consultations scoping (owner decision 2026-07-24).

A doctor sees and acts on only their own consultations; a direct-URL
probe of another doctor's consultation is a 403 (matching the
receptionist-probe pattern; voided stays 410). Unowned rows
(doctor_id IS NULL — legacy/test data) remain open to clinical roles,
because real consultations always record their doctor at creation.
Admin sees all. Chosen over continuity-of-care sharing for this
prototype; revisit only as an owner decision.
"""

import asyncio
import os
import secrets

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import auth, consultations

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role
    ))


def _client_for(user: dict) -> TestClient:
    from app.main import app

    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _make_consultation(doctor_id: int | None) -> int:
    consultations.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation(None, doctor_id)
        await consultations.save_turns(
            cid, [{"role": "Doctor", "start": 0.0, "end": 2.0,
                   "text": "Hello.", "confidence": 0.9}])
        await consultations.save_note(
            cid, {"subjective": [{"text": "x", "turns": [0], "uncited": False,
                                  "flagged": False}],
                  "objective": [], "assessment": [], "plan": []})
        await consultations.set_status(cid, "awaiting_review")
        return cid

    return asyncio.run(build())


@pytest.fixture(scope="module")
def two_doctors():
    doc_a, doc_b = _make_user("doctor"), _make_user("doctor")
    return (doc_a, _client_for(doc_a)), (doc_b, _client_for(doc_b))


def test_doctor_list_is_scoped_to_own_consultations(two_doctors):
    (doc_a, client_a), (doc_b, client_b) = two_doctors
    cid_a = _make_consultation(doc_a["id"])

    ids_a = {c["id"] for c in client_a.get("/api/consultations").json()}
    ids_b = {c["id"] for c in client_b.get("/api/consultations").json()}
    assert cid_a in ids_a
    assert cid_a not in ids_b


def test_direct_probe_of_another_doctors_consultation_is_403(two_doctors):
    (doc_a, client_a), (doc_b, client_b) = two_doctors
    cid_a = _make_consultation(doc_a["id"])

    # The owner can open and work with it…
    assert client_a.get(f"/api/consultations/{cid_a}").status_code == 200
    # …the other doctor is refused on the detail AND every mutation.
    assert client_b.get(f"/api/consultations/{cid_a}").status_code == 403
    assert client_b.post(f"/api/consultations/{cid_a}/approve",
                         json={"text": "S:"}).status_code == 403
    assert client_b.post(f"/api/consultations/{cid_a}/regenerate").status_code == 403
    assert client_b.post(f"/api/consultations/{cid_a}/swap-roles").status_code == 403
    assert client_b.post(f"/api/consultations/{cid_a}/acknowledge-urgent").status_code == 403
    assert client_b.patch(f"/api/consultations/{cid_a}/turns/0",
                          json={"text": "y"}).status_code == 403


def test_unowned_legacy_rows_stay_open_to_doctors(two_doctors):
    (_, client_a), (_, client_b) = two_doctors
    cid = _make_consultation(None)

    assert client_a.get(f"/api/consultations/{cid}").status_code == 200
    assert client_b.get(f"/api/consultations/{cid}").status_code == 200
    ids_b = {c["id"] for c in client_b.get("/api/consultations").json()}
    assert cid in ids_b


def test_admin_sees_all(two_doctors):
    (doc_a, _), _ = two_doctors
    cid_a = _make_consultation(doc_a["id"])
    admin = _make_user("admin")
    admin_client = _client_for(admin)

    assert admin_client.get(f"/api/consultations/{cid_a}").status_code == 200
    ids = {c["id"] for c in admin_client.get("/api/consultations").json()}
    assert cid_a in ids
