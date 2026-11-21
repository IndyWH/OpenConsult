"""The mark of an edited entry (spec 15.13, ruling 75; the details of step
9f). Until this step an entry the doctor had changed kept its chips and
showed no sign that its words were the doctor's: the chip went on saying
that the entry rests on what was said, though nobody had checked the new
words against it. Now its words stand on a green ground and the small
word Edited follows it, in both views, so that it is never told by
colour alone. The mark is the page's: the copy text, the approved text
and the print sheet are the note alone. Made-up words; no browser."""

import re

from openconsult import words
from tests.conftest import text_of
from tests.test_simple_note import RESTS, blocks, made, note_of

WORD = f'<span class="mark edited-word no-print">{words.ENTRY_EDITED}</span>'
MODELS, DOCTORS = "made up tablets", "the doctor's own words"


def entry_of(app, text: str) -> dict:
    p = app.state.parts
    return next(e for e in p.notes.entries(p.notes.current_draft(1)["id"]) if e["text"] == text)


def marked(raw: str) -> list[str]:
    """The words of each entry that carries the mark: the class on its block and the word in it, both or neither."""
    found = []
    for opening, block in re.findall(r'<div class="(entry[^"]*)" id="entry-\d+-block">(.*?)</div>', note_of(raw), flags=re.S):
        assert (opening == "entry edited") is (WORD in block) and opening in ("entry", "entry edited") and block.count(WORD) <= 1
        if opening == "entry edited":
            found.append(re.search(r'<span class="entry-text[^"]*">([^<]*)</span>', block).group(1))
    return found


def test_ruling_75_an_entry_the_doctor_changed_is_marked_in_both_views_by_a_ground_and_the_word_and_one_typed_back_is_not(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    p = app.state.parts
    assert words.ENTRY_EDITED == "Edited"
    assert marked(client.get("/consultations/1").text) == [] and words.ENTRY_EDITED not in text_of(client.get("/consultations/1"))
    entry = entry_of(app, MODELS)
    assert client.post(f"/consultations/1/entries/{entry['id']}", data={"text": DOCTORS}).status_code == 303
    # Marked in both views, on that entry alone; the record holds the model's own words beside the doctor's.
    for address in ("/consultations/1", "/consultations/1?note=advanced"):
        raw = client.get(address).text
        assert marked(raw) == ["the doctor&#39;s own words"] and text_of(client.get(address)).count(words.ENTRY_EDITED) == 1
    stored = p.notes.entry(entry["id"])
    assert (stored["text"], stored["model_text"]) == (DOCTORS, MODELS)
    # The word follows the entry, after its chips and its line numbers; the chips stay, for they still say what the model's entry rested on.
    block = blocks(client.get("/consultations/1").text)["the doctor&#39;s own words"]
    assert block.rindex('class="chip') < block.index(WORD) and block.rindex('class="cite') < block.index(WORD) and block.count('class="chip') == 3
    # Typed back to the model's words, spaces at the ends aside: no mark, though the record keeps both edits.
    assert client.post(f"/consultations/1/entries/{entry['id']}", data={"text": f"  {MODELS} "}).status_code == 303
    assert marked(client.get("/consultations/1").text) == [] and len(p.notes.edits(entry["id"])) == 2
    c.close()


def test_ruling_75_after_approve_the_page_still_shows_which_entries_were_edited_and_a_new_draft_has_none(tmp_path, clock, machine):
    app, client, c = made(tmp_path / "approved", clock, machine)
    entry = entry_of(app, MODELS)
    client.post(f"/consultations/1/entries/{entry['id']}", data={"text": DOCTORS})
    assert client.post("/consultations/1/note/approve").status_code == 303
    for address in ("/consultations/1", "/consultations/1?note=advanced"):
        raw = client.get(address).text
        assert "entry-form" not in raw and marked(raw) == ["the doctor&#39;s own words"]      # read only, and still marked
    c.close()
    # A new draft has new entries, each the model's own words: no mark.
    app, client, c = made(tmp_path / "again", clock, machine, note=[RESTS, RESTS])
    entry = entry_of(app, MODELS)
    client.post(f"/consultations/1/entries/{entry['id']}", data={"text": DOCTORS})
    assert marked(client.get("/consultations/1").text) != []
    assert client.post("/consultations/1/lines/7", data={"label": "doctor", "text": "Tell me more, please."}).status_code == 303
    assert client.post("/consultations/1/note/draft").status_code == 303 and len(app.state.parts.notes.drafts(1)) == 2
    assert marked(client.get("/consultations/1").text) == []
    c.close()


def test_ruling_75_the_mark_is_the_pages_alone_the_copy_text_the_approved_text_and_the_print_sheet_carry_none(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    entry = entry_of(app, MODELS)
    client.post(f"/consultations/1/entries/{entry['id']}", data={"text": DOCTORS})
    copy = client.get("/consultations/1/note.txt").text
    assert DOCTORS in copy and words.ENTRY_EDITED not in copy and "edited" not in copy.lower()
    # On the sheet the word is not printed, for it is among the pieces the sheet leaves out, and the ground is taken off.
    sheet = client.get("/static/print.css").text
    assert ".no-print" in sheet.split("{ display: none !important; }")[0] and "no-print" in WORD
    assert ".entry.edited .entry-text { background: none !important;" in sheet
    client.post("/consultations/1/note/approve")
    approved = app.state.parts.notes.approval(1)["text"]
    assert DOCTORS in approved and words.ENTRY_EDITED not in approved and approved == copy
    c.close()


def channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    r, g, b = (int(colour[k:k + 2], 16) for k in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_ruling_75_the_words_on_the_green_and_on_the_yellow_of_a_doubted_name_and_the_word_edited_each_measure_at_least_4_5_to_1(logged_in):
    # The contrast of the style sheet's own values, by the formula of WCAG 2. The plan gave them: 12.38, 12.67 and 7.94.
    css = logged_in.get("/static/theme.css").text
    ink, panel = (re.search(rf"--{name}: (#[0-9A-Fa-f]{{6}});", css).group(1) for name in ("ink", "panel"))
    green = re.search(r"\.entry\.edited \.entry-text \{ background: (#[0-9A-Fa-f]{6}); \}", css).group(1)
    yellow = re.search(r"mark\.doubted \{ background: (#[0-9A-Fa-f]{6});", css).group(1)
    word = re.search(r"\.mark\.edited-word \{ color: (#[0-9A-Fa-f]{6});", css).group(1)
    assert (green, yellow, word) == ("#D3ECD9", "#FBE7B0", "#1F5C38")
    assert [round(contrast(ink, green), 2), round(contrast(ink, yellow), 2), round(contrast(word, panel), 2)] == [12.38, 12.67, 7.94]
    assert min(contrast(ink, green), contrast(ink, yellow), contrast(word, panel)) >= 4.5
    # The two grounds are almost equally light, so the word, not the ground, tells an edited entry to an eye that
    # cannot tell green from yellow: the mark is a class on the entry and a word in it, never the ground alone.
    assert round(contrast(green, yellow), 2) == 1.02
