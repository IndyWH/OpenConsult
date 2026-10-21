"""The background block (spec 15.11 rulings 5 and 10; 8.3; 8.4; 8.5; R4,
R25; D23, D24): built and tested on made notes in 7a; since 7b carried
by the two calls of the pass while the switch is on, never by the note
or the label check, with the mark of 8.5 on the panel and at review.
What a model would say is never asserted; what it would read is."""

import json
from datetime import datetime, timezone

from openconsult import words
from openconsult.consult import messages
from openconsult.consult.background import BACKGROUND_NOTE_MAX_WORDS, block_for, build_block, date_in_words, lay_out
from openconsult.consult.earlier import ApprovedNote, sections_of
from openconsult.consult.live import FINAL
from openconsult.prompts import loader
from openconsult.speech.choices import NEMOTRON
from openconsult.speech.door import Door as SpeechDoor
from openconsult.web.live import capture_from
from tests.conftest import text_of
from tests.fakes import MadeUpWorker
from tests.test_review_page import CAPTURE, LINES, LOUD, engine_with, run_through
from tests.test_start import TICKS
from tests.test_stop import until

WHEN = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)
HEADING = loader.file_text("background.frame").split("\n")[0]


def made(cid, day, **sections):
    full = {"subjective": [], "objective": [], "assessment": [], "plan": [], **sections}
    return ApprovedNote(cid, day, day, full)


def test_ruling_5_D23_the_block_lays_out_three_made_notes_newest_first_with_the_date_in_words_and_none_for_an_empty_section():
    notes = [made(3, WHEN, subjective=["cough 3 days [2]", "no fever"], assessment=["viral URTI"], plan=["fluids", "return if worse"]),
             made(2, datetime(2026, 1, 1, tzinfo=timezone.utc), subjective=["made up"], objective=["BP 120/80"]),
             made(1, datetime(2025, 12, 31, tzinfo=timezone.utc), plan=["only a plan"])]
    block = build_block(notes)
    assert block == (
        "BACKGROUND FROM EARLIER CONSULTATIONS, approved by the doctor:\n"
        "Consultation of 12 March 2026:\nSubjective: cough 3 days [2]\nno fever\nObjective: none\nAssessment: viral URTI\n"
        "Plan: fluids\nreturn if worse\n\n"
        "Consultation of 1 January 2026:\nSubjective: made up\nObjective: BP 120/80\nAssessment: none\nPlan: none\n\n"
        "Consultation of 31 December 2025:\nSubjective: none\nObjective: none\nAssessment: none\nPlan: only a plan\n\n"
        "This is background only. Today's problem may be new and unrelated to it.")
    # The citation is stripped where the entries come from an approved text (sections_of); the layout keeps the words it is given.
    assert sections_of("Subjective\ncough 3 days [2]\n")["subjective"] == ["cough 3 days"]
    assert date_in_words(datetime(2026, 10, 4)) == "4 October 2026"
    assert '"' not in block


def test_ruling_5_D23_a_note_over_the_limit_is_cut_at_the_end_of_an_entry_with_the_cut_line_last():
    assert BACKGROUND_NOTE_MAX_WORDS == 400
    whole = made(1, WHEN, subjective=["one two three"], objective=["four five"], assessment=["six"], plan=["seven eight"])
    assert lay_out(whole, max_words=8).endswith("Plan: seven eight") and "cut" not in lay_out(whole, max_words=8)
    cut = lay_out(whole, max_words=5)          # the objective entry fits (5 words), the assessment's would pass
    assert cut == "Consultation of 12 March 2026:\nSubjective: one two three\nObjective: four five\nThe note is cut here"
    cut_in_section = lay_out(made(1, WHEN, subjective=["a b", "c d", "e f"]), max_words=4)
    assert cut_in_section == "Consultation of 12 March 2026:\nSubjective: a b\nc d\nThe note is cut here"
    empty_first = lay_out(made(1, WHEN, assessment=["a b", "c d"]), max_words=2)
    assert empty_first == "Consultation of 12 March 2026:\nSubjective: none\nObjective: none\nAssessment: a b\nThe note is cut here"
    first_too_long = lay_out(made(1, WHEN, subjective=["a b c"]), max_words=2)
    assert first_too_long == "Consultation of 12 March 2026:\nThe note is cut here"
    long_note = made(1, WHEN, subjective=[("word " * 300).strip()], plan=[("word " * 101).strip()])
    # 300 words fit; the plan's 101 would pass 400: the empty sections before the cut say none, the plan is not written.
    assert lay_out(long_note).endswith(("word " * 300).strip() + "\nObjective: none\nAssessment: none\nThe note is cut here")


def test_ruling_5_8_3_only_notes_approved_before_the_consultation_started_reach_the_block_and_a_deleted_one_is_gone(tmp_path, clock, machine):
    app, client, c = run_through(tmp_path, clock, machine, _doors(), engine_with())
    p = app.state.parts
    assert block_for(p.notes, 1, clock(), 2) is None                         # a draft is not an approval (R25)
    client.post("/consultations/1/note/refuse")
    assert block_for(p.notes, 1, clock(), 2) is None                         # a refused note is not
    _approve_rows(p, 1)
    clock.advance(minutes=1)
    block = block_for(p.notes, 1, clock(), 2)
    assert block.startswith(HEADING) and "Consultation of 4 October 2026:" in block and "made up impression" in block
    assert block_for(p.notes, 1, clock(), 1) is None                         # never the consultation itself
    assert block_for(p.notes, 1, datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc), 2) is None   # approved after that moment
    # A deleted consultation has no rows: its note is gone from the block (ruling 8 builds the delete; here the rows go).
    with p.db.transaction() as con:
        con.execute("DELETE FROM note_approval WHERE consultation_id = 1")
    assert block_for(p.notes, 1, clock(), 2) is None


def _three_consultations(tmp_path, clock, machine):
    """Consultation 1 approved; 2 under the same patient with the switch on;
    3 with it off; each fed eight pieces and stopped to final."""
    app, client, c = run_through(tmp_path, clock, machine, _doors(), engine_with(note=[_NOTE, _NOTE, _NOTE]))
    p = app.state.parts
    _approve_rows(p, 1)
    for cid, data in ((2, {**TICKS, "earlier_notes": "yes"}), (3, TICKS)):
        clock.advance(minutes=1)
        client.post("/consultations/start/1", data=data)
        c = p.running[cid]
        c.begin_sound(capture_from(CAPTURE))
        for _ in range(8):
            c.sound(LOUD)
            c.wait_for_pass()
        client.post(f"/consultations/{cid}/stop")
        assert until(lambda: c.stop_stage == "who_spoke")
        client.post(f"/consultations/{cid}/speakers", data={"speaker": "S1"})
        assert until(lambda: c.state == FINAL)
    return app, client, p


def test_8_4_D24_R4_the_two_calls_get_the_block_only_while_the_switch_is_on_and_the_note_and_the_label_check_never_do(tmp_path, clock, machine):
    app, client, p = _three_consultations(tmp_path, clock, machine)
    on, off = p.running[2], p.running[3]
    assert p.consultations.get(2)["earlier_notes_shown"] == 1 and p.consultations.get(3)["earlier_notes_shown"] == 0
    block = block_for(p.notes, 1, on.started_at, 2)
    assert block.startswith(HEADING) and on.background == block and off.background is None
    calls = p.consultations.model_calls(2)
    assert sorted({call["job"] for call in calls}) == ["alarm", "assessment", "label_check", "note"]
    for call in calls:
        user = json.loads(call["request"])["user"]
        if call["job"] in ("alarm", "assessment"):
            assert user.count(HEADING) == 1 and "This is background only" in user, call["job"]
        else:
            assert HEADING not in user and "This is background only" not in user, call["job"]
    # The stored request holds the message as sent: the patient line, the block, the frame around the transcript (ruling 5).
    stored = p.consultations.passes(2)[0]
    alarm_call = [c for c in calls if c["job"] == "alarm" and c["id"] == stored["alarm_call_id"]][0]
    assert json.loads(alarm_call["request"])["user"] == messages.with_background(
        messages.with_patient(messages.alarm_message(stored["transcript"]), on.model_patient), block)
    assert json.loads(alarm_call["request"])["user"].split(f"{block}\n\n", 1)[1] == loader.fill(loader.frame("alarm"), transcript=stored["transcript"])
    # With the switch off no request holds it, and the note's call reads today's turns alone (R4; D24).
    for call in p.consultations.model_calls(3):
        assert HEADING not in json.loads(call["request"])["user"], call["job"]
    note_call = [c for c in p.consultations.model_calls(2) if c["job"] == "note"][0]
    assert json.loads(note_call["request"])["user"].startswith("TRANSCRIPT:\n[0]")


def test_ruling_10_8_5_the_mark_shows_on_the_decision_support_panel_while_the_block_is_sent_and_at_review(tmp_path, clock, machine):
    from openconsult.web.live import script_words
    app, client, p = _three_consultations(tmp_path, clock, machine)
    assert p.running[2].page_state()["background"] is True and p.running[3].page_state()["background"] is False
    assert p.running[1].page_state()["background"] is False                                      # no note before it
    assert script_words()["EARLIER_NOTES_IN_USE"] == words.EARLIER_NOTES_IN_USE == "Earlier notes in use."
    # At review the same words beside the model's differentials, only where the row says the model read them.
    assert 'id="background-read"' in client.get("/consultations/2").text and words.EARLIER_NOTES_IN_USE in text_of(client.get("/consultations/2"))
    for cid in (1, 3):
        assert 'id="background-read"' not in client.get(f"/consultations/{cid}").text
    assert words.EARLIER_NOTES_IN_USE not in client.get("/consultations/2/note.txt").text    # the copy text carries no mark
    # A fourth consultation with the switch on but no mark line until a pass; its live page's state carries the flag.
    clock.advance(minutes=1)
    client.post("/consultations/start/1", data={**TICKS, "earlier_notes": "yes"})
    raw = client.get("/consultations/4").text
    assert '"background": true' in raw and words.EARLIER_NOTES_IN_USE in raw


_NOTE = {"reasoning": "made up.", "subjective": [{"text": "made up history", "turns": [0]}], "objective": [],
         "assessment": [{"text": "made up impression", "turns": [0]}], "plan": []}


def _doors():
    # One worker serves both consultations (the door keeps it): lines for the first's eight pieces, then the second's.
    return {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: MadeUpWorker(live=LINES + ([[]] * 6 + LINES) * 2), installed=lambda: True)}


def _approve_rows(p, cid):
    from openconsult.consult import note
    draft = p.notes.current_draft(cid)
    p.notes.approve(cid, draft["id"], note.plain_text(p.notes.entries(draft["id"])))
