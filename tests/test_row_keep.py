"""Leaving the box of a doubted drug name, and the page keeping its place
(spec 15.10 rulings 11, 28, 33, 34 and 37 and the details of the mend run
of step 6d: Leaving the box, The kept words go, The page keeps its
place; R15). The room run of 15 Nov 2026: a name typed and then left was
lost at the next press, and after a press the page moved by itself. A
made-up page and made-up replies; a made-up name stands for what the
doctor types. The page's scripts are seen in a browser, not run here."""

from openconsult import words
from tests.conftest import refusal_on, text_of
from tests.test_drug_marks import PAGE, REPLY
from tests.test_drug_rows import DRAFT_OFF, TYPED, counted, events, mark_of, row, texts, tick
from tests.test_review_marks import page_of, part
from tests.test_review_page import NOTE, engine_with
from tests.test_who_check import HeldEngine, reviewed, said

OTHER = "another made-up name"


def test_ruling_33_keep_with_new_words_corrects_the_line_offers_draft_the_note_again_and_does_not_settle(tmp_path, clock, machine):
    engine = engine_with(drug_name=[REPLY], note=[NOTE, NOTE])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    before, start = texts(p), counted(page_of(client)[0])
    answer = tick(client, 1, words=f"  {TYPED} ", press="keep")
    assert answer.status_code == 303 and answer.headers["location"].endswith("/consultations/1#drug-mark-1")
    after = texts(p)
    # Into the line at once, as a correction made at the tick: every place, by the function the line's own box uses.
    assert after[3] == before[3].replace("met for min", TYPED) and {n: t for n, t in after.items() if n != 3} == {n: t for n, t in before.items() if n != 3}
    assert [(e["kind"], e["line_n"], e["before"], e["after"]) for e in p.consultations.transcript_edits(1)] == [("words", 3, before[3], after[3])]
    assert events(p) == [("transcript.edited", "consultation 1: line 3")]              # the audit line of an edit, and none of a tick
    mark = mark_of(p, 1)
    assert (mark["heard"], mark["standing"], mark["settled_at"]) == ("met for min", TYPED, None)
    # Not settled: the tick stays faded, the box can be typed in again, the line keeps its highlight, and it still counts on Approve.
    raw, page = page_of(client)
    kept = row(raw, 1)
    assert 'data-settled="no"' in kept and f'<input name="words" value="{TYPED}"' in kept and "readonly" not in kept
    assert 'class="tick not-ticked" id="tick-1" name="press" value="settle" aria-pressed="false"' in kept
    assert "doubted" in part(raw, 'id="line-3"', 'id="line-4"') and counted(raw) == start
    # Draft the note again is offered at the top and under the rows, and never run (ruling 11).
    assert DRAFT_OFF not in raw and part(raw, 'id="warnings"', 'id="alarms"').count('id="draft-rows"') == 1 and len(engine.calls_for("note")) == 1
    # Typed over again and left again: kept again. Then the tick settles what stands, with no further edit.
    assert tick(client, 1, words=OTHER, press="keep").status_code == 303
    assert texts(p)[3] == before[3].replace("met for min", OTHER) and len(p.consultations.transcript_edits(1)) == 2
    assert tick(client, 1, words=OTHER, press="settle").status_code == 303
    assert mark_of(p, 1)["settled_at"] is not None and len(p.consultations.transcript_edits(1)) == 2
    assert events(p)[-1] == ("drug_name.settled", "consultation 1: line 3") and counted(page_of(client)[0]) == start - 1
    # The note drafted again is written from the kept words.
    assert client.post("/consultations/1/note/draft").status_code == 303 and OTHER in engine.calls_for("note")[1].user
    c.close()


def test_ruling_33_keep_with_the_same_words_changes_nothing(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    before = texts(p)
    for same in ("met for min", "  met for min "):
        assert tick(client, 1, words=same, press="keep").status_code == 303
    assert texts(p) == before and p.consultations.transcript_edits(1) == [] and events(p) == []
    raw, _ = page_of(client)
    assert mark_of(p, 1)["settled_at"] is None and DRAFT_OFF in raw and 'id="draft-rows"' not in raw
    c.close()


def test_ruling_33_R15_keep_with_an_empty_field_is_refused_at_the_row_and_the_words_that_stood_come_back(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    before = texts(p)
    refused = tick(client, 1, words="   ", press="keep")
    assert refused.status_code == 400 and refusal_on(text_of(refused), "tick-1") == words.ENTRY_EMPTY       # the sentence the tick uses
    assert '<input name="words" value="met for min"' in row(refused.text, 1)                                # the page sent back holds what stood
    assert texts(p) == before and events(p) == [] and mark_of(p, 1)["settled_at"] is None
    c.close()


def test_6d2_keep_on_a_settled_mark_as_from_a_stale_page_changes_nothing(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    assert tick(client, 1, words="met for min", press="settle").status_code == 303
    before, settled = texts(p), mark_of(p, 1)["settled_at"]
    assert tick(client, 1, words=TYPED, press="keep").status_code == 303
    assert texts(p) == before and mark_of(p, 1)["settled_at"] == settled and mark_of(p, 1)["standing"] == "met for min"
    assert events(p) == [("drug_name.settled", "consultation 1: line 3")]
    c.close()


def test_R15_keep_on_a_read_only_page_is_refused_at_the_row_while_a_check_runs_and_after_approve(tmp_path, clock, machine):
    engine = HeldEngine({"note": [NOTE], "drug_name": [REPLY], "label_check": [said("doctor", "patient", "doctor")]})
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    before = texts(p)
    assert client.post("/consultations/1/who-check").status_code == 303 and engine.entered.wait(20)
    refused = tick(client, 1, words=TYPED, press="keep")
    assert refused.status_code == 400 and refusal_on(text_of(refused), "tick-1") == words.CHECK_RUNNING
    engine.release.set()
    p.who_checks.wait(1, 20)
    assert client.post("/consultations/1/note/approve").status_code == 303
    refused = tick(client, 1, words=TYPED, press="keep")
    assert refused.status_code == 400 and refusal_on(text_of(refused), "tick-1") == words.NOTE_READ_ONLY
    assert texts(p) == before and mark_of(p, 1)["standing"] == "met for min" and events(p) == []
    c.close()
