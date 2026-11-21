"""The simple and the advanced view of the draft note (spec 15.13, rulings
46 and 71; the details of step 9f). Since run 9b a doctor in cloud mode
met a note in which every entry was a box with a Save and 20 to 55 line
numbers after it. The note now opens as plain words under its four
headings, each entry with one small chip for each turn of speech it
rests on; one press shows the advanced view, which is the note as it
stood. Both views are one piece of the page, an attribute says which is
shown and the style sheet shows it: so a test here reads the page as
the app gives it and the rules of the style sheet, and the look in a
browser shows the rest. Made-up words; no browser and no script engine."""

import hashlib
import re

from openconsult import words
from openconsult.llm.engine import EngineTimeout
from openconsult.web.review import SCRIPT_WORDS
from tests.conftest import refusal_on, text_of
from tests.test_reading_page import PAGE
from tests.test_review_page import engine_with
from tests.test_row_keep import stop_thread_done
from tests.test_who_check import press, reviewed, said

# Five entries on the made-up page of the reading view's tests, whose seven lines read as four turns: lines 1 to 4,
# line 5, line 6 (a word with no speaker, on its own), line 7. The model's own turns are six, numbered from 0. The
# first entry rests on lines 1 to 4, one turn; the second on lines 3, 4, 5 and 7, three turns; the third on line 6;
# the fourth on line 5; the last cites a turn that is not there.
RESTS = {"reasoning": "made up.",
         "subjective": [{"text": "made up history of the sugar", "turns": [0, 1, 2]}, {"text": "made up tablets", "turns": [2, 3, 5]}],
         "objective": [{"text": "made up finding", "turns": [4]}], "assessment": [{"text": "made up impression", "turns": [3]}],
         "plan": [{"text": "made up plan", "turns": [9]}]}
CHIPS = {"made up history of the sugar": [1], "made up tablets": [1, 2, 4], "made up finding": [3], "made up impression": [2], "made up plan": []}


def made(tmp_path, clock, machine, **script):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(**{"note": [RESTS], **script}), page=PAGE)
    assert stop_thread_done(app)
    return app, client, c


def note_of(raw: str) -> str:
    """The note's own area of the page, whole."""
    return raw.split('<section class="pane note print-keep" id="note"', 1)[1].split("</section>", 1)[0]


def blocks(raw: str) -> dict[str, str]:
    """Each entry's piece of the page by its words as they stand; no entry holds a block inside it."""
    found = re.findall(r'<div class="entry[^"]*" id="entry-\d+-block">(.*?)</div>', note_of(raw), flags=re.S)
    return {re.search(r'<span class="entry-text[^"]*">([^<]*)</span>', block).group(1): block for block in found}


def chips(block: str) -> list[int]:
    return [int(k) for k in re.findall(r'<button type="button" class="chip no-print" data-turn="(\d+)"', block)]


def view_rules(css: str, area: str) -> dict[str, str]:
    """Every rule of the style sheet that speaks of a view of an area: each selector with what it does."""
    found = {}
    for selectors, body in re.findall(r"([^{}]*)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        for selector in selectors.split(","):
            if f"#{area}[data-view=" in selector:
                found[selector.strip()] = body.strip()
    return found


def test_ruling_46_a_fresh_visit_gives_the_note_in_the_simple_view_and_the_one_in_use_is_told_without_colour(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    assert '<section class="pane note print-keep" id="note" data-view="simple">' in raw
    head = note_of(raw).split('<div class="pane-body">')[0]
    # The owner's two words, each a press, the one in use told to a screen reader, inside a group named for the area.
    assert (words.VIEW_WORDS["simple"], words.VIEW_WORDS["advanced"]) == ("Simple", "Advanced")
    assert f'<span class="views no-print" id="note-views" role="group" aria-label="{words.VIEW_GROUP["note"]}">' in head
    assert '<a class="view" id="note-simple" data-area="note" data-view="simple" href="/consultations/1#note" aria-current="true">Simple</a>' in head
    assert '<a class="view" id="note-advanced" data-area="note" data-view="advanced" href="/consultations/1?note=advanced#note">Advanced</a>' in head
    assert head.count("aria-current") == 1 and head.index(words.NOTE_HEADING) < head.index('id="note-views"')
    # Told by more than colour: the press in use is heavier, has a heavier edge and a line under it (R15).
    css = client.get("/static/theme.css").text
    in_use = css.split('.views .view[aria-current="true"] {')[1].split("}")[0]
    assert "font-weight: 700" in in_use and "border: 2px solid" in in_use and "text-decoration: underline" in in_use
    c.close()


def test_ruling_71_each_entry_is_its_words_whole_then_one_chip_for_each_turn_it_rests_on_and_the_simple_view_shows_no_box_no_save_and_no_line_number(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    held = blocks(raw)
    assert list(held) == list(CHIPS)                                             # the entries in the note's order, by section
    for text, numbers in CHIPS.items():
        block = held[text]
        # The words whole, as text: the piece the print sheet has had since stage 6, so no word of the note is sent twice.
        assert block.count(f'<span class="entry-text print-only">{text}</span>') == 1
        # One chip for each turn of the reading view that holds a line the entry cites, in order, each once.
        assert chips(block) == numbers, text
        for k in numbers:
            said_to_a_reader = words.SHOW_TURN.format(n=k)
            assert f'<button type="button" class="chip no-print" data-turn="{k}" aria-label="{said_to_a_reader}" title="{said_to_a_reader}">{k}</button>' in block
        # The words come first, the line numbers of the advanced view next, then the chips.
        assert block.index("entry-text print-only") < (block.index('class="chip') if numbers else len(block))
    assert words.SHOW_TURN == "Show turn {n} in the transcript"
    # The rules of the two views, every one of them: the simple view hides the box with its Save, the line numbers and
    # the differentials beside the assessment, and shows the words; the advanced view hides the chips. Nothing else of
    # the note is under a view's rule, so everything else stands in both.
    rules = view_rules(client.get("/static/theme.css").text, "note")
    assert rules == {'#note[data-view="simple"] .entry-form': "display: none;", '#note[data-view="simple"] button.cite': "display: none;",
                     '#note[data-view="simple"] .section .differentials': "display: none;",
                     '#note[data-view="simple"] .entry-text.print-only': "display: inline;", '#note[data-view="advanced"] button.chip': "display: none;"}
    # The box, its Save and each line number are pieces those rules name; a chip is a piece of its own.
    first = held["made up history of the sugar"]
    assert 'class="entry-form no-print"' in first and f">{words.SAVE_ENTRY}</button>" in first.split("</form>")[0]
    assert first.count('class="cite no-print"') == 4 and "chip" not in first.split("</form>")[0]
    c.close()


def test_ruling_71_an_entry_that_rests_on_nothing_that_was_said_has_no_chip_and_says_so_once_in_both_views(tmp_path, clock, machine):
    # The entry a doctor most needs to see: it cites no line. It says so in the words it has had since stage 6, in a
    # piece that no rule of a view names.
    app, client, c = made(tmp_path, clock, machine)
    for address in ("/consultations/1", "/consultations/1?note=advanced"):
        raw = client.get(address).text
        block = blocks(raw)["made up plan"]
        assert chips(block) == [] and 'class="cite' not in block
        assert block.count(f'<span class="mark uncited no-print">({words.ENTRY_UNCITED})</span>') == 1
        assert text_of(client.get(address)).count(words.ENTRY_UNCITED) == 1
    assert not any("uncited" in selector for selector in view_rules(client.get("/static/theme.css").text, "note"))
    c.close()


def test_9f_the_lines_that_say_the_state_of_the_note_stand_in_both_views(tmp_path, clock, machine):
    # A call that failed: the line, and the differentials outside every section, where no view's rule reaches them.
    app, client, c = made(tmp_path / "failed", clock, machine, note=[EngineTimeout("no answer")])
    for address in ("/consultations/1", "/consultations/1?note=advanced"):
        note = note_of(client.get(address).text)
        assert '<p class="failed" id="note-state">' in note and 'id="section-assessment"' not in note and 'id="differentials"' in note
    c.close()
    # A draft the citation check refused: four of five entries cite nothing.
    nothing = {**RESTS, "subjective": [{"text": "a", "turns": [8]}, {"text": "b", "turns": [9]}], "objective": [{"text": "c", "turns": [7]}],
               "plan": [{"text": "d", "turns": [9]}]}
    app, client, c = made(tmp_path / "refused", clock, machine, note=[nothing])
    refused_line = words.NOTE_REFUSED_CITATIONS.format(cited=1, total=5)
    assert all(refused_line in text_of(client.get(address)) for address in ("/consultations/1", "/consultations/1?note=advanced"))
    c.close()
    # Who spoke has changed since the note was written; then the count of earlier drafts.
    app, client, c = made(tmp_path / "changed", clock, machine, note=[RESTS, RESTS], label_check=[said("doctor", "doctor", "doctor", "patient", "patient", "patient")])
    press(app, client)
    for address in ("/consultations/1", "/consultations/1?note=advanced"):
        assert '<p class="statement no-print" id="speakers-changed">' in note_of(client.get(address).text)
    assert client.post("/consultations/1/note/draft").status_code == 303
    for address in ("/consultations/1", "/consultations/1?note=advanced"):
        assert f'<p class="mark" id="earlier-drafts">{words.EARLIER_DRAFTS.format(count=1)}</p>' in note_of(client.get(address).text)
    # None of them is under a rule of a view.
    selectors = " ".join(view_rules(client.get("/static/theme.css").text, "note"))
    assert not any(name in selectors for name in ("note-state", "speakers-changed", "earlier-drafts", ".failed", ".statement"))
    c.close()


def test_15_10_ruling_4_the_models_differentials_are_in_the_advanced_view_and_the_alarms_stay_in_sight_in_every_view(tmp_path, clock, machine):
    # Ruling 46 gives the simple note as the SOAP note alone: the model's last differentials, which are not part of the
    # note, stand inside the assessment and are under the simple view's rule. The count of alarms beside Approve and the
    # alarm lines are outside the note.
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    note = note_of(raw)
    section = note[note.find('id="section-assessment"'):note.find('id="section-plan"')]
    assert 'class="differentials no-print" id="differentials"' in section and note.count('id="differentials"') == 1
    assert 'id="alarm-count"' not in note and 'id="alarms"' not in note
    assert raw.index("</section>", raw.index('id="note"')) < raw.index('id="alarm-count"') < raw.index('id="alarms"')
    c.close()


# The advanced note of the made-up page as the code of 385ad5e gave it, before step 9f touched the template: every
# entry's box with its Save and every line number, in the page's order; and, read only after Approve, every entry's
# words with its slot and every line number. Taken from the page the app gives, which is the same text on every system.
ADVANCED = re.compile(r'<form method="post" action="/consultations/1/entries/\d+" class="entry-form no-print" data-stay>.*?</form>'
                      r'|<button type="button" class="cite no-print"[^>]*>\[\d+\]</button>'
                      r'|<span class="entry-text">[^<]*</span><p class="refusal" id="entry-\d+-refusal" role="alert"></p>', re.S)
AS_BUILT = {"open to edit": "f89b09058a047c7a4cf6ac980a05750b24a141e82d1dce6328cb0aefa9f6ae6a",
            "after Approve": "900115017aee4215c00f811a9fa3ab6995cbde6782e22e43fb34b59eacab669f"}


def digest(raw: str) -> str:
    pieces = ADVANCED.findall(note_of(raw))
    assert len(pieces) == 15                                                     # five entries and their ten line numbers
    return hashlib.sha256("\n".join(pieces).encode("utf-8")).hexdigest()


def test_ruling_46_the_advanced_note_is_the_note_as_it_stood_at_385ad5e_piece_for_piece(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    found = {"open to edit": digest(client.get("/consultations/1?note=advanced").text)}
    assert digest(client.get("/consultations/1").text) == found["open to edit"]      # the same pieces whichever view is shown
    assert client.post("/consultations/1/note/approve").status_code == 303
    found["after Approve"] = digest(client.get("/consultations/1?note=advanced").text)
    assert found == AS_BUILT
    c.close()


def test_ruling_46_the_view_named_in_the_address_is_the_view_given_so_a_view_is_chosen_with_no_script(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    advanced = client.get("/consultations/1?note=advanced").text
    assert '<section class="pane note print-keep" id="note" data-view="advanced">' in advanced
    head = note_of(advanced).split('<div class="pane-body">')[0]
    # Each press is a link that loads the page with that view, at the note.
    assert '<a class="view" id="note-simple" data-area="note" data-view="simple" href="/consultations/1#note">Simple</a>' in head
    assert ('<a class="view" id="note-advanced" data-area="note" data-view="advanced" href="/consultations/1?note=advanced#note" '
            'aria-current="true">Advanced</a>') in head
    # A name the app does not know is the simple view, and a view is never kept by the app: the next plain load is simple.
    for address in ("/consultations/1?note=other", "/consultations/1?note=", "/consultations/1"):
        assert 'id="note" data-view="simple">' in client.get(address).text
    # The press is the doctor's, so the load is use, as any load of the page is (15.6).
    clock.advance(minutes=29)
    assert client.get("/consultations/1?note=advanced").status_code == 200
    clock.advance(minutes=29)
    assert client.get("/consultations/1").status_code == 200
    # A Save that the app refuses comes back with the note in the advanced view, where the box and its sentence stand (R15).
    entry = app.state.parts.notes.entries(app.state.parts.notes.current_draft(1)["id"])[0]["id"]
    refused = client.post(f"/consultations/1/entries/{entry}", data={"text": " "})
    assert refused.status_code == 400 and refusal_on(text_of(refused), f"entry-{entry}") == words.ENTRY_EMPTY
    assert 'id="note" data-view="advanced">' in refused.text
    c.close()


def test_15_10_ruling_12_the_page_gives_its_script_what_it_needs_to_keep_unsaved_words_from_being_hidden_by_a_change_of_view(tmp_path, clock, machine):
    # The plan review of 9f, change A: a doctor types in a box of the advanced view and presses Simple; the note must not
    # be approved without the words he believes he gave it. The script leaves the view as it is and says why. What the app
    # can show of that: the sentence, handed with the others; the place where the area says it; and each box holding
    # the words the app gave it, which is how the script tells a box that is not saved.
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1?note=advanced").text
    assert "VIEW_NOT_SAVED" in SCRIPT_WORDS and words.VIEW_NOT_SAVED == "This view holds words that are not saved. Save them first."
    assert words.VIEW_NOT_SAVED in raw.split('<script id="words" type="application/json">')[1].split("</script>")[0]
    assert note_of(raw).count('<p class="refusal view-says no-print" id="note-view-says" role="alert"></p>') == 1
    for text in CHIPS:
        assert f'<input name="text" value="{text}" class="entry-text"' in blocks(raw)[text]
    c.close()
