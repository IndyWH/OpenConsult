"""The cloud mark's third line on the review page (spec 15.13, ruling 52;
Cowork's review of the plan of run 9c, point e). After Stop the
recording went to Speechmatics. stands there whenever the request that
carried the recording was made and the record cannot show that nothing
left this computer: any answer of the service, a refusal too, and a
failure that may have come after the connection was open. It is left
out only where no connection to the service was opened at all, or the
request was never made. The Start screen and the live page keep goes.
A made upload service inside the suite; nothing here opens a connection."""

from __future__ import annotations

import errno
import socket
import ssl
import urllib.error

import pytest

from openconsult import schema, words
from openconsult.consult.consultations import Consultations
from openconsult.consult.live import FINAL
from openconsult.db import open_database
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER, ChosenPath
from openconsult.settings.statement import mark_lines, review_mark_lines
from openconsult.speech import upload
from openconsult.speech.upload import Answer
from openconsult.web.live import capture_from
from tests.conftest import text_of
from tests.test_cloud_mark import mark_of
from tests.test_recording_after_stop import LongPage, TICKED, consult, ticked_app
from tests.test_review_page import CAPTURE, LOUD
from tests.test_start import TICKS
from tests.test_stop import until

GOES, WENT = "After Stop the recording goes to Speechmatics.", "After Stop the recording went to Speechmatics."
WORDS = "Words go to Claude."


class NeverConnected(LongPage):
    """The made service not reached at all: the request that carries the
    recording fails before any connection is open."""

    def __call__(self, method, url, headers, body):
        self.requests.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        return Answer(0, b"", "URLError", never_connected=True)


@pytest.mark.parametrize("failure, shows", [
    (socket.gaierror(-2, "made up: name not found"), True),
    (ConnectionRefusedError(errno.ECONNREFUSED, "made up"), True),
    (OSError(errno.ENETUNREACH, "made up: no route"), True),
    (OSError(errno.EHOSTUNREACH, "made up: no route"), True),
    (TimeoutError("made up: it may have come after the connection was open"), False),
    (ConnectionResetError(errno.ECONNRESET, "made up"), False),
    (BrokenPipeError(errno.EPIPE, "made up"), False),
    (ssl.SSLError("made up"), False),
])
def test_15_13_ruling_52_only_a_failure_before_any_connection_shows_that_nothing_left(failure, shows):
    assert upload.never_connected(failure) is shows
    assert upload.never_connected(urllib.error.URLError(failure)) is shows                 # the same, as the library wraps it


@pytest.mark.parametrize("sent, request_was", [
    ([], "not_made"),
    ([{"method": "POST", "status": 0, "never_connected": True}], "never_connected"),
    ([{"method": "POST", "status": 0}], "made"),                                           # no answer, after the connection may have opened
    ([{"method": "POST", "status": 401}], "made"),                                         # a refusal is an answer: the bytes travelled
    ([{"method": "POST", "status": 201}, {"method": "GET", "status": 0, "never_connected": True}], "made"),   # the first request carries the recording
])
def test_15_13_ruling_52_what_the_record_can_show_of_the_request_that_carried_the_recording(sent, request_was):
    assert upload.request_made(sent) == request_was


@pytest.mark.parametrize("path, request_was, lines", [
    (TICKED, "made", (WENT,)),
    (TICKED, "never_connected", ()),
    (TICKED, "not_made", ()),
    (ChosenPath(CLAUDE, THIS_COMPUTER, True), "made", (WORDS, WENT)),
    (ChosenPath(CLAUDE, THIS_COMPUTER, True), "never_connected", (WORDS,)),
    (ChosenPath(CLAUDE, SPEECHMATICS), None, ("Sound goes to Speechmatics as it is spoken.", WORDS)),       # no press: no third line
    (ChosenPath(CLAUDE, SPEECHMATICS), "made", ("Sound goes to Speechmatics as it is spoken.", WORDS, WENT)),   # the one press
])
def test_15_13_ruling_52_the_marks_lines_on_the_review_page_for_each_case(path, request_was, lines):
    assert review_mark_lines(path, request_was) == lines
    assert GOES not in review_mark_lines(path, request_was)                                # goes is never said on the review page


CASES = [
    ("", "made", True),                    # taken by the service and named
    ("submit 401", "made", True),          # refused by the service: the request was made and answered
    ("submit 0", "made", True),            # no answer, and nothing shows that no connection was opened
    ("rejected", "made", True),            # taken, then ended as rejected
]


@pytest.mark.parametrize("mode, request_was, went", CASES)
def test_15_13_ruling_52_the_review_page_says_went_whenever_the_request_was_made_and_nothing_shows_that_nothing_left(tmp_path, clock, server, mode, request_was, went):
    made = LongPage(mode)
    app, client, local = ticked_app(tmp_path, clock, server, made)
    start = mark_of(client.get("/consultations/start/1").text)
    assert start is not None and GOES in start and WENT not in start                       # before it is sent: goes
    consult(app, client)
    assert app.state.parts.consultations.upload(1)["request"] == request_was
    review = mark_of(client.get("/consultations/1").text)
    assert review is not None and (WENT in review) is went and GOES not in review


def test_15_13_ruling_52_the_line_is_left_out_where_no_connection_was_opened_and_where_the_request_was_never_made(tmp_path, clock, server):
    # Never connected: the request was made and nothing can have left; the warning says why the transcript is the live one.
    app, client, local = ticked_app(tmp_path / "a", clock, server, NeverConnected())
    consult(app, client)
    p = app.state.parts
    assert p.consultations.upload(1)["request"] == "never_connected" and p.consultations.upload(1)["job_id"] is None
    page = client.get("/consultations/1")
    assert mark_of(page.text) is None and WENT not in text_of(page) and GOES not in text_of(page)
    assert words.UPLOAD_FAILED.format(detail="Speechmatics could not be reached. Check the internet connection and try again.") in text_of(page)
    # No key at Stop: the stage never made the request.
    made = LongPage()
    app, client, local = ticked_app(tmp_path / "b", clock, server, made)
    p = app.state.parts
    client.post("/consultations/start/1", data=TICKS)
    p.connections.remove(SPEECHMATICS)
    c = p.running[1]
    c.begin_sound(capture_from(CAPTURE))
    c.sound(LOUD)
    live = mark_of(client.get("/consultations/1").text)
    assert live is not None and GOES in live                                               # the live page keeps the words of ruling 40
    client.post("/consultations/1/stop")
    assert until(lambda: c.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "none"})
    assert until(lambda: c.state == FINAL)
    assert made.requests == [] and p.consultations.upload(1)["request"] == "not_made"
    assert mark_of(client.get("/consultations/1").text) is None


def test_6_5_a_version_11_database_comes_forward_to_12_with_every_row_and_an_older_upload_reads_made_when_it_held_bytes(tmp_path, monkeypatch, clock):
    path = tmp_path / "openconsult.db"
    monkeypatch.setattr(schema, "VERSION", 11)
    old = open_database(path)
    old.execute("INSERT INTO patient (name, date_of_birth, sex, created_at) VALUES ('Made-up', '1990-01-01', 'F', 't')")
    rows = Consultations(old, clock)
    sent = rows.start(1, 15, "nemotron", "vllm", None, "tag", None, 2, path=TICKED)
    never = rows.start(1, 15, "nemotron", "vllm", None, "tag", None, 2, path=TICKED)
    old.execute("INSERT INTO recording_upload (consultation_id, way, sent_at, file_name, bytes, job_id) VALUES (?, 'tick', 't', 'recording.wav', 1234, 'made-up-job')", (sent,))
    old.execute("INSERT INTO recording_upload (consultation_id, way, sent_at, file_name, bytes) VALUES (?, 'tick', 't', 'recording.wav', 0)", (never,))
    counts = {t: old.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in old.tables()}
    old.close()
    monkeypatch.setattr(schema, "VERSION", 12)
    new = open_database(path)
    assert new.version() == 12
    assert {t: new.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in counts} == counts          # every row came forward
    rows = Consultations(new, clock)
    assert rows.upload(sent)["request"] == "made" and rows.upload(never)["request"] == "not_made"
    assert review_mark_lines(TICKED, rows.upload(sent)["request"]) == (WENT,) and mark_lines(TICKED) == (GOES,)
    with pytest.raises(ValueError):
        rows.end_upload(sent, None, None, None, None, None, [], None, None, None, result=False, request="made up")
    new.close()
