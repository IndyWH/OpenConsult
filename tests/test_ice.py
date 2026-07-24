"""ICE capture in notes + the letter's patient-expectation sentence
(NOTE_ICE_SPEC.md addendum, 2026-07-24).

Model-behaviour tests: need Ollama serving MedGemma locally; skipped
otherwise (same pattern as test_cds). Deterministic decoding (temp 0,
seed 42) keeps them stable.
"""

import asyncio
import re

import httpx
import pytest

from app.letters import draft_letter
from app.notes import NOTE_MODEL, OLLAMA_URL, draft_note


def _ollama_has_model() -> bool:
    try:
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2.0).json()
        return any(NOTE_MODEL in m["name"] or m["name"] == NOTE_MODEL.removeprefix("hf.co/")
                   for m in tags.get("models", []))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_has_model(), reason="Ollama with the note model is not available"
)


def _turns(*texts_roles):
    return [
        {"idx": i, "role": role, "start": float(i), "end": float(i) + 1.0,
         "text": text, "confidence": 0.95}
        for i, (role, text) in enumerate(texts_roles)
    ]


ICE_TRANSCRIPT = _turns(
    ("Doctor", "What brings you in today?"),
    ("Patient", "I've had this cough for three weeks now. It's not shifting."),
    ("Doctor", "Any blood when you cough? Fevers or night sweats?"),
    ("Patient", "No blood, no fevers. But my father died of lung cancer and "
                "I'm really worried this could be the same thing. I was hoping "
                "you could send me for a chest X-ray."),
    ("Doctor", "I understand. Let me examine your chest first."),
)

NO_ICE_TRANSCRIPT = _turns(
    ("Doctor", "Good morning. I have your blood pressure readings here — "
               "one thirty over eighty today, well controlled."),
    ("Patient", "That's good to hear."),
    ("Doctor", "Carry on with amlodipine five milligrams daily and we will "
               "review again in three months."),
    ("Patient", "Okay doctor, thank you."),
)


def _ice_claims(note):
    return [c for section in ("subjective", "objective", "assessment", "plan")
            for c in note[section] if c["text"].lower().startswith("patient's")]


def test_note_captures_cited_ice_when_patient_volunteers_it():
    note = asyncio.run(draft_note(ICE_TRANSCRIPT))
    assert not note.get("refusal")
    ice = _ice_claims(note)
    labels = " ".join(c["text"].lower() for c in ice)
    assert "patient's expectations:" in labels
    expectation = next(c for c in ice
                       if c["text"].lower().startswith("patient's expectations"))
    assert "x-ray" in expectation["text"].lower() or "xray" in expectation["text"].lower()
    # Grounded like every claim: cites the turn where the patient said it.
    assert 3 in expectation["turns"]
    # ICE lives at the end of Subjective, per the owner's spec.
    subjective_texts = [c["text"].lower() for c in note["subjective"]]
    assert any(t.startswith("patient's") for t in subjective_texts)


def test_note_omits_ice_entirely_when_transcript_has_none():
    note = asyncio.run(draft_note(NO_ICE_TRANSCRIPT))
    assert not note.get("refusal")
    assert _ice_claims(note) == []


NOTE_WITH_EXPECTATION = """\
S:
  Cough for three weeks, not resolving.
  No haemoptysis, no fever, no night sweats.
  Family history: father died of lung cancer.
  Patient's concerns: worried this could be lung cancer.
  Patient's expectations: hoping for a chest X-ray.
O:
  Chest clear on auscultation.
A:
  Persistent cough, cause not yet established.
P:
  Refer respiratory clinic.
"""

NOTE_WITHOUT_EXPECTATION = """\
S:
  Cough for three weeks, not resolving.
  No haemoptysis, no fever, no night sweats.
  Family history: father died of lung cancer.
O:
  Chest clear on auscultation.
A:
  Persistent cough, cause not yet established.
P:
  Refer respiratory clinic.
"""

PATIENT = {"name": "Test Patient", "age": 58, "sex": "M"}


def test_letter_carries_exactly_one_expectation_sentence_when_note_has_one():
    drafted = asyncio.run(draft_letter(
        NOTE_WITH_EXPECTATION, "Respiratory", PATIENT, "Dr Test"))
    sentences = re.split(r"[.!?]", drafted["body"])
    with_xray = [s for s in sentences if "x-ray" in s.lower() or "xray" in s.lower()]
    assert len(with_xray) == 1


def test_letter_has_no_expectation_sentence_when_note_has_none():
    drafted = asyncio.run(draft_letter(
        NOTE_WITHOUT_EXPECTATION, "Respiratory", PATIENT, "Dr Test"))
    body = drafted["body"].lower()
    assert "x-ray" not in body and "xray" not in body
    assert "hoping" not in body and "expectation" not in body
