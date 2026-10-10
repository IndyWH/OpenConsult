"""The rules every cloud worker keeps (spec 15.9, ruling 9; 10.4; the
details of 5b): the EU address only, the certificate always checked, a
dead line noticed, nothing reconnecting. The frame is loaded by path, as
the workers load it; the service is made up and on loopback."""

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

from tests.made_up_service import SPEECHMATICS, MadeUpService

CLOUD = Path(__file__).resolve().parents[1] / "openconsult" / "speech" / "common" / "cloud.py"


def load_cloud():
    spec = importlib.util.spec_from_file_location("cloud_frame", CLOUD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cloud = load_cloud()


class Recorder:
    """Stands where the library's connect stands: records what it was asked."""

    def __init__(self):
        self.calls = []

    def __call__(self, address, **kwargs):
        self.calls.append((address, kwargs))
        return object()


@pytest.mark.parametrize("address", [
    "wss://global.rt.speechmatics.com/v2",            # may route to any region
    "wss://eu.rt.speechmatics.com.example/v2",         # a longer host
    "ws://eu.rt.speechmatics.com/v2",                  # not wss
    "wss://127.0.0.1/v2",                              # loopback
    "wss://streaming.assemblyai.com/v3/ws",            # the other service's global host
])
def test_ruling_9_the_frame_refuses_any_address_but_the_eu_one(address):
    recorder = Recorder()
    with pytest.raises(cloud.Refused) as refused:
        cloud.dial(address, "eu.rt.speechmatics.com", {}, connect=recorder)
    assert (refused.value.kind, refused.value.detail) == ("address_refused", address)
    assert recorder.calls == []                                   # refused before any connection


def test_ruling_9_the_eu_address_is_dialled_with_the_librarys_own_certificate_checking():
    recorder = Recorder()
    cloud.dial("wss://eu.rt.speechmatics.com/v2", "eu.rt.speechmatics.com", {"Authorization": "Bearer made-up"}, connect=recorder)
    address, kwargs = recorder.calls[0]
    assert address == "wss://eu.rt.speechmatics.com/v2" and kwargs["additional_headers"] == {"Authorization": "Bearer made-up"}
    assert "ssl" not in kwargs and "server_hostname" not in kwargs    # the default context: certificate and host checked
    assert kwargs["ping_interval"] == 20.0 and kwargs["ping_timeout"] == 20.0 and kwargs["close_timeout"] == 10.0
    assert cloud.NOTICED_WITHIN_S == 50.0


@pytest.mark.parametrize("status, kind", [(401, "key_refused"), (403, "key_refused"), (402, "no_credit"),
                                          (429, "limit_reached"), (500, "service_down"), (503, "service_down")])
def test_7_2_a_refused_handshake_has_its_plain_name(status, kind):
    service = MadeUpService(SPEECHMATICS, mode=f"refuse_handshake {status}")
    try:
        with pytest.raises(cloud.Refused) as refused:
            cloud.open_connection(service.address, {"Authorization": "Bearer made-up"})
        assert refused.value.kind == kind
        assert service.handshakes[0]["headers"]["authorization"] == "Bearer made-up"
        assert service.connections == 0
    finally:
        service.stop()


def test_7_2_no_internet_is_a_name_lookup_or_a_connection_that_cannot_be_made():
    with pytest.raises(cloud.Refused) as refused:
        cloud.open_connection("ws://127.0.0.1:1/", {})                 # nothing listens there
    assert refused.value.kind == "no_internet"


class Simplest(cloud.Session):
    """The least a session can be: the frame's own parts, with a protocol
    of two messages, so the frame is tested apart from either service."""

    def start(self):
        self.ws.send(json.dumps({"message": "StartRecognition"}))
        self.first_reply(timeout_s=5.0)

    def take(self, message):
        body = json.loads(message)
        if body.get("message") == "AddTranscript":
            self.segments.append({"id": len(self.segments) + 1, "start": 0.0, "end": 0.5, "text": body["text"]})
        self.last = body

    def end_message(self):
        return json.dumps({"message": "EndOfStream", "last_seq_no": self.pieces})

    def ended(self, message):
        return json.loads(message).get("message") == "EndOfTranscript"


def test_the_frames_session_sends_sound_takes_messages_and_ends_so_the_last_words_arrive():
    service = MadeUpService(SPEECHMATICS, script={1: [{"message": "AddTranscript", "text": "made up"}],
                                                   "stop": [{"message": "AddTranscript", "text": "the last words"}]})
    try:
        session = Simplest(cloud.open_connection(service.address, {}), 16000, 1)
        session.start()
        session.accept(bytes(8000))                                   # the service answers this piece
        time.sleep(0.3)
        assert [s["text"] for s in session.accept(bytes(8000))["segments"]] == ["made up"]
        done = session.finish()
        assert [s["text"] for s in done["last_live"]] == ["the last words"] and done["seconds"]["sent"] == 0.5
        assert service.ended == [{"message": "EndOfStream", "last_seq_no": 2}] and len(service.audio) == 2
    finally:
        service.stop()


def test_10_4_a_line_that_dies_without_closing_is_noticed_and_nothing_reconnects():
    service = MadeUpService(SPEECHMATICS, mode="quiet")
    try:
        ws = cloud.open_connection(service.address, {}, ping_interval_s=0.2, ping_timeout_s=0.2, close_timeout_s=0.2)
        session = Simplest(ws, 16000, 1)
        session.start()
        started = time.perf_counter()
        with pytest.raises(cloud.Refused) as lost:
            for _ in range(60):
                session.accept(bytes(8000))
                time.sleep(0.1)
        assert lost.value.kind == "connection_lost" and time.perf_counter() - started < 5.0
        assert service.connections == 1                               # no second connection was made
    finally:
        service.stop()


# -------------------------------------------- never silent, both ways (10.4)

from openconsult import words  # noqa: E402
from openconsult.speech import door as door_module  # noqa: E402
from openconsult.speech import choices  # noqa: E402  (the service kinds above are strings)
from openconsult.speech.door import Door, make_door  # noqa: E402
from tests.fakes import MadeUpWorker  # noqa: E402


def test_10_4_a_cloud_service_that_fails_is_a_failure_and_nothing_else_is_tried():
    worker = MadeUpWorker()
    asked = []

    def refusing(header, payload=b"", timeout_s=None):
        asked.append(header)
        return {"type": "error", "fatal": False, "reason": "no_credit", "message": "made-up", "detail": ""}

    worker.request = refusing
    door = Door(choices.SPEECHMATICS, make_worker=lambda: worker, installed=lambda: True)
    failed = door.open(16000, speakers=1)
    assert (failed.failure, failed.detail) == ("no_credit", words.NO_CREDIT.format(service="Speechmatics"))
    assert door.feed(bytes(8000)).failure == "no_session"
    assert worker.starts == 1 and [h["type"] for h in asked] == ["open"]     # one try, then the plain failure


class RecordingWorker(MadeUpWorker):
    """Stands where the real worker class stands in make_door: keeps the
    command it was given, and dies at start."""

    started: list = []

    def __init__(self, command, log_path=None, env=None):
        super().__init__(ready=False)
        self.command = command
        RecordingWorker.started.append(command)


def test_10_4_a_local_choice_that_fails_never_falls_to_a_cloud_service(tmp_path, monkeypatch):
    monkeypatch.setattr(door_module, "Worker", RecordingWorker)
    RecordingWorker.started.clear()
    python = tmp_path / "speech" / "nemotron" / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("")
    door = make_door(tmp_path, choices.NEMOTRON, environ={"SPEECHMATICS_API_KEY": "made-up", "ASSEMBLYAI_API_KEY": "made-up"})
    if not door.installed:                                                  # Windows looks for Scripts/python.exe
        (python.parents[1] / "Scripts").mkdir()
        (python.parents[1] / "Scripts" / "python.exe").write_text("")
    first = door.open(16000, speakers=2)
    second = door.open(16000, speakers=2)
    assert first.failure == "died" and second.failure == "died"
    assert len(RecordingWorker.started) == 2
    for command in RecordingWorker.started:
        assert command[1].endswith(str(choices.NEMOTRON.worker_folder / "worker.py"))
        assert not any(str(choice.worker_folder) in part for choice in (choices.SPEECHMATICS, choices.ASSEMBLYAI) for part in command)
