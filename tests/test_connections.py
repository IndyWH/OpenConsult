"""The test of a connection (spec 7.2; 15.13, the details of run 9b),
against made services on this machine: Claude's two small requests, and
the Speechmatics session that is opened and ended with no sound. No key,
no internet; the words of a reply are never read."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from openconsult.db import open_database
from openconsult.llm import claude
from openconsult.llm.claude import ClaudeEngine
from openconsult.llm.record import ModelCalls
from openconsult.settings import connections
from openconsult.settings.connections import test_claude as check_claude, test_speechmatics as check_speechmatics
from openconsult.speech.worker import Worker
from tests.made_up_service import SPEECHMATICS, MadeUpService

MADE_KEY = "made-up-key-for-the-test-of-a-connection"
RUNNER = Path(__file__).parent / "made_up_dial.py"
OK = (200, {"id": "msg_made_up", "type": "message", "role": "assistant", "model": "made-up-name", "content": [{"type": "text", "text": "made up"}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 11, "output_tokens": 4}})


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def engine_at(server) -> ClaudeEngine:
    return ClaudeEngine(server.address, MADE_KEY, expected=server.address)


def test_details_of_9b_the_test_of_claude_is_two_small_requests_one_for_each_model_with_the_owners_six_words_and_nothing_else(server, record):
    server.routes["/v1/messages"] = OK
    tested = check_claude(MADE_KEY, record, engine_at(server))
    assert tested.ok and tested.reason is None and tested.sentence is None and tested.service == "claude"
    sent = sorted((body for path, body in server.received), key=lambda body: body["model"])
    # The two requests, in full, as the plan gave them and the owner approved the words (16 Nov 2026).
    assert sent == [
        {"model": "claude-haiku-5-5", "max_tokens": 8, "messages": [{"role": "user", "content": "Connection test. Reply with OK."}],
         "thinking": {"type": "disabled"}},
        {"model": "claude-sonnet-5-5", "max_tokens": 8, "messages": [{"role": "user", "content": "Connection test. Reply with OK."}],
         "thinking": {"type": "between_tools"}}]
    assert [path for path, _ in server.received] == ["/v1/messages", "/v1/messages"]       # nothing else is asked: no list, no second try
    assert all(h["x-api-key"] == MADE_KEY and h["anthropic-version"] == claude.VERSION for h in server.headers)
    # R20: each request is in the record of model calls, with what was sent and what came back, and never the key.
    rows = [record.get(call_id) for call_id in tested.call_ids]
    assert len(rows) == 2 and {row["job"] for row in rows} == {"connection_test"} and all(row["outcome"] == "ok" for row in rows)
    assert all(row["engine"] == "claude" and row["model_tag"] == "made-up-name" and row["consultation_id"] is None for row in rows)
    assert sorted(json.loads(row["request"])["model"] for row in rows) == ["claude-haiku-5-5", "claude-sonnet-5-5"]
    assert all((row["prompt_tokens"], row["output_tokens"]) == (11, 4) for row in rows)
    assert MADE_KEY not in json.dumps(rows) and MADE_KEY not in repr(tested)
    # The words are the test's alone: no job of the app sends them.
    assert claude.TEST_WORDS == "Connection test. Reply with OK." and claude.TEST_JOB not in __import__("openconsult.llm.jobs", fromlist=["JOBS"]).JOBS


CLAUDE_FAILURES = [
    ((401, {"type": "error", "error": {"type": "authentication_error", "message": "made up"}}), "key_refused", "Claude refused the key. Check the key and try again."),
    ((403, {"type": "error", "error": {"type": "permission_error", "message": "made up"}}), "key_refused", "Claude refused the key. Check the key and try again."),
    ((400, {"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low to access the API."}}), "no_credit",
     "Claude refused to start: the account has no credit left."),
    ((402, {"type": "error", "error": {"type": "billing_error", "message": "made up"}}), "no_credit", "Claude refused to start: the account has no credit left."),
    ((429, {"type": "error", "error": {"type": "rate_limit_error", "message": "made up"}}), "limit_reached", "Claude refused to start: a limit on the account was reached."),
    ((500, {"type": "error", "error": {"type": "api_error", "message": "made up"}}), "service_down", "Claude is not answering. Try again later."),
    ((529, {"type": "error", "error": {"type": "overloaded_error", "message": "made up"}}), "service_down", "Claude is not answering. Try again later."),
    ((404, {"type": "error", "error": {"type": "not_found_error", "message": "made up"}}), "service_down", "Claude is not answering. Try again later."),
]


@pytest.mark.parametrize("answer, reason, sentence", CLAUDE_FAILURES)
def test_7_2_each_answer_of_claude_that_is_not_a_pass_has_its_exact_reason_in_one_sentence(server, record, answer, reason, sentence):
    # One model answers and the other does not: the test fails with the reason of the one that failed.
    server.routes["/v1/messages"] = lambda body: OK if body["model"] == "claude-haiku-5-5" else answer
    tested = check_claude(MADE_KEY, record, engine_at(server))
    assert (tested.ok, tested.reason, tested.sentence) == (False, reason, sentence)
    assert tested.detail == f"claude-sonnet-5-5: HTTP {answer[0]}" and len(server.received) == 2          # each asked once, never again
    outcomes = sorted(record.get(call_id)["outcome"] for call_id in tested.call_ids)
    assert outcomes == ["ok", "unreachable"] and MADE_KEY not in json.dumps([record.get(i) for i in tested.call_ids])


def test_7_2_no_internet_and_a_service_too_slow_are_said_as_what_they_are(server, record):
    gone = ClaudeEngine("http://127.0.0.1:9", MADE_KEY, expected="http://127.0.0.1:9")                      # nothing listens there
    tested = check_claude(MADE_KEY, record, gone)
    assert (tested.reason, tested.sentence) == ("no_internet", "Claude could not be reached. Check the internet connection and try again.")

    def slow(body):
        time.sleep(1.0)
        return OK

    server.routes["/v1/messages"] = slow
    started = time.perf_counter()
    tested = check_claude(MADE_KEY, record, engine_at(server), limit_s=0.2)
    assert tested.reason == "too_slow" and time.perf_counter() - started < 0.9                              # the limit holds the wait
    assert tested.sentence == "Claude did not answer within 10 seconds. Try again."                         # the app's own limit is 10 s
    assert connections.LIMIT_S == 10.0
    assert {record.get(i)["outcome"] for i in tested.call_ids} == {"too_slow"}


# ------------------------------------------------------------ Speechmatics

def made_worker(service, tmp_path):
    """The Speechmatics worker's own code, as a process of its own, dialling the made service."""
    import os
    env = {**os.environ, "SPEECHMATICS_API_KEY": MADE_KEY}
    return lambda: Worker([sys.executable, "-u", str(RUNNER), "speechmatics", service.address], log_path=tmp_path / "worker.log", env=env)


def test_details_of_9b_the_test_of_speechmatics_opens_a_session_with_the_apps_own_settings_and_ends_it_with_no_sound_sent(tmp_path):
    service = MadeUpService(SPEECHMATICS)
    try:
        tested = check_speechmatics(MADE_KEY, tmp_path, make_worker=made_worker(service, tmp_path))
        assert tested.ok and tested.service == "speechmatics" and tested.sentence is None
        assert service.connections == 1 and service.audio == [] and service.ended == []                    # no sound, and no end of a stream
        # The opening message is the one a consultation sends (15.9, rulings 9 and 32).
        assert service.openings == [{"message": "StartRecognition", "audio_format": {"type": "raw", "encoding": "pcm_s16le", "sample_rate": 48000},
                                     "transcription_config": {"language": "en", "model": "enhanced", "domain": "medical", "diarization": "speaker",
                                                              "enable_partials": True, "speaker_diarization_config": {"max_speakers": 2}}}]
        assert service.handshakes[0]["headers"]["authorization"] == f"Bearer {MADE_KEY}"
        assert MADE_KEY not in (tmp_path / "worker.log").read_text(encoding="utf-8") and MADE_KEY not in repr(tested)
    finally:
        service.stop()


@pytest.mark.parametrize("mode, reason, sentence", [
    ("refuse_handshake 401", "key_refused", "Speechmatics refused the key. Check the key and try again."),
    ("refuse_handshake 402", "no_credit", "Speechmatics refused to start: the account has no credit left."),
    ("refuse_handshake 429", "limit_reached", "Speechmatics refused to start: a limit on the account was reached."),
    ("refuse_handshake 503", "service_down", "Speechmatics is not answering. Try again later."),
    ("error", "key_refused", "Speechmatics refused the key. Check the key and try again."),          # the service's own error after the opening
])
def test_7_2_each_refusal_of_speechmatics_has_its_exact_reason_and_no_sound_is_sent(tmp_path, mode, reason, sentence):
    service = MadeUpService(SPEECHMATICS, mode=mode)
    try:
        tested = check_speechmatics(MADE_KEY, tmp_path, make_worker=made_worker(service, tmp_path))
        assert (tested.ok, tested.reason, tested.sentence) == (False, reason, sentence)
        assert service.audio == [] and MADE_KEY not in repr(tested)
    finally:
        service.stop()


def test_7_2_speechmatics_not_reached_and_too_slow(tmp_path):
    service = MadeUpService(SPEECHMATICS)
    service.stop()                                                                                         # nothing listens at its address now
    tested = check_speechmatics(MADE_KEY, tmp_path, make_worker=made_worker(service, tmp_path))
    assert (tested.reason, tested.sentence) == ("no_internet", "Speechmatics could not be reached. Check the internet connection and try again.")
    quiet = MadeUpService(SPEECHMATICS, mode="quiet")                                                      # a line that never answers the opening
    try:
        started = time.perf_counter()
        tested = check_speechmatics(MADE_KEY, tmp_path, make_worker=made_worker(quiet, tmp_path), limit_s=1.5)
        assert tested.reason == "too_slow" and time.perf_counter() - started < 8
        assert tested.sentence == "Speechmatics did not answer within 10 seconds. Try again."
    finally:
        quiet.stop()
