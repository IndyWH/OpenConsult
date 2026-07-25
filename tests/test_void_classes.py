"""Void reason classes and the unvoid guard (2026-07-25).

Why this exists, from HANDOVER docket 5: consultation #70 was voided for
an unsafe transcript, unvoided during governance testing (2026-07-22),
re-voided by the documented restoration (2026-07-24 10:43:32), and
unvoided AGAIN six minutes later (10:49:20). A written "don't exercise
governance actions on real rows" lesson did not survive its own commit,
so the correction is a code guard:

- a `clinical_safety` void cannot be reversed over HTTP at all;
- unvoid always needs its own typed reason, and the UI shows the original
  void reason before allowing it;
- refusals are audited as `consultation.unvoid_refused`.

Reversal of a clinical_safety void is break-glass only:
`scripts/manage_consultations.py`, server shell.
"""

import asyncio
import os
import re
import secrets
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import auth, consultations

load_dotenv()

REPO = Path(__file__).parent.parent


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


def _make_consultation() -> int:
    consultations.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(
            cid, [{"role": "Doctor", "start": 0.0, "end": 2.0,
                   "text": "Hello.", "confidence": 0.9}])
        await consultations.set_status(cid, "awaiting_review")
        return cid

    return asyncio.run(build())


def _void(client: TestClient, cid: int, reason: str, reason_class: str | None = None):
    body = {"reason": reason}
    if reason_class is not None:
        body["reason_class"] = reason_class
    return client.post(f"/api/admin/consultations/{cid}/void", json=body)


def _audit_events(cid: int, action: str) -> list[dict]:
    async def fetch() -> list[dict]:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            rows = await (
                await conn.execute(
                    "SELECT detail FROM audit_event WHERE subject_type = 'consultation'"
                    " AND subject_id = %s AND action = %s ORDER BY id",
                    (cid, action),
                )
            ).fetchall()
        return [r[0] for r in rows]

    return asyncio.run(fetch())


# ------------------------------------------------------- the guard itself

def test_clinical_safety_void_cannot_be_unvoided_over_http():
    """The whole point. A clinical_safety void is irreversible here."""
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()

    assert _void(admin_client, cid, "hallucinated transcript",
                 "clinical_safety").status_code == 200

    response = admin_client.post(f"/api/admin/consultations/{cid}/unvoid",
                                 json={"reason": "I want it back"})
    assert response.status_code == 409
    body = response.json()
    assert body["reason_class"] == "clinical_safety"
    assert "break-glass" in body["error"]
    assert "manage_consultations.py" in body["error"]

    # Still voided — the refusal is real, not cosmetic.
    state = asyncio.run(consultations.void_state(cid))
    assert state["voided"] is True
    assert state["reason_class"] == "clinical_safety"


def test_refused_unvoid_is_audited():
    """consultation.unvoid_refused is the event that shows the guard
    earned its place — without it we would never know it fired."""
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    _void(admin_client, cid, "unsafe record", "clinical_safety")

    assert _audit_events(cid, "consultation.unvoid_refused") == []
    admin_client.post(f"/api/admin/consultations/{cid}/unvoid",
                      json={"reason": "please"})

    events = _audit_events(cid, "consultation.unvoid_refused")
    assert len(events) == 1
    assert events[0]["reason_class"] == "clinical_safety"
    assert events[0]["attempted_reason"] == "please"


def test_test_data_void_still_unvoids():
    """The common case keeps working: routine voids stay reversible."""
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()

    assert _void(admin_client, cid, "wrong patient", "test_data").status_code == 200
    assert admin_client.post(f"/api/admin/consultations/{cid}/unvoid",
                             json={"reason": "voided the wrong row"}).status_code == 200

    state = asyncio.run(consultations.void_state(cid))
    assert state["voided"] is False
    assert state["reason_class"] is None  # cleared with the void


def test_void_defaults_to_test_data():
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    assert _void(admin_client, cid, "routine").status_code == 200
    assert asyncio.run(consultations.void_state(cid))["reason_class"] == "test_data"


def test_unknown_reason_class_is_rejected():
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    response = _void(admin_client, cid, "routine", "whatever_i_like")
    assert response.status_code == 400
    assert asyncio.run(consultations.void_state(cid))["voided"] is False


# ------------------------------------------------------------- friction

def test_unvoid_without_a_typed_reason_is_rejected():
    """#70 was unvoided twice partly because nothing made anyone say why."""
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    _void(admin_client, cid, "wrong patient", "test_data")

    assert admin_client.post(f"/api/admin/consultations/{cid}/unvoid",
                             json={"reason": "   "}).status_code == 400
    # Untouched.
    assert asyncio.run(consultations.void_state(cid))["voided"] is True


def test_unvoid_reason_reaches_the_audit_trail():
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    _void(admin_client, cid, "wrong patient", "test_data")
    admin_client.post(f"/api/admin/consultations/{cid}/unvoid",
                      json={"reason": "patient identity confirmed correct"})

    events = _audit_events(cid, "consultation.unvoided")
    assert events[-1]["reason"] == "patient identity confirmed correct"
    assert events[-1]["reverted_class"] == "test_data"


def test_void_audit_carries_the_reason_class():
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    _void(admin_client, cid, "unsafe record", "clinical_safety")
    assert _audit_events(cid, "consultation.voided")[-1]["reason_class"] == "clinical_safety"


# ------------------------------------------------------------------- UI

def test_unvoid_button_is_not_rendered_for_clinical_safety():
    """The API refuses it; the page must not offer it either."""
    page = (REPO / "app" / "static" / "worklist.html").read_text(encoding="utf-8")
    assert "c.void_reason_class === 'clinical_safety'" in page
    assert "unvoid is break-glass only" in page
    # The Unvoid button is created only in the else branch of that check.
    guard = page.index("c.void_reason_class === 'clinical_safety'")
    button = page.index("textContent = 'Unvoid'")
    assert guard < button, "the class check must precede the Unvoid button"


def test_unvoid_confirmation_shows_the_original_void_reason():
    """The reason #70 was unvoided twice is that nothing made the person
    read why it had been voided."""
    page = (REPO / "app" / "static" / "worklist.html").read_text(encoding="utf-8")
    assert "c.void_reason" in page
    assert re.search(r"was voided.*for this reason", page, re.S)


def test_void_ui_offers_the_reason_class():
    page = (REPO / "app" / "static" / "worklist.html").read_text(encoding="utf-8")
    assert "reason_class" in page
    assert "clinical_safety" in page and "test_data" in page


# --------------------------------------------------------------- migration

def test_migration_classifies_voided_rows():
    """Existing voided rows become test_data; #70 becomes clinical_safety.

    Both UPDATEs are guarded on voided_at, so an un-voided row never
    carries a stale class — which is why this asserts on the guard rather
    than on #70's live state (it is not voided at the time of writing;
    see HANDOVER docket 5).
    """
    schema = (REPO / "app" / "consultations.py").read_text(encoding="utf-8")
    assert ("UPDATE consultation SET void_reason_class = 'test_data'\n"
            " WHERE voided_at IS NOT NULL AND void_reason_class IS NULL"
            " AND id <> 70;") in schema
    assert ("UPDATE consultation SET void_reason_class = 'clinical_safety'\n"
            " WHERE voided_at IS NOT NULL AND id = 70;") in schema

    consultations.ensure_schema()  # idempotent; must not raise

    async def check() -> list:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            return await (
                await conn.execute(
                    "SELECT id, void_reason_class FROM consultation"
                    " WHERE voided_at IS NOT NULL AND void_reason_class IS NULL"
                )
            ).fetchall()

    assert asyncio.run(check()) == [], "every voided row must carry a class"


def test_no_unvoided_row_carries_a_stale_class():
    async def check() -> list:
        async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
            return await (
                await conn.execute(
                    "SELECT id FROM consultation"
                    " WHERE voided_at IS NULL AND void_reason_class IS NOT NULL"
                )
            ).fetchall()

    assert asyncio.run(check()) == []


# -------------------------------------------------------------- break-glass

def test_break_glass_cli_can_reverse_a_clinical_safety_void():
    """The deliberate way past the guard, server shell only."""
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    _void(admin_client, cid, "unsafe record", "clinical_safety")

    reverted = asyncio.run(
        consultations.unvoid_consultation(cid, allow_clinical_safety=True))
    assert reverted is not None
    assert reverted["reverted_class"] == "clinical_safety"
    assert asyncio.run(consultations.void_state(cid))["voided"] is False


def test_break_glass_cli_is_shell_only():
    """It must never acquire an HTTP surface."""
    script = (REPO / "scripts" / "manage_consultations.py").read_text(encoding="utf-8")
    assert "server shell only, never over HTTP" in script
    for banned in ("fastapi", "@app.", "APIRouter", "uvicorn"):
        assert banned not in script, f"{banned} would give the CLI an HTTP surface"


# -------------------------------------------------------------------- RBAC

@pytest.mark.parametrize("role", ["doctor", "receptionist"])
def test_rbac_unchanged_for_void_and_unvoid(role):
    client = _client_for(_make_user(role))
    cid = _make_consultation()
    assert client.post(f"/api/admin/consultations/{cid}/void",
                       json={"reason": "x", "reason_class": "test_data"}).status_code == 403
    assert client.post(f"/api/admin/consultations/{cid}/unvoid",
                       json={"reason": "x"}).status_code == 403


def test_receptionist_cannot_reach_the_class_through_the_worklist():
    admin_client = _client_for(_make_user("admin"))
    cid = _make_consultation()
    _void(admin_client, cid, "unsafe", "clinical_safety")

    receptionist = _client_for(_make_user("receptionist"))
    assert receptionist.get("/api/admin/consultations").status_code == 403
    assert cid not in {c["id"] for c in receptionist.get("/api/consultations").json()}
