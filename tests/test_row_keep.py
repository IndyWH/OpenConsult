"""Leaving the box of a doubted drug name, and the page keeping its place
(spec 15.10 rulings 11, 28, 33, 34 and 37 and the details of the mend run
of step 6d: Leaving the box, The kept words go, The page keeps its
place; R15). The room run of 15 Nov 2026: a name typed and then left was
lost at the next press, and after a press the page moved by itself. A
made-up page and made-up replies; a made-up name stands for what the
doctor types. The page's scripts are seen in a browser, not run here."""

import json
import re
from html.parser import HTMLParser

from openconsult import words
from tests.conftest import refusal_on, text_of
from tests.test_drug_marks import PAGE, REPLY
from tests.test_drug_rows import CUT_PAGE, CUT_REPLY, DRAFT_OFF, TYPED, counted, events, mark_of, row, texts, tick
from tests.test_review_marks import page_of, part
from tests.test_review_page import NOTE, engine_with
from tests.test_stop import until
from tests.test_who_check import HeldEngine, press, reviewed, said

OTHER = "another made-up name"


def stop_thread_done(app, consultation_id: int = 1) -> bool:
    """Waits until the Stop thread has finished its last step, the conversion (15.11 ruling 7). The helpers give the
    consultation back as soon as it is final, as the app shows the review page then; the conversion's one write to
    the row comes a moment later, and with no converter in the suite it puts a sentence on the page. A test that
    compares two reads of the page, or runs the conversion itself, waits for that write first."""
    return until(lambda: app.state.parts.consultations.get(consultation_id)["recording_format"] is not None)


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


# ------------------------------------------- the page after a keep, with no load

class Parts(HTMLParser):
    """The page cut at the parts it marks with data-part: the text outside
    them, each part's name with the count of fields a doctor can change in
    it, the fields outside every part, and whether a part stands in a part."""

    VOID = ("input", "br", "hr", "img", "meta", "link")

    def __init__(self, raw: str):
        super().__init__(convert_charrefs=False)
        self.outside, self.fields, self.loose, self.nested, self._depth, self._part = [], {}, [], 0, 0, None
        self.feed(raw)

    def handle_starttag(self, tag, attrs):
        held = dict(attrs)
        field = tag in ("input", "select", "textarea") and held.get("type") != "hidden"
        if self._depth:
            self.nested += "data-part" in held
            self.fields[self._part] += field
            self._depth += tag not in self.VOID
        elif "data-part" in held:
            self._part, self._depth = held["id"], 1
            assert self._part not in self.fields, f"the part {self._part} is named twice"
            self.fields[self._part] = 0
        else:
            self.outside.append(self.get_starttag_text())
            if field:
                self.loose.append(held.get("class"))

    def handle_endtag(self, tag):
        if self._depth:
            self._depth -= 1
        else:
            self.outside.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._depth:
            self.outside.append(data)

    handle_entityref = handle_charref = handle_comment = lambda self, data: self.handle_data(data)


def player_data_of(raw: str) -> dict:
    return json.loads(raw.split('<script id="player-data" type="application/json">')[1].split("</script>")[0])


def outside_the_parts(raw: str) -> str:
    # The stretch of a cleared mark leaves the player data, which stands outside the parts. No press reads a stretch from
    # there: since ruling 29 each button carries its own start and end. So the data is compared without its stretches.
    data = player_data_of(raw)
    plain = raw.replace(json.dumps(data), json.dumps({**data, "stretches": []}))
    assert plain != raw or data["stretches"] == []
    # White space is folded: where a row has gone, the list holds one run of it fewer, which shows nothing.
    return " ".join("".join(Parts(plain).outside).split())


def test_ruling_33_everything_a_keep_changes_on_the_page_lies_inside_the_parts_the_page_marks_for_its_script(tmp_path, clock, machine):
    # After a keep the page is not loaded: the script puts the app's own answer in place, part by part (fresh.js), and must
    # then show what a load would show. So everything a keep can change has to lie inside a marked part. Three cases: new
    # words on the first edit; another mark on the line cleared, its row gone; a line left with no words.
    cleared = {"doubtful": [{"line": 2, "heard": "met for min", "meant": ""}, {"line": 2, "heard": "min twice", "meant": ""},
                            {"line": 2, "heard": "at night", "meant": ""}]}
    for name, page, reply, gone in (("new", PAGE, REPLY, []), ("cleared", PAGE, cleared, ["drug-mark-2"]), ("empty", CUT_PAGE, CUT_REPLY, [])):
        app, client, c = reviewed(tmp_path / name, clock, machine, engine_with(drug_name=[reply]), page=page)
        # Not steady as first written: the first read could come before the Stop thread's conversion step had written its
        # sentence into the row and the second after it, and the two pages then differed outside the marked parts.
        assert stop_thread_done(app)
        before = client.get("/consultations/1").text
        assert tick(client, 1, words=TYPED, press="keep").status_code == 303
        after = client.get("/consultations/1").text
        assert before != after and outside_the_parts(before) == outside_the_parts(after), name
        was, now = Parts(before), Parts(after)
        # Each part is named once and none stands inside another, so a part can be put in place, or left, whole.
        assert was.nested == now.nested == 0 and sorted(set(was.fields) - set(now.fields)) == gone and set(now.fields) <= set(was.fields)
        assert all(after.count(f'id="{part}"') == 1 for part in now.fields)
        # Review point 1c (ruling 12): a box or a choice the doctor can change stands in one part at most, so that a part
        # holding unsaved words is left whole: a row holds its one box, a line its box and its speaker choice, and the
        # note's own boxes stand in no part, so the note is never put in place.
        for part, fields in now.fields.items():
            expected = 1 if part.startswith("drug-mark-") else 2 if part.startswith("line-") else 0
            assert fields == expected, (name, part, fields)
        entries = len(app.state.parts.notes.entries(app.state.parts.notes.current_draft(1)["id"]))
        assert now.loose == ["entry-text"] * entries and entries > 0
        # The parts that hold what the keep changed: the row, the lines of the name, and Draft the note again in both places.
        for part in ("approve-form", "draft-form", "drug-head", "drug-mark-1", "draft-rows-slot", "other-warnings", "line-1"):
            assert part in now.fields, (name, part)
        c.close()


def test_6d2_nothing_of_the_kept_words_is_left_on_the_page(tmp_path, clock, machine):
    # The details, The kept words go: no words can now stand typed and unsaved in a row the doctor has left, so the script
    # that kept them in the browser's store, and what the page told it, are gone. What took their place sends to the app.
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    raw, _ = page_of(client)
    assert "data-kept" not in raw and "data-mark" not in raw and "kept.js" not in raw
    assert client.get("/static/kept.js").status_code == 404
    for script in ("rows.js", "fresh.js"):
        served = client.get(f"/static/{script}")
        assert f'<script src="/static/{script}"></script>' in raw and served.status_code == 200
        assert "sessionStorage" not in served.text and "localStorage" not in served.text
    c.close()


# ------------------------------------------------------ the page keeps its place

def test_ruling_34_a_rows_press_that_asks_to_keep_the_pages_place_is_sent_to_no_anchor_and_one_that_does_not_goes_to_its_row(tmp_path, clock, machine):
    # The room run of 15 Nov 2026: a press on a row came back with that row at the top of the window, past the next row.
    # The page's script keeps the place itself and says so with the press; with no script the press comes back at its row.
    app, client, c = reviewed(tmp_path, clock, machine, engine_with(drug_name=[REPLY]), page=PAGE)
    for fields in ({"words": TYPED, "press": "keep"}, {"words": TYPED, "press": "settle"}, {"press": "open"}, {"words": OTHER, "press": "keep"}):
        asked = tick(client, 1, place="keep", **fields)
        assert asked.status_code == 303 and asked.headers["location"].endswith("/consultations/1"), fields
    assert mark_of(app.state.parts, 1)["standing"] == OTHER                                    # each press still did its work
    for fields in ({"words": TYPED, "press": "keep"}, {"words": TYPED, "press": "settle"}, {"press": "open"}):
        plain = tick(client, 1, **fields)
        assert plain.status_code == 303 and plain.headers["location"].endswith("/consultations/1#drug-mark-1"), fields
    # At its anchor the row stands clear of the app's bar, which stays at the top of the window.
    css = client.get("/static/theme.css").text
    assert "scroll-margin-top" in css.split(".drug-row {")[1].split("}")[0] and "position: sticky; top: 0" in css.split("header.app {")[1].split("}")[0]
    c.close()


def test_ruling_34_the_page_marks_the_presses_that_keep_its_place_and_no_other(tmp_path, clock, machine):
    engine = engine_with(drug_name=[REPLY], label_check=[said("patient", "patient", "doctor")])
    app, client, c = reviewed(tmp_path, clock, machine, engine, page=PAGE)

    def forms(raw: str) -> dict:
        return {action.replace("/consultations/1/", ""): "data-stay" in rest for action, rest in re.findall(r'<form method="post" action="([^"]+)"([^>]*)>', raw)}

    raw = client.get("/consultations/1").text
    assert '<script src="/static/place.js"></script>' in raw and client.get("/static/place.js").status_code == 200
    entry = app.state.parts.notes.entries(app.state.parts.notes.current_draft(1)["id"])[0]["id"]
    before = forms(raw)
    # A row, Save on a line, Swap and Save on a note entry keep the place.
    for kept in ("marks/1", "marks/2", "lines/1", "lines/4", "lines/swap", f"entries/{entry}"):
        assert before[kept] is True, kept
    # Draft the note again, Approve and Refuse bring the page to the note; Check who spoke goes to its own place; Delete asks its question.
    for moved in ("note/approve", "note/refuse", "note/draft", "who-check", "delete"):
        assert before[moved] is False, moved
    # After a check that changed lines, and an edit: Undo on a line and Undo all keep the place; Draft the note again under the rows does not.
    press(app, client)
    assert tick(client, 1, words=TYPED, press="keep").status_code == 303
    after = forms(client.get("/consultations/1").text)
    assert after["lines/1/undo"] is True and after["who-check/undo-all"] is True and after["note/draft"] is False
    assert [action for action, stays in after.items() if stays and not action.startswith(("marks/", "lines/", "entries/", "who-check/undo-all"))] == []
    assert 'id="draft-rows-form" class="draft-rows">' in client.get("/consultations/1").text
    c.close()
