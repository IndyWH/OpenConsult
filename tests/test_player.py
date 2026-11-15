"""The player and the recording route (spec 8.8; D51; 15.6 ruling 6;
R18; V1_LESSONS 5.2) and the printed page (ruling 4; the plan review,
point 3). Made sound; made-up doors."""

import json
import re

from openconsult import words
from openconsult.consult import opus
from openconsult.web import review
from openconsult.web.review import STRIP_COLUMNS, player_data, strip_of
from tests.conftest import ORIGIN, browser, changes, log_in, snapshot, text_of
from tests.fakes import MadeUpConverter
from tests.test_review_page import reviewed
from tests.test_row_keep import stop_thread_done


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
    # The address that gives the file's name (6d2, fault one) is guarded the same, and gives nothing for a consultation that is not there.
    assert browser(app).get("/consultations/1/recording/file").status_code == 303
    assert elsewhere.get("/consultations/1/recording/file").status_code == 403
    missing = client.get("/consultations/9/recording/file")
    assert missing.status_code == 404 and missing.text == ""
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
    assert words.PLAY_LINE in raw and client.get("/static/player.js").status_code == 200
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
    assert re.search(r'<link rel="stylesheet" href="/static/print\.css\?v=[0-9a-f]{12}" media="print">', raw)    # with the mark of its file (6d2)
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


def test_rulings_29_38_every_press_that_plays_a_line_carries_a_start_one_second_before_it_and_its_end_to_stop_at_and_the_alarms_press_no_end(tmp_path, clock, machine):
    # As built for 8.8 a pressed line played to the end of the recording, and the pause was far up the page (15.10 ruling 29).
    # The app gives each press its stretch on the button itself; the script plays it and stops. The alarm's press plays on.
    # Since ruling 38 the stretch starts one second before the line, never before the recording's start; its end is the line's.
    app, client, c = reviewed(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    data = json.loads(raw.split('<script id="player-data" type="application/json">')[1].split("</script>")[0])
    times = {line["n"]: (line["start_s"], line["end_s"]) for line in data["lines"]}
    presses = re.findall(r'<button type="button" class="play-line cite" data-line="(\d+)" data-start="([^"]*)" data-end="([^"]*)"', raw)
    assert len(presses) == raw.count('class="play-line') >= 3                    # on the transcript and in the warnings: none without its end
    for n, start, end in presses:
        assert (float(start), float(end)) == (max(0.0, times[int(n)][0] - 1.0), times[int(n)][1]) and float(end) > float(start)
    assert {int(n) for n, _, _ in presses} == set(times)
    in_warnings = raw.split('id="warnings"')[1].split('id="transcript"')[0]
    assert 'class="play-line cite"' in in_warnings and ">" + words.PLAY_LINE + "</button>" in in_warnings
    assert "Play from here" not in text_of(client.get("/consultations/1")) and "Play from here" not in raw     # the name that became untrue
    assert raw.count(f'aria-label="{words.PLAY_LINE}"') == len(times)
    # The alarm's Play from where it fired carries a start and no end; a warning's stretch keeps its own end.
    alarm = re.findall(r'<button type="button" class="play-at"([^>]*)>', raw)
    assert alarm and all("data-start=" in a and "data-end" not in a for a in alarm) and words.PLAY_FROM_ALARM in raw
    c.close()


def test_6d2_fault_one_the_page_names_the_file_its_player_was_shown_with_and_once_converted_the_addresses_give_the_ogg_and_its_name(tmp_path, clock, machine):
    # The room run of 15 Nov 2026: the review page was shown 3 s before the WAV was converted and removed. The player held the
    # head of the WAV, the same address then gave the Ogg, and the first press of play was silent until the page was loaded
    # again. The page now tells its script which file it was shown with, and one address gives the file's name as it is now,
    # so that the script can take the recording afresh. What the script then does is seen in a browser, not asserted here.
    app, client, c = reviewed(tmp_path, clock, machine)

    def shown_with():
        raw = client.get("/consultations/1").text
        return json.loads(raw.split('<script id="player-data" type="application/json">')[1].split("</script>")[0])["file"]

    # The Stop thread's own conversion step, which finds no converter in the suite, has ended: the test then runs the
    # step itself with a made converter, and the two must not meet.
    assert stop_thread_done(app)
    assert shown_with() == "consultation_1.wav"
    named = client.get("/consultations/1/recording/file")
    assert named.status_code == 200 and named.text == "consultation_1.wav" and named.headers["content-type"].startswith("text/plain")
    # Stop's last job, run as it runs in the room: after the page has been shown (15.11 ruling 7). Nothing in it changes.
    c.converter = MadeUpConverter()
    assert opus.convert_consultation(c).ok and not (tmp_path / "recordings" / "consultation_1.wav").exists()
    played = client.get("/consultations/1/recording")
    assert played.status_code == 200 and played.headers["content-type"].startswith("audio/ogg") and played.content == b"OggS made up"
    named = client.get("/consultations/1/recording/file")
    assert named.status_code == 200 and named.text == "consultation_1.ogg"                    # nothing but the name
    # The address the script then gives the player, the name as a query the route does not read: the same Ogg.
    assert client.get("/consultations/1/recording?file=consultation_1.ogg").content == played.content
    assert shown_with() == "consultation_1.ogg"                                               # a page loaded again names the Ogg
    # The script's question is the page's own and is not use (15.6): asked with ?quiet it does not put off the lock.
    clock.advance(minutes=29)
    assert client.get("/consultations/1/recording/file?quiet").text == "consultation_1.ogg"
    clock.advance(minutes=2)
    assert client.get("/consultations/1?quiet").status_code == 303 and log_in(client).status_code == 303
    # The recording gone (retention): no name, and the page names no file.
    (tmp_path / "recordings" / "consultation_1.ogg").unlink()
    gone = client.get("/consultations/1/recording/file")
    assert gone.status_code == 404 and gone.text == "" and shown_with() is None
    c.close()


def test_ruling_38_a_press_that_plays_a_line_or_a_row_starts_one_second_before_the_line_never_below_zero_and_ends_where_it_ended(tmp_path, clock, machine):
    # The room check of 15 Nov 2026: the sound of a row began late; at one row the drug's name was gone and the sound began
    # at the dose, and a row of 0.24 s gave no sound. So the app gives each press on a line or a row a start one second
    # before the line's own, not below zero, and leaves the end. The player's data keeps the true times; the alarm's press
    # (pinned in tests/test_alarms.py), a warning's own stretch and the strip are not changed.
    from tests.test_live import live_seg
    from tests.test_review_page import engine_with
    from tests.test_who_check import reviewed as reviewed_with
    page = [live_seg(1, 0.4, 0.9, "What do you take", "S1"), live_seg(2, 1.0, 1.3, "for the sugar?", "S1"),
            live_seg(3, 1.5, 1.8, "I take met for min twice a day. " + "word " * 60, "S2"), live_seg(4, 1.85, 2.0, "Yes.", None)]
    reply = {"doubtful": [{"line": 2, "heard": "met for min", "meant": "a made-up drug"}, {"line": 1, "heard": "take for", "meant": ""}]}
    app, client, c = reviewed_with(tmp_path, clock, machine, engine_with(drug_name=[reply]), page=page)
    assert stop_thread_done(app)
    raw = client.get("/consultations/1").text
    data = json.loads(raw.split('<script id="player-data" type="application/json">')[1].split("</script>")[0])
    # The true times stay in the player's data: the line marked while it plays is the line that is sounding.
    assert [(line["n"], line["start_s"], line["end_s"]) for line in data["lines"]] == [(1, 0.4, 0.9), (2, 1.0, 1.3), (3, 1.5, 1.8), (4, 1.85, 2.0)]
    assert {"kind": "drug_mark", "start_s": 1.5, "end_s": 1.8} in data["stretches"] and {"kind": "drug_mark", "start_s": 0.4, "end_s": 1.3} in data["stretches"]
    # A line's press, on the transcript: one second early, not below zero; the end as it was.
    transcript = raw.split('id="final-transcript"')[1]
    presses = re.findall(r'class="play-line cite" data-line="(\d+)" data-start="([^"]*)" data-end="([^"]*)"', transcript)
    assert [(int(n), float(start), float(end)) for n, start, end in presses] == [(1, 0.0, 0.9), (2, 0.0, 1.3), (3, 0.5, 1.8), (4, 0.85, 2.0)]
    # The same press in the warnings: line 4 has no speaker, and its warning plays it.
    warnings = raw.split('id="warnings"')[1].split('id="transcript"')[0]
    assert 'class="play-line cite" data-line="4" data-start="0.85" data-end="2.0"' in warnings
    # A row's press: from one second before the first line the name was heard on, to the end of the last.
    rows = re.findall(r'id="drug-mark-(\d+)".*?class="play-stretch row-play" data-start="([^"]*)" data-end="([^"]*)"', warnings, flags=re.S)
    assert [(int(m), float(start), float(end)) for m, start, end in rows] == [(2, 0.0, 1.3), (1, 0.5, 1.8)]
    # The line itself still says where it truly starts, and the alarm's press carries a start and no end.
    assert 'id="line-3" data-start="1.5" data-end="1.8"' in raw
    assert review.press_start(None) is None and review.press_start(0.99) == 0.0 and review.press_start(61.37) == 60.37
    assert review.PLAY_LEAD_S == 1.0
    c.close()


# ------------------------------------- what counts as use (15.10 ruling 41)

def test_ruling_41_a_request_for_the_recording_or_for_its_files_name_is_never_use_whatever_its_address_says(tmp_path, clock, machine):
    # Found by the mend run of step 6d and older than it: the review page fetches the recording by itself when it is shown,
    # the app counted that fetch as use, and so after a line had been played the lock could fail to fall: a consultation
    # left on a screen stayed on the screen. The recording and the question for its file are now never use.
    app, client, c = reviewed(tmp_path, clock, machine)
    assert stop_thread_done(app)
    name = app.state.parts.consultations.get(1)["recording_file"]
    asked = (("/consultations/1/recording", {}), (f"/consultations/1/recording?file={name}", {}), ("/consultations/1/recording", {"Range": "bytes=0-99"}),
             ("/consultations/1/recording/file", {}), ("/consultations/1/recording/file?quiet", {}))
    for address, headers in asked:
        assert log_in(client).status_code == 303
        clock.advance(minutes=29)
        assert client.get(address, headers=headers).status_code in (200, 206), address      # the login is live, and is not touched
        clock.advance(minutes=2)
        answer = client.get("/consultations/1")
        assert answer.status_code == 303 and "/login" in answer.headers["location"], address  # 31 minutes with no use: the lock has fallen
    # Set beside it, a request that is use: the page itself, asked for by the doctor.
    assert log_in(client).status_code == 303
    clock.advance(minutes=29)
    assert client.get("/consultations/1").status_code == 200
    clock.advance(minutes=2)
    assert client.get("/consultations/1").status_code == 200
    c.close()


def test_ruling_41_the_page_tells_its_script_that_every_press_is_use_and_the_app_answers_a_tell_and_the_copy_with_the_seconds_left(tmp_path, clock, machine):
    # The plan review of 6e, point 4, from the words of the ruling: your last press or keystroke. The review page is marked
    # so that its script tells the app at a press anywhere on it, as at typing; the new-patient form is not.
    app, client, c = reviewed(tmp_path, clock, machine)
    raw = client.get("/consultations/1").text
    assert re.search(r'<div id="review" data-use data-seconds-left="\d+" data-path="/consultations/1" data-consultation="1" data-presses>', raw)
    form = client.get("/patients/new").text
    assert "data-use" in form and "data-presses" not in form
    # A tell is use and gives the seconds left, from which the page's own count runs.
    clock.advance(minutes=20)
    assert client.post("/use").json() == {"seconds_left": 1800}
    # The copy of the note is use, as built; the page's script then tells, and the answer is the same count as the app's.
    clock.advance(minutes=20)
    assert client.get("/consultations/1/note.txt").status_code == 200
    clock.advance(minutes=20)
    assert client.post("/use").json() == {"seconds_left": 1800}
    clock.advance(minutes=31)
    assert client.get("/consultations/1?quiet").status_code == 303
    c.close()
