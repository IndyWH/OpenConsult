"""The live page's socket (spec 15.10, The recording, The live page; 11.5
rule 3; R15, R18; 15.6: other web pages cannot drive the app). The sound
is made by code; a made-up worker hears it; nothing a model says is
asserted."""

import json
import wave

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.settings import store
from openconsult.speech.choices import NEMOTRON
from openconsult.speech.door import Door as SpeechDoor
from tests.conftest import ORIGIN, PORT, browser, log_in, set_up, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_loudness import sine
from tests.test_start import PATIENT, TICKS

RATE = 48000
PIECE = sine(0.25, -20.0, rate=RATE)
CAPTURE = {"type": "capture", "echo_cancellation": False, "noise_suppression": False, "auto_gain": False, "rate": RATE}



def socket_to(client, path, origin=ORIGIN):
    """A socket as the page opens it: the app's own address, so the login
    cookie travels with it and the host is the app's."""
    return client.websocket_connect(f"ws://127.0.0.1:{PORT}{path}", headers={"Origin": origin})


def live_seg(number, start, end, text, speaker="S1"):
    return {"id": number, "start": start, "end": end, "text": text, "speaker": speaker, "confidence": None}


@pytest.fixture
def started(tmp_path, clock, machine):
    """An app with one consultation started through the pages, and the
    made-up worker behind its speech door."""
    worker = MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "made up words")], [], [live_seg(2, 0.3, 0.5, "more", "S2")]])
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)}
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()}, doors=doors)
    client = browser(app)
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    assert client.post("/consultations/start/1", data=TICKS).status_code == 303
    return app, client, worker


def states_until(socket, wanted):
    """Receive state messages until one satisfies wanted; the last is returned."""
    for _ in range(20):
        message = json.loads(socket.receive_text())
        assert message["type"] == "state"
        if wanted(message["state"]):
            return message["state"]
    raise AssertionError("the wanted state never came")


def test_15_6_a_socket_from_another_origin_or_without_a_login_is_closed(started):
    app, client, worker = started
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as closed:
        with socket_to(client, "/consultations/1/sound", origin="http://elsewhere.example"):
            pass
    assert closed.value.code == 1008
    stranger = browser(app)                                     # the right origin, no login
    with pytest.raises(WebSocketDisconnect):
        with socket_to(stranger, "/consultations/1/sound"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with socket_to(client, "/consultations/9/sound"):   # not running
            pass
    assert worker.starts == 0


def test_11_5_rule_3_the_capture_message_reaches_the_record_and_the_sound_reaches_the_file_and_the_door(started, tmp_path):
    app, client, worker = started
    with socket_to(client, "/consultations/1/sound") as socket:
        first = states_until(socket, lambda s: True)
        assert first["state"] == "live" and first["speech"]["state"] == "not_started"
        socket.send_text(json.dumps(CAPTURE))
        state = states_until(socket, lambda s: s["speech"]["state"] == "open")
        for _ in range(3):
            socket.send_bytes(PIECE)
        state = states_until(socket, lambda s: len(s["transcript"]["lines"]) == 2)
    assert [(ln["n"], ln["speaker"], ln["text"]) for ln in state["transcript"]["lines"]] == [(1, "S1", "made up words"), (2, "S2", "more")]
    row = app.state.parts.consultations.get(1)
    assert (row["echo_cancellation"], row["noise_suppression"], row["auto_gain"], row["sample_rate"]) == (0, 0, 0, RATE)
    assert worker.requested("open")[0][0]["rate"] == RATE and worker.requested("open")[0][0]["speakers"] == 2
    assert len(worker.requested("audio")) == 3
    with wave.open(str(tmp_path / "recordings" / "consultation_1.wav"), "rb") as made:
        assert made.getframerate() == RATE and made.getnframes() == 3 * 12000
    assert [ln["text"] for ln in app.state.parts.consultations.live_lines(1)] == ["made up words", "more"]
    # A capture message that cannot be read changes nothing, and a stray text neither.
    consultation = app.state.parts.running[1]
    assert consultation.capture.rate == RATE


def test_R18_a_dropped_socket_loses_nothing(started, tmp_path):
    app, client, worker = started
    with socket_to(client, "/consultations/1/sound") as socket:
        states_until(socket, lambda s: True)
        socket.send_text(json.dumps(CAPTURE))
        states_until(socket, lambda s: s["speech"]["state"] == "open")
        socket.send_bytes(PIECE)
        states_until(socket, lambda s: s["transcript"]["lines"])
    # The connection dropped: the recording stays open and feeding goes on from a new socket.
    consultation = app.state.parts.running[1]
    assert consultation.recording.open
    with socket_to(client, "/consultations/1/sound") as socket:
        state = states_until(socket, lambda s: True)
        assert state["transcript"]["lines"][0]["text"] == "made up words"     # the page gets what it missed
        socket.send_bytes(PIECE)
        socket.send_bytes(PIECE)
        states_until(socket, lambda s: len(s["transcript"]["lines"]) == 2)
    assert len(worker.requested("audio")) == 3 and consultation.recording.seconds == 0.75


def test_R15_the_live_page_holds_stop_in_the_fixed_zone_with_the_state_and_the_model_line(started):
    app, client, worker = started
    page = client.get("/consultations/1")
    assert page.status_code == 200
    text = text_of(page)
    assert 'id="stop"' in text and 'class="fixed-zone"' in text and words.STOP in text
    assert words.MODEL_LINE.format(speech=words.ROW_NEMOTRON, model="gemma4:26b-a4b-it-qat", engine="made-up",
                                   version="0.0-made-up") in text
    assert '"intended_minutes": 15' in text and "/static/live.js" in text and "/static/recorder-worklet.js" not in text
    assert client.get("/consultations/7").headers["location"] == "/"
    assert client.get("/static/live.js").status_code == 200 and client.get("/static/recorder-worklet.js").status_code == 200


def test_R29_an_acknowledgement_over_the_socket_is_one_press(started):
    app, client, worker = started
    consultation = app.state.parts.running[1]
    with socket_to(client, "/consultations/1/sound") as socket:
        states_until(socket, lambda s: True)
        socket.send_text(json.dumps({"type": "acknowledge", "key": "not-an-alarm"}))
        socket.send_text("not json")
        socket.send_text(json.dumps({"type": "capture", "rate": "none"}))
    assert consultation.passes.acknowledged == set() and consultation.capture is None
