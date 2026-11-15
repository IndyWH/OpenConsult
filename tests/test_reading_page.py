"""The reading view of the review page (spec 15.10 rulings 35 and 42 to 44;
the details of step 6e): the transcript as turns of speech, each opening
into its lines as they are today, with every mark that protects the
patient in sight inside the turn. Made-up words, a made-up engine and
worker; no browser and no script engine."""

import hashlib
import re

from tests.conftest import text_of
from tests.test_live import live_seg
from tests.test_review_page import NOTE, engine_with
from tests.test_row_keep import stop_thread_done
from tests.test_who_check import press, reviewed, said

# Seven lines. Line 2 has no speaker and stands between two lines of the doctor; line 6 has none and stands at a change
# of speaker. The model reads six joined lines: lines 3 and 4 are one. One doubted name on line 5, one over lines 3 and 4.
PAGE = [live_seg(1, 0.0, 0.2, "Good morning", "S1"), live_seg(2, 0.25, 0.3, "do", None),
        live_seg(3, 0.35, 0.6, "come in. What do you take", "S1"), live_seg(4, 0.65, 0.8, "for the sugar?", "S1"),
        live_seg(5, 0.9, 1.5, "I take met for min twice a day. " + "word " * 60, "S2"), live_seg(6, 1.55, 1.6, "Yes.", None),
        live_seg(7, 1.7, 2.0, "Tell me more.", "S1")]
REPLY = {"doubtful": [{"line": 4, "heard": "met for min", "meant": "a made-up drug"}, {"line": 3, "heard": "take for", "meant": ""}]}
# The check names the two lines that had no speaker and moves line 7 to the patient.
CHECK = said("doctor", "doctor", "doctor", "patient", "patient", "patient")


def made(tmp_path, clock, machine, **script):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY], label_check=[CHECK], note=[NOTE], **script), page=PAGE)
    assert stop_thread_done(app)
    return app, client, c


def line_pieces(raw: str) -> list[str]:
    """Each line's own piece of the page, whole: no line holds a block inside it."""
    return re.findall(r'<div class="line[^"]*" id="line-\d+".*?</div>', raw, flags=re.S)


def digest(raw: str) -> str:
    pieces = line_pieces(raw)
    assert len(pieces) == len(PAGE)
    return hashlib.sha256("\n".join(pieces).encode("utf-8")).hexdigest()


# The lines of the made-up page as the code of 9aa9aab gave them, before the transcript was shown as turns.
AS_BUILT = {"open to edit": "ba553f69e1baaaed9bebd12845db0f07a2d0a41342a21829403f3ba3aaf56391",
            "after the check": "07eba551b0920c238d5a2569778307ad1c4a4c592c8fc08f5c8c631e54b4d91d",
            "after Approve": "c321c77382d788b16f0a96f71bf3b49ad96553abb4ee2a648a3ebf3da377a087"}


def test_ruling_43_the_lines_of_an_opened_turn_are_the_lines_as_they_were_before_the_reading_view_byte_for_byte(tmp_path, clock, machine):
    # Ruling 43 and the details: the opened turn shows each of its lines exactly as before: the same piece of the page, the
    # same ids, forms and addresses, the same sentences. Each sha256 was taken from the page of 9aa9aab, before the
    # template was touched, over every line's piece: open to edit with two doubted names, after a check that moved a line,
    # and read only after Approve.
    app, client, c = made(tmp_path, clock, machine)
    found = {"open to edit": digest(client.get("/consultations/1").text)}
    press(app, client)
    found["after the check"] = digest(client.get("/consultations/1").text)
    assert client.post("/consultations/1/note/approve").status_code == 303
    found["after Approve"] = digest(client.get("/consultations/1").text)
    assert found == AS_BUILT
    c.close()


# ------------------------------------------------------------ the page as turns

def turns(raw: str) -> list[dict]:
    """Each turn as the page sends it: its first line, whether it is sent open, its summary, and its lines' numbers."""
    transcript = raw.split('id="final-transcript"')[1].split("</section>")[0]
    found = []
    for first, opened, summary, body in re.findall(r'<details class="turn" id="turn-(\d+)"( open)?>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>', transcript, flags=re.S):
        found.append({"first": int(first), "open": bool(opened), "summary": summary, "head": re.search(r'<span class="speaker">(.*?)</span>', summary).group(1),
                      "lines": [int(n) for n in re.findall(r'<div class="line[^"]*" id="line-(\d+)"', body)]})
    return found


def pieces(raw: str) -> dict[int, str]:
    """The words of each line inside its turn's running text: the marked part turn-line-{n}, whole."""
    text = raw.split('id="final-transcript"')[1].split("</section>")[0]
    # A piece ends where the next begins, or where the running text of its turn ends.
    found = re.findall(r'id="turn-line-(\d+)" data-part>(.*?)</span> (?=<span class="turn-line|</span>\s*</summary>)', text, flags=re.S)
    return {int(n): held for n, held in found}


def test_rulings_35_42_43_the_transcript_is_sent_as_turns_each_closed_with_its_speaker_its_first_and_last_number_and_a_piece_for_each_line(tmp_path, clock, machine):
    # The room run of 15 Nov 2026: one greeting stood as ten lines, each a row with its own boxes. The page now reads doctor,
    # patient, doctor: a word with no speaker between two lines of the doctor sits inside that turn (line 2); one at a
    # change of speaker is an entry of its own (line 6). Every turn is sent closed.
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    sent = turns(raw)
    assert [(t["head"], t["lines"]) for t in sent] == [("[1–4] Doctor", [1, 2, 3, 4]), ("[5] Patient", [5]), ("[6] Unsure", [6]), ("[7] Doctor", [7])]
    assert not any(t["open"] for t in sent) and "<details" not in "".join(line_pieces(raw))
    # The words of each line stand as a piece of their own, in order, before the turn's lines in the page.
    held = pieces(raw)
    assert list(held) == [1, 2, 3, 4, 5, 6, 7] and held[1] == "Good morning" and held[7] == "Tell me more."
    assert [int(n) for n in re.findall(r'id="turn-line-(\d+)"', sent[0]["summary"])] == [1, 2, 3, 4]
    assert all(raw.index(f'id="turn-line-{n}"') < raw.index(f'id="line-{n}"') for n in held)
    # Every id of a line stands once, as before the reading view, and each new id once.
    for n in range(1, 8):
        for name in (f"line-{n}", f"save-line-{n}", f"save-line-{n}-refusal", f"undo-{n}-refusal", f"turn-line-{n}"):
            assert raw.count(f'id="{name}"') == 1, name
    assert [raw.count(f'id="turn-{first}"') for first in (1, 5, 6, 7)] == [1, 1, 1, 1] and raw.count("<details class=\"turn\"") == 4
    # What a screen reader is told at a turn is its description, never its name: the turn's own words are still read.
    page = text_of(client.get("/consultations/1"))
    assert raw.count('<summary aria-describedby="turn-says">') == 4 and raw.count('id="turn-says"') == 1 and "aria-label" not in sent[0]["summary"]
    assert '<p id="turn-says" hidden>' + "Press to open or close the lines of this turn." + "</p>" in page
    c.close()


def test_ruling_42_R15_each_mark_a_line_carries_stands_inside_its_turn_on_that_lines_own_words_and_nowhere_else(tmp_path, clock, machine):
    # Nothing a line shows is lost from sight by collating, but its box, its speaker choice and its Save: a doubted drug
    # name, highlighted, with its press to its row; an unsure word; a speaker set by hand; a low confidence.
    from openconsult import words
    low = PAGE[:6] + [{**PAGE[6], "confidence": 0.2}]
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY], note=[NOTE]), page=low)
    assert stop_thread_done(app)
    assert client.post("/consultations/1/lines/1", data={"label": "doctor", "text": "Good morning"}).status_code == 303
    assert client.post("/consultations/1/lines/1", data={"label": "patient", "text": "Good morning"}).status_code == 303
    assert client.post("/consultations/1/lines/1", data={"label": "doctor", "text": "Good morning"}).status_code == 303
    held = {n: text_of_piece for n, text_of_piece in pieces(text_of(client.get("/consultations/1"))).items()}

    def doubted(mark: int, words_heard: str) -> str:
        return f'<a class="turn-doubt" href="#drug-mark-{mark}" title="{words.CHECK_THIS_NAME}"><mark class="doubted">{words_heard}</mark></a>'

    # The name cut over two lines is a piece on each, each a press to the one row; the other name a press to its own.
    assert held[3] == "come in. What do you " + doubted(2, "take") and held[4] == doubted(2, "for") + " the sugar?"
    assert held[5].startswith("I take " + doubted(1, "met for min") + " twice a day. word")
    unsure, by_you, low_mark = (f'<span class="mark"> ({mark})</span>' for mark in (words.LABEL_UNSURE, words.LABEL_SET_BY_YOU, words.LOW_CONFIDENCE_MARK.format(score="0.20")))
    assert held[2] == "do" + unsure and held[6] == "Yes." + unsure and held[1] == "Good morning" + by_you and held[7] == "Tell me more." + low_mark
    for mark, on in ((unsure, [2, 6]), (by_you, [1]), (low_mark, [7]), ("turn-doubt", [3, 4, 5])):
        assert [n for n in held if mark in held[n]] == on
    # A settled name shows no highlight inside its turn, as on its line.
    assert client.post("/consultations/1/marks/1", data={"press": "settle"}).status_code == 303
    held = pieces(text_of(client.get("/consultations/1")))
    assert held[5].startswith("I take met for min twice a day. word") and "doubted" not in held[5] and "turn-doubt" in held[3]
    c.close()


def test_ruling_33_after_a_name_is_kept_its_words_stand_inside_the_closed_turn_in_a_part_of_their_own_and_new_entries_come_with_the_next_load(tmp_path, clock, machine):
    # The plan review of 6e, point 2: the piece of each line in the running text is a marked part beside the line itself, so
    # the script that puts a kept name in place shows it inside a closed turn too, and replaces nothing else. A keep can
    # take an unsure line over three words: the entries are then those of the rule at the next load of the page.
    from tests.test_row_keep import Parts
    reply = {"doubtful": REPLY["doubtful"] + [{"line": 2, "heard": "do", "meant": ""}]}
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[reply], note=[NOTE]), page=PAGE)
    assert stop_thread_done(app)
    before = client.get("/consultations/1").text
    assert [t["lines"] for t in turns(before)] == [[1, 2, 3, 4], [5], [6], [7]]
    mark = next(m["id"] for m in app.state.parts.consultations.drug_marks(1) if m["heard"] == "do")
    assert client.post(f"/consultations/1/marks/{mark}", data={"words": "do sit down here", "press": "keep"}).status_code == 303
    after = client.get("/consultations/1").text
    assert "do sit down here" in pieces(after)[2] and "do sit down here" not in before
    parts = Parts(after)
    assert parts.nested == 0 and all(parts.fields[f"turn-line-{n}"] == 0 and parts.fields[f"line-{n}"] == 2 for n in range(1, 8))
    # Four words with no speaker are no longer inside the doctor's turn: an entry of their own, and the doctor's lines two turns.
    assert [(t["head"], t["lines"]) for t in turns(after)][:3] == [("[1] Doctor", [1]), ("[2] Unsure", [2]), ("[3–4] Doctor", [3, 4])]
    c.close()


# ------------------------------------------------- a turn opens, and stays open

def test_ruling_43_the_control_that_opens_all_works_by_a_load_with_no_script_and_the_page_hands_its_script_the_turns_words(tmp_path, clock, machine):
    from openconsult import words
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    # Closed: the control opens all, beside Swap at the top of the transcript, by a load that comes back at the transcript.
    head = raw.split('id="transcript"')[1].split('id="who-check"')[0]
    assert head.index('id="swap"') < head.index('id="open-all"')
    assert f'<a class="open-all" id="open-all" href="/consultations/1?lines=open#transcript">{words.OPEN_ALL_LINES}</a>' in head
    opened = client.get("/consultations/1?lines=open").text
    assert [t["open"] for t in turns(opened)] == [True] * 4 and [t["lines"] for t in turns(opened)] == [t["lines"] for t in turns(raw)]
    # Open: the same control closes them again, by a load of the page's plain address. The lines are those of the closed page.
    assert f'<a class="open-all" id="open-all" href="/consultations/1#transcript">{words.CLOSE_ALL_LINES}</a>' in opened
    assert line_pieces(opened) == line_pieces(raw) and not any(t["open"] for t in turns(client.get("/consultations/1").text))
    # The press is the doctor's, so it is use, as any load of the page is (15.6).
    clock.advance(minutes=29)
    assert client.get("/consultations/1?lines=open").status_code == 200
    clock.advance(minutes=29)
    assert client.get("/consultations/1").status_code == 200
    # The script that opens the turns again after a load runs before the one that keeps the page's place, and its sentences are the app's.
    assert raw.index("/static/review.js") < raw.index("/static/place.js") and client.get("/static/review.js").status_code == 200
    handed = raw.split('<script id="words" type="application/json">')[1].split("</script>")[0]
    assert all(sentence in text_of(client.get("/consultations/1")) or sentence in handed for sentence in (words.CLOSE_ALL_LINES, words.TURN_NOT_SAVED))
    assert (words.OPEN_ALL_LINES, words.CLOSE_ALL_LINES, words.TURN_NOT_SAVED) == (
        "Open all the lines", "Close all the lines", "This turn holds words that are not saved. Save them first.")
    # Read only, after Approve: the same reading view, turns that open to lines with no box.
    assert client.post("/consultations/1/note/approve").status_code == 303
    after = client.get("/consultations/1?lines=open").text
    assert [t["open"] for t in turns(after)] == [True] * 4 and 'id="open-all"' in after and 'class="line-form"' not in after
    c.close()


def test_R15_a_save_or_an_undo_on_a_line_that_is_refused_comes_back_with_that_lines_turn_open_and_the_sentence_in_its_slot(tmp_path, clock, machine):
    # A turn is sent closed, and the slot of a line's refusal stands on the line: so the app sends that one turn open, with
    # and without a script. No other press opens a turn.
    from openconsult import words
    from tests.conftest import refusal_on
    from tests.test_review_page import slot_text
    app, client, c = made(tmp_path, clock, machine)
    emptied =client.post("/consultations/1/lines/3", data={"label": "doctor", "text": ""})
    assert emptied.status_code == 400 and refusal_on(text_of(emptied), "save-line-3") == words.ENTRY_EMPTY
    assert [(t["first"], t["open"]) for t in turns(emptied.text)] == [(1, True), (5, False), (6, False), (7, False)]
    undone = client.post("/consultations/1/lines/5/undo")
    assert undone.status_code == 400 and slot_text(text_of(undone), "undo-5") == words.NOT_CHANGED_BY_CHECK
    assert [(t["first"], t["open"]) for t in turns(undone.text)] == [(1, False), (5, True), (6, False), (7, False)]
    # A refusal elsewhere on the page opens none: the note entry whose number is also a line's.
    entry = app.state.parts.notes.entries(app.state.parts.notes.current_draft(1)["id"])[0]["id"]
    refused = client.post(f"/consultations/1/entries/{entry}", data={"text": " "})
    assert refused.status_code == 400 and not any(t["open"] for t in turns(refused.text))
    c.close()
