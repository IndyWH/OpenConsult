"""The note is given the patient's age and sex, and the code checks the
note's stated age and sex against the record.

Owner decision 3 Oct 2026 (Task 5d). The note model was told nothing about
the patient and called a man "they". With the line it writes "47yo male
presenting with…", as a GP would, but the age and sex come from the front
desk, not the transcript, and the gate only checked that a cited turn
exists. So the gate now checks every claim's stated age and sex noun
against the record. A claim that contradicts it is kept and gets
`record_mismatch` and `flagged`. Nothing is dropped and the note is not
refused for it. The model is stubbed; no Ollama, no database.
"""

import asyncio
import copy
import json

import httpx
import pytest

from app import cds, notes
from app.notes import validate_and_gate

_REAL_CLIENT = httpx.AsyncClient

TURNS = [
    {"idx": 0, "role": "Doctor", "start": 0.0, "end": 3.0,
     "text": "What brings you in today?", "confidence": 0.9},
    {"idx": 1, "role": "Patient", "start": 3.0, "end": 9.0,
     "text": "I've had a scratchy throat since yesterday and a blocked nose.",
     "confidence": 0.9},
    {"idx": 2, "role": "Patient", "start": 9.0, "end": 15.0,
     "text": "My dad had a heart attack at 52, so I worry about my chest.",
     "confidence": 0.9},
]
# Today's note message for these turns, written out by hand: the patient
# line goes in front of exactly this, and nothing else changes.
_TODAY_NOTE_MESSAGE = (
    "TRANSCRIPT:\n"
    "[0] Doctor: What brings you in today?\n"
    "[1] Patient: I've had a scratchy throat since yesterday and a blocked nose.\n"
    "[2] Patient: My dad had a heart attack at 52, so I worry about my chest.")
MAN = {"age": 47, "sex": "M"}


def _note(*subjective) -> dict:
    return {"reasoning": "", "subjective": [{"text": t, "turns": ns} for t, ns in subjective],
            "objective": [], "assessment": [{"text": "URTI.", "turns": [1]}],
            "plan": [{"text": "Self-care advice.", "turns": [0]}]}


def _claims(gated: dict) -> list[dict]:
    return [c for s in notes.SECTIONS for c in gated[s]]


# ------------------------------------------------------- the note request

def _capture(monkeypatch, reply: dict) -> list[dict]:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(reply)}})

    monkeypatch.setattr(notes.httpx, "AsyncClient",
                        lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    return seen


def _draft_with(monkeypatch, patient, reply: dict | None = None) -> tuple[dict, dict]:
    """The one note request draft_note sends for this patient, and its note."""
    seen = _capture(monkeypatch, reply or _note(("Scratchy throat since yesterday.", [1])))
    note = asyncio.run(notes.draft_note(copy.deepcopy(TURNS), patient))
    assert [b["messages"][0]["content"] for b in seen] == [notes.NOTE_PROMPT]
    return seen[0], note


@pytest.mark.parametrize("age, sex, line", [
    (31, "F", "The patient is a 31-year-old woman."),
    (47, "M", "The patient is a 47-year-old man."),
    (15, "M", "The patient is a 15-year-old boy."),
])
def test_the_note_message_opens_with_the_patient_line(monkeypatch, age, sex, line):
    with_line, _ = _draft_with(monkeypatch, {"age": age, "sex": sex})
    without, _ = _draft_with(monkeypatch, None)
    assert line == cds.patient_line(age, sex)            # the shared function's line
    assert with_line["messages"][1]["content"] == f"{line}\n\n{_TODAY_NOTE_MESSAGE}"
    assert without["messages"][1]["content"] == _TODAY_NOTE_MESSAGE
    # Only the user message differs: system prompt, schema, options, model.
    with_line["messages"][1]["content"] = without["messages"][1]["content"]
    assert with_line == without


@pytest.mark.parametrize("patient", [
    None,                                     # a consultation with no patient row
    {},
    {"age": None, "sex": None},               # an old row: no age or sex
    {"age": None, "sex": "F"},
    {"age": 47, "sex": None},
    {"age": 47, "sex": "X"},
    {"age": 47},
])
def test_no_line_and_no_check_without_a_usable_patient(monkeypatch, patient):
    wrong = _note(("52yo female with scratchy throat.", [1]))   # wrong for any record
    request, note = _draft_with(monkeypatch, patient, reply=wrong)
    assert request["messages"][1]["content"] == _TODAY_NOTE_MESSAGE
    # The gate's output is exactly today's: no record_mismatch key, no flag.
    assert note == validate_and_gate(copy.deepcopy(wrong), TURNS)
    assert note["subjective"] == [{"text": "52yo female with scratchy throat.", "turns": [1],
                                   "uncited": False, "flagged": False}]


def test_the_patient_name_never_reaches_the_note_model(monkeypatch):
    name = "Zephyrine Quillfeather"
    request, _ = _draft_with(monkeypatch, {"name": name, "age": 31, "sex": "F"})
    sent = json.dumps(request, ensure_ascii=False)
    # The record did reach the note code: its age and sex are in the message.
    assert request["messages"][1]["content"].startswith("The patient is a 31-year-old woman.")
    for part in (name, "Zephyrine", "Quillfeather"):
        assert part not in sent


def test_draft_note_hands_the_patient_to_the_check(monkeypatch):
    _, note = _draft_with(monkeypatch, MAN, reply=_note(("46yo male, scratchy throat.", [1])))
    assert note["subjective"][0]["record_mismatch"] is True
    assert note["subjective"][0]["flagged"] is True


# ------------------------------------------------------------- the check

@pytest.mark.parametrize("stated", [
    "47yo male", "47 yo male", "47 y/o male", "47-year-old man", "47 year old man",
    "47 years old, male", "Male aged 47", "man, age 47", "47yo gentleman",
])
def test_the_records_age_and_sex_pass(stated):
    note = _note((f"{stated}, scratchy throat since yesterday.", [1]),
                 ("Man with a blocked nose.", [1]))
    gated = validate_and_gate(copy.deepcopy(note), TURNS, MAN)
    assert gated == validate_and_gate(copy.deepcopy(note), TURNS)   # exactly today's output
    assert not any(c.get("record_mismatch") or c["flagged"] for c in _claims(gated))
    # Not vacuous: the same claim against another age is caught.
    other = validate_and_gate(copy.deepcopy(note), TURNS, {"age": 48, "sex": "M"})
    assert other["subjective"][0].get("record_mismatch") is True


@pytest.mark.parametrize("stated", [
    "46yo male", "46 y/o male", "46-year-old man", "46 year old man", "Male aged 46",
    "man, age 46", "64 years old",
])
def test_a_wrong_age_is_flagged_not_dropped(stated):
    claim = f"{stated}, scratchy throat since yesterday."
    gated = validate_and_gate(_note((claim, [1])), TURNS, MAN)
    assert not gated.get("refusal")
    first = gated["subjective"][0]
    assert first["text"] == claim                      # kept, word for word
    assert first["turns"] == [1] and first["uncited"] is False   # citation as today
    assert first["record_mismatch"] is True and first["flagged"] is True
    # The other claims are untouched.
    assert all("record_mismatch" not in c and not c["flagged"] for c in _claims(gated)[1:])


@pytest.mark.parametrize("claim", [
    "47yo female, scratchy throat since yesterday.",
    "47-year-old woman with a blocked nose.",
    "Woman, aged 47, scratchy throat.",
    "Female presenting with scratchy throat.",
    "Lady with a blocked nose.",
    "47yo girl with a scratchy throat.",
])
def test_a_wrong_sex_noun_is_flagged(claim):
    gated = validate_and_gate(_note((claim, [1])), TURNS, MAN)
    first = gated["subjective"][0]
    assert first["record_mismatch"] is True and first["flagged"] is True
    assert first["text"] == claim and first["turns"] == [1]
    # Not vacuous: the same claim for a 47-year-old woman passes.
    woman = validate_and_gate(_note((claim.replace("girl", "woman"), [1])), TURNS,
                              {"age": 47, "sex": "F"})
    assert "record_mismatch" not in woman["subjective"][0]


def test_an_uncited_claim_with_a_wrong_age_is_flagged_and_stays_uncited():
    gated = validate_and_gate(_note(("46yo male with sore throat.", [])), TURNS, MAN)
    first = gated["subjective"][0]
    assert first["uncited"] is True and first["turns"] == []
    assert first["record_mismatch"] is True and first["flagged"] is True


def test_a_relatives_age_spoken_in_a_cited_turn_is_not_flagged():
    for claim in ("Father had MI aged 52.", "FHx: father MI at 52 years old.",
                  "Father, 52yo male, had MI."):
        gated = validate_and_gate(_note((claim, [2])), TURNS, {"age": 31, "sex": "F"})
        assert "record_mismatch" not in gated["subjective"][0], claim
        assert gated["subjective"][0]["flagged"] is False, claim
        # Not vacuous: cited to a turn that does not say 52, it is flagged.
        elsewhere = validate_and_gate(_note((claim, [1])), TURNS, {"age": 31, "sex": "F"})
        assert elsewhere["subjective"][0]["record_mismatch"] is True, claim


@pytest.mark.parametrize("claim", [
    "Wife says he snores.",                       # a woman's note may say he of her husband
    "Husband drove her in.",
    "They are worried about their chest.",
    "Patient is concerned about his chest.",
])
def test_pronouns_are_not_checked(claim):
    for patient in ({"age": 31, "sex": "F"}, MAN):
        gated = validate_and_gate(_note((claim, [1])), TURNS, patient)
        assert "record_mismatch" not in gated["subjective"][0]


def test_months_are_not_an_age_in_years():
    baby = {"age": 0, "sex": "F"}
    gated = validate_and_gate(_note(("Baby girl aged 6 months, coryzal.", [1])), TURNS, baby)
    assert "record_mismatch" not in gated["subjective"][0]
    boy = validate_and_gate(_note(("Baby boy aged 6 months, coryzal.", [1])), TURNS, baby)
    assert "record_mismatch" not in boy["subjective"][0]   # "boy" is not tied to an age


def test_a_record_mismatch_never_makes_a_refusal():
    every = _note(("46yo female.", [1]), ("Woman with a scratchy throat.", [1]))
    gated = validate_and_gate(every, TURNS, MAN)
    assert not gated.get("refusal")
    assert sum(bool(c.get("record_mismatch")) for c in _claims(gated)) == 2
    assert len(_claims(gated)) == 4


# ------------------------------------------------------------- the callers

def test_both_note_callers_pass_the_consultations_patient_record(monkeypatch):
    from pathlib import Path

    from app import consultations, finalize, frontdesk

    rows = {7: {"id": 7, "name": "Zephyrine Quillfeather", "age": 31, "sex": "F"}}

    async def get_consultation(cid):
        return {"id": cid, "patient_id": {1: 7, 2: None}[cid]}

    async def get_patient(pid):
        return rows.get(pid)

    async def get_turns(cid):
        return copy.deepcopy(TURNS)

    seen = []

    async def draft_note(turns, patient=None):
        seen.append(patient)
        return {"refusal": True}

    async def save_note(cid, note):
        return 1

    monkeypatch.setattr(consultations, "get_consultation", get_consultation)
    monkeypatch.setattr(frontdesk, "get_patient", get_patient)
    monkeypatch.setattr(consultations, "get_turns", get_turns)
    monkeypatch.setattr(consultations, "save_note", save_note)
    monkeypatch.setattr(finalize, "draft_note", draft_note)
    asyncio.run(finalize.regenerate_note(1))
    asyncio.run(finalize.regenerate_note(2))
    # Age and sex only: the name stays behind.
    assert seen == [{"age": 31, "sex": "F"}, None]
    # The pipeline's own call (after the transcript gates, so not driven
    # here) goes through the same function.
    source = (Path(__file__).parent.parent / "app" / "finalize.py").read_text()
    calls = [line.strip() for line in source.splitlines() if "await draft_note(" in line]
    assert len(calls) == 2
    assert all("await note_patient(cid)" in call for call in calls)
