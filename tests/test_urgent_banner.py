"""The review-page urgency banner flow: unresolved urgent actions block
approval until explicitly acknowledged, the acknowledgement is recorded,
and urgent actions never leak into the note's plain text."""

import asyncio
import os

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import consultations
from app.notes import note_as_plain_text

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


@pytest.fixture()
def consultation_with_urgency():
    consultations.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(
            cid,
            [{"role": "Doctor", "start": 0.0, "end": 4.0,
              "text": "Any chest pain?", "confidence": 0.9},
             {"role": "Patient", "start": 4.0, "end": 9.0,
              "text": "Yes, when I climb stairs.", "confidence": 0.9}],
        )
        await consultations.save_note(
            cid,
            {"subjective": [{"text": "Exertional chest pain", "turns": [1],
                             "uncited": False, "flagged": False}],
             "objective": [], "assessment": [], "plan": []},
        )
        await consultations.save_urgent_actions(
            cid,
            [{"action": "Perform bedside ECG", "reason": "Possible ACS",
              "first_fired_s": 42.5}],
        )
        await consultations.set_status(cid, "awaiting_review")
        return cid

    return asyncio.run(build())


def test_urgent_ack_gates_approval(consultation_with_urgency):
    cid = consultation_with_urgency
    from app.main import app

    # No lifespan: the endpoints under test don't need the ML models.
    client = TestClient(app)

    state = client.get(f"/api/consultations/{cid}").json()
    assert state["urgent_actions"][0]["action"] == "Perform bedside ECG"
    assert state["urgent_actions"][0]["first_fired_s"] == 42.5
    assert state["urgent_ack_at"] is None

    # Approval is blocked before acknowledgement...
    response = client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert response.status_code == 409

    # ...acknowledgement is recorded...
    ack = client.post(f"/api/consultations/{cid}/acknowledge-urgent").json()
    assert ack["acknowledged_at"]
    state = client.get(f"/api/consultations/{cid}").json()
    assert state["urgent_ack_at"] is not None

    # ...and approval then succeeds.
    response = client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert response.status_code == 200
    assert client.get(f"/api/consultations/{cid}").json()["status"] == "approved"


def test_urgent_actions_stay_out_of_plain_text(consultation_with_urgency):
    cid = consultation_with_urgency
    note = asyncio.run(consultations.latest_note(cid))
    plain = note_as_plain_text(note["content"])
    assert "ECG" not in plain  # the urgent action lives in the banner only
    assert "Exertional chest pain" in plain