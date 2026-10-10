"""The Speechmatics worker against the made-up service (spec 15.9,
rulings 3, 4 and 9; 7.2; 10.4; 11.1; 11.4; 13.2; the details of 5b).
What the app sends is asserted here; what the service hears never is."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

from openconsult.speech.worker import Worker
from tests.made_up_dial import load_worker
from tests.made_up_service import SPEECHMATICS, MadeUpService

worker = load_worker("speechmatics")
cloud = worker.cloud
RUNNER = Path(__file__).parent / "made_up_dial.py"


def word(content, start, end, speaker="S1", confidence=0.9):
    return {"type": "word", "start_time": start, "end_time": end,
            "alternatives": [{"content": content, "confidence": confidence, "speaker": speaker}]}


def punctuation(content, at, speaker="S1"):
    return {"type": "punctuation", "start_time": at, "end_time": at, "attaches_to": "previous",
            "alternatives": [{"content": content, "confidence": 1.0, "speaker": speaker}]}


def transcript(results, text):
    return {"message": "AddTranscript", "metadata": {"transcript": text, "start_time": results[0]["start_time"],
                                                     "end_time": results[-1]["end_time"]}, "results": results}


def session_on(service, rate=16000, speakers=1, **settings):
    ws = cloud.open_connection(service.address + "/v2", worker.headers("made-up-key"), **settings)
    return worker.open_session(ws, rate, speakers)


def test_ruling_9_the_opening_message_word_for_word():
    service = MadeUpService(SPEECHMATICS)
    try:
        session_on(service, rate=16000, speakers=1).close()
        session_on(service, rate=48000, speakers=2).close()
        assert service.handshakes[0]["headers"]["authorization"] == "Bearer made-up-key"
        assert service.handshakes[0]["path"] == "/v2"
        assert service.openings[0] == {
            "message": "StartRecognition",
            "audio_format": {"type": "raw", "encoding": "pcm_s16le", "sample_rate": 16000},
            "transcription_config": {"language": "en", "model": "enhanced", "domain": "medical",
                                     "diarization": "speaker", "enable_partials": True},
        }
        config = service.openings[1]["transcription_config"]
        assert config["speaker_diarization_config"] == {"max_speakers": 2}        # 2 or more is sent as given
        assert service.openings[1]["audio_format"]["sample_rate"] == 48000        # the session's rate, as it is
        assert "additional_vocab" not in config                                    # ruling 3: no word list
        assert worker.ADDRESS == "wss://eu.rt.speechmatics.com/v2"
    finally:
        service.stop()


def test_11_4_final_text_becomes_lines_and_partial_text_becomes_partial():
    results = [word("Ask", 0.5, 0.7), word("not", 0.75, 0.9, confidence=0.7), punctuation(",", 0.9),
               word("what", 1.0, 1.2, "S2"), word("you", 1.25, 1.4, "S2", 0.5), word("can", 1.45, 1.6, "UU")]
    service = MadeUpService(SPEECHMATICS, script={
        1: [{"message": "AddPartialTranscript", "metadata": {"transcript": "ask no"}}],
        2: [transcript(results, "Ask not, what you can")],
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
            {"id": 1, "speaker": "S1", "start": 0.5, "end": 0.9, "text": "Ask not,", "confidence": 0.8},
            {"id": 2, "speaker": "S2", "start": 1.0, "end": 1.4, "text": "what you", "confidence": 0.7},
            {"id": 3, "speaker": None, "start": 1.45, "end": 1.6, "text": "can", "confidence": 0.9},   # UU is no speaker
        ]
        done = session.finish()
        assert service.ended == [{"message": "EndOfStream", "last_seq_no": 3}]
    finally:
        service.stop()


def test_an_info_before_recognition_started_is_read_and_not_taken_for_the_answer():
    # The real service answered first with Info (its usage, its region) on 10 Oct 2026.
    info = {"message": "Info", "type": "concurrent_session_usage", "reason": "made-up", "region": "eu"}
    started = {"message": "RecognitionStarted", "id": "made-up-id"}
    service = MadeUpService(SPEECHMATICS, first=[info, {"message": "Warning", "type": "made-up"}, started])
    try:
        session = session_on(service)
        assert session.started == started
        session.close()
    finally:
        service.stop()


def test_11_1_stop_ends_the_session_so_the_last_words_arrive():
    service = MadeUpService(SPEECHMATICS, script={"stop": [transcript([word("hospital", 9.0, 9.5)], "hospital")]})
    try:
        session = session_on(service)
        session.accept(bytes(8000))
        done = session.finish()
        assert [s["text"] for s in done["last_live"]] == ["hospital"] and done["seconds"]["sent"] == 0.25
    finally:
        service.stop()


@pytest.mark.parametrize("error, kind", [
    ({"message": "Error", "type": "not_authorised", "reason": "made-up"}, "key_refused"),
    ({"message": "Error", "type": "not_allowed", "reason": "made-up"}, "no_credit"),
    ({"message": "Error", "type": "timelimit_exceeded", "reason": "made-up"}, "no_credit"),
    ({"message": "Error", "type": "quota_exceeded", "reason": "made-up"}, "limit_reached"),
    ({"message": "Error", "type": "job_error", "reason": "made-up"}, "service_down"),
    ({"message": "Error", "type": "invalid_config", "reason": "made-up"}, "worker_error"),
])
def test_7_2_each_service_failure_has_its_plain_name(error, kind):
    service = MadeUpService(SPEECHMATICS, mode="error", first=error)
    try:
        with pytest.raises(cloud.Refused) as refused:
            session_on(service)
        assert refused.value.kind == kind and service.connections == 1
    finally:
        service.stop()


def test_7_2_a_close_in_the_middle_is_a_lost_line_with_its_name_and_nothing_reconnects():
    service = MadeUpService(SPEECHMATICS, mode="close 4001 not_authorised")
    try:
        session = session_on(service)
        with pytest.raises(cloud.Refused) as refused:
            for _ in range(20):
                session.accept(bytes(8000))
                time.sleep(0.05)
        assert refused.value.kind == "key_refused" and service.connections == 1
    finally:
        service.stop()
    plain = MadeUpService(SPEECHMATICS, mode="close 1001 going away")
    try:
        session = session_on(plain)
        with pytest.raises(cloud.Refused) as refused:
            for _ in range(20):
                session.accept(bytes(8000))
                time.sleep(0.05)
        assert refused.value.kind == "connection_lost" and plain.connections == 1
    finally:
        plain.stop()


def test_ruling_9_main_dials_the_eu_address_whatever_argv_and_the_environment_say(monkeypatch):
    import io

    from openconsult.speech import frames

    asked = []

    def recording_dial(address, eu_host, headers_, connect=None):
        asked.append((address, eu_host, headers_))
        raise cloud.Refused("no_internet", "made-up: not dialled")

    monkeypatch.setattr(cloud, "dial", recording_dial)
    monkeypatch.setattr(sys, "argv", ["worker.py", "--address", "wss://global.rt.speechmatics.com/v2"])
    environ = {"SPEECHMATICS_URL": "wss://global.rt.speechmatics.com/v2", "SPEECHMATICS_ADDRESS": "wss://127.0.0.1/v2",
               "SPEECHMATICS_API_KEY": "made-up-key"}
    inp, out = io.BytesIO(), io.BytesIO()
    frames.write_frame(inp, {"type": "open", "session": "s1", "rate": 16000, "speakers": 1})
    inp.seek(0)
    assert worker.main(inp=inp, out=out, environ=environ) == 0
    assert asked == [("wss://eu.rt.speechmatics.com/v2", "eu.rt.speechmatics.com", {"Authorization": "Bearer made-up-key"})]
    out.seek(0)
    ready, _ = frames.read_frame(out)
    error, _ = frames.read_frame(out)
    assert ready["type"] == "ready" and (error["type"], error["reason"]) == ("error", "no_internet")
    assert "made-up-key" not in json.dumps(ready) and "made-up-key" not in json.dumps(error)


def test_the_real_worker_runs_as_a_subprocess_against_the_made_up_service(tmp_path):
    service = MadeUpService(SPEECHMATICS, script={1: [transcript([word("made", 0.0, 0.2), word("up", 0.2, 0.4)], "made up")]})
    env = {**os.environ, "SPEECHMATICS_API_KEY": "made-up-key"}
    process = Worker([sys.executable, "-u", str(RUNNER), "speechmatics", service.address], log_path=tmp_path / "worker.log",
                     env=env, ready_timeout_s=30.0, request_timeout_s=30.0)
    try:
        process.start()
        assert process.wait_ready(), process.reason
        stamp = process.info["models"]["speechmatics"]
        assert stamp["address"] == worker.ADDRESS and stamp["model"] == "enhanced" and stamp["options"]["domain"] == "medical"
        assert "made-up-key" not in json.dumps(process.info)
        assert process.request({"type": "open", "session": "s1", "rate": 16000, "speakers": 1})["type"] == "opened"
        process.request({"type": "audio", "session": "s1"}, bytes(8000))
        time.sleep(0.3)
        reply = process.request({"type": "audio", "session": "s1"}, bytes(8000))
        assert [s["text"] for s in reply["segments"]] == ["made up"]
        stopped = process.request({"type": "stop", "session": "s1", "speakers": 1}, timeout_s=30.0)
        assert stopped["type"] == "stopped" and service.ended[0]["last_seq_no"] == 2
        assert "made-up-key" not in (tmp_path / "worker.log").read_text(errors="replace")
    finally:
        process.stop()
        service.stop()
