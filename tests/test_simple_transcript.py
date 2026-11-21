"""The simple view of the transcript (spec 15.13, rulings 46, 73 and 74;
the details of step 9f). The transcript opens as numbered passages,
doctor, patient, doctor, patient: each turn of the reading view its
number, the speaker's word, one press that plays it, and its words as
running text. Of all the marks only a doubted drug name stays in sight,
because a misheard name is the one mark that can reach the patient
through the note. A passage is plain text: nothing opens. The advanced
view is the transcript as it stood, one press away, with Check who
spoke and the control that opens the lines; Swap stands in both. The
page holds both and an attribute says which is shown: so a test here
reads the page as the app gives it and the rules of the style sheet.
Made-up words, a made-up engine and worker; no browser."""

import re

from openconsult import words
from tests.conftest import refusal_on, text_of
from tests.test_reading_page import PAGE, REPLY, made, pieces, turn_plays, turns
from tests.test_review_page import NOTE, engine_with
from tests.test_row_keep import Parts, stop_thread_done
from tests.test_simple_note import view_rules
from tests.test_who_check import HeldEngine, press, reviewed, said

SECTION = '<section class="pane transcript no-print" id="transcript" data-view="{view}"{held}>'


def passages(raw: str) -> list[dict]:
    """Each passage as the page sends it: its number, the first line of its turn, the speaker's word, its play, and
    the piece of each of its lines, whole."""
    block = raw.split('<div class="pane-body passages" id="passages">', 1)[1].split('<div class="pane-body" id="final-transcript">', 1)[0]
    found = []
    for number, first, body in re.findall(r'<p class="passage" id="passage-(\d+)" data-first="(\d+)">(.*?)</p>', block, flags=re.S):
        head = re.match(r'<span class="passage-head"><span class="passage-number">(\d+)</span> ([^<]*)</span>', body)
        play = re.search(r'<button type="button" class="play-stretch passage-play" data-start="([^"]*)" data-end="([^"]*)" aria-label="([^"]*)" title="([^"]*)">', body)
        assert head.group(1) == number and (play is None or play.group(3) == play.group(4) == words.PLAY_TURN)
        found.append({"number": int(number), "first": int(first), "speaker": head.group(2), "body": body,
                      "play": (float(play.group(1)), float(play.group(2))) if play else None,
                      "lines": {int(n): held for n, held in re.findall(r'<span class="passage-line" id="passage-line-(\d+)" data-part>(.*?)</span> ', body, flags=re.S)}})
    assert len(found) == block.count("<p ") == block.count("</p>")
    return found


def passages_block(raw: str) -> str:
    return raw.split('id="passages">', 1)[1].split('<div class="pane-body" id="final-transcript">', 1)[0]


def doubted(mark: int, heard: str) -> str:
    return f'<a class="passage-doubt" href="#drug-mark-{mark}" title="{words.CHECK_THIS_NAME}"><mark class="doubted">{heard}</mark></a>'


def test_ruling_73_each_turn_is_one_passage_with_its_number_the_speaker_a_play_and_its_words_and_a_doubted_name_stays_marked(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    assert SECTION.format(view="simple", held="") in raw                           # a fresh visit: the simple view
    sent = passages(raw)
    # Doctor, patient, a word with no speaker on its own, doctor: numbered from 1, in order, one passage a turn.
    assert [(p["number"], p["speaker"], list(p["lines"])) for p in sent] == [(1, "Doctor", [1, 2, 3, 4]), (2, "Patient", [5]), (3, "Unsure", [6]), (4, "Doctor", [7])]
    assert [(p["first"], t["first"]) for p, t in zip(sent, turns(raw))] == [(1, 1), (5, 5), (6, 6), (7, 7)]
    # The one press plays the turn, with the stretch the turn's own press has (15.10, rulings 29 and 38).
    assert {p["first"]: p["play"] for p in sent} == turn_plays(raw) == {1: (0.0, 0.8), 5: (0.0, 1.5), 6: (0.55, 1.6), 7: (0.7, 2.0)}
    # The words of each line a piece of their own, in order, as running text.
    assert sent[0]["lines"][1] == "Good morning" and sent[0]["lines"][2] == "do" and sent[3]["lines"][7] == "Tell me more."
    assert re.sub(r"<[^>]+>", "", sent[0]["body"].split('<span class="passage-text">')[1]).split() == "Good morning do come in. What do you take for the sugar?".split()
    # A doubted drug name is highlighted inside its passage and is the press to its row among the warnings.
    assert sent[0]["lines"][3] == "come in. What do you " + doubted(2, "take") and sent[0]["lines"][4] == doubted(2, "for") + " the sugar?"
    assert sent[1]["lines"][5].startswith("I take " + doubted(1, "met for min") + " twice a day. word")
    assert raw.count('id="drug-mark-1"') == raw.count('id="drug-mark-2"') == 1
    # Settled at its row, a name shows no highlight in its passage, as in its turn.
    assert client.post("/consultations/1/marks/1", data={"press": "settle"}).status_code == 303
    assert "doubted" not in passages(client.get("/consultations/1").text)[1]["lines"][5]
    # The recording gone: no press on a passage, as none on a turn.
    for file in (tmp_path / "recordings").iterdir():
        file.unlink()
    gone = client.get("/consultations/1").text
    assert [p["play"] for p in passages(gone)] == [None] * 4 and "passage-play" not in gone
    c.close()


def test_rulings_73_74_no_other_mark_stands_in_a_passage_and_a_passage_is_plain_text_that_opens_nothing(tmp_path, clock, machine):
    # Every other mark is in the advanced view: a word with no sure speaker, a low score, a speaker set by the doctor,
    # a line the check moved with its Undo. Here each of them is on the page, in the turns, and none in the passages.
    low = PAGE[:6] + [{**PAGE[6], "confidence": 0.2}]
    check = said("doctor", "doctor", "doctor", "patient", "patient", "patient")
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY], label_check=[check], note=[NOTE]), page=low)
    assert stop_thread_done(app)
    assert client.post("/consultations/1/lines/1", data={"label": "patient", "text": "Good morning"}).status_code == 303
    assert client.post("/consultations/1/lines/1", data={"label": "doctor", "text": "Good morning"}).status_code == 303
    press(app, client)
    raw = client.get("/consultations/1").text
    advanced = "".join(pieces(text_of(client.get("/consultations/1"))).values())
    marks = (words.LABEL_UNSURE, words.LABEL_SET_BY_YOU, words.LABEL_CHANGED, words.UNDO_LABEL, words.LOW_CONFIDENCE_MARK.format(score="0.20"))
    assert all(mark in advanced for mark in marks)                                # each stands in the turns of the advanced view
    block = passages_block(raw)
    assert not any(mark in text_of(client.get("/consultations/1")).split('id="passages">', 1)[1].split('id="final-transcript"', 1)[0] for mark in marks)
    for piece in ('class="mark"', "changed", "turn-undo", "<form", "<input", "<select", "<details", "<summary", "–", "[1"):
        assert piece not in block, piece
    # A passage holds its head, at most one press, and its words: nothing that opens, and no box (ruling 74).
    assert set(re.findall(r"<(\w+)", block)) == {"p", "span", "button", "a", "mark"} and block.count("<button") == len(passages(raw))
    # The lines' own numbers and speakers are untouched by how the page is shown.
    assert [p["speaker"] for p in passages(raw)] == ["Doctor", "Patient"] and list(passages(raw)[1]["lines"]) == [5, 6, 7]
    c.close()


def test_ruling_73_a_line_with_no_words_adds_nothing_to_its_passage_and_keeps_its_own_piece(tmp_path, clock, machine):
    # A leftover piece of a drug name taken out at its row (15.10, ruling 40) leaves a line with no words. Its passage
    # shows nothing for it. Its piece stays, empty, so that words typed back at the row show there with no load.
    reply = {"doubtful": REPLY["doubtful"] + [{"line": 5, "heard": "Yes.", "meant": ""}]}
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[reply], note=[NOTE]), page=PAGE)
    assert stop_thread_done(app)
    mark = next(m["id"] for m in app.state.parts.consultations.drug_marks(1) if m["heard"] == "Yes.")
    assert client.post(f"/consultations/1/marks/{mark}", data={"words": "", "press": "settle"}).status_code == 303
    assert app.state.parts.consultations.line(1, 6)["text"] == ""
    sent = passages(client.get("/consultations/1").text)
    assert (sent[2]["number"], sent[2]["speaker"], sent[2]["lines"]) == (3, "Unsure", {6: ""})
    assert words.LINE_NO_WORDS not in passages_block(text_of(client.get("/consultations/1")))
    c.close()


def test_ruling_74_swap_and_the_two_presses_stand_in_both_views_and_check_who_spoke_and_the_control_that_opens_the_lines_in_the_advanced_view(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    head = raw.split('id="transcript"')[1].split('id="who-check"')[0]
    # The head, in order: Swap, Check who spoke, Open all the lines, then the two presses at the right.
    assert head.index('id="swap"') < head.index('id="check-who"') < head.index('id="open-all"') < head.index('id="transcript-views"')
    assert f'<span class="views no-print" id="transcript-views" role="group" aria-label="{words.VIEW_GROUP["transcript"]}">' in head
    assert '<a class="view" id="transcript-simple" data-area="transcript" data-view="simple" href="/consultations/1#transcript" aria-current="true">Simple</a>' in head
    assert '<a class="view" id="transcript-advanced" data-area="transcript" data-view="advanced" href="/consultations/1?transcript=advanced#transcript">Advanced</a>' in head
    # The rules of the two views, every one of them. Simple hides the turns with their lines, Check who spoke (the form
    # that can act and the control that has run), the pane with its line, its running sentence, its outcome and Undo
    # all, and the control that opens the lines. Advanced hides the passages. Swap, the two presses and the player are
    # under no rule of a view.
    rules = view_rules(client.get("/static/theme.css").text, "transcript")
    simple = '#transcript[data-view="simple"] '
    assert rules == {simple + "#final-transcript": "display: none;", simple + "#who-check": "display: none;", simple + "#check-who-form": "display: none;",
                     simple + "#check-who": "display: none;", simple + "#open-all": "display: none;",
                     '#transcript[data-view="advanced"] #passages': "display: none;"}
    for name in ("check-who-line", "check-who-outcome", "undo-all", "check-who-ran", "check-who-running"):
        where = raw.find(f'id="{name}"')
        assert where < 0 or raw.index('id="who-check"') < where < raw.index('id="player"'), name      # each stands in that pane
    assert raw.index('id="player"') < raw.index('id="passages"') < raw.index('id="final-transcript"')
    assert 'id="check-who-form"' in head and raw.count('id="passages"') == 1
    c.close()


def test_ruling_46_the_view_of_the_transcript_named_in_the_address_and_the_loads_that_come_back_to_the_advanced_view(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    advanced = client.get("/consultations/1?transcript=advanced").text
    assert SECTION.format(view="advanced", held="") in advanced and 'id="note" data-view="simple">' in advanced
    assert 'id="transcript-advanced" data-area="transcript" data-view="advanced" href="/consultations/1?transcript=advanced#transcript" aria-current="true">' in advanced
    # Each area's presses keep the view the other area has.
    both = client.get("/consultations/1?note=advanced&transcript=advanced").text
    assert 'id="note" data-view="advanced">' in both and SECTION.format(view="advanced", held="") in both
    assert 'id="note-simple" data-area="note" data-view="simple" href="/consultations/1?transcript=advanced#note">' in both
    assert 'id="transcript-simple" data-area="transcript" data-view="simple" href="/consultations/1?note=advanced#transcript">' in both
    # The same pieces whichever view is shown: the passages and the turns are both in the page.
    plain = client.get("/consultations/1").text
    assert passages_block(plain) == passages_block(advanced) and [t["lines"] for t in turns(plain)] == [t["lines"] for t in turns(advanced)]
    # With no script, a load that comes back to something of the advanced view alone gives that view: every line opened;
    # a Save or an Undo of a line that the app refused, with its sentence on the line.
    assert SECTION.format(view="advanced", held="") in client.get("/consultations/1?lines=open").text
    emptied = client.post("/consultations/1/lines/3", data={"label": "doctor", "text": ""})
    assert emptied.status_code == 400 and refusal_on(text_of(emptied), "save-line-3") == words.ENTRY_EMPTY
    assert SECTION.format(view="advanced", held="") in emptied.text
    assert SECTION.format(view="advanced", held="") in client.post("/consultations/1/lines/5/undo").text
    # A refusal that stands in both views changes no view: Swap after Approve.
    assert client.post("/consultations/1/note/approve").status_code == 303
    swapped = client.post("/consultations/1/lines/swap")
    assert swapped.status_code == 400 and SECTION.format(view="simple", held="") in swapped.text
    c.close()


def test_ruling_74_while_the_check_of_who_spoke_runs_the_transcript_is_held_in_the_advanced_view_and_its_outcome_comes_back_there(tmp_path, clock, machine):
    engine = HeldEngine({"note": [NOTE], "drug_name": [REPLY], "label_check": [said("doctor", "doctor", "doctor", "patient", "patient", "patient")]})
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)
    assert stop_thread_done(app)
    assert client.post("/consultations/1/who-check").status_code == 303 and engine.entered.wait(20)
    # Running: advanced whatever the address says, and held; Simple cannot act, looks so, and is described by the running sentence (R15).
    for address in ("/consultations/1", "/consultations/1?quiet=2", "/consultations/1?transcript=simple"):
        running = client.get(address).text
        assert SECTION.format(view="advanced", held=" data-view-held") in running
        assert f'<span class="view" id="transcript-simple" aria-disabled="true" aria-describedby="check-who-running">{words.VIEW_WORDS["simple"]}</span>' in running
        assert running.count('id="check-who-running"') == 1 and 'id="transcript-advanced"' in running and 'href="/consultations/1#transcript"' not in running
    assert "opacity" in client.get("/static/theme.css").text.split('.views .view[aria-disabled="true"] {')[1].split("}")[0]
    engine.release.set()
    app.state.parts.who_checks.wait(1, 20)
    # The load that follows the last wait shows the outcome, which stands in the advanced view: with no script too.
    last = client.get("/consultations/1?quiet=5").text
    assert SECTION.format(view="advanced", held="") in last and 'id="check-who-outcome"' in last and 'id="transcript-simple" data-area' in last
    # The page's own timed look, which carries no count, and a plain load are the simple view again.
    for address in ("/consultations/1?quiet", "/consultations/1"):
        assert SECTION.format(view="simple", held="") in client.get(address).text
    c.close()


def test_9f_an_advanced_turn_carries_the_number_its_passage_shows_and_every_name_stands_once(tmp_path, clock, machine):
    app, client, c = made(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    sent = turns(raw)
    for passage, turn in zip(passages(raw), sent):
        k = passage["number"]
        # At the start of the turn's summary, before its first and last line number: read by a screen reader, found by a chip's press.
        assert turn["summary"].startswith(f'<span class="turn-number" id="turn-number-{k}">Turn {k}</span><span class="speaker">')
        assert raw.count(f'id="turn-number-{k}"') == raw.count(f'id="passage-{k}"') == 1 and raw.count(f'id="turn-{passage["first"]}"') == 1
    assert words.TURN_NUMBER == "Turn {n}" and raw.count('class="turn-number"') == len(sent) == 4
    # Hidden from the eye by its rule, not from a reader: no display none, no hidden.
    rule = client.get("/static/theme.css").text.split(".turn-number {")[1].split("}")[0]
    assert "clip-path" in rule and "display" not in rule and "visibility" not in rule
    for n in range(1, 8):
        for name in (f"line-{n}", f"turn-line-{n}", f"passage-line-{n}"):
            assert raw.count(f'id="{name}"') == 1, name
    # The page gives its script what a chip's press needs in each view: every chip names a passage that is on the page.
    chips = {int(k) for k in re.findall(r'class="chip no-print" data-turn="(\d+)"', raw)}
    assert chips and chips <= {p["number"] for p in passages(raw)}
    c.close()


def test_15_10_ruling_33_a_kept_name_stands_in_its_passage_in_a_part_of_its_own_that_holds_no_field(tmp_path, clock, machine):
    # After a name is kept on leaving its box the page is not loaded: fresh.js puts each marked part of the app's answer
    # in place. So the words of a line inside a passage are a part, as they are inside a closed turn since step 6e.
    reply = {"doubtful": REPLY["doubtful"] + [{"line": 2, "heard": "do", "meant": ""}]}
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[reply], note=[NOTE]), page=PAGE)
    assert stop_thread_done(app)
    before = client.get("/consultations/1").text
    mark = next(m["id"] for m in app.state.parts.consultations.drug_marks(1) if m["heard"] == "do")
    assert client.post(f"/consultations/1/marks/{mark}", data={"words": "do sit", "press": "keep"}).status_code == 303
    after = client.get("/consultations/1").text
    assert "do sit" in passages(after)[0]["lines"][2] and "do sit" not in passages_block(before)
    parts = Parts(after)
    assert parts.nested == 0 and all(parts.fields[f"passage-line-{n}"] == 0 for n in range(1, 8))
    c.close()
