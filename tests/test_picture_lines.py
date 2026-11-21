"""The arrows of the picture show the path chosen (the owner's words at
10:06 and his word A at 10:14 on 20 Nov 2026, by mail 6 of run 9c; a
change to the picture of 15.13, ruling 56). His words, from his room
check: After choosing cloud services, the arrows of the diagram was not
updated to represents the data path. ... Think visually representing the
selected options. Until then an arrow was a small sign in each gap
between two columns, tilted where a step went to the cloud row, and with
the tick for better accuracy none led to the Speechmatics box.

Ruled: every arrow is a line from box to box with a head at its end,
drawn for the path chosen. Solid lines are what happens during the
consultation: Microphone, the transcription box chosen, the language
model box chosen, Consultation. Dashed lines are what happens after Stop
where the tick for better accuracy is set: one from the Microphone to
the Speechmatics box, one from the Speechmatics box to the language
model box chosen. A box that is not on the path has no line. Under the
picture a key, Cowork's draft: a solid sample with During the
consultation, a dashed sample with After Stop, the dashed part only
where a dashed line is drawn.

The suite has no browser: these tests pin which lines the picture holds
and what the page and the style sheet give the browser to draw them
from. Where each line lands on the screen is measured in the look of
mail 6. Made engines, made doors, a made store."""

from __future__ import annotations

import re

import pytest

from openconsult import words
from openconsult.settings.path import CLAUDE, SPEECHMATICS, ChosenPath
from openconsult.web import panel
from tests.test_panel import BOTH_KEYS, PATHS, made

SOLID, DASHED = "during", "after_stop"
MIC, HERE_SPEECH, SM, HERE_MODEL, CL, CONSULT = "microphone", "speech_local", "speechmatics", "model_local", "claude", "consultation"
# For each of the six paths: every line, from which box to which, solid or dashed.
LINES = {
    "L": [(MIC, HERE_SPEECH, SOLID), (HERE_SPEECH, HERE_MODEL, SOLID), (HERE_MODEL, CONSULT, SOLID)],
    "R": [(MIC, HERE_SPEECH, SOLID), (HERE_SPEECH, HERE_MODEL, SOLID), (HERE_MODEL, CONSULT, SOLID),
          (MIC, SM, DASHED), (SM, HERE_MODEL, DASHED)],
    "S": [(MIC, SM, SOLID), (SM, HERE_MODEL, SOLID), (HERE_MODEL, CONSULT, SOLID)],
    "C": [(MIC, HERE_SPEECH, SOLID), (HERE_SPEECH, CL, SOLID), (CL, CONSULT, SOLID)],
    "CR": [(MIC, HERE_SPEECH, SOLID), (HERE_SPEECH, CL, SOLID), (CL, CONSULT, SOLID), (MIC, SM, DASHED), (SM, CL, DASHED)],
    "CS": [(MIC, SM, SOLID), (SM, CL, SOLID), (CL, CONSULT, SOLID)],
}
ALL_BOXES = {MIC, HERE_SPEECH, SM, HERE_MODEL, CL, CONSULT}
ARROW = re.compile(r'<span class="panel-arrow ([^"]*)" data-from="([a-z_]+)" data-to="([a-z_]+)" data-kind="([a-z_]+)" aria-hidden="true">(.*?)</span>', re.S)


def picture_of(client, address="/settings") -> str:
    return client.get(address).text.split('id="control-panel"', 1)[1].split('<table class="plain facts">', 1)[0]


def style_of(client) -> str:
    return client.get("/static/theme.css").text


@pytest.mark.parametrize("name", list(LINES))
def test_his_ruling_of_20_nov_for_each_path_the_picture_holds_its_lines_from_box_to_box_solid_or_dashed_and_a_box_off_the_path_has_none(tmp_path, clock, name):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    made_panel = panel.build(app.state.parts)
    assert [(a.start, a.end, a.kind) for a in made_panel.arrows] == LINES[name]
    # On the page: one drawn line for each, naming its two boxes and its kind, and no other.
    picture = picture_of(client)
    drawn = ARROW.findall(picture)
    assert [(start, end, kind) for _, start, end, kind, _ in drawn] == LINES[name] and picture.count("panel-arrow ") == len(LINES[name])
    # A box that is not on the path has no line: none leaves it and none ends at it.
    with_a_line = {box for start, end, _ in LINES[name] for box in (start, end)}
    off = ALL_BOXES - with_a_line
    assert off == {"L": {SM, CL}, "R": {CL}, "S": {HERE_SPEECH, CL}, "C": {SM, HERE_MODEL}, "CR": {HERE_MODEL}, "CS": {HERE_SPEECH, HERE_MODEL}}[name]
    for box in off:
        assert f'data-from="{box}"' not in picture and f'data-to="{box}"' not in picture
        assert f"from-{box} " not in picture and f"to-{box}\"" not in picture
    # Every box on the doctor's chosen path is joined: the solid lines run through exactly the boxes marked on the path.
    solid = {box for start, end, kind in LINES[name] if kind == SOLID for box in (start, end)}
    assert solid == {box.name for box in made_panel.boxes if box.on_path}
    # The solid lines are one path from the microphone to the consultation, each beginning where the one before ended.
    path = [line for line in LINES[name] if line[2] == SOLID]
    assert path[0][0] == MIC and path[-1][1] == CONSULT and all(a[1] == b[0] for a, b in zip(path, path[1:]))


@pytest.mark.parametrize("name", ["R", "CR"])
def test_his_ruling_of_20_nov_the_dashed_lines_are_the_recording_from_the_microphone_and_the_transcript_to_the_language_model_chosen(tmp_path, clock, name):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    made_panel = panel.build(app.state.parts)
    dashed = [(a.start, a.end) for a in made_panel.arrows if a.kind == DASHED]
    chosen_model = next(box.name for box in made_panel.boxes if box.column == "language_model" and box.chosen)
    # The recording goes from the microphone, not from the transcript made here; the note is drafted by the model chosen.
    assert dashed == [(MIC, SM), (SM, chosen_model)] and made_panel.after_stop
    assert made_panel.box(SM).also == "Used after Stop" and not made_panel.box(SM).on_path
    assert not any(a.start == HERE_SPEECH and a.end == SM for a in made_panel.arrows)


def test_15_9_ruling_36_the_tick_with_speechmatics_live_draws_no_dashed_line_because_nothing_is_sent_a_second_time(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=ChosenPath(CLAUDE, SPEECHMATICS, True))
    made_panel = panel.build(app.state.parts)
    assert [(a.start, a.end, a.kind) for a in made_panel.arrows] == LINES["CS"] and not made_panel.after_stop
    assert "after_stop" not in picture_of(client)


@pytest.mark.parametrize("name", list(LINES))
def test_his_ruling_of_20_nov_the_key_under_the_picture_and_its_dashed_part_only_where_a_dashed_line_is_drawn(tmp_path, clock, name):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    # Cowork's draft, by mail 6.
    assert words.PANEL_KEY == {"during": "During the consultation", "after_stop": "After Stop"}
    picture = picture_of(client)
    key = picture.split('<p class="panel-key" id="panel-key" aria-hidden="true">', 1)[1].split("</p>", 1)[0]
    parts = re.findall(r'<span class="key-part ([a-z_]+)" id="panel-key-([a-z_]+)"><svg [^>]*>.*?</svg> ([^<]+)</span>', key)
    has_dashed = name in ("R", "CR")
    assert parts == [("during", "during", "During the consultation")] + ([("after_stop", "after_stop", "After Stop")] if has_dashed else [])
    assert ("After Stop</span>" in picture) is has_dashed and ("has-after-stop" in picture) is has_dashed
    # Under the picture: after the boxes and the lines, before the small table.
    assert picture.index('id="box-consultation"') < picture.index("panel-arrow ") < picture.index('id="panel-key"')
    # Each part holds a sample of its line, drawn as the lines are.
    assert key.count("<line ") == len(parts) == key.count('class="arrow-head"')


def test_his_ruling_of_20_nov_solid_and_dashed_are_told_by_the_line_itself_and_the_key_never_by_colour(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS["CR"])
    style = style_of(client)
    # One rule makes a line dashed, for the lines of after Stop and the key's sample of them, and for nothing else.
    assert ".panel-arrow.after_stop line, .panel-key .after_stop line { stroke-dasharray: 4 6; }" in style
    assert style.count("stroke-dasharray") == 1
    # Every line and every head is drawn in the one ink of the arrow: no rule gives a kind a colour of its own.
    assert ".panel-arrow line, .panel-key line, .arrow-head { fill: none; stroke: currentColor;" in style
    for rule in re.findall(r"[^{}]*\{[^{}]*\}", style):
        selector, body = rule.split("{", 1)
        if "after_stop" in selector or ".during" in selector:
            assert "color" not in body and "stroke:" not in body and "opacity" not in body, rule
    picture = picture_of(client)
    assert "stroke=" not in picture.split("panel-arrow ", 1)[1] and 'style="' not in picture
    # Drawn for the eye alone: every line and the key hidden from a reader; the lines above the picture say it in words.
    drawn = ARROW.findall(picture)
    assert len(drawn) == 5 and picture.count('aria-hidden="true"><span class="key-part') == 1
    # Restated on the owner's word B of 21 Nov 2026 (15.13, ruling 76; step 9f): on this path the recording and the
    # language model are two things in the cloud, each now with a line of its own. OLD: "In the cloud: After Stop, the
    # recording goes to Speechmatics once." in the lines above the picture, with a capital. NEW: with a small letter.
    assert "In the cloud: after Stop, the recording goes to Speechmatics once." in picture.split('id="panel-path"', 1)[1].split("</div>", 1)[0]
    assert "<script" not in picture                                                     # the page draws them with no script


@pytest.mark.parametrize("name", list(LINES))
def test_his_ruling_of_20_nov_side_by_side_each_line_runs_in_the_gutter_between_its_two_columns_and_crosses_no_box(tmp_path, clock, name):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS[name])
    made_panel = panel.build(app.state.parts)
    style = style_of(client)
    columns = list(words.PANEL_COLUMNS)
    # The boxes stand in the grid's columns 1, 3, 5 and 7 and the lines in 2, 4 and 6: a line is never in a box's column.
    assert ".panel-grid .col-1 { grid-column: 1; } .panel-grid .col-2 { grid-column: 3; } .panel-grid .col-3 { grid-column: 5; } .panel-grid .col-4 { grid-column: 7; }" in style
    assert ".panel-arrow.gutter-1 { grid-column: 2; } .panel-arrow.gutter-2 { grid-column: 4; } .panel-arrow.gutter-3 { grid-column: 6; }" in style
    in_gutter = {}
    for arrow in made_panel.arrows:
        start, end = made_panel.box(arrow.start), made_panel.box(arrow.end)
        # From a box to a box of the next column, through the gutter between the two.
        assert columns.index(end.column) == columns.index(start.column) + 1 == arrow.gutter
        assert (arrow.from_row, arrow.to_row) == (start.row, end.row)
        assert arrow.shape == ("straight" if start.row == end.row else "down" if start.row < end.row else "up")
        in_gutter.setdefault(arrow.gutter, []).append(arrow)
    # Where two lines share a gutter they are one solid and one dashed, at two heights, and at most one of them turns a
    # corner: so they never run in each other and never cross.
    for shared in in_gutter.values():
        assert len(shared) <= 2
        if len(shared) == 2:
            assert {a.kind for a in shared} == {SOLID, DASHED} and sum(a.shape != "straight" for a in shared) == 1
    drawn = {(start, end): (classes.split(), body) for classes, start, end, kind, body in ARROW.findall(picture_of(client))}
    for arrow in made_panel.arrows:
        classes, body = drawn[(arrow.start, arrow.end)]
        assert {arrow.kind, arrow.shape, f"gutter-{arrow.gutter}", f"rows-{arrow.from_row}-{arrow.to_row}"} <= set(classes)
        wide = body.split('<svg class="wide" focusable="false">', 1)[1].split('<svg class="narrow"', 1)[0]
        height = "18" if arrow.kind == SOLID else "40"                                  # the solid above the dashed, in every gutter
        assert f'y1="{height}"' in wide and wide.count('class="arrow-head"') == 1       # one head, at its end
        assert wide.count("<line ") == {"straight": 1, "down": 4, "up": 4}[arrow.shape]


def test_his_ruling_of_20_nov_in_a_narrow_window_the_boxes_stack_in_the_order_of_the_path_and_every_line_runs_down_a_rail_beside_them(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, path=PATHS["CR"])
    style = style_of(client)
    narrow = style.split("@media (max-width: 760px) {", 1)[1].split("\n}", 1)[0]
    # Each heading and each box has a row of its own, in the order of the path: this computer before its cloud service.
    rows = {(int(col), int(row or 0)): int(n) for col, row, n in re.findall(r"\.panel-grid \.box\.col-(\d)(?:\.row-(\d))? \{ grid-row: (\d+); \}", narrow)}
    heads = [int(n) for n in re.findall(r"\.panel-grid \.panel-head\.col-\d \{ grid-row: (\d+);", narrow)]
    assert rows == {(1, 0): 2, (2, 0): 4, (2, 1): 5, (3, 0): 7, (3, 1): 8, (4, 0): 10} and heads == [1, 3, 6, 9]
    assert ".panel-grid .panel-head, .panel-grid details.box { grid-column: 2; }" in narrow
    # The rails: the solid lines down the left of the boxes, the dashed pair of after Stop down the right, so the two are
    # told apart and never cross; the right rail is there only where a dashed line is drawn.
    assert ".panel-grid { grid-template-columns: 1.6rem minmax(0, 1fr); }" in narrow
    assert ".panel-grid.has-after-stop { grid-template-columns: 1.6rem minmax(0, 1fr) 1.6rem; }" in narrow
    assert ".panel-grid .panel-arrow.during { grid-column: 1; } .panel-grid .panel-arrow.after_stop { grid-column: 3; }" in narrow
    assert ".panel-arrow > svg.wide { display: none; } .panel-arrow > svg.narrow { display: block; }" in narrow
    # A line begins at the row of the box it leaves and ends where the row of its next box begins; for every path it
    # runs downward, which is the order of the path.
    begins = {box: int(n) for box, n in re.findall(r"\.panel-arrow\.from-([a-z_]+) \{ grid-row-start: (\d+); \}", narrow)}
    ends = {box: int(n) for box, n in re.findall(r"\.panel-arrow\.to-([a-z_]+) \{ grid-row-end: (\d+); \}", narrow)}
    made_panel = panel.build(app.state.parts)
    columns = list(words.PANEL_COLUMNS)
    row_of = {box.name: rows[(columns.index(box.column) + 1, box.row)] for box in made_panel.boxes}
    assert begins == {name: row for name, row in row_of.items() if name != CONSULT}
    assert ends == {name: row for name, row in row_of.items() if name != MIC}
    for lines in LINES.values():
        assert all(begins[start] < ends[end] for start, end, _ in lines)
    # Each drawing for the stack: out of its box, down the rail, into the next box with one head; the dashed mirrored.
    drawn = {(start, end): body.split('<svg class="narrow" focusable="false">', 1)[1] for _, start, end, _, body in ARROW.findall(picture_of(client))}
    assert len(drawn) == 5
    for (start, end), body in drawn.items():
        dashed = (start, end) in ((MIC, SM), (SM, CL))
        assert body.count("<line ") == 4 and body.count('class="arrow-head"') == 1
        assert ('<line x1="0" y1="34" x2="16" y2="34"/>' in body) is dashed and ('<line x1="100%" y1="34" x2="9" y2="34"/>' in body) is not dashed


def test_7_1_and_his_ruling_of_20_nov_the_same_lines_at_step_2_of_the_first_run(tmp_path, clock):
    app, client, *_ = made(tmp_path, clock, held=BOTH_KEYS, user=False)
    client.post("/first-run/statement", data={"agree": "yes"})
    picture = picture_of(client, "/first-run")
    # A suitable card begins with both on this computer: the three solid lines, and the solid part of the key alone.
    assert [(start, end, kind) for _, start, end, kind, _ in ARROW.findall(picture)] == LINES["L"]
    assert "During the consultation</span>" in picture and "After Stop</span>" not in picture
