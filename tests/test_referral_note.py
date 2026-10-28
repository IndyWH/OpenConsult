"""The approved note as the two letter calls read it (spec 15.12, rulings
2, 3 and 8; the detail The two letter frames; R5, R11, R30; D24; 10.4;
V1_LESSONS 3.4). Made-up notes through a made-up engine; no model's
words asserted."""

import pytest

from openconsult.consult import referral_note
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.jobs import job
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from tests.fakes import FakeEngine, reply

TEXT = ("Subjective\nmade up history\nPatient's expectations: a made-up wish\n\nObjective\nBP 120/80\n\n"
        "Assessment\nmade up impression\n\nPlan\nRoutine referral to a made-up specialty\n")
WOMAN = Patient(64, "F")
LIST = ("The patient is a 64-year-old woman.\n\nAPPROVED CONSULTATION NOTE:\n[1] Subjective\n[2] made up history\n"
        "[3] Patient's expectations: a made-up wish\n[4] Objective\n[5] BP 120/80\n[6] Assessment\n[7] made up impression\n"
        "[8] Plan\n[9] Routine referral to a made-up specialty")
LETTER = ("The patient is a 64-year-old woman.\n\nSPECIALTY: a made-up specialty\n\nAPPROVED CONSULTATION NOTE:\n[1] Subjective\n"
          "[2] made up history\n[3] Patient's expectations: a made-up wish\n[4] Objective\n[5] BP 120/80\n[6] Assessment\n"
          "[7] [assessment withheld from referral letters]\n[8] Plan\n[9] Routine referral to a made-up specialty")


def test_R5_ruling_2_the_two_frames_number_the_approved_text_the_same_and_the_letter_masks_the_assessment():
    lines = referral_note.numbered_lines(TEXT)
    assert [(l.n, l.section, l.heading, l.text) for l in lines][:4] == [
        (1, "subjective", True, "Subjective"), (2, "subjective", False, "made up history"),
        (3, "subjective", False, "Patient's expectations: a made-up wish"), (4, "objective", True, "Objective")]
    assert referral_note.citable(lines) == {2, 3, 5, 9}                 # headings and the Assessment line never
    assert referral_note.words_of(lines)[7] == "made up impression"
    assert referral_note.list_message(TEXT, WOMAN) == LIST and len(LIST.encode()) == 261
    assert referral_note.letter_message(TEXT, "a made-up specialty", WOMAN) == LETTER and len(LETTER.encode()) == 318
    # The numbers are the same in both; only the Assessment entry's words differ.
    shown, masked = referral_note.list_text(lines).split("\n"), referral_note.letter_text(lines).split("\n")
    assert [s.split("]")[0] for s in shown] == [m.split("]")[0] for m in masked]
    assert [i for i, (s, m) in enumerate(zip(shown, masked)) if s != m] == [6]
    # Blank lines and an entry that reads like a heading out of order do not break the numbering.
    odd = "Subjective\n\nPlan\nmade up\n\n\nObjective\nAssessment\n\nPlan\nmade plan\n"
    found = referral_note.numbered_lines(odd)
    assert [(l.n, l.section, l.heading) for l in found] == [
        (1, "subjective", True), (2, "subjective", False), (3, "subjective", False), (4, "objective", True),
        (5, "assessment", True), (6, "plan", True), (7, "plan", False)]
    assert referral_note.numbered_lines("") == [] and referral_note.citable([]) == set()


def test_R5_the_text_sent_is_note_approvals_never_a_drafts_entries(tmp_path, clock):
    # A consultation whose draft entries differ from its approved text (an entry edited after approval cannot happen
    # on the page; made here by rows) sends the approved text.
    from datetime import date
    from openconsult.consult.consultations import Consultations
    from openconsult.consult.note_rows import DraftRow, Notes
    from openconsult.patients.audit import Audit
    from openconsult.patients.patients import Patients
    db = open_database(tmp_path / "rows.db")
    audit, cons, notes = Audit(db, clock), Consultations(db, clock), Notes(db, clock)
    patient = Patients(db, audit, clock).add("Made-up", date(1962, 3, 1), "F")
    cid = cons.start(patient.id, 15, "nemotron", "made-up", "0", "tag", "d", 2)
    draft = notes.add_draft(DraftRow(cid, "stop", None, "e", "0", "t", "d", "h", "x", None, None, 1, 1, False, None, 1,
                                     [{"section": "subjective", "text": "the draft's words", "turns": [0], "lines": [1], "uncited": False}]))
    notes.approve(cid, draft, TEXT)
    approved = notes.approval(cid)["text"]
    assert "the draft's words" not in referral_note.list_message(approved, WOMAN)
    assert "made up history" in referral_note.letter_message(approved, "x", WOMAN)
    # The patient line's age is the age on the consultation's start day from the details it ran with (15.11 ruling 2).
    row = cons.get(cid)
    assert referral_note.patient_of(row) == Patient(64, "F")            # born 1 March 1962, started 4 Oct 2026
    assert referral_note.patient_of({**row, "patient_date_of_birth": "1962-10-05"}) == Patient(63, "F")   # the day before the birthday
    db.close()


def test_R11_3_4_D24_R30_both_letter_calls_open_with_the_patient_line_and_carry_the_named_limits(tmp_path, clock):
    db = open_database(tmp_path / "openconsult.db")
    answer_list = {"reasoning": "made up", "referrals": []}
    answer_letter = {"reasoning": "made up", "paragraphs": [{"text": "Made up.", "note_lines": [2]}]}
    engine = FakeEngine({"referrals": [answer_list, reply({"reasoning": "cut"}, ended="cut")],
                         "letter": [answer_letter, reply({"reasoning": "cut"}, ended="cut")]})
    door = Door(engine, ModelCalls(db, clock))
    listed = door.ask("referrals", referral_note.list_message(TEXT, WOMAN), consultation_id=None)
    drafted = door.ask("letter", referral_note.letter_message(TEXT, "a made-up specialty", WOMAN))
    assert listed.ok and listed.answer == answer_list and drafted.ok and drafted.answer == answer_letter
    for name, text in (("referrals", LIST), ("letter", LETTER)):
        call = engine.calls_for(name)[0]
        assert call.user == text and call.user.startswith("The patient is a 64-year-old woman.\n\n")
        assert call.user.count("The patient is") == 1 and "BACKGROUND FROM EARLIER CONSULTATIONS" not in call.user   # D24
        assert call.system == loader.prompt(name) and call.form == loader.form(name)
        assert (call.temperature, call.seed, call.context, call.think) == (0.0, 42, 16384, False)
    assert (job("referrals").max_tokens, job("referrals").timeout_s) == (1500, 60.0)
    assert (job("letter").max_tokens, job("letter").timeout_s) == (2500, 120.0)
    assert engine.calls_for("referrals")[0].max_tokens == 1500 and engine.calls_for("letter")[0].timeout_s == 120.0
    # A cut reply is too_long, plainly, and nothing is asked a second time by itself (R30; 10.4).
    assert door.ask("referrals", LIST).failure == "too_long" and door.ask("letter", LETTER).failure == "too_long"
    assert len(engine.calls_for("referrals")) == 2 and len(engine.calls_for("letter")) == 2
    # Without a usable patient there is no call (R11).
    with pytest.raises(Exception):
        referral_note.list_message(TEXT, None)
    db.close()
