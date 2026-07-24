"""Referral letters: grounding gate, approve-first flow, RBAC, audit.

The validation gate is pure post-processing (testable without Ollama,
same split as notes.validate_and_gate); the endpoint tests monkeypatch
the two model calls so the flow runs without MedGemma.
"""

import asyncio
import os
import secrets

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import audit, auth, consultations, letters
from app.letters import (PLACEHOLDER, assemble_letter, citable_line_numbers,
                         format_note_lines, note_lines, validate_letter)

load_dotenv()


# ------------------------------------------------- grounding gate (no DB)

LINES = note_lines("S:\n  Chest tightness since last night.\n"
                   "  BP 150/95 at triage.\nP:\n  Refer cardiology.")
# LINES: ["S:", "Chest tightness since last night.", "BP 150/95 at triage.",
#         "P:", "Refer cardiology."]


def test_cited_paragraph_passes():
    result = validate_letter(
        [{"text": "He reports chest tightness since last night.", "note_lines": [2]}],
        LINES)
    assert result["body_paragraphs"] == ["He reports chest tightness since last night."]
    assert result["sentences_grounded"] == 1
    assert result["placeholders"] == 0


def test_uncited_clinical_paragraph_becomes_placeholder():
    result = validate_letter(
        [{"text": "On examination his BP was 150/95.", "note_lines": []}], LINES)
    assert result["body_paragraphs"] == [PLACEHOLDER]
    assert result["placeholders"] == 1


def test_invented_number_becomes_placeholder():
    # Cites a real line, but the dose is nowhere in the cited text —
    # exactly the "atorvastatin 1mg" specimen class from the docket.
    result = validate_letter(
        [{"text": "He takes atorvastatin 10 mg at night.", "note_lines": [2]}], LINES)
    assert result["body_paragraphs"] == [PLACEHOLDER]


def test_number_present_in_cited_line_passes():
    result = validate_letter(
        [{"text": "Blood pressure recorded as 150/95.", "note_lines": [3]}], LINES)
    assert result["body_paragraphs"] == ["Blood pressure recorded as 150/95."]


def test_allowed_numbers_cover_code_supplied_demographics():
    result = validate_letter(
        [{"text": "I would be grateful for your review of this 54-year-old.",
          "note_lines": [2]}], LINES, allowed_numbers={"54"})
    assert result["sentences_grounded"] == 1


def test_courtesy_boilerplate_passes_uncited():
    result = validate_letter(
        [{"text": "Thank you for seeing him at your earliest opportunity.",
          "note_lines": []}], LINES)
    assert result["body_paragraphs"] == [
        "Thank you for seeing him at your earliest opportunity."]


def test_uncited_non_boilerplate_prose_becomes_placeholder():
    result = validate_letter(
        [{"text": "He has a strong family history of ischaemic heart disease.",
          "note_lines": []}], LINES)
    assert result["body_paragraphs"] == [PLACEHOLDER]


# --------- owner's letter framework (REFERRAL_LETTER_STYLE.md addendum)

FULL_NOTE = note_lines(
    "S:\n  Chest tightness on exertion for two weeks.\n"
    "A:\n  Concern for angina.\n"
    "P:\n  An ECG was arranged today.\n  Refer cardiology.")
# 1 "S:" | 2 tightness | 3 "A:" | 4 angina | 5 "P:" | 6 ECG arranged | 7 refer


def test_assessment_and_heading_lines_are_not_citable():
    assert citable_line_numbers(FULL_NOTE) == {2, 6, 7}


def test_paragraph_grounded_only_in_assessment_becomes_placeholder():
    # The gate is the guarantee that a letter never carries the
    # differential: "angina" lives only in the Assessment section.
    result = validate_letter(
        [{"text": "There is concern for angina.", "note_lines": [4]}], FULL_NOTE)
    assert result["body_paragraphs"] == [PLACEHOLDER]
    assert "angina" not in " ".join(result["body_paragraphs"])


def test_assessment_masked_in_model_input_but_numbering_kept():
    masked = format_note_lines(FULL_NOTE, for_letter=True)
    assert "angina" not in masked            # the model never sees the differential
    assert "[4] [assessment — withheld from referral letters]" in masked
    assert "[6] An ECG was arranged today." in masked  # numbering unchanged


def test_tense_upgrade_arranged_to_performed_becomes_placeholder():
    # QA finding on the #66 letter: planned ≠ performed ≠ resulted.
    result = validate_letter(
        [{"text": "An ECG was performed and showed no ischaemia.",
          "note_lines": [6]}], FULL_NOTE)
    assert result["body_paragraphs"] == [PLACEHOLDER]


def test_planned_wording_kept_when_note_says_planned():
    result = validate_letter(
        [{"text": "An ECG was arranged today.", "note_lines": [6]}], FULL_NOTE)
    assert result["body_paragraphs"] == ["An ECG was arranged today."]


def test_result_wording_allowed_when_note_records_a_result():
    lines = note_lines("O:\n  ECG performed: sinus rhythm, no acute changes.")
    result = validate_letter(
        [{"text": "An ECG performed today showed sinus rhythm.",
          "note_lines": [2]}], lines)
    assert result["body_paragraphs"] == ["An ECG performed today showed sinus rhythm."]


def test_validation_is_sentence_level_not_paragraph_level():
    # Seen on the #66 regen: the model under-cited one line and the whole
    # history paragraph died. A bad sentence now costs itself only.
    result = validate_letter(
        [{"text": "He reports chest tightness since last night. "
                  "Episodes last 5-10 minutes.",
          "note_lines": [2]}], LINES)
    assert result["body_paragraphs"] == [
        "He reports chest tightness since last night. " + PLACEHOLDER]
    assert result["sentences_grounded"] == 1
    assert result["placeholders"] == 1


def test_adjacent_failing_sentences_collapse_to_one_placeholder():
    result = validate_letter(
        [{"text": "Episodes last 5-10 minutes. His BP was 180/110. "
                  "He reports chest tightness since last night.",
          "note_lines": [2]}], LINES)
    assert result["body_paragraphs"] == [
        PLACEHOLDER + " He reports chest tightness since last night."]
    assert result["placeholders"] == 2


ICE_NOTE = note_lines(
    "S:\n  Cough for three weeks.\n  Patient's expectations: hoping for a chest X-ray.\n"
    "P:\n  Refer respiratory clinic.")
# 1 "S:" | 2 cough | 3 expectations | 4 "P:" | 5 refer


def test_invented_expectation_is_dropped_not_placeholdered():
    # Seen on the #66 regen: "Patient wants investigation of his chest
    # pain" invented from a Plan line. No ICE bullet → no sentence.
    result = validate_letter(
        [{"text": "The patient was hoping for further investigation.",
          "note_lines": [5]}], ICE_NOTE)
    assert result["body_paragraphs"] == []
    assert result["dropped_expectations"] == 1
    assert result["placeholders"] == 0


def test_expectation_kept_when_note_records_it():
    result = validate_letter(
        [{"text": "He is hoping for a chest X-ray.", "note_lines": [3]}],
        ICE_NOTE)
    assert result["body_paragraphs"] == ["He is hoping for a chest X-ray."]
    assert result["dropped_expectations"] == 0


def test_assemble_letter_uses_server_demographics():
    body = assemble_letter(["Paragraph one."],
                           {"name": "Nimal Perera", "age": 54, "sex": "M"},
                           "Dr S. Herath")
    assert body.startswith("Dear Colleague,")
    assert "Re: Nimal Perera, 54 y, M" in body
    assert body.rstrip().endswith("Yours faithfully,\nDr S. Herath")


# --------------------------------------------------- endpoint flow (DB)

def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


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


def _make_approved_consultation(doctor_id: int) -> int:
    consultations.ensure_schema()
    letters.ensure_schema()

    async def build() -> int:
        cid = await consultations.create_consultation(None, doctor_id)
        await consultations.save_turns(
            cid, [{"role": "Patient", "start": 0.0, "end": 2.0,
                   "text": "Chest tightness since last night.", "confidence": 0.9}])
        await consultations.save_note(
            cid, {"subjective": [{"text": "Chest tightness since last night.",
                                  "turns": [0], "uncited": False, "flagged": False}],
                  "objective": [], "assessment": [], "plan": []})
        await consultations.set_status(cid, "awaiting_review")
        await consultations.approve_note(
            cid, "S:\n  Chest tightness since last night.\nP:\n  Refer cardiology.\n")
        return cid

    return asyncio.run(build())


FAKE_SUGGESTIONS = [{"specialty": "Cardiology",
                     "reason": "Plan: refer cardiology", "urgency": "urgent"}]


@pytest.fixture()
def fake_model(monkeypatch):
    calls = {"suggest": 0, "draft": 0}

    async def fake_suggest(note_text):
        calls["suggest"] += 1
        assert "Chest tightness" in note_text  # approved note text, not transcript
        return FAKE_SUGGESTIONS

    async def fake_draft(note_text, specialty, patient, doctor_name):
        calls["draft"] += 1
        return {"body": f"Dear Colleague,\n\nRe: referral to {specialty}.\n\n"
                        f"Yours faithfully,\n{doctor_name}",
                "grounding": {"paragraphs_total": 1, "paragraphs_grounded": 1,
                              "placeholders": 0}}

    monkeypatch.setattr(letters, "suggest_referrals", fake_suggest)
    monkeypatch.setattr(letters, "draft_letter", fake_draft)
    return calls


@needs_db
def test_letters_require_an_approved_consultation(fake_model):
    doctor = _make_user("doctor")
    client = _client_for(doctor)

    async def build() -> int:
        cid = await consultations.create_consultation(None, doctor["id"])
        await consultations.set_status(cid, "awaiting_review")
        return cid

    cid = asyncio.run(build())
    letters.ensure_schema()
    assert client.post(f"/api/consultations/{cid}/letters/suggest").status_code == 409
    assert client.post(f"/api/consultations/{cid}/letters",
                       json={"specialty": "Cardiology"}).status_code == 409
    assert fake_model["suggest"] == 0 and fake_model["draft"] == 0


@needs_db
def test_letter_rbac_receptionist_and_foreign_doctor_denied(fake_model):
    doctor, recep, other = (_make_user("doctor"), _make_user("receptionist"),
                            _make_user("doctor"))
    cid = _make_approved_consultation(doctor["id"])
    for client, code in ((_client_for(recep), 403), (_client_for(other), 403)):
        assert client.post(f"/api/consultations/{cid}/letters/suggest").status_code == code
        assert client.post(f"/api/consultations/{cid}/letters",
                           json={"specialty": "Cardiology"}).status_code == code
        assert client.put(f"/api/consultations/{cid}/letters/1",
                          json={"body": "x"}).status_code == code
        assert client.post(f"/api/consultations/{cid}/letters/1/approve").status_code == code
    assert fake_model["suggest"] == 0 and fake_model["draft"] == 0


@needs_db
def test_letter_full_flow_with_cache_edit_approve_audit(fake_model):
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    cid = _make_approved_consultation(doctor["id"])

    # Suggest: model called once, then served from the note-version cache.
    first = client.post(f"/api/consultations/{cid}/letters/suggest")
    assert first.status_code == 200
    assert first.json()["suggestions"] == FAKE_SUGGESTIONS
    second = client.post(f"/api/consultations/{cid}/letters/suggest")
    assert second.json()["suggestions"] == FAKE_SUGGESTIONS
    assert fake_model["suggest"] == 1

    # Create a draft letter; it rides on the consultation payload.
    created = client.post(f"/api/consultations/{cid}/letters",
                          json={"specialty": "Cardiology",
                                "reason": "Plan: refer cardiology"})
    assert created.status_code == 200
    lid = created.json()["letter_id"]
    state = client.get(f"/api/consultations/{cid}").json()
    letter = next(l for l in state["letters"] if l["id"] == lid)
    assert letter["status"] == "draft"
    assert "Dear Colleague" in letter["body"]

    # Edit the draft; the edited body wins.
    assert client.put(f"/api/consultations/{cid}/letters/{lid}",
                      json={"body": "Edited body."}).status_code == 200
    state = client.get(f"/api/consultations/{cid}").json()
    assert next(l for l in state["letters"] if l["id"] == lid)["body"] == "Edited body."

    # Approve: letter locks — further edits and re-approval are refused.
    assert client.post(f"/api/consultations/{cid}/letters/{lid}/approve").status_code == 200
    assert client.put(f"/api/consultations/{cid}/letters/{lid}",
                      json={"body": "Nope."}).status_code == 409
    assert client.post(f"/api/consultations/{cid}/letters/{lid}/approve").status_code == 409
    state = client.get(f"/api/consultations/{cid}").json()
    assert next(l for l in state["letters"] if l["id"] == lid)["status"] == "approved"

    # Audit trail covers the whole lifecycle, matching note.* naming.
    events = asyncio.run(audit.recent(50))
    actions = {(e["action"], e["subject_id"]) for e in events}
    assert ("letter.suggested", cid) in actions
    assert ("letter.created", lid) in actions
    assert ("letter.edited", lid) in actions
    assert ("letter.approved", lid) in actions


@needs_db
def test_letters_frozen_on_voided_consultation(fake_model):
    doctor, admin = _make_user("doctor"), _make_user("admin")
    client = _client_for(doctor)
    cid = _make_approved_consultation(doctor["id"])
    created = client.post(f"/api/consultations/{cid}/letters",
                          json={"specialty": "Cardiology"})
    lid = created.json()["letter_id"]

    admin_client = _client_for(admin)
    assert admin_client.post(f"/api/admin/consultations/{cid}/void",
                             json={"reason": "letters freeze test"}).status_code == 200

    assert client.post(f"/api/consultations/{cid}/letters/suggest").status_code == 409
    assert client.put(f"/api/consultations/{cid}/letters/{lid}",
                      json={"body": "x"}).status_code == 409
    assert client.post(f"/api/consultations/{cid}/letters/{lid}/approve").status_code == 409
