"""The Start screen for a patient seen before and the earlier-notes panel
(spec 15.11 rulings 3 and 4; 8.2; R15, R25; D23, D25). Made-up notes,
made-up doors; the approved text is the app's own copy text."""

from datetime import datetime, timezone

from openconsult import words
from openconsult.consult.earlier import ApprovedNote, approved_notes, sections_of
from openconsult.web.live import SCRIPT_WORDS, script_words
from tests.conftest import text_of
from tests.test_review_page import reviewed
from tests.test_start import PATIENT, TICKS


def approve(client, cid):
    client.post(f"/consultations/{cid}/note/approve")


def test_ruling_3_D25_the_start_screen_for_a_patient_seen_before_lists_the_approved_notes_and_stores_the_switch(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    approve(client, 1)
    clock.advance(minutes=1)
    raw = client.get("/consultations/start/1").text
    page = text_of(client.get("/consultations/start/1"))
    assert words.EARLIER_NOTES in page and words.SWITCH_SHOWS_ON_SCREEN in page
    assert words.EARLIER_NOTE_LINE.format(number=1, date="4 Oct 2026", line="made up impression") in page
    assert 'name="earlier_notes" value="yes" id="earlier-switch" checked' in raw            # on by default
    assert "background" not in words.SWITCH_SHOWS_ON_SCREEN                                   # 7a: the doctor's screen only
    client.post("/consultations/start/1", data={**TICKS, "earlier_notes": "yes"})
    row = p.consultations.get(2)
    assert row["earlier_notes_shown"] == 1 and row["earlier_notes"] == "[1]"
    client.post("/consultations/start/1", data=TICKS)                                         # the switch turned off
    assert p.consultations.get(3)["earlier_notes_shown"] == 0 and p.consultations.get(3)["earlier_notes"] == "[1]"
    # The headline is the first plan entry where the assessment is empty, and empty where both are.
    plan_only = ApprovedNote(9, clock(), clock(), {"subjective": ["s"], "objective": [], "assessment": [], "plan": ["first plan", "second"]})
    assert plan_only.headline() == "first plan"
    assert ApprovedNote(9, clock(), clock(), sections_of("")).headline() == ""


def test_ruling_3_a_patient_with_no_approved_note_shows_no_list_and_no_switch_and_the_new_patients_start_is_unchanged(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    client.post("/consultations/1/note/refuse")                                               # a refused note does not count
    raw = client.get("/consultations/start/1").text
    assert "earlier-switch" not in raw and words.EARLIER_NOTES not in text_of(client.get("/consultations/start/1"))
    client.post("/consultations/start/1", data={**TICKS, "earlier_notes": "yes"})
    assert p.consultations.get(2)["earlier_notes_shown"] is None and p.consultations.get(2)["earlier_notes"] == "[]"
    client.post("/patients", data={**PATIENT, "name": "New Patient"})
    assert "earlier-switch" not in client.get("/consultations/start/2").text
    assert approved_notes(p.notes, 1) == [] and approved_notes(p.notes, 2) == []


def test_ruling_4_R25_D23_the_earlier_notes_panel_shows_the_last_three_approved_notes_folded_and_opens_the_approved_text(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    p = app.state.parts
    approve(client, 1)
    # Three more approved notes, by rows (made up), newest first on the panel; the oldest of four left out.
    for n in range(2, 5):
        clock.advance(minutes=1)
        cid = p.consultations.start(1, 15, "nemotron", "made-up", "0", "tag", None, 2)
        p.consultations.set(cid, state="final")
        draft = p.notes.add_draft(_draft(cid))
        p.notes.approve(cid, draft, f"Subjective\nmade up history {n} [1]\n\nObjective\n\nAssessment\nimpression {n}\n\nPlan\nplan {n}\n")
    clock.advance(minutes=1)
    client.post("/consultations/start/1", data={**TICKS, "earlier_notes": "yes"})
    raw = client.get("/consultations/5").text
    page = text_of(client.get("/consultations/5"))
    assert words.PANEL_EARLIER_NOTES in page and "/static/earlier.js" in raw
    assert [part.split('"')[0] for part in raw.split('data-note="')[1:]] == ["4", "3", "2"]   # the last three, newest first
    assert "made up impression" not in page                                                   # the fourth (consultation 1) left out
    assert "impression 4" in page and "made up history 4" in page and "made up history 4 [1]" not in page   # citations stripped
    assert 'class="note-body" id="earlier-4" hidden' in raw                                   # folded until pressed
    assert raw.index('id="earlier-notes"') > raw.index('</div>', raw.index('class="fixed-zone"'))   # never in the fixed zone
    assert all(words.SECTION_WORDS[s] in page for s in words.SECTION_WORDS)
    assert client.get("/static/earlier.js").status_code == 200
    # From the rows: only the approvals, before the consultation started, never the consultation itself.
    found = approved_notes(p.notes, 1, before=datetime(2026, 10, 4, 9, 3, tzinfo=timezone.utc))
    assert [n.consultation_id for n in found] == [3, 2, 1]
    assert sections_of(p.notes.approval(1)["text"])["subjective"] == ["made up history"]
    assert sections_of("Subjective\nonly [2] this\n")["plan"] == [] and sections_of("Subjective\nonly [2] this\n")["subjective"] == ["only this"]


def test_ruling_4_the_panel_is_hidden_when_the_switch_is_off_for_this_consultation(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    approve(client, 1)
    clock.advance(minutes=1)
    client.post("/consultations/start/1", data=TICKS)                                         # off
    raw = client.get("/consultations/2").text
    assert 'id="earlier-notes"' not in raw and "made up impression" not in raw
    assert set(script_words()) == set(SCRIPT_WORDS)


def _draft(cid):
    from openconsult.consult.note_rows import DraftRow
    return DraftRow(cid, "stop", None, "e", None, "t", None, "h", "x", None, None, 1, 1, False, None, 1,
                    [{"section": "subjective", "text": "made up", "turns": [0], "lines": [1], "uncited": False}])
