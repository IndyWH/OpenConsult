"""An entry of the note corrected where it stands (spec 15.13, ruling 72;
the details of step 9f; the plan review, changes A and B). In the simple
view a click on an entry's words turns them into a field in place, and
Enter or leaving the field saves. The page's script does that; it is
seen in a browser. Here: what the app gives it. The save goes through
the address and the function an edit has always used, so what stood
before is kept and the audit line is written; the app answers with the
page, from which the script takes that entry's own piece; a refusal
comes with the app's own sentence in the entry's slot; and where the
entries are read only the page gives the script nothing to act on.
Made-up words; no browser and no script engine."""

import re

from openconsult import words
from openconsult.web.review import SCRIPT_WORDS
from tests.conftest import text_of
from tests.test_edited_mark import WORD, entry_of
from tests.test_reading_page import PAGE
from tests.test_review_page import engine_with, slot_text
from tests.test_row_keep import stop_thread_done
from tests.test_simple_note import RESTS, blocks, made, note_of
from tests.test_who_check import HeldEngine, reviewed, said

MODELS, DOCTORS = "made up tablets", "the tablets, as the doctor heard them"


def save(client, entry_id: int, text: str):
    """The save as the page's script makes it: the entry's own form, posted, and the app's answer followed to the page."""
    return client.post(f"/consultations/1/entries/{entry_id}", data={"text": text}, follow_redirects=True)


def test_ruling_72_a_save_from_the_simple_view_goes_through_the_address_of_today_and_the_answer_is_the_page_with_that_entrys_own_piece(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    p = app.state.parts
    entry = entry_of(app, MODELS)
    # The script reads the address from the entry's own form, which stands in its piece of the page in both views.
    assert f'<form method="post" action="/consultations/1/entries/{entry["id"]}" class="entry-form no-print" data-stay>' in blocks(client.get("/consultations/1").text)[MODELS]
    answer = save(client, entry["id"], f"  {DOCTORS} ")
    # What stood before is kept in the record, and the audit line is written, as with every edit of an entry.
    assert [(e["text_before"], e["text_after"]) for e in p.notes.edits(entry["id"])] == [(MODELS, DOCTORS)]
    assert (p.audit.lines()[0].event, p.audit.lines()[0].detail) == ("entry.edited", f"consultation 1: entry {entry['id']}")
    # The answer is the review page as it now stands, with the seconds left to the lock and that entry's piece by its
    # own name: the new words, the mark of an edited entry, the box of the advanced view holding the same words.
    assert answer.status_code == 200 and re.search(r'<div id="review" data-use data-seconds-left="\d+"', answer.text)
    block = re.search(rf'<div class="entry edited" id="entry-{entry["id"]}-block">(.*?)</div>', answer.text, flags=re.S).group(1)
    assert f'<span class="entry-text print-only">{DOCTORS}</span>' in block and WORD in block and f'value="{DOCTORS}"' in block
    assert answer.text.count(f'id="entry-{entry["id"]}-block"') == 1
    # The place where the entry says Saved stands in its piece, empty: the script writes the app's own word there.
    assert f'<span class="entry-said no-print" id="entry-{entry["id"]}-said" role="status"></span>' in block
    assert words.ENTRY_SAVED == "Saved." and text_of(answer).count(words.ENTRY_SAVED) == 1      # once: among the script's sentences
    c.close()


def test_ruling_72_words_left_as_they_stood_write_nothing_and_an_empty_field_is_refused_with_the_sentence_of_today_in_the_entrys_slot(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    p = app.state.parts
    entry = entry_of(app, MODELS)
    events = len(p.audit.lines())
    # The script sends nothing for unchanged words; the app, asked all the same, writes no edit and no audit line.
    assert save(client, entry["id"], f" {MODELS}  ").status_code == 200
    assert p.notes.edits(entry["id"]) == [] and len(p.audit.lines()) == events
    # An empty field: refused, with the sentence an empty entry has had since stage 6, in that entry's own slot of the
    # answer, from where the script takes it. The words as they stood are untouched.
    for nothing in ("", "   "):
        refused = save(client, entry["id"], nothing)
        assert refused.status_code == 400 and slot_text(text_of(refused), f"entry-{entry['id']}") == words.ENTRY_EMPTY
    assert words.ENTRY_EMPTY == "An entry cannot be empty. Edit its words instead."
    assert p.notes.entry(entry["id"])["text"] == MODELS and p.notes.edits(entry["id"]) == [] and len(p.audit.lines()) == events
    c.close()


def test_review_change_b_a_save_the_app_refuses_for_another_reason_answers_with_its_own_sentence_or_with_a_page_that_no_longer_holds_the_entry(tmp_path, clock, machine):
    # Nothing typed is lost without a word: the script leaves the field open and the entry says why. What the app
    # gives it for that. One: the entries have become read only meanwhile: the app's sentence in the entry's slot.
    app, client, c = made(tmp_path / "approved", clock, machine)
    entry = entry_of(app, MODELS)
    assert client.post("/consultations/1/note/approve").status_code == 303
    refused = save(client, entry["id"], DOCTORS)
    assert refused.status_code == 400 and slot_text(text_of(refused), f"entry-{entry['id']}") == words.NOTE_READ_ONLY
    assert app.state.parts.notes.entry(entry["id"])["text"] == MODELS
    c.close()
    # Two: the note was drafted again, so the entry is of an earlier draft: the app answers with the page, which holds
    # no piece of that name; the script then says the sentence handed to it. Nothing is written.
    app, client, c = made(tmp_path / "again", clock, machine, note=[RESTS, RESTS])
    entry = entry_of(app, MODELS)
    assert client.post("/consultations/1/lines/7", data={"label": "doctor", "text": "Tell me more, please."}).status_code == 303
    assert client.post("/consultations/1/note/draft").status_code == 303
    stale = save(client, entry["id"], DOCTORS)
    assert stale.status_code == 200 and f'id="entry-{entry["id"]}-block"' not in stale.text and 'id="review"' in stale.text
    assert app.state.parts.notes.entry(entry["id"])["text"] == MODELS and app.state.parts.notes.edits(entry["id"]) == []
    # The sentences the script says are the app's, handed with the others (15.6).
    handed = stale.text.split('<script id="words" type="application/json">')[1].split("</script>")[0]
    for name in ("ENTRY_SAVED", "ENTRY_NOT_SAVED", "NOT_SAVED_NEW_DRAFT", "NOT_SAVED_NO_ANSWER", "NOT_SAVED_ERROR"):
        assert name in SCRIPT_WORDS and f'"{name}"' in handed
    assert words.ENTRY_NOT_SAVED == "These words were not saved: {reason}. They are still in the box."
    assert words.NOT_SAVED_NEW_DRAFT == "the note has been drafted again since this page was shown"
    c.close()


def editable(raw: str) -> tuple[int, int, int]:
    """What the page gives the script to act on in the note: the forms, the places for Saved, the reader's sentence."""
    note = note_of(raw)
    return note.count('class="entry-form no-print"'), note.count('class="entry-said no-print"'), note.count('<p id="entry-says" hidden>')


def test_ruling_72_R15_where_the_entries_are_read_only_the_page_gives_the_script_nothing_to_act_on(tmp_path, clock, machine):
    # Where entries can be edited: a form in each entry's piece, a place for Saved in each, and once the sentence a
    # screen reader is told at such an entry.
    app, client, c = made(tmp_path / "open", clock, machine)
    raw = client.get("/consultations/1").text
    assert editable(raw) == (5, 5, 1) and f'<p id="entry-says" hidden>{words.ENTRY_PRESS}</p>' in text_of(client.get("/consultations/1"))
    assert words.ENTRY_PRESS == "Press Enter to edit the words of this entry."
    # After Refuse the entries are read only; after Approve the whole page is: no form, so the script gives no entry a
    # stop of the Tab key, and a click does nothing.
    client.post("/consultations/1/note/refuse")
    assert editable(client.get("/consultations/1").text) == (0, 0, 0)
    c.close()
    app, client, c = made(tmp_path / "approved", clock, machine)
    client.post("/consultations/1/note/approve")
    assert editable(client.get("/consultations/1").text) == (0, 0, 0)
    c.close()
    # While the check of who spoke runs nothing changes under it: no form either.
    engine = HeldEngine({"note": [RESTS], "label_check": [said("doctor", "doctor", "doctor", "patient", "patient", "patient")]})
    app, client, c = reviewed(tmp_path / "running", clock, machine, engine, page=PAGE)
    assert stop_thread_done(app) and editable(client.get("/consultations/1").text) == (5, 5, 1)
    assert client.post("/consultations/1/who-check").status_code == 303 and engine.entered.wait(20)
    assert editable(client.get("/consultations/1").text) == (0, 0, 0)
    engine.release.set()
    app.state.parts.who_checks.wait(1, 20)
    assert editable(client.get("/consultations/1").text) == (5, 5, 1)
    c.close()
