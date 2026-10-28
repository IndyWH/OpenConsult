"""The referral list and the sorting by code (spec 15.12, rulings 2, 8
and 11; R2, R5, R20, R30; 10.4). Made-up answers on made-up notes; no
model's words asserted."""

from datetime import date

import pytest

from openconsult.consult import referral_note, referrals
from openconsult.consult.consultations import Consultations
from openconsult.consult.letter_rows import Letters
from openconsult.consult.note_rows import DraftRow, Notes
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineTimeout
from openconsult.llm.record import ModelCalls
from openconsult.patients.audit import Audit
from openconsult.patients.patients import Patients
from tests.fakes import FakeEngine
from tests.test_referral_note import TEXT

LINES = referral_note.numbered_lines(
    "Subjective\nmade up history\n\nObjective\nmade up finding\n\nAssessment\nmade up impression\n\n"
    "Plan\nUrgent suspected cancer referral to gastroenterology for a made-up test.\nRoutine referral to ENT for a made-up polyp.\n"
    "Omeprazole 20 mg od meanwhile.\n")


def given(specialty, lines, suggestion=False, title="Physician", reason="a made reason", urgency="routine"):
    return {"specialty": specialty, "title": title, "reason": reason, "urgency": urgency, "lines": lines, "suggestion": suggestion}


def test_ruling_2_code_sorts_the_items_by_the_cited_plan_line_and_the_specialtys_word():
    answer = {"reasoning": "made up", "referrals": [
        given("Gastroenterology", [8], urgency="urgent"),                 # cites the plan line that holds its word: stated
        given("Dermatology", [2]),                                       # cites a subjective line: demoted
        given("Cardiology", [10]),                                       # cites a plan line without its word: demoted
        given("Neurology", [99, True]),                                  # cites no existing line (a boolean is not a number): suggested, lines emptied
        given("ENT", [3, 9], suggestion=True),                           # marked a suggestion, but a plan line states it: stated
        given("", [8]),                                                  # no specialty: dropped
        given("Rheumatology", [5], suggestion=True, urgency="soon")]}    # a made urgency reads as routine
    found = referrals.sort_items(answer, LINES)
    assert [(i.kind, i.specialty, i.lines, i.position, i.urgency) for i in found] == [
        ("stated", "Gastroenterology", [8], 0, "urgent"), ("stated", "ENT", [3, 9], 1, "routine"),
        ("suggested", "Dermatology", [2], 2, "routine"), ("suggested", "Cardiology", [10], 3, "routine"),
        ("suggested", "Neurology", [], 4, "routine"), ("suggested", "Rheumatology", [5], 5, "routine")]
    # The specialty's words as a whole-word run through normalise: case, a plural letter and spelling fold; a part of a word does not.
    plan = [line for line in LINES if line.n == 8][0]
    assert referrals.states_referral(plan, "gastroenterology") and referrals.states_referral(plan, "Suspected cancer referral")
    assert not referrals.states_referral(plan, "gastro") and not referrals.states_referral(plan, "ENT")
    assert referrals.holds_words("Routine referral to ENT for a polyp.", "ent") and not referrals.holds_words("a sentence", "ent")
    assert referrals.holds_words("Referral to haematology.", "Hematology")                     # the spelling table
    heading = [line for line in LINES if line.n == 7][0]
    assert heading.heading and not referrals.states_referral(heading, "Plan")                # a heading states nothing
    assert referrals.sort_items({"reasoning": "x", "referrals": []}, LINES) == [] and referrals.sort_items({}, LINES) == []


@pytest.fixture
def rows(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    audit = Audit(db, clock)
    made = {"db": db, "audit": audit, "consultations": Consultations(db, clock), "notes": Notes(db, clock),
            "letters": Letters(db, clock), "patients": Patients(db, audit, clock)}
    yield made
    db.close()


def approved(rows, text=TEXT, born=date(1962, 3, 1)):
    patient = rows["patients"].add("Made-up", born, "F")
    cid = rows["consultations"].start(patient.id, 15, "nemotron", "made-up", "0", "tag", "d", 2)
    rows["consultations"].set(cid, state="final")
    draft = rows["notes"].add_draft(DraftRow(cid, "stop", None, "e", "0", "t", "d", "h", "x", None, None, 1, 1, False, None, 1))
    rows["notes"].approve(cid, draft, text)
    return cid


def test_ruling_2_ruling_11_the_list_call_runs_once_stores_the_note_lines_sent_and_a_failed_call_keeps_its_row(rows, clock):
    answer = {"reasoning": "made reasoning", "referrals": [given("a made-up specialty", [9], urgency="urgent"), given("Other", [2], suggestion=True)]}
    engine = FakeEngine({"referrals": [answer, EngineTimeout("no answer"), answer]})
    door = Door(engine, ModelCalls(rows["db"], clock))
    cid = approved(rows)
    listed = referrals.make_list(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], cid)
    assert listed["note_lines"] == referral_note.list_text(referral_note.numbered_lines(TEXT)) and listed["reasoning"] == "made reasoning"
    assert listed["failure"] is None and listed["call_id"] is not None and listed["approval_id"] == rows["notes"].approval(cid)["id"]
    items = rows["letters"].items(cid)
    assert [(i["kind"], i["specialty"], i["note_lines"], i["call_id"], i["list_id"], i["position"]) for i in items] == [
        ("stated", "a made-up specialty", [9], listed["call_id"], listed["id"], 0), ("suggested", "Other", [2], listed["call_id"], listed["id"], 1)]
    assert engine.calls_for("referrals")[0].user == referral_note.list_message(TEXT, referral_note.patient_of(rows["consultations"].get(cid)))
    line = rows["audit"].lines()[0]
    assert line.event == "referrals.listed" and line.detail.startswith(f"consultation {cid}: 1 stated, 1 suggested")
    assert "made up history" not in line.detail and "specialty" not in line.detail
    # Once: a second make_list gives the list that stands and makes no call.
    assert referrals.make_list(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], cid)["id"] == listed["id"]
    assert len(engine.calls_for("referrals")) == 1
    # A failed call keeps its row with the failure and no item, said in the audit log; no second call by itself (R30).
    other = approved(rows)
    failed = referrals.make_list(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], other)
    assert failed["failure"].startswith("too_slow") and rows["letters"].items(other) == [] and failed["note_lines"]
    assert rows["audit"].lines()[0].event == "referrals.failed" and len(engine.calls_for("referrals")) == 2
    # No approved note: no call (R5).
    third = rows["consultations"].start(1, 15, "nemotron", "made-up", "0", "tag", "d", 2)
    with pytest.raises(ValueError):
        referrals.make_list(door, rows["letters"], rows["notes"], rows["consultations"], rows["audit"], third)
    assert len(engine.calls_for("referrals")) == 2
    # The doctor's own item: no call, kind named, positions among the named.
    one = referrals.name_item(rows["letters"], rows["audit"], cid, " Cardiology ", "Cardiologist ")
    two = referrals.name_item(rows["letters"], rows["audit"], cid, "Urology", "Urologist")
    named = [i for i in rows["letters"].items(cid) if i["kind"] == "named"]
    assert [(i["id"], i["specialty"], i["title"], i["position"]) for i in named] == [(one, "Cardiology", "Cardiologist", 0), (two, "Urology", "Urologist", 1)]
    assert rows["audit"].lines()[0].event == "referral.named" and len(engine.calls_for("referrals")) == 2
