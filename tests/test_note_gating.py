"""Note grounding gate: a substantially-uncited draft is demoted to a
refusal, never presented for review, and never approvable.

Specimen: consultation #78 (2026-07-15) — a mic-check transcript
("Check one, two, three") produced a fully fabricated angina consultation
(history, medication doses, BP reading, plan). Citation validation caught
every claim (12/12 uncited) but nothing acted on it. See the note-quality
eval, fidelity specimen 4.
"""

import asyncio
import os
import secrets

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import auth, consultations
from app.notes import validate_and_gate, note_as_plain_text

load_dotenv()

MIC_CHECK_TURNS = [
    {"idx": 0, "role": "Doctor", "start": 2.3, "end": 5.5,
     "text": "Check one, two, three. Check one, two, three.", "confidence": 0.7},
]


def _claims(*texts_and_turns) -> list[dict]:
    return [{"text": t, "turns": ns} for t, ns in texts_and_turns]


def _note(subjective=(), objective=(), assessment=(), plan=()) -> dict:
    return {"reasoning": "", "subjective": _claims(*subjective),
            "objective": _claims(*objective), "assessment": _claims(*assessment),
            "plan": _claims(*plan)}


# ------------------------------------------------------------ the pure gate

def test_fabricated_note_on_mic_check_is_demoted_to_refusal():
    """The consultation-#78 shape: every claim cites nothing that exists."""
    fabricated = _note(
        subjective=[("Chest pain, worse on exertion.", []),
                    ("Takes Ramipril 5mg daily.", [])],
        objective=[("BP 150/95 mmHg.", [])],
        assessment=[("Possible angina.", [])],
        plan=[("ECG requested.", [7])],  # invalid turn — stripped
    )
    gated = validate_and_gate(fabricated, MIC_CHECK_TURNS)
    assert gated["refusal"] is True
    assert "insufficient clinical content" in gated["refusal_reason"]
    assert gated["claims_total"] == 5 and gated["claims_cited"] == 0
    for section in ("subjective", "objective", "assessment", "plan"):
        assert gated[section] == []  # the fabricated draft is discarded


def test_sparse_but_real_transcript_keeps_its_note():
    """A thin consultation whose few claims are grounded must NOT refuse."""
    turns = [
        {"idx": 0, "role": "Doctor", "start": 0.0, "end": 3.0,
         "text": "What brings you in?", "confidence": 0.9},
        {"idx": 1, "role": "Patient", "start": 3.0, "end": 8.0,
         "text": "Just a sore throat since yesterday.", "confidence": 0.9},
    ]
    note = _note(subjective=[("Sore throat since yesterday.", [1])],
                 plan=[("Symptomatic advice.", [0, 1])])
    gated = validate_and_gate(note, turns)
    assert not gated.get("refusal")
    assert gated["subjective"][0]["uncited"] is False


def test_threshold_majority_uncited_refuses_but_half_cited_stands():
    turns = MIC_CHECK_TURNS + [
        {"idx": 1, "role": "Patient", "start": 6.0, "end": 9.0,
         "text": "My knee hurts.", "confidence": 0.9},
    ]
    # 1 of 3 cited (33%) — below the 50% default: refusal.
    minority = _note(subjective=[("Knee pain.", [1]), ("Fever for a week.", []),
                                 ("Smoker.", [])])
    assert validate_and_gate(minority, turns)["refusal"] is True
    # 1 of 2 cited (exactly 50%) — at the threshold: the note stands.
    boundary = _note(subjective=[("Knee pain.", [1]), ("Fever for a week.", [])])
    assert not validate_and_gate(boundary, turns).get("refusal")


def test_empty_draft_refuses():
    gated = validate_and_gate(_note(), MIC_CHECK_TURNS)
    assert gated["refusal"] is True
    assert "no claims" in gated["refusal_reason"]


def test_refusal_plain_text_is_the_refusal_not_a_note():
    gated = validate_and_gate(_note(), MIC_CHECK_TURNS)
    plain = note_as_plain_text(gated)
    assert "insufficient clinical content" in plain
    assert "S:" not in plain


# --------------------------------------------------- approval is impossible

def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")
def test_refusal_note_cannot_be_approved():
    auth.ensure_schema()
    consultations.ensure_schema()
    from app.main import app

    async def build() -> int:
        cid = await consultations.create_consultation()
        await consultations.save_turns(cid, MIC_CHECK_TURNS)
        gated = validate_and_gate(_note(subjective=[("Fabricated.", [])]),
                                  MIC_CHECK_TURNS)
        await consultations.save_note(cid, gated)
        await consultations.set_status(cid, "awaiting_review")
        return cid

    cid = asyncio.run(build())
    client = TestClient(app)
    response = client.post(
        "/api/register",
        json={"username": f"doc_{secrets.token_hex(4)}", "password": "test-password-123",
              "display_name": "Doc", "role": "doctor"},
    )
    assert response.status_code == 200

    response = client.post(f"/api/consultations/{cid}/approve", json={"text": "S:\n"})
    assert response.status_code == 409
    state = client.get(f"/api/consultations/{cid}").json()
    assert state["status"] == "awaiting_review"  # never became approved
    assert state["note"]["content"]["refusal"] is True


# ------------------------------------------- end-to-end with the real model

def _ollama_has_model() -> bool:
    from app.notes import NOTE_MODEL, OLLAMA_URL

    try:
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0).json()
        return any(m["name"] == NOTE_MODEL.removeprefix("hf.co/") or NOTE_MODEL in m["name"]
                   for m in tags.get("models", []))
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_has_model(),
                    reason="Ollama with the note model is not available")
def test_draft_note_on_mic_check_transcript_refuses():
    """Regression for consultation #78: the real model, a mic-check
    transcript, and whatever it fabricates must come out as a refusal."""
    from app.notes import draft_note

    note = asyncio.run(draft_note(MIC_CHECK_TURNS))
    assert note.get("refusal") is True, (
        "mic-check transcript produced an approvable note: " + str(note)
    )
