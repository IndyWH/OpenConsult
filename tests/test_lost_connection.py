"""A lost connection in a consultation in cloud mode (spec 15.13, ruling
29; 15.9 ruling 4; 15.10 ruling 7; the details of run 9b): said at once,
the recording going on, a new session tried at an interval, the later
lines unsure until their own question is answered, and the stretch with
no transcript named by its times. A made speech worker that loses its
line when told to; nothing here hears any sound."""

from __future__ import annotations

from openconsult import words
from openconsult.consult import live as live_module, stop
from openconsult.consult.live import FINAL
from openconsult.settings.path import CLAUDE
from openconsult.speech.choices import NEMOTRON, SPEECHMATICS as SPEECHMATICS_CHOICE
from openconsult.speech.door import Door as SpeechDoor
from openconsult.speech.worker import WorkerGone
from openconsult.web.live import capture_from
from tests.conftest import refusal_on, text_of
from tests.test_cloud_consultation import cloud_app
from tests.test_connect_screens import NO_CARD, SUITABLE
from tests.test_review_page import CAPTURE, LONG, LOUD
from tests.test_start import TICKS
from tests.test_stop import until

PIECE_S = 0.25


def seg(n, start, end, text, speaker):
    return {"id": n, "start": start, "end": end, "text": text, "speaker": speaker, "confidence": 0.9}


class SessionsWorker:
    """A made cloud worker with sessions: each session answers its own
    script of lines, piece by piece, and loses its line at the piece it
    is told to; an open can be made to fail a number of times first."""

    def __init__(self, sessions: list[dict], open_fails: int = 0):
        self.sessions, self.open_fails = sessions, open_fails
        self.opened, self.fed, self.requests = 0, 0, []
        self.state, self.kind, self.reason, self.info = "stopped", None, None, {}
        self.starts = 0

    def start(self):
        self.starts += 1
        self.state = "starting"

    def wait_ready(self, timeout_s=None):
        self.state = "ready"
        self.info = {"type": "ready", "models": {"made-up": {"revision": "r0"}}, "versions": {"made-up": "0.0"}}
        return True

    def stop(self):
        self.state = "stopped"

    def request(self, header, payload=b"", timeout_s=None):
        self.requests.append(header["type"])
        if self.state != "ready":
            raise WorkerGone("died", "made-up: not ready")
        kind = header["type"]
        if kind == "open":
            if self.open_fails:
                self.open_fails -= 1
                return {"type": "error", "fatal": False, "reason": "no_internet", "detail": "made-up: no route"}
            self.opened, self.fed = self.opened + 1, 0
            return {"type": "opened", "session": header["session"]}
        if kind == "audio":
            self.fed += 1
            script = self.sessions[self.opened - 1]
            if script.get("lose_at") == self.fed:
                return {"type": "error", "fatal": False, "reason": "connection_lost", "detail": "1006: made-up"}
            return {"type": "lines", "segments": script.get("lines", {}).get(self.fed, []), "pending": [], "revisions": []}
        if kind == "stop":
            return {"type": "stopped", "last_live": [], "revisions": [], "seconds": {"stop": 0.1, "sent": self.fed * PIECE_S}}
        return {"type": "closed", "session": header.get("session")}


FIRST = {"lines": {1: [seg(1, 0.0, 0.2, LONG, "S1")], 2: [seg(2, 0.3, 0.45, "Yes it does.", "S2")]}, "lose_at": 3}
SECOND = {"lines": {1: [seg(1, 0.0, 0.2, "Later words of the patient.", "S1")], 2: [seg(2, 0.3, 0.45, "Later words of the doctor.", "S2")]}}


def lost_and_found(tmp_path, clock, server, monkeypatch, worker=None):
    """A consultation in cloud mode whose first session is lost at its third
    piece. The clock of the tries is the test's: nothing waits."""
    worker = worker or SessionsWorker([FIRST, SECOND])
    app, client, local, workers, testers = cloud_app(tmp_path, clock, server, machine=NO_CARD)
    p = app.state.parts
    p.doors[SPEECHMATICS_CHOICE.name] = SpeechDoor(SPEECHMATICS_CHOICE, make_worker=lambda: worker, installed=lambda: True)
    client.post("/consultations/start/1", data=TICKS)
    c = p.running[1]
    now = {"t": 100.0}
    c.timer = lambda: now["t"]
    c.begin_sound(capture_from(CAPTURE))
    for _ in range(3):
        c.sound(LOUD)
    return app, client, c, worker, now


def test_15_13_ruling_29_a_lost_session_is_said_with_its_reason_the_recording_goes_on_and_a_new_session_is_tried_at_the_interval(tmp_path, clock, server, monkeypatch):
    app, client, c, worker, now = lost_and_found(tmp_path, clock, server, monkeypatch)
    p = app.state.parts
    state = c.page_state()["speech"]
    assert (state["state"], state["trying"], state["back"]) == ("failed", True, False)
    assert state["reason"] == words.CONNECTION_LOST.format(service="Speechmatics")              # the sentence the page has
    for name in ("ALARM_NOT_LISTENING", "TRYING_AGAIN", "CONNECTION_BACK"):                      # and the three it gains, handed to the page's script
        assert name in __import__("openconsult.web.live", fromlist=["SCRIPT_WORDS"]).SCRIPT_WORDS
    assert words.ALARM_NOT_LISTENING == "The emergency alarm has stopped listening."
    assert [(s["n"], s["opened_at_s"], s["lost_at_s"]) for s in p.consultations.sessions(1)] == [(1, 0.0, 0.75)]
    # The recording goes on while nothing is transcribed, and no try is made before the interval has passed.
    size = c.recording.path.stat().st_size if hasattr(c.recording, "path") else None
    for _ in range(4):
        c.sound(LOUD)
    assert worker.requests.count("open") == 1 and c.loudness.seconds == 7 * PIECE_S
    assert size is None or c.recording.path.stat().st_size >= size
    now["t"] += live_module.RECONNECT_EVERY_S - 0.5
    c.sound(LOUD)
    assert worker.requests.count("open") == 1 and live_module.RECONNECT_EVERY_S == 10.0          # not yet: half a second short
    now["t"] += 0.5
    c.sound(LOUD)                                                                                # the interval has passed: one try, on its own thread
    assert until(lambda: c.speech.state == "open")
    state = c.page_state()["speech"]
    assert (state["state"], state["back"], state["session"]) == ("open", True, 2) and worker.requests.count("open") == 2
    assert [(s["n"], s["opened_at_s"], s["lost_at_s"], s["reason"]) for s in p.consultations.sessions(1)] == [
        (1, 0.0, 0.75, words.CONNECTION_LOST.format(service="Speechmatics")), (2, 2.25, None, None)]
    # The lines of the later session keep their numbers in order, carry their session, and stand at their place in the recording.
    c.sound(LOUD)
    c.sound(LOUD)
    lines = p.consultations.live_lines(1)
    assert [(l["n"], l["session"], l["speaker"], l["start_s"], l["end_s"]) for l in lines] == [
        (1, 1, "S1", 0.0, 0.2), (2, 1, "S2", 0.3, 0.45), (3, 2, "S1", 2.25, 2.45), (4, 2, "S2", 2.55, 2.7)]
    assert [l["n"] for l in c.page_state()["transcript"]["lines"]] == [1, 2, 3, 4]


def test_15_13_ruling_29_a_try_that_fails_is_tried_again_at_the_next_interval(tmp_path, clock, server, monkeypatch):
    worker = SessionsWorker([FIRST, SECOND], open_fails=0)
    app, client, c, worker, now = lost_and_found(tmp_path, clock, server, monkeypatch, worker)
    worker.open_fails = 2                                                                        # the internet is still gone for two tries
    for expected in (2, 3):
        now["t"] += live_module.RECONNECT_EVERY_S
        c.sound(LOUD)
        assert until(lambda: worker.requests.count("open") == expected and c._retry_at is not None)
        assert c.speech.state == "failed" and c.speech.trying
    now["t"] += live_module.RECONNECT_EVERY_S
    c.sound(LOUD)
    assert until(lambda: c.speech.state == "open") and worker.requests.count("open") == 4
    assert [s["n"] for s in app.state.parts.consultations.sessions(1)] == [1, 2]                 # a failed try opens no session


def test_15_13_ruling_29_a_local_worker_that_dies_is_said_as_before_and_never_started_again(tmp_path, clock, server):
    app, client, local, workers, testers = cloud_app(tmp_path / "local", clock, server, machine=SUITABLE)
    p = app.state.parts
    dying = SessionsWorker([{"lose_at": 2}])
    p.doors[NEMOTRON.name] = SpeechDoor(NEMOTRON, make_worker=lambda: dying, installed=lambda: True)
    client.post("/consultations/start/1", data=TICKS)
    c2 = p.running[1]
    now2 = {"t": 0.0}
    c2.timer = lambda: now2["t"]
    c2.begin_sound(capture_from(CAPTURE))
    for _ in range(3):
        c2.sound(LOUD)
    now2["t"] += 10 * live_module.RECONNECT_EVERY_S
    c2.sound(LOUD)
    assert c2.speech.state == "failed" and not c2.speech.trying and dying.requests.count("open") == 1
    assert p.consultations.sessions(1) == []                                                     # no session row for a local choice


def through_to_question(tmp_path, clock, server, monkeypatch, lost_pieces=4):
    app, client, c, worker, now = lost_and_found(tmp_path, clock, server, monkeypatch)
    for _ in range(lost_pieces):
        c.sound(LOUD)
    now["t"] += live_module.RECONNECT_EVERY_S
    c.sound(LOUD)
    assert until(lambda: c.speech.state == "open")
    c.sound(LOUD)
    c.sound(LOUD)
    c.wait_for_pass()
    client.post("/consultations/1/stop")
    # After a lost connection Stop asks first whether to send the recording (the press of half two): here, go on without.
    assert until(lambda: c.stop_stage == "lost")
    assert client.post("/consultations/1/whole", data={"send": "no"}).status_code == 303
    assert until(lambda: c.stop_stage == "who_spoke")
    return app, client, c


def test_15_9_ruling_4_the_question_is_asked_once_for_each_session_and_a_line_never_takes_a_speaker_from_another_sessions_answer(tmp_path, clock, server, monkeypatch):
    app, client, c = through_to_question(tmp_path, clock, server, monkeypatch)
    p = app.state.parts
    rows = p.consultations.transcript_lines(1)
    assert [(r["n"], r["session"], r["raw_speaker"], r["label"], r["unsure"]) for r in rows] == [
        (1, 1, "S1", "unsure", 1), (2, 1, "S2", "unsure", 1), (3, 2, "S1", "unsure", 1), (4, 2, "S2", "unsure", 1)]   # never guessed
    page = client.get("/consultations/1")
    said = text_of(page)
    assert words.WHO_SPOKE_PARTS in said and words.WHO_SPOKE_PART.format(n=1, first=1, last=2) in said
    assert words.WHO_SPOKE_PART.format(n=2, first=3, last=4) in said
    assert 'name="speaker_1" value="S1"' in page.text and 'name="speaker_2" value="S2"' in page.text and 'name="speaker"' not in page.text
    assert "No transcript from 0.8 to 2.0 s: the connection was lost." in said                   # the stretch, named by its times
    # One part left unanswered is refused on the control, and nothing is set.
    refused = client.post("/consultations/1/speakers", data={"speaker_1": "S1"})
    assert refused.status_code == 400 and refusal_on(refused.text, "answer") == words.PICK_ONE_EACH and c.doctor_speaker is None
    assert not stop.answer(c, "S1")                                                              # one answer cannot stand for two sessions
    assert not stop.answer_parts(c, {1: "S1", 2: "S9"})                                          # nor a speaker the session did not give
    # The doctor was the first speaker before the loss and the second after it: each session by its own answer.
    assert client.post("/consultations/1/speakers", data={"speaker_1": "S1", "speaker_2": "S2"}).status_code == 303
    assert until(lambda: c.state == FINAL)
    labels = {r["n"]: (r["label"], r["unsure"]) for r in p.consultations.transcript_lines(1)}
    assert labels == {1: ("doctor", 0), 2: ("patient", 0), 3: ("patient", 0), 4: ("doctor", 0)}
    assert [(s["n"], s["doctor_speaker"]) for s in p.consultations.sessions(1)] == [(1, "S1"), (2, "S2")]
    answered = next(l for l in p.audit.lines() if l.event == "speakers.answered")
    assert answered.detail == "consultation 1: part 1 S1, part 2 S2"


def test_15_13_ruling_29_the_stretch_with_no_transcript_is_found_from_the_loudness_of_the_whole_recording_and_named_by_its_times(tmp_path, clock, server, monkeypatch):
    app, client, c = through_to_question(tmp_path, clock, server, monkeypatch, lost_pieces=12)    # three seconds with no session
    p = app.state.parts
    import json
    windows = json.loads(p.consultations.get(1)["loudness"])
    assert len(windows) == round(c.loudness.seconds / 0.1) and len(windows) > 20                # every piece of the recording, also those no session heard
    client.post("/consultations/1/speakers", data={"speaker_1": "S1", "speaker_2": "none"})
    assert until(lambda: c.state == FINAL)
    warnings = p.consultations.warnings(1)
    named = [(w["start_s"], w["end_s"]) for w in warnings if w["kind"] == "no_transcript"]
    assert named == [(0.8, 4.0)]                                                                 # lost at 0.75 s, found again at 4.0 s
    uncovered = [(w["start_s"], w["end_s"]) for w in warnings if w["kind"] == "uncovered_speech"]
    assert any(start <= 1.0 and end >= 3.9 for start, end in uncovered)                          # the check of today finds the speech inside it
    page = text_of(client.get("/consultations/1"))
    assert "No transcript from 0.8 to 4.0 s: the connection was lost." in page
    assert {r["n"]: r["label"] for r in p.consultations.transcript_lines(1)} == {1: "doctor", 2: "patient", 3: "unsure", 4: "unsure"}


def test_15_13_ruling_29_stop_while_a_session_is_lost_keeps_what_was_heard_and_a_session_opened_after_stop_is_ended(tmp_path, clock, server, monkeypatch):
    app, client, c, worker, now = lost_and_found(tmp_path, clock, server, monkeypatch)
    p = app.state.parts
    c.sound(LOUD)
    client.post("/consultations/1/stop")                                                         # Stop while the connection is still lost
    assert until(lambda: c.stop_stage == "lost")
    client.post("/consultations/1/whole", data={"send": "no"})                                   # go on without the whole transcript
    assert until(lambda: c.stop_stage == "who_spoke")
    rows = p.consultations.transcript_lines(1)
    assert [(r["n"], r["session"]) for r in rows] == [(1, 1), (2, 1)]                            # the lines heard live are the transcript
    page = client.get("/consultations/1")
    assert 'name="speaker" value="S1"' in page.text and "No transcript from 0.8 to 1.0 s" in text_of(page)   # one question; the stretch to the end
    # A try that was in flight when Stop came: the session it opens is ended at once, with nothing asked of it.
    c._try_again()
    assert worker.requests[-2:] == ["open", "close"] and c.session == 1 and c.speech.state == "stopped"
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: c.state == FINAL)
    assert any(w["kind"] == "speech_failed" for w in p.consultations.warnings(1))
    assert CLAUDE == p.consultations.get(1)["language_model_path"]


def test_15_13_ruling_29_the_door_can_open_a_new_session_after_the_service_ended_one():
    worker = SessionsWorker([{"lose_at": 1}, {"lines": {1: [seg(1, 0.0, 0.2, "made up words", "S1")]}}])
    door = SpeechDoor(SPEECHMATICS_CHOICE, make_worker=lambda: worker, installed=lambda: True)
    assert door.open(16000, speakers=2).ok
    lost = door.feed(LOUD)
    assert (lost.ok, lost.failure) == (False, "connection_lost")
    again = door.open(16000, speakers=2)                                                         # not refused as a session still open
    assert again.ok and worker.starts == 1                                                       # the same worker: its process goes on
    heard = door.feed(LOUD)
    assert heard.ok and [line.text for line in heard.lines] == ["made up words"]
    door.close()
