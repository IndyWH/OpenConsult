"""A leftover piece of a drug name is taken out at its row (spec 15.10
ruling 40; the details of step 6e). In the owner's room check of 15 Nov
2026 the speech choice cut one medicine over two lines and the model
marked the halves as two names; the leftover word could not be taken
out, and would have gone to the note's model as if it had been said.
Made-up words; no model is asked by any of this."""

from openconsult import words
from openconsult.consult import drug_marks
from tests.conftest import text_of
from tests.test_drug_marks import PAGE, REPLY
from tests.test_drug_rows import DRAFT_OFF, counted, events, mark_of, row, texts, tick
from tests.test_live import live_seg
from tests.test_review_marks import page_of
from tests.test_review_page import engine_with
from tests.test_row_keep import stop_thread_done
from tests.test_who_check import reviewed

# One medicine cut over two lines and marked as two names: the first half on line 2, the leftover the whole of line 3.
HALVES = [live_seg(1, 0.0, 0.3, "Do you still take", "S1"), live_seg(2, 0.35, 0.6, "the glick", "S1"), live_seg(3, 0.65, 0.8, "la side", "S1"),
          live_seg(4, 0.85, 1.0, "every morning?", "S1"), live_seg(5, 1.1, 2.0, "Yes I do. " + "word " * 60, "S2")]
TWO_NAMES = {"doubtful": [{"line": 1, "heard": "glick", "meant": "a made-up drug"}, {"line": 1, "heard": "la side", "meant": "a made-up drug"}]}


def halves(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[TWO_NAMES]), page=HALVES)
    assert stop_thread_done(app)
    return app, client, c


def test_ruling_40_a_tick_with_an_empty_box_takes_the_doubted_words_out_of_the_line_settles_the_mark_and_asks_no_model(tmp_path, clock, machine):
    app, client, c = halves(tmp_path, clock, machine)
    p = app.state.parts
    calls_before = len(p.consultations.model_calls(1))
    lines_before = {line["n"]: line for line in p.consultations.transcript_lines(1)}
    assert counted(page_of(client)[0]) == 2 + counted_other(client, p) and DRAFT_OFF in page_of(client)[0]
    # The whole name typed at the first row, as the owner did; then the leftover's box emptied and ticked.
    assert tick(client, 1, words="made-up-ide", press="settle").status_code == 303
    assert tick(client, 2, words="", press="settle", place="keep").status_code == 303
    now = {line["n"]: line for line in p.consultations.transcript_lines(1)}
    assert texts(p) == {1: "Do you still take", 2: "the made-up-ide", 3: "", 4: "every morning?", 5: lines_before[5]["text"]}
    # The line stays, with its number, speaker, times and sound. No line is removed and none is given a new number.
    for field in ("n", "label", "raw_speaker", "start_s", "end_s", "unsure"):
        assert [now[n][field] for n in sorted(now)] == [lines_before[n][field] for n in sorted(lines_before)], field
    # The edit of the kind words with the words before, the audit line of an edit, and the mark settled with its own.
    edit = p.consultations.transcript_edits(1)[-1]
    assert (edit["kind"], edit["line_n"], edit["before"], edit["after"]) == ("words", 3, "la side", "")
    assert events(p)[-2:] == [("transcript.edited", "consultation 1: line 3"), ("drug_name.settled", "consultation 1: line 3")]
    mark = mark_of(p, 2)
    assert mark["settled_at"] is not None and mark["cleared_at"] is None and mark["standing"] == "" and mark["heard"] == "la side"      # the words heard never change
    assert mark["places"] == [{"line": 3, "first": 0, "last": 0}]
    # Draft the note again is offered, never run: no model was asked by either press.
    raw, page = page_of(client)
    assert DRAFT_OFF not in raw and len(p.consultations.model_calls(1)) == calls_before
    # Where no words are left the line says so with the sentence it has, and the count on Approve has fallen by both.
    assert words.LINE_NO_WORDS in raw.split('id="line-3"')[1].split('id="line-4"')[0] and counted(raw) == counted_other(client, p)
    c.close()


def counted_other(client, p) -> int:
    """The warnings counted on Approve that are not doubted names."""
    return page_of(client)[0].count('<li class="warning"')


def test_ruling_40_the_settled_row_shows_its_sentence_and_a_second_press_opens_the_mark_with_an_empty_box(tmp_path, clock, machine):
    app, client, c = halves(tmp_path, clock, machine)
    p = app.state.parts
    assert tick(client, 2, words="  ", press="settle").status_code == 303
    raw, page = page_of(client)
    settled = row(raw, 2)
    # In place of the settled words: one short sentence, a draft. The row still shows its line's number, its play and its tick.
    assert f'<span class="settled-words taken-out">{words.DRUG_TAKEN_OUT}</span>' in settled and words.DRUG_TAKEN_OUT == "Taken out of the line."
    assert "<input" not in settled and 'aria-pressed="true"' in settled and 'class="play-stretch row-play"' in settled and "la side" not in settled
    assert settled.index(words.DRUG_ROW_LINE.format(n=3)) < settled.index("taken-out") < settled.index("row-play") < settled.index('id="tick-2"')
    base = counted(raw)
    # A second press opens it again: an empty box at the place, and it counts on Approve again. The line keeps what it has.
    assert tick(client, 2, press="open").status_code == 303
    raw, _ = page_of(client)
    opened = row(raw, 2)
    assert '<input name="words" value="" class="doubted-field"' in opened and 'aria-pressed="false"' in opened and "taken-out" not in opened
    assert counted(raw) == base + 1 and texts(p)[3] == "" and mark_of(p, 2)["settled_at"] is None
    # Nothing on the line itself points at words that are not there.
    assert "doubted" not in raw.split('id="line-3"')[1].split('id="line-4"')[0]
    # A keep with an empty box there changes nothing, and neither does a tick: it settles the mark as it stands.
    before = (texts(p), events(p))
    assert tick(client, 2, words=" ", press="keep").status_code == 303 and (texts(p), events(p)) == before
    assert tick(client, 2, words="", press="settle").status_code == 303 and texts(p) == before[0] and mark_of(p, 2)["settled_at"] is not None
    # Read only, after Approve: the row shows the sentence, and a press is answered at the row.
    assert client.post("/consultations/1/note/approve").status_code == 303
    assert words.DRUG_TAKEN_OUT in row(page_of(client)[0], 2) and tick(client, 2, press="open").status_code == 400
    c.close()


def test_ruling_40_words_typed_back_and_ticked_or_left_go_into_the_line_at_the_place_the_doubted_words_stood(tmp_path, clock, machine):
    # In the middle of a line and twice on it (the made-up page of the drug marks: line 3 holds the doubted words twice).
    app, client, c = reviewed(tmp_path / "twice", clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    whole = texts(p)[3]
    assert tick(client, 1, words="", press="settle").status_code == 303
    assert texts(p)[3] == whole.replace("met for min ", "") and len(mark_of(p, 1)["places"]) == 2      # every place is out
    assert tick(client, 1, press="open").status_code == 303
    assert tick(client, 1, words="met for min", press="keep").status_code == 303                        # left, not ticked: kept, not settled
    assert texts(p)[3] == whole and mark_of(p, 1)["settled_at"] is None and mark_of(p, 1)["standing"] == "met for min"
    c.close()
    # A name cut over two lines: every piece is out, and words typed back stand on the first line, where the name began.
    app, client, c = reviewed(tmp_path / "cut", clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    assert tick(client, 2, words="", press="settle").status_code == 303
    assert (texts(p)[1], texts(p)[2]) == ("What do you", "the sugar?") and mark_of(p, 2)["places"] == [{"line": 1, "first": 11, "last": 11}]
    assert tick(client, 2, press="open").status_code == 303 and tick(client, 2, words="use for", press="settle").status_code == 303
    assert (texts(p)[1], texts(p)[2]) == ("What do you use for", "the sugar?") and mark_of(p, 2)["standing"] == "use for"
    c.close()
    # At the start of a line, at its end, and on a line left with no words: one space each side where a word stands.
    app, client, c = halves(tmp_path / "ends", clock, machine)
    p = app.state.parts
    for mark, back, line, stood in ((1, "made-up", 2, "the made-up"), (2, "a b", 3, "a b")):
        assert tick(client, mark, words="", press="settle").status_code == 303
        assert tick(client, mark, press="open").status_code == 303 and tick(client, mark, words=back, press="settle").status_code == 303
        assert texts(p)[line] == stood, mark
    c.close()
    assert drug_marks.corrected("", {"standing": "Do", "page_lines": [1]}, {1: "Do you take it"}) == {1: "you take it"}
    assert drug_marks.corrected("Do", {"standing": "", "page_lines": [1], "places": [{"line": 1, "first": 0, "last": 0}]}, {1: "you take it"}) == {1: "Do you take it"}


def test_ruling_40_an_edit_elsewhere_on_the_line_does_not_clear_the_mark_and_words_typed_back_never_land_inside_a_word(tmp_path, clock, machine):
    # The plan review of 6e, point 9. The point an emptied name left moves with the letters around it.
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[{"doubtful": [{"line": 2, "heard": "met for min twice", "meant": ""}]}]), page=PAGE)
    p = app.state.parts
    assert tick(client, 1, words="", press="settle").status_code == 303
    rest = texts(p)[3].split("night. ")[1]
    assert texts(p)[3].startswith("I take a day and met for min at night.") and mark_of(p, 1)["places"] == [{"line": 3, "first": 7, "last": 7}]
    # The line's own box, saved with other words before the point and after it: the mark stays, with its row, and is not cleared.
    assert client.post("/consultations/1/lines/3", data={"label": "patient", "text": "Well, I do take a pill each day and met for min at night. " + rest}).status_code == 303
    mark = mark_of(p, 1)
    assert mark["cleared_at"] is None and mark["settled_at"] is not None and words.DRUG_TAKEN_OUT in row(page_of(client)[0], 1)
    assert tick(client, 1, press="open").status_code == 303 and tick(client, 1, words="NAME", press="settle").status_code == 303
    assert texts(p)[3].startswith("Well, I do take NAME a pill each day and met for min at night.")
    c.close()
    # The rule alone: before the change, after it, and where the change went over the point; never inside a word.
    moved = drug_marks.point_after
    assert moved(7, "I take a day", "I take a day at night") == 7                    # words added after the point: it stays
    assert moved(7, "I take a day", "Well I take a day") == 12                       # words added before it: it moves with them
    assert moved(7, "I take a day", "I took one a day") == 11                        # the letter after it still stands: beside that letter
    assert moved(4, "ab cd ef", "ab xy z ef") == 7                                   # the change went over it: where the changed stretch ends
    assert moved(7, "I take a day", "") == 0
    for before, now in (("I take a day", "I takeaway"), ("I take a day", "Itakeaday"), ("ab cd ef", "abcdef gh")):
        at = moved(7 if len(before) > 8 else 3, before, now)
        assert at in (0, len(now)) or now[at - 1].isspace() or now[at].isspace(), (before, now, at)
