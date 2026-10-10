"""The AssemblyAI worker against the made-up service (spec 15.9,
rulings 3, 4 and 9; 7.2; 10.4; 11.1; 11.4; 13.2; the details of 5b).
What the app sends is asserted here; what the service hears never is."""

import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

from openconsult.speech import frames
from openconsult.speech.worker import Worker
from tests.made_up_dial import load_worker
from tests.made_up_service import ASSEMBLYAI, MadeUpService

worker = load_worker("assemblyai")
cloud = worker.cloud
RUNNER = Path(__file__).parent / "made_up_dial.py"


def turn(order, text, words, end=True, speaker="A"):
    return {"type": "Turn", "turn_order": order, "turn_is_formatted": True, "end_of_turn": end, "transcript": text,
            "end_of_turn_confidence": 0.9, "speaker_label": speaker,
            "words": [{"text": w, "start": s, "end": e, "confidence": c, "word_is_final": True, "speaker": speaker}
                      for w, s, e, c in words]}


def session_on(service, rate=16000, speakers=1):
    ws = cloud.open_connection(worker.address_for(rate, speakers, service.address + "/v3/ws"), worker.headers("made-up-key"))
    return worker.open_session(ws, rate, speakers)


def test_ruling_9_the_connection_parameters_word_for_word():
    service = MadeUpService(ASSEMBLYAI)
    try:
        session_on(service, rate=16000, speakers=1).close()
        session_on(service, rate=48000, speakers=2).close()
        assert service.handshakes[0]["headers"]["authorization"] == "made-up-key"
        assert service.openings[0] == "speech_model=universal-3-6-pro&sample_rate=16000&encoding=pcm_s16le&speaker_labels=true&domain=medical-v1&max_speakers=1"
        assert service.openings[1] == "speech_model=universal-3-6-pro&sample_rate=48000&encoding=pcm_s16le&speaker_labels=true&domain=medical-v1&max_speakers=2"
        assert "keyterms_prompt" not in service.openings[0] and "format_turns" not in service.openings[0]
        assert worker.ADDRESS == "wss://streaming.eu.assemblyai.com/v3/ws"
    finally:
        service.stop()


def test_ruling_9_an_echo_that_differs_from_what_was_asked_is_refused():
    echo = {"type": "Begin", "id": "made-up", "expires_at": 0,
            "configuration": {"model": "universal-3-6-pro", "domain": None, "speaker_labels": True, "max_speakers": 1}}
    service = MadeUpService(ASSEMBLYAI, first=echo)
    try:
        with pytest.raises(cloud.Refused) as refused:
            session_on(service)
        assert refused.value.kind == "worker_error" and "medical-v1" in refused.value.detail
        assert service.connections == 1
    finally:
        service.stop()
    # A field the echo does not carry is recorded as not echoed, never taken for a difference.
    silent = {"type": "Begin", "id": "made-up", "expires_at": 0,
              "configuration": {"model": "universal-3-6-pro", "domain": "medical-v1", "speaker_labels": True}}
    service = MadeUpService(ASSEMBLYAI, first=silent)
    try:
        session = session_on(service)
        assert session.not_echoed == ["max_speakers"]
        session.close()
    finally:
        service.stop()


def test_11_4_final_turns_become_lines_and_an_open_turn_is_partial():
    service = MadeUpService(ASSEMBLYAI, script={
        1: [turn(0, "ask no", [("ask", 500, 700, 0.9)], end=False)],
        2: [turn(0, "Ask not,", [("Ask", 500, 700, 0.9), ("not,", 750, 900, 0.7)]),
            turn(1, "what you can", [("what", 1000, 1200, 0.8)], speaker="PENDING"),
            turn(2, "do", [("do", 1300, 1400, None)], speaker="UNKNOWN")],
    })
    try:
        session = session_on(service, speakers=2)
        session.accept(bytes(8000))
        time.sleep(0.3)
        first = session.accept(bytes(8000))
        assert first["segments"] == [] and first["pending"][0]["text"] == "ask no"
        time.sleep(0.3)
        second = session.accept(bytes(8000))
        assert second["pending"] == [] and second["segments"] == [
            {"id": 0, "speaker": "A", "start": 0.5, "end": 0.9, "text": "Ask not,", "confidence": 0.8},
            {"id": 1, "speaker": None, "start": 1.0, "end": 1.2, "text": "what you can", "confidence": 0.8},
            {"id": 2, "speaker": None, "start": 1.3, "end": 1.4, "text": "do", "confidence": None},
        ]
    finally:
        service.stop()


def test_ruling_4_a_revision_changes_labels_only_and_the_last_one_comes_at_stop():
    revision = {"type": "SpeakerRevision", "revisions": [
        {"turn_order": 0, "speaker_label": "B", "words": [{"text": "CHANGED", "speaker": "B", "start": 1, "end": 2}]},
        {"turn_order": 3, "speaker_label": "UNKNOWN", "words": []},
    ]}
    service = MadeUpService(ASSEMBLYAI, script={1: [turn(0, "one", [("one", 0, 200, 0.9)]), revision],
                                                "stop": [turn(4, "the last words", [("the", 9000, 9100, 0.9)]), revision]})
    try:
        session = session_on(service, speakers=2)
        session.accept(bytes(8000))
        time.sleep(0.3)
        got = session.accept(bytes(8000))
        assert got["segments"][0]["text"] == "one" and got["segments"][0]["speaker"] == "A"
        assert got["revisions"] == [{"id": 0, "speaker": "B"}, {"id": 3, "speaker": None}]   # id and label, nothing else
        done = session.finish()
        assert [s["text"] for s in done["last_live"]] == ["the last words"]
        assert done["revisions"] == [{"id": 0, "speaker": "B"}, {"id": 3, "speaker": None}]
        assert service.ended == [{"type": "Terminate"}]
    finally:
        service.stop()


def test_13_2_the_rate_travels_and_a_rate_the_service_does_not_take_is_refused():
    with pytest.raises(cloud.Refused) as refused:
        worker.dial("made-up-key", 7000, 1)
    assert refused.value.kind == "rate_not_supported" and "7,000" in refused.value.detail
    assert worker.address_for(48000, 1).endswith("sample_rate=48000&encoding=pcm_s16le&speaker_labels=true&domain=medical-v1&max_speakers=1")


@pytest.mark.parametrize("mode, kind", [
    ("close 1008 Unauthorized Connection: Missing Authorization header", "key_refused"),
    ("close 1008 Unauthorized Connection: insufficient balance", "no_credit"),
    ("close 3009 Unauthorized Connection: Too many concurrent sessions", "limit_reached"),
    ("close 1011 Internal error", "service_down"),
    ("close 3007 Audio Transmission Rate Exceeded", "worker_error"),
    ("close 1001 going away", "connection_lost"),
])
def test_7_2_each_service_failure_has_its_plain_name_and_nothing_reconnects(mode, kind):
    service = MadeUpService(ASSEMBLYAI, mode=mode)
    try:
        session = session_on(service)
        with pytest.raises(cloud.Refused) as refused:
            for _ in range(20):
                session.accept(bytes(8000))
                time.sleep(0.05)
        assert refused.value.kind == kind and service.connections == 1
    finally:
        service.stop()


def test_7_2_a_wrong_key_is_answered_with_an_error_frame_and_is_key_refused():
    # The real service, 10 Oct 2026: the handshake succeeds, then one Error frame
    # {"type": "Error", "error_code": 1008, "error": "Unauthorized Connection: Invalid API key"}, then the close.
    service = MadeUpService(ASSEMBLYAI, mode="error")
    try:
        with pytest.raises(cloud.Refused) as refused:
            session_on(service)
        assert refused.value.kind == "key_refused" and service.connections == 1
    finally:
        service.stop()
    balance = {"type": "Error", "error_code": 1008, "error": "Unauthorized Connection: insufficient balance"}
    service = MadeUpService(ASSEMBLYAI, first=balance)
    try:
        with pytest.raises(cloud.Refused) as refused:
            session_on(service)
        assert refused.value.kind == "no_credit"
    finally:
        service.stop()


def test_ruling_9_main_dials_the_eu_address_whatever_argv_and_the_environment_say(monkeypatch):
    asked = []

    def recording_dial(address, eu_host, headers_, connect=None):
        asked.append((address, eu_host, headers_))
        raise cloud.Refused("no_internet", "made-up: not dialled")

    monkeypatch.setattr(cloud, "dial", recording_dial)
    monkeypatch.setattr(sys, "argv", ["worker.py", "--address", "wss://streaming.assemblyai.com/v3/ws"])
    environ = {"ASSEMBLYAI_URL": "wss://streaming.assemblyai.com/v3/ws", "ASSEMBLYAI_API_KEY": "made-up-key"}
    inp, out = io.BytesIO(), io.BytesIO()
    frames.write_frame(inp, {"type": "open", "session": "s1", "rate": 16000, "speakers": 1})
    inp.seek(0)
    assert worker.main(inp=inp, out=out, environ=environ) == 0
    assert asked == [(worker.address_for(16000, 1), "streaming.eu.assemblyai.com", {"Authorization": "made-up-key"})]
    assert asked[0][0].startswith("wss://streaming.eu.assemblyai.com/v3/ws?")
    out.seek(0)
    ready, _ = frames.read_frame(out)
    error, _ = frames.read_frame(out)
    assert ready["type"] == "ready" and (error["type"], error["reason"]) == ("error", "no_internet")
    assert "made-up-key" not in json.dumps(ready) and "made-up-key" not in json.dumps(error)


def test_the_real_worker_runs_as_a_subprocess_against_the_made_up_service(tmp_path):
    service = MadeUpService(ASSEMBLYAI, script={1: [turn(0, "Made up.", [("Made", 0, 200, 0.9), ("up.", 200, 400, 0.9)])]})
    env = {**os.environ, "ASSEMBLYAI_API_KEY": "made-up-key"}
    process = Worker([sys.executable, "-u", str(RUNNER), "assemblyai", service.address], log_path=tmp_path / "worker.log",
                     env=env, ready_timeout_s=30.0, request_timeout_s=30.0)
    try:
        process.start()
        assert process.wait_ready(), process.reason
        stamp = process.info["models"]["assemblyai"]
        assert stamp["address"] == worker.ADDRESS and stamp["model"] == "universal-3-6-pro" and stamp["options"]["domain"] == "medical-v1"
        assert "made-up-key" not in json.dumps(process.info)
        assert process.request({"type": "open", "session": "s1", "rate": 16000, "speakers": 1})["type"] == "opened"
        process.request({"type": "audio", "session": "s1"}, bytes(8000))
        time.sleep(0.3)
        reply = process.request({"type": "audio", "session": "s1"}, bytes(8000))
        assert [s["text"] for s in reply["segments"]] == ["Made up."]
        stopped = process.request({"type": "stop", "session": "s1", "speakers": 1}, timeout_s=30.0)
        assert stopped["type"] == "stopped" and service.ended == [{"type": "Terminate"}]
        assert "made-up-key" not in (tmp_path / "worker.log").read_text(errors="replace")
    finally:
        process.stop()
        service.stop()
