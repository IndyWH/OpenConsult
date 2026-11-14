"""The row of a doubted drug name, the one place to hear it, correct it
and settle it (spec 15.10 rulings 6, 11, 26, 27 and 28 and the details of
step 6d: The row of a doubted name, What the field changes, The play
button, The tick, Settled, An edit in the line's own box, After Approve;
the plan review of 6d, points 1, 2, 6 and 7; 15.9 ruling 1; R15). A
made-up page and made-up replies; a made-up name stands for what the
doctor types and for the drug the model named, which no page shows."""

import hashlib
import json
import re

from openconsult import words
from openconsult.consult import drug_marks, note
from tests.conftest import refusal_on, text_of
from tests.test_drug_marks import PAGE, REPLY
from tests.test_live import live_seg
from tests.test_review_marks import NAMED, count_on_approve, page_of, part
from tests.test_review_page import NOTE, engine_with
from tests.test_who_check import HeldEngine, press, reviewed, said, slot_text

TYPED = "a made-up name"
DRAFT_OFF = 'id="draft" aria-describedby="draft-refusal" disabled'
# A name the speech choice cut over three lines: its last two words are the whole of line 2. Lines 1 to 3 join.
CUT_PAGE = [live_seg(1, 0.0, 0.5, "Do you take glick", "S1"), live_seg(2, 0.6, 0.9, "la side", "S1"),
            live_seg(3, 1.0, 1.4, "every day?", "S1"), live_seg(4, 1.5, 2.0, "Yes I do. " + "word " * 60, "S2")]
CUT_REPLY = {"doubtful": [{"line": 1, "heard": "glick la side", "meant": "a made-up drug"}]}


def row(raw: str, mark: int) -> str:
    return part(raw, f'id="drug-mark-{mark}"', "</li>")


def tick(client, mark: int, **fields):
    return client.post(f"/consultations/1/marks/{mark}", data=fields)


def texts(p) -> dict:
    return {line["n"]: line["text"] for line in p.consultations.transcript_lines(1) if line["n"] is not None}


def mark_of(p, mark: int) -> dict:
    return next(m for m in p.consultations.drug_marks(1, every=True) if m["id"] == mark)


def events(p) -> list[tuple[str, str]]:
    return [(line.event, line.detail) for line in reversed(p.audit.lines()) if line.event.startswith(("drug_name.", "transcript."))]


def counted(raw: str) -> int:
    return int(count_on_approve(raw).split()[0])


def test_rulings_26_28_each_mark_is_a_row_a_form_of_its_own_with_line_words_field_play_and_tick_in_that_order(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    raw, page = page_of(client)
    warnings = part(raw, 'id="warnings"', 'id="alarms"')
    # Under the head sentences and above the other warnings, one row for each mark, in the order the names were heard.
    assert warnings.index(words.DRUG_MARKED.format(count=2)) < warnings.index(words.DRUG_NOT_PROVEN) < warnings.index('id="drug-rows"') \
        < warnings.index('data-kind="confidence_not_measured"')
    assert re.findall(r'id="drug-mark-(\d+)"', warnings) == ["2", "1"] and "may be a drug name that was misheard" not in page
    first = row(raw, 2)
    places = [first.index(piece) for piece in (
        'class="cite row-line" data-line="1">' + words.DRUG_ROW_LINE.format(n=1) + "</button>",
        '<span class="row-words">What do you <input name="words" value="take for"',
        'class="play-stretch row-play" data-start="0.0" data-end="0.9"',                 # the first line's start to the last line's end
        'class="tick not-ticked" id="tick-2" name="press" value="settle"')]
    assert places == sorted(places)
    assert "> the sugar?</span>" in first                       # the piece on the later line is held in the field; the rest of the line follows
    assert words.DRUG_FIELD_NAME.format(n=1) in first and first.count(words.PLAY_LINE) == 2          # the play button's name and its title
    # A form of its own that works with no script: a real text field, and the tick is the form's one submit button.
    assert first.count("<form") == 1 and 'method="post" action="/consultations/1/marks/2" class="drug-row-form"' in first
    buttons = re.findall(r"<button([^>]*)>", first)
    assert len(buttons) == 3 and [("type=\"button\"" in b) for b in buttons] == [True, True, False] and "onclick" not in first
    # The words twice on a line: one field at the first place, the other place highlighted, so the row shows all that a press changes.
    second = row(raw, 1)
    assert '<span class="row-words">I take <input name="words" value="met for min"' in second and second.count("<input") == 1
    assert '> twice a day and <mark class="doubted">met for min</mark> at night.' in second
    assert 'class="play-stretch row-play" data-start="1.0" data-end="1.6"' in second and 'data-line="3">' + words.DRUG_ROW_LINE.format(n=3) in second
    # The player's data holds each row's stretch; no guess is shown (ruling 6): not in a row, a field or the page.
    data = json.loads(raw.split('<script id="player-data" type="application/json">')[1].split("</script>")[0])
    assert {"kind": "drug_mark", "start_s": 0.0, "end_s": 0.9} in data["stretches"] and {"kind": "drug_mark", "start_s": 1.0, "end_s": 1.6} in data["stretches"]
    assert NAMED not in page and NAMED not in raw and NAMED in mark_of(app.state.parts, 1)["meant"]
    # The recording has gone: no play button in a row; the field and the tick stay.
    (tmp_path / "recordings" / "consultation_1.wav").unlink()
    gone = row(client.get("/consultations/1").text, 2)
    assert "row-play" not in gone and "play-stretch" not in gone and 'name="words"' in gone and 'id="tick-2"' in gone
    c.close()


def test_ruling_28_a_tick_with_the_words_unchanged_settles_the_mark_changes_no_line_and_a_second_press_opens_it_again(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    before, start = texts(p), counted(page_of(client)[0])
    answer = tick(client, 1, words="met for min", press="settle")
    assert answer.status_code == 303 and answer.headers["location"].endswith("/consultations/1#drug-mark-1")     # back at the row, not the top
    mark = mark_of(p, 1)
    assert mark["settled_at"] is not None and (mark["heard"], mark["standing"]) == ("met for min", "met for min")
    assert texts(p) == before and p.consultations.transcript_edits(1) == [] and events(p) == [("drug_name.settled", "consultation 1: line 3")]
    raw, page = page_of(client)
    ticked = row(raw, 1)
    # Settled: the row stays, ticked, its words locked; no highlight on its line; not counted on Approve; no draft is offered.
    assert ticked.startswith(' data-kind="drug_mark" data-settled="yes"') and "<input" not in ticked and "<mark" not in ticked
    assert ticked.count('<span class="settled-words">met for min</span>') == 2
    assert 'class="tick ticked" id="tick-1" name="press" value="open" aria-pressed="true"' in ticked
    line_three = part(raw, 'id="line-3"', 'id="line-4"')
    assert "doubted" not in line_three and words.CHECK_THIS_NAME not in line_three
    assert counted(raw) == start - 1 and words.DRUG_MARKED.format(count=2) in page and DRAFT_OFF in raw      # the head counts the rows
    assert 'id="approve" aria-describedby="approve-refusal" disabled' not in raw
    # A press from a stale page never turns it the wrong way: settle on a ticked mark does nothing.
    assert tick(client, 1, words="other words", press="settle").status_code == 303
    assert mark_of(p, 1)["settled_at"] == mark["settled_at"] and texts(p) == before
    # A second press opens it: not settled, the field back, counted again.
    assert tick(client, 1, press="open").status_code == 303
    assert mark_of(p, 1)["settled_at"] is None and events(p)[-1] == ("drug_name.opened", "consultation 1: line 3")
    raw, _ = page_of(client)
    assert '<input name="words" value="met for min"' in row(raw, 1) and 'data-settled="no"' in row(raw, 1) and counted(raw) == start
    assert "doubted" in part(raw, 'id="line-3"', 'id="line-4"')
    assert tick(client, 1, press="open").status_code == 303 and len(events(p)) == 2                            # open on an open mark does nothing
    c.close()


def test_rulings_26_28_11_a_tick_with_new_words_corrects_every_place_on_the_line_offers_draft_again_and_settles(tmp_path, clock, machine):
    engine = engine_with(drug_name=[REPLY], note=[NOTE, NOTE])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    before = texts(p)
    assert before[3].count("met for min") == 2 and DRAFT_OFF in page_of(client)[0]
    assert tick(client, 1, words=f"  {TYPED} ", press="settle").status_code == 303
    after = texts(p)
    # The same words twice on the mark's lines: both corrected, by the function the line's own box uses. No other letter changes.
    assert after[3] == before[3].replace("met for min", TYPED) and {n: t for n, t in after.items() if n != 3} == {n: t for n, t in before.items() if n != 3}
    edits = p.consultations.transcript_edits(1)
    assert [(e["kind"], e["line_n"], e["before"], e["after"]) for e in edits] == [("words", 3, before[3], after[3])]
    assert events(p) == [("transcript.edited", "consultation 1: line 3"), ("drug_name.settled", "consultation 1: line 3")]
    mark = mark_of(p, 1)
    assert (mark["heard"], mark["standing"], mark["meant"]) == ("met for min", TYPED, "a made-up drug") and mark["settled_at"] is not None
    assert [after[3][place["first"]:place["last"]] for place in mark["places"]] == [TYPED, TYPED]
    raw, page = page_of(client)
    assert row(raw, 1).count(f'<span class="settled-words">{TYPED}</span>') == 2 and "met for min" not in raw
    # Draft the note again is offered, never run: one press makes one draft from the corrected line, and the drug-name call is not made again.
    assert DRAFT_OFF not in raw and words.DRAFT_AGAIN in page and len(engine.calls_for("note")) == 1
    assert client.post("/consultations/1/note/draft").status_code == 303
    assert len(engine.calls_for("note")) == 2 and TYPED in engine.calls_for("note")[1].user and len(engine.calls_for("drug_name")) == 1
    # Opened again, the field holds what was typed and the line keeps it.
    assert tick(client, 1, press="open").status_code == 303 and texts(p) == after
    assert f'<input name="words" value="{TYPED}"' in row(page_of(client)[0], 1)
    # An edit in the line's own box: a settled mark whose words still stand is found again, still settled; one whose words are gone is cleared.
    assert tick(client, 1, words=TYPED, press="settle").status_code == 303
    assert client.post("/consultations/1/lines/3", data={"label": "patient", "text": "So " + after[3]}).status_code == 303
    moved = mark_of(p, 1)
    assert moved["settled_at"] is not None and moved["cleared_at"] is None and moved["places"][0]["first"] == mark["places"][0]["first"] + 3
    assert client.post("/consultations/1/lines/3", data={"label": "patient", "text": "I take the tablets."}).status_code == 303
    assert mark_of(p, 1)["cleared_at"] is not None and 'id="drug-mark-1"' not in page_of(client)[0]             # judged by the typed words: gone
    assert (mark_of(p, 1)["heard"], mark_of(p, 1)["meant"]) == ("met for min", "a made-up drug")               # the record keeps it
    c.close()


def test_6d_review_point_2_words_over_two_lines_go_on_the_first_and_the_row_still_plays_and_shows_both_lines(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    assert 'data-start="0.0" data-end="0.9"' in row(page_of(client)[0], 2)
    assert tick(client, 2, words="use", press="settle").status_code == 303
    after = texts(p)
    # The typed words replace the piece on the first line; the piece on the later line is taken out with one of its spaces.
    assert (after[1], after[2]) == ("What do you use", "the sugar?") and sorted(after) == [1, 2, 3, 4]         # no line removed or renumbered
    assert [(e["kind"], e["line_n"], e["before"], e["after"]) for e in p.consultations.transcript_edits(1)] == [
        ("words", 1, "What do you take", "What do you use"), ("words", 2, "for the sugar?", "the sugar?")]
    mark = mark_of(p, 2)
    assert (mark["standing"], mark["places"], mark["heard_first"], mark["heard_last"]) == ("use", [{"line": 1, "first": 12, "last": 15}], 1, 2)
    # Opened again, the row has not shrunk: Line 1, both lines' words, and play from the first line's start to the last line's end.
    assert tick(client, 2, press="open").status_code == 303
    opened = row(page_of(client)[0], 2)
    assert 'data-start="0.0" data-end="0.9"' in opened and 'data-line="1">' + words.DRUG_ROW_LINE.format(n=1) in opened
    assert '<span class="row-words">What do you <input name="words" value="use"' in opened and "> the sugar?</span>" in opened
    c.close()


def test_6d_review_point_6_every_place_that_will_take_the_typed_words_is_highlighted_in_the_row_before_the_press(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    # The doctor types words that already stand, rightly, on the same joined line: the mark is then found in both places.
    assert tick(client, 2, words="the", press="settle").status_code == 303 and tick(client, 2, press="open").status_code == 303
    assert (texts(p)[1], texts(p)[2]) == ("What do you the", "the sugar?")
    shown = row(page_of(client)[0], 2)
    assert '<span class="row-words">What do you <input name="words" value="the"' in shown and '> <mark class="doubted">the</mark> sugar?</span>' in shown
    # So nothing on a line changes that the row did not show: the next typed words go to both.
    assert tick(client, 2, words="your", press="settle").status_code == 303
    assert (texts(p)[1], texts(p)[2]) == ("What do you your", "your sugar?")
    c.close()


def test_6d_review_point_1_a_later_line_left_with_no_words_stays_with_its_number_speaker_and_sound_and_no_model_reads_it(tmp_path, clock, machine):
    engine = engine_with(drug_name=[CUT_REPLY], note=[NOTE, NOTE], label_check=[said("doctor", "patient")])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=CUT_PAGE)
    p = app.state.parts
    held = {line["n"]: (line["label"], line["start_s"], line["end_s"]) for line in p.consultations.transcript_lines(1) if line["n"] is not None}
    assert tick(client, 1, words=TYPED, press="settle").status_code == 303
    after = texts(p)
    assert after == {1: "Do you take " + TYPED, 2: "", 3: "every day?", 4: texts(p)[4]}          # nothing nobody spoke or typed is written into it
    assert {line["n"]: (line["label"], line["start_s"], line["end_s"]) for line in p.consultations.transcript_lines(1) if line["n"] is not None} == held
    assert [(e["line_n"], e["before"], e["after"]) for e in p.consultations.transcript_edits(1)] == [
        (1, "Do you take glick", "Do you take " + TYPED), (2, "la side", "")]                    # the words before are kept
    raw, page = page_of(client)
    emptied = part(raw, 'id="line-2"', 'id="line-3"')
    assert words.LINE_NO_WORDS in emptied and 'class="play-line cite" data-line="2"' in emptied and 'name="text" value=""' in emptied
    assert page.count(words.LINE_NO_WORDS) == 1
    # Its own box: an empty line may stay empty, so that its speaker can be set; a line that holds words is still never emptied there.
    assert client.post("/consultations/1/lines/2", data={"label": "patient", "text": ""}).status_code == 303
    assert p.consultations.line(1, 2)["label"] == "patient" and p.consultations.line(1, 2)["text"] == ""
    refused = client.post("/consultations/1/lines/1", data={"label": "doctor", "text": " "})
    assert refused.status_code == 400 and refusal_on(text_of(refused), "save-line-1") == words.ENTRY_EMPTY and texts(p)[1] == "Do you take " + TYPED
    # The note drafted again: the model reads no empty turn and no empty line, though line 2 now sits under another speaker.
    assert client.post("/consultations/1/note/draft").status_code == 303
    sent = engine.calls_for("note")[1].user
    assert f"[0] {note.DOCTOR}: Do you take {TYPED} every day?" in sent.splitlines() and not re.search(r"^\[\d+\] \w+:\s*$", sent, re.M)
    # The check of who spoke: no empty numbered line is sent, the run answers, and the empty line takes no label from it.
    press(app, client)
    asked = engine.calls_for("label_check")[0].user
    assert f"[1] Do you take {TYPED} every day?" in asked.splitlines() and not re.search(r"^\[\d+\]\s*$", asked, re.M)
    assert p.consultations.check_runs(1)[-1]["outcome"] == "answered" and p.consultations.line(1, 2)["label"] == "patient"
    c.close()


def test_6d_review_point_1c_the_notes_text_for_a_page_with_no_empty_line_is_the_bytes_it_was_and_an_empty_line_is_left_out():
    rows = [{"n": 1, "label": "doctor", "text": "What do you take"}, {"n": 2, "label": "doctor", "text": "for the sugar?"},
            {"n": None, "label": "unsure", "text": "refused words"}, {"n": 3, "label": "patient", "text": "I take a made-up name twice a day."},
            {"n": 4, "label": "unsure", "text": " and at night "}, {"n": 5, "label": "doctor", "text": "Tell me more."}]
    text = note.turns_text(note.turns_of(rows))
    # The figure was taken with the code as it stood before step 6d changed turns_of: no word the note model reads is new.
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == "e23da01f63c407b70e62a6a3403114f40f734e5a1fede538d68e773f3b56cd01"
    assert [t["lines"] for t in note.turns_of(rows)] == [[1, 2], [3], [4], [5]]
    # An empty line is in no turn, and a turn is never made of empty lines alone: its neighbours of one speaker join over it.
    emptied = rows[:4] + [{"n": 4, "label": "unsure", "text": " "}, {"n": 5, "label": "patient", "text": "At night."}]
    turns = note.turns_of(emptied)
    assert [(t["n"], t["label"], t["lines"], t["text"]) for t in turns] == [
        (0, "doctor", [1, 2], "What do you take for the sugar?"), (1, "patient", [3, 5], "I take a made-up name twice a day. At night.")]
    assert note.turns_of([{"n": 1, "label": "doctor", "text": ""}]) == []


def test_6d_taking_a_piece_out_leaves_one_space_at_the_cut_and_none_at_an_end_of_the_line():
    mark = {"standing": "up made", "page_lines": [1, 2, 3]}
    assert drug_marks.corrected("name", mark, {1: "it is made up", 2: "made of words", 3: "and more"}) == {1: "it is made name", 2: "of words"}
    assert drug_marks.corrected("name", mark, {1: "made up", 2: "made", 3: "up there"}) == {1: "made name", 2: ""}
    assert drug_marks.corrected("name", {**mark, "standing": "is made up made of"}, {1: "it is made", 2: "up", 3: "made of words"}) == {
        1: "it name", 2: "", 3: "words"}
    assert drug_marks.corrected("name", mark, {1: "none of them", 2: "stands", 3: "here"}) == {}
    assert drug_marks.places_of("of", [1, 2, 3], {1: "made", 2: " ", 3: "of words"}) == [{"line": 3, "first": 0, "last": 2}]   # an empty line holds no place


def test_6d_an_empty_field_is_refused_at_the_row_and_a_press_for_a_mark_that_is_not_on_the_page_changes_nothing(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    p = app.state.parts
    before = texts(p)
    refused = tick(client, 1, words="   ", press="settle")
    assert refused.status_code == 400 and refusal_on(text_of(refused), "tick-1") == words.ENTRY_EMPTY       # the line box's own sentence
    assert texts(p) == before and mark_of(p, 1)["settled_at"] is None and events(p) == []
    # A mark that is unknown, or cleared by an edit, has no row: the press goes back to the warnings and changes nothing (R15).
    p.consultations.clear_mark(2)
    for mark in (2, 99):
        answer = tick(client, mark, words=TYPED, press="settle")
        assert answer.status_code == 303 and answer.headers["location"].endswith("/consultations/1#warnings")
    assert texts(p) == before and events(p) == [] and mark_of(p, 2)["settled_at"] is None
    c.close()


def test_6d_another_mark_on_a_corrected_line_is_found_again_where_its_words_now_stand_or_cleared_when_they_are_gone(tmp_path, clock, machine):
    reply = {"doubtful": [{"line": 2, "heard": "met for min", "meant": ""}, {"line": 2, "heard": "min twice", "meant": ""},
                          {"line": 2, "heard": "at night", "meant": ""}]}
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[reply]), page=PAGE)
    p = app.state.parts
    was = mark_of(p, 3)["places"][0]["first"]
    assert tick(client, 1, words=TYPED, press="settle").status_code == 303
    line = texts(p)[3]
    assert mark_of(p, 2)["cleared_at"] is not None                                                 # its words ran into the corrected name: gone
    found = mark_of(p, 3)
    assert found["cleared_at"] is None and found["settled_at"] is None and found["places"][0]["first"] == was + 2 * (len(TYPED) - len("met for min"))
    assert line[found["places"][0]["first"]:found["places"][0]["last"]] == "at night"
    assert re.findall(r'id="drug-mark-(\d+)"', page_of(client)[0]) == ["1", "3"]
    c.close()


def test_R15_ruling_28_the_ticks_state_is_told_in_words_and_shape_as_well_as_colour(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    assert tick(client, 1, words="met for min", press="settle").status_code == 303
    raw, _ = page_of(client)
    open_tick = re.search(r'<button class="tick[^>]*id="tick-2"[^>]*>([^<]*)</button>', raw)
    ticked = re.search(r'<button class="tick[^>]*id="tick-1"[^>]*>([^<]*)</button>', raw)
    # Its name for a screen reader, its title and aria-pressed say the state; so does its sign, a thin tick or a heavy one.
    for found, state, pressed, name, sign in ((open_tick, "not-ticked", "false", words.TICK_OPEN, "&#10003;"),
                                              (ticked, "ticked", "true", words.TICK_SETTLED, "&#10004;")):
        tag = found.group(0)
        assert f'class="tick {state}"' in tag and f'aria-pressed="{pressed}"' in tag and found.group(1) == sign
        assert f'aria-label="{name}"' in tag and f'title="{name}"' in tag and "aria-disabled" not in tag
    assert (words.TICK_OPEN, words.TICK_SETTLED) == ("Tick this name when it is right", "Ticked as right. Press to open it again")
    # The style sheet: the edge, broken or whole, and the weight carry the state, not the fill alone (the plan review, point 3).
    css = client.get("/static/theme.css").text
    faded = css.split("button.tick.not-ticked {")[1].split("}")[0]
    full = css.split("button.tick.ticked, button.tick.ticked:hover {")[1].split("}")[0]
    assert "border: 2px dashed" in faded and "font-weight: 400" in faded and "border: 2px solid" in full and "font-weight: 700" in full
    assert "@media (forced-colors: active) { button.tick.ticked { border-width: 4px; } }" in css
    c.close()


def test_6d_review_point_7_nothing_presses_on_a_read_only_page_and_the_rows_show_with_their_ticks_as_they_stood(tmp_path, clock, machine):
    engine = HeldEngine({"note": [NOTE], "drug_name": [REPLY], "label_check": [said("doctor", "patient", "doctor")]})
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    assert tick(client, 1, words="met for min", press="settle").status_code == 303
    before, settled = texts(p), mark_of(p, 1)["settled_at"]

    def nothing_presses(sentence):
        raw = client.get("/consultations/1").text
        ticked, open_row = row(raw, 1), row(raw, 2)
        assert '<input name="words" value="take for"' in open_row and " readonly>" in open_row.split('name="words"')[1].split(">")[0] + ">"
        assert f'aria-label="{words.TICK_OPEN_READ_ONLY}"' in open_row and f'aria-label="{words.TICK_SETTLED_READ_ONLY}"' in ticked
        assert open_row.count('aria-disabled="true"') == 1 and ticked.count('aria-disabled="true"') == 1 and "<input" not in ticked
        assert words.TICK_OPEN not in open_row and words.TICK_SETTLED not in ticked                  # no name invites a press that cannot act
        for mark, fields in ((2, {"words": TYPED, "press": "settle"}), (1, {"press": "open"})):
            answer = tick(client, mark, **fields)
            assert answer.status_code == 400 and refusal_on(text_of(answer), f"tick-{mark}") == sentence
        assert texts(p) == before and mark_of(p, 1)["settled_at"] == settled and mark_of(p, 2)["settled_at"] is None

    # While a check of who spoke runs, nothing changes under it.
    assert client.post("/consultations/1/who-check").status_code == 303 and engine.entered.wait(20)
    nothing_presses(words.CHECK_RUNNING)
    engine.release.set()
    p.who_checks.wait(1, 20)
    # After Approve the page is read-only: the highlight of the mark that was not settled stands in the line itself.
    assert client.post("/consultations/1/note/approve").status_code == 303
    nothing_presses(words.NOTE_READ_ONLY)
    raw = client.get("/consultations/1").text
    assert '<mark class="doubted">take</mark>' in part(raw, 'id="line-1"', 'id="line-2"') and "doubted" not in part(raw, 'id="line-3"', 'id="line-4"')
    assert slot_text(text_of(client.get("/consultations/1")), "tick-1") == ""
    c.close()


def test_6d_beside_the_lines_box_the_doubted_words_are_a_press_that_goes_to_the_row_and_nothing_to_type_in(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    raw, _ = page_of(client)
    line_three = part(raw, 'id="line-3"', 'id="line-4"')
    link = '<a class="doubted-word" href="#drug-mark-1"><mark class="doubted">met for min</mark> <span class="mark">' + words.CHECK_THIS_NAME + "</span></a>"
    assert line_three.count(link) == 2 and line_three.count("<input") == 1                       # the line's own box, and nothing else to type in
    assert 'href="#drug-mark-2"><mark class="doubted">take</mark>' in part(raw, 'id="line-1"', 'id="line-2"')
    assert 'href="#drug-mark-2"><mark class="doubted">for</mark>' in part(raw, 'id="line-2"', 'id="line-3"')
    assert 'id="drug-mark-1"' in raw and 'id="drug-mark-2"' in raw                               # where each press goes
    # A settled mark shows none.
    assert tick(client, 1, words="met for min", press="settle").status_code == 303
    raw, _ = page_of(client)
    assert "doubted-word" not in part(raw, 'id="line-3"', 'id="line-4"') and 'href="#drug-mark-2"' in part(raw, 'id="line-1"', 'id="line-2"')
    c.close()


def test_6d_ruling_11_R15_draft_the_note_again_shows_a_second_time_under_the_rows_only_when_the_first_is_offered(tmp_path, clock, machine):
    engine = engine_with(drug_name=[REPLY], note=[NOTE, NOTE])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    p = app.state.parts
    raw, _ = page_of(client)
    assert DRAFT_OFF in raw and 'id="draft-rows"' not in raw                                    # nothing edited: neither can act, the second is not shown
    stale = client.post("/consultations/1/note/draft", data={"where": "rows"})                 # a press from a stale page answers under the rows
    assert stale.status_code == 400 and slot_text(text_of(stale), "draft-rows") == words.DRAFT_AGAIN_NEEDS_EDIT and len(engine.calls_for("note")) == 1
    assert tick(client, 1, words=TYPED, press="settle").status_code == 303
    raw, _ = page_of(client)
    warnings = part(raw, 'id="warnings"', 'id="alarms"')
    assert DRAFT_OFF not in raw and warnings.count('id="draft-rows"') == 1
    assert warnings.rindex('class="drug-row"') < warnings.index('id="draft-rows"') < warnings.index('data-kind="confidence_not_measured"')
    assert 'action="/consultations/1/note/draft" id="draft-rows-form"' in warnings and ">" + words.DRAFT_AGAIN + "</button>" in warnings
    assert len(engine.calls_for("note")) == 1                                                  # never by itself
    assert client.post("/consultations/1/note/draft", data={"where": "rows"}).status_code == 303
    assert len(engine.calls_for("note")) == 2 and len(p.notes.drafts(1)) == 2 and len(engine.calls_for("drug_name")) == 1    # one press, one draft
    raw, _ = page_of(client)
    assert DRAFT_OFF in raw and 'id="draft-rows"' not in raw
    c.close()
    # With no row, an edit by hand offers the control at the top alone.
    app, client, c = reviewed(tmp_path / "none", clock, machine, engine_with(drug_name=[{"doubtful": []}]), page=PAGE)
    assert client.post("/consultations/1/lines/4", data={"label": "doctor", "text": "Tell me a little more."}).status_code == 303
    raw, _ = page_of(client)
    assert DRAFT_OFF not in raw and 'id="draft-rows"' not in raw and 'id="drug-rows"' not in raw
    c.close()


def test_6d_review_point_5_the_page_tells_its_script_what_may_be_done_with_words_typed_and_not_yet_ticked(tmp_path, clock, machine):
    # Each row is a form of its own, so a press on one tick loads the page again; the script keeps the words typed into
    # the other rows in the browser's own store and puts them back. The app decides what the store may do and says so on
    # the page; the suite has no browser, so what the script then does is seen in a browser and not asserted here.
    engine = HeldEngine({"note": [NOTE], "drug_name": [REPLY], "label_check": [said("doctor", "patient", "doctor")]})
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    raw, _ = page_of(client)
    assert 'data-path="/consultations/1" data-consultation="1" data-kept="open"' in raw and '<script src="/static/kept.js"></script>' in raw
    assert 'class="doubted-field" size="11" data-mark="1"' in row(raw, 1) and 'data-mark="2"' in row(raw, 2)   # which row a kept word belongs to
    script = client.get("/static/kept.js")
    assert script.status_code == 200 and "sessionStorage" in script.text and "fetch(" not in script.text and "XMLHttpRequest" not in script.text
    # A row that is ticked has no field, so nothing can be put back into it.
    assert tick(client, 1, words="met for min", press="settle").status_code == 303 and "data-mark" not in row(page_of(client)[0], 1)
    # While a check of who spoke runs the store is left alone; once the page is approved everything kept is dropped.
    assert client.post("/consultations/1/who-check").status_code == 303 and engine.entered.wait(20)
    assert 'data-kept="wait"' in client.get("/consultations/1").text
    engine.release.set()
    app.state.parts.who_checks.wait(1, 20)
    assert 'data-kept="open"' in client.get("/consultations/1").text
    assert client.post("/consultations/1/note/approve").status_code == 303 and 'data-kept="drop"' in client.get("/consultations/1").text
    c.close()
