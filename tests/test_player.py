"""The player and the recording route (spec 8.8; D51; 15.6 ruling 6;
R18; V1_LESSONS 5.2) and the printed page (ruling 4; the plan review,
point 3). Made sound; made-up doors."""

import json

from openconsult import words
from openconsult.web.review import STRIP_COLUMNS, player_data, strip_of
from tests.conftest import ORIGIN, browser, changes, snapshot, text_of
from tests.test_review_page import reviewed


def test_8_8_D51_15_6_ruling_6_the_recording_is_served_to_the_logged_in_user_on_this_computer_only(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    folder = tmp_path / "recordings"
    before = snapshot(folder)
    played = client.get("/consultations/1/recording")
    assert played.status_code == 200 and played.headers["content-type"].startswith("audio/wav")
    assert played.content == (folder / "consultation_1.wav").read_bytes() and played.content[:4] == b"RIFF"
    # No login: to the login page. From another computer: refused, with or without the cookie.
    assert browser(app).get("/consultations/1/recording").status_code == 303
    elsewhere = browser(app, address="192.0.2.9")
    elsewhere.cookies = client.cookies
    assert elsewhere.get("/consultations/1/recording").status_code == 403
    assert changes(before, snapshot(folder)) == []                  # read, never written (R18)
    assert client.get("/consultations/9/recording").status_code == 303   # no such consultation: back to the home page


def test_8_8_the_players_data_holds_each_lines_start_the_loudness_strip_and_each_warnings_stretch(tmp_path):
    (tmp_path / "recordings").mkdir()
    (tmp_path / "recordings" / "consultation_3.wav").write_bytes(b"RIFF" + b"\\0" * 40)
    row = {"recording_file": "consultation_3.wav", "loudness": json.dumps([-20.0, None, -35.0, -18.0]), "started_at": "2026-10-20T10:00:00"}
    lines = [{"n": 1, "start_s": 0.0, "end_s": 0.2, "label": "doctor"}, {"n": 2, "start_s": 0.25, "end_s": 0.4, "label": "patient"}]
    warnings = [{"kind": "uncovered_speech", "start_s": 0.1, "end_s": 0.3, "line_n": None},
                {"kind": "no_speaker", "start_s": None, "end_s": None, "line_n": 2},
                {"kind": "confidence_not_measured", "start_s": None, "end_s": None, "line_n": None}]
    data = player_data(row, lines, warnings, tmp_path)
    assert data["available"] and data["length_s"] == 0.4 and data["window_s"] == 0.1
    assert data["lines"] == [{"n": 1, "start_s": 0.0, "end_s": 0.2}, {"n": 2, "start_s": 0.25, "end_s": 0.4}]
    assert data["strip"] == [-20.0, None, -35.0, -18.0]                       # fewer windows than columns: one each
    assert data["stretches"] == [{"kind": "uncovered_speech", "start_s": 0.1, "end_s": 0.3}]   # a warning with no place has no press
    # The strip folds many windows into columns, each the loudest, None where every window is silence.
    windows = [None, None, -50.0, -10.0] * 300
    folded = strip_of(windows)
    assert len(folded) == STRIP_COLUMNS and folded[:2] == [-50.0, -10.0] and set(folded) == {-50.0, -10.0}   # three windows a column
    assert strip_of([None, None]) == [None, None] and strip_of([]) == []
    # The file not there: not available.
    gone = player_data({**row, "recording_file": "consultation_4.wav"}, lines, warnings, tmp_path)
    assert not gone["available"] and gone["lines"] == data["lines"]


def test_8_8_the_page_has_the_player_the_presses_and_the_strip_and_when_the_recording_has_gone_says_so_with_the_date(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    assert '<audio id="audio" controls' in raw and 'src="/consultations/1/recording"' in raw
    assert '<canvas id="strip"' in raw and 'id="player-data"' in raw and '/static/player.js' in raw
    assert raw.count('class="play-line cite" data-line="') >= 3          # each line, and the no-speaker warning
    assert words.PLAY_FROM_LINE in raw and client.get("/static/player.js").status_code == 200
    data = json.loads(raw.split('<script id="player-data" type="application/json">')[1].split("</script>")[0])
    assert data["available"] and [line["n"] for line in data["lines"]] == [1, 2] and data["length_s"] == 2.0
    assert words.AUDIO_GONE.split("{")[0] not in text_of(client.get("/consultations/1"))
    # The audio has gone (stage 7's retention): the line with the date stands in the player's place, and no press plays.
    (tmp_path / "recordings" / "consultation_1.wav").unlink()
    raw = client.get("/consultations/1").text
    page = text_of(client.get("/consultations/1"))
    assert words.AUDIO_GONE.format(date="4 Oct 2026") in page and 'id="audio-gone"' in raw
    assert "<audio" not in raw and "play-line" not in raw and "play-stretch" not in raw
    assert client.get("/consultations/1/recording").status_code == 404


def test_ruling_4_the_printed_page_is_the_note_alone(tmp_path, clock, machine):
    app, client, c = reviewed(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    assert '<link rel="stylesheet" href="/static/print.css" media="print">' in raw
    sheet = client.get("/static/print.css")
    assert sheet.status_code == 200
    hidden = sheet.text.split("{ display: none !important; }")[0]
    for selector in (".differentials", "#controls", "#warnings", "#transcript", "#model-line", ".entry-form", "button.cite", ".uncited", "header.app", "footer.disclaimer"):
        assert selector in hidden, selector
    assert ".print-only { display: inline !important; }" in sheet.text
    # The template puts those classes and ids on the parts, and the note, the name and the date are kept.
    for mark in ('id="differentials"', 'id="controls"', 'id="warnings"', 'id="transcript"', 'id="model-line"', 'class="entry-form no-print"',
                 'class="entry-text print-only"', 'class="statement print-keep"', 'class="pane note print-keep"'):
        assert mark in raw, mark
