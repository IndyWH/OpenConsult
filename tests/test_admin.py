"""Admin governance: user deactivation (never deletion), consultation
void + purge (two deliberate steps), password self-service, and the RBAC
walls around all of it.

The purge-sequence test uses consultations.purge_voided(only_ids=...) so a
test run can never delete voided data the owner is still holding for a
real purge; the admin endpoint (purge-all) shares the same implementation.
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


def _make_consultation() -> tuple[int, int]:
    """A consultation with a synthetic patient, turns, and a note."""
    consultations.ensure_schema()

    async def build() -> tuple[int, int]:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            patient = await (
                await conn.execute(
                    "INSERT INTO patient (name) VALUES ('Test Purge Patient') RETURNING id"
                )
            ).fetchone()
        cid = await consultations.create_consultation(patient_id=patient[0])
        await consultations.save_turns(
            cid, [{"role": "Doctor", "start": 0.0, "end": 2.0,
                   "text": "Hello.", "confidence": 0.9}])
        await consultations.save_note(
            cid, {"subjective": [{"text": "x", "turns": [0], "uncited": False,
                                  "flagged": False}],
                  "objective": [], "assessment": [], "plan": []})
        await consultations.set_status(cid, "awaiting_review")
        return cid, patient[0]

    return asyncio.run(build())


# ---------------------------------------------------------------------- RBAC

ADMIN_POSTS = [
    "/api/admin/users/999999/deactivate",
    "/api/admin/users/999999/reactivate",
    "/api/admin/consultations/999999/void",
    "/api/admin/consultations/999999/unvoid",
    "/api/admin/purge-voided",
]


@pytest.mark.parametrize("role", ["doctor", "receptionist"])
def test_admin_endpoints_are_403_for_other_roles(role):
    client = _client_for(_make_user(role))
    assert client.get("/api/admin/users").status_code == 403
    assert client.get("/api/admin/consultations").status_code == 403
    assert client.get("/users", follow_redirects=False).status_code == 403
    for url in ADMIN_POSTS:
        assert client.post(url, json={"reason": "x"}).status_code == 403, url


# ------------------------------------------------------- deactivate/reactivate

def test_deactivate_blocks_login_and_sessions_reactivate_restores():
    admin = _make_user("admin")
    victim = _make_user("doctor")
    admin_client = _client_for(admin)
    victim_client = _client_for(victim)
    assert victim_client.get("/api/me").status_code == 200

    response = admin_client.post(f"/api/admin/users/{victim['id']}/deactivate")
    assert response.status_code == 200

    # Existing session is dead, login refused, name still on record.
    assert victim_client.get("/api/me").status_code == 401
    login = victim_client.post("/api/login", json={
        "username": victim["username"], "password": "test-password-123"})
    assert login.status_code == 401
    listed = {u["id"]: u for u in admin_client.get("/api/admin/users").json()}
    assert listed[victim["id"]]["active"] is False
    assert listed[victim["id"]]["display_name"] == "Doctor"

    response = admin_client.post(f"/api/admin/users/{victim['id']}/reactivate")
    assert response.status_code == 200
    login = victim_client.post("/api/login", json={
        "username": victim["username"], "password": "test-password-123"})
    assert login.status_code == 200


def test_admin_cannot_deactivate_self():
    admin = _make_user("admin")
    client = _client_for(admin)
    response = client.post(f"/api/admin/users/{admin['id']}/deactivate")
    assert response.status_code == 409
    assert "own account" in response.json()["error"]


def test_last_active_admin_cannot_be_deactivated():
    """Exercised inside a rolled-back transaction: all other admins are
    deactivated first, so the guard is genuinely at its boundary, and the
    rollback puts every real account back exactly as it was."""
    admin = _make_user("admin")

    async def run() -> tuple[bool, bool]:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            await conn.execute(
                "UPDATE app_user SET active = false WHERE role = 'admin' AND id != %s",
                (admin["id"],),
            )
            last_refused = not await auth.set_user_active(admin["id"], False, conn=conn)
            still_active = (await (await conn.execute(
                "SELECT active FROM app_user WHERE id = %s", (admin["id"],)
            )).fetchone())[0]
            await conn.rollback()
            return last_refused, still_active

    last_refused, still_active = asyncio.run(run())
    assert last_refused, "the last active admin must not be deactivatable"
    assert still_active


# ------------------------------------------------------------ void then purge

def test_void_requires_reason_and_hides_from_working_views():
    admin = _make_user("admin")
    doctor = _make_user("doctor")
    cid, _pid = _make_consultation()
    admin_client = _client_for(admin)
    doctor_client = _client_for(doctor)

    # Reason is mandatory.
    response = admin_client.post(f"/api/admin/consultations/{cid}/void",
                                 json={"reason": "   "})
    assert response.status_code == 400

    response = admin_client.post(f"/api/admin/consultations/{cid}/void",
                                 json={"reason": "test data — wrong patient"})
    assert response.status_code == 200

    # Gone from the working worklist for everyone…
    assert cid not in {c["id"] for c in doctor_client.get("/api/consultations").json()}
    # …unreachable directly for non-admins…
    assert doctor_client.get(f"/api/consultations/{cid}").status_code == 410
    # …but present, with its reason, in the admin view.
    admin_rows = {c["id"]: c for c in admin_client.get("/api/admin/consultations").json()}
    assert admin_rows[cid]["void_reason"] == "test data — wrong patient"
    assert admin_rows[cid]["voided_at"] is not None

    # Frozen: no edits, no regeneration, no approval, no double-void.
    assert admin_client.post(f"/api/consultations/{cid}/approve",
                             json={"text": "S:\n"}).status_code == 409
    assert admin_client.post(f"/api/consultations/{cid}/regenerate").status_code == 409
    assert admin_client.post(f"/api/admin/consultations/{cid}/void",
                             json={"reason": "again"}).status_code == 409


def test_unvoid_restores_a_mistaken_void():
    admin = _make_user("admin")
    doctor = _make_user("doctor")
    cid, _pid = _make_consultation()
    admin_client = _client_for(admin)
    doctor_client = _client_for(doctor)

    # Unvoiding something that isn't voided is refused.
    assert admin_client.post(f"/api/admin/consultations/{cid}/unvoid").status_code == 409

    assert admin_client.post(f"/api/admin/consultations/{cid}/void",
                             json={"reason": "oops, wrong one"}).status_code == 200
    assert doctor_client.get(f"/api/consultations/{cid}").status_code == 410

    assert admin_client.post(f"/api/admin/consultations/{cid}/unvoid").status_code == 200

    # Back in working views, prior status intact, editable again.
    state = doctor_client.get(f"/api/consultations/{cid}").json()
    assert state["status"] == "awaiting_review"
    assert state["voided_at"] is None
    assert cid in {c["id"] for c in doctor_client.get("/api/consultations").json()}
    # Editable again (turn edits share the voided/approved guard):
    assert doctor_client.patch(f"/api/consultations/{cid}/turns/0",
                               json={"text": "Hello there."}).status_code == 200

    # The audit trail kept the round trip, reason included.
    async def audit_detail() -> list:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            rows = await (await conn.execute(
                "SELECT action, detail FROM audit_event WHERE subject_type = 'consultation'"
                " AND subject_id = %s ORDER BY id", (cid,))).fetchall()
            return rows

    events = asyncio.run(audit_detail())
    actions = [e[0] for e in events]
    assert "consultation.voided" in actions and "consultation.unvoided" in actions
    unvoid_detail = next(e[1] for e in events if e[0] == "consultation.unvoided")
    assert unvoid_detail["reverted_reason"] == "oops, wrong one"


def test_void_then_purge_sequence():
    admin = _make_user("admin")
    cid, pid = _make_consultation()
    client = _client_for(admin)

    # Purge before void must not touch it: purge only takes voided rows.
    purged = asyncio.run(consultations.purge_voided(only_ids=[cid]))
    assert purged["consultations"] == 0
    assert asyncio.run(consultations.get_consultation(cid)) is not None

    response = client.post(f"/api/admin/consultations/{cid}/void",
                           json={"reason": "test data"})
    assert response.status_code == 200

    purged = asyncio.run(consultations.purge_voided(only_ids=[cid]))
    assert purged["consultations"] == 1
    assert purged["patients"] == 1  # the synthetic patient had no other visits

    # Hard-deleted: consultation, turns/notes (cascade), and the patient.
    assert asyncio.run(consultations.get_consultation(cid)) is None

    async def patient_exists() -> bool:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            return await (await conn.execute(
                "SELECT 1 FROM patient WHERE id = %s", (pid,))).fetchone() is not None

    assert not asyncio.run(patient_exists())

    # The audit trail kept both deliberate steps.
    async def audit_actions() -> set:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            rows = await (await conn.execute(
                "SELECT action FROM audit_event WHERE subject_type = 'consultation'"
                " AND subject_id = %s", (cid,))).fetchall()
            return {r[0] for r in rows}

    assert "consultation.voided" in asyncio.run(audit_actions())


# ------------------------------------------------------------------ passwords

def test_change_password_flow():
    user = _make_user("doctor")
    client = _client_for(user)

    response = client.post("/api/change-password", json={
        "current_password": "wrong-password", "new_password": "new-password-456"})
    assert response.status_code == 403

    response = client.post("/api/change-password", json={
        "current_password": "test-password-123", "new_password": "short"})
    assert response.status_code == 400

    response = client.post("/api/change-password", json={
        "current_password": "test-password-123", "new_password": "new-password-456"})
    assert response.status_code == 200

    assert client.post("/api/login", json={
        "username": user["username"], "password": "test-password-123"}).status_code == 401
    assert client.post("/api/login", json={
        "username": user["username"], "password": "new-password-456"}).status_code == 200


def test_break_glass_reset_and_role_guard():
    user = _make_user("receptionist")
    assert asyncio.run(auth.reset_password(user["username"], "reset-by-cli-789"))
    assert asyncio.run(auth.authenticate(user["username"], "reset-by-cli-789"))
    assert not asyncio.run(auth.reset_password("no-such-user-xyz", "whatever-123"))

    # Promotion works; the last-admin invariant also guards CLI demotion.
    assert asyncio.run(auth.set_role(user["username"], "doctor"))
    with pytest.raises(ValueError):
        asyncio.run(auth.set_role(user["username"], "superuser"))
