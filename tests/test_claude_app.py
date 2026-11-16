"""Claude behind the app's door (spec 15.13, rulings 15, 16, 19 and 21, the
details of run 9b; 15.10 rulings 25 and 36): the engine the benches used,
moved to where the app reads it, against a made service on this machine.
No key, no internet; what a model writes is never asserted."""

from __future__ import annotations

import json

import pytest

from openconsult.bench import claude as bench_claude
from openconsult.db import open_database
from openconsult.llm import claude
from openconsult.llm.claude import ENGINE_VERSION, NO_DIGEST, ClaudeEngine
from openconsult.llm.door import Door
from openconsult.llm.jobs import JOBS
from openconsult.llm.profile import CLAUDE, GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from tests.fakes import ALARM_QUIET, FakeEngine

MADE_KEY = "made-up-claude-key-9b-0123456789"
HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"
LIST_PATH = "/v1/models?limit=1000"


def listed():
    data = [{"id": tag, "type": "model", "max_input_tokens": 1000000} for tag in (HAIKU, SONNET)]
    return 200, {"data": data, "has_more": False}


def message(text, model, status=200):
    return status, {"id": "msg_made_up", "type": "message", "role": "assistant", "model": model,
                    "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                    "usage": {"input_tokens": 100, "output_tokens": 20}}


def serve(server, answer=None):
    server.routes[LIST_PATH] = listed()
    server.routes["/v1/messages"] = answer or (lambda body: message(json.dumps(ALARM_QUIET), body["model"]))
    return ClaudeEngine(server.address, MADE_KEY, expected=server.address)


def sent(server):
    return [body for path, body in server.received if path == "/v1/messages"]


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def test_15_13_ruling_15_the_messages_of_every_job_are_equal_on_the_local_path_and_on_the_claude_path(server, record):
    local_engine = FakeEngine()
    local, cloud = Door(local_engine, record, GEMMA_4_QAT), Door(serve(server), record, CLAUDE)
    for name in JOBS:
        user = f"made-up words for the job {name}"
        local.ask(name, user)
        cloud.ask(name, user)
    assert len(sent(server)) == len(local_engine.calls) == len(JOBS)
    for call, body in zip(local_engine.calls, sent(server)):
        # The same system text and the same user text, byte for byte; the engine's own fields apart.
        assert body["system"] == call.system and body["messages"] == [{"role": "user", "content": call.user}], call.job
        assert body["max_tokens"] == call.max_tokens and "temperature" not in body and "seed" not in body
        assert "effort" not in body["output_config"]                                  # the effort is not sent: the service's default


def test_15_10_ruling_36_claude_sonnet_does_the_drug_name_call_and_claude_haiku_every_other_from_the_profile_alone(server, record):
    door = Door(serve(server), record, CLAUDE)
    for name in JOBS:
        door.ask(name, "made-up words")
    by_job = dict(zip(JOBS, sent(server)))
    assert {name: body["model"] for name, body in by_job.items()} == {name: SONNET if name == "drug_name" else HAIKU for name in JOBS}
    assert CLAUDE.tag == HAIKU and CLAUDE.job_tags == {"drug_name": SONNET} and CLAUDE.tag_for("note") == HAIKU
    # Thinking is switched off by the service's own field for each model, as the bench sent it.
    assert by_job["drug_name"]["thinking"] == {"type": "between_tools"} and by_job["alarm"]["thinking"] == {"type": "disabled"}
    assert GEMMA_4_QAT.tag_for("drug_name") == GEMMA_4_QAT.tag                         # a local model does every job


def test_R19_each_models_room_is_read_from_the_services_list_once_and_a_model_the_list_does_not_name_is_never_called(server, record):
    door = Door(serve(server), record, CLAUDE)
    for name in ("alarm", "drug_name", "alarm", "drug_name", "note"):
        door.ask(name, "made-up words")
    assert [path for path, _ in server.received].count(LIST_PATH) == 4                 # for each of two models: its room once, its identity once
    assert len(sent(server)) == 5
    # The list names Claude Haiku alone: the drug-name call is not sent, and fails plainly (10.4).
    lone = Door(serve(server), record, CLAUDE)
    server.routes[LIST_PATH] = (200, {"data": [{"id": HAIKU, "type": "model", "max_input_tokens": 1000000}], "has_more": False})
    before = len(sent(server))
    failed = lone.ask("drug_name", "made-up words")
    assert not failed.ok and failed.failure == "unreachable" and len(sent(server)) == before
    assert lone.ask("alarm", "made-up words").ok


def test_R20_a_call_to_claude_records_the_service_the_model_as_the_reply_names_it_the_version_line_and_that_no_digest_is_given(server, record):
    named = "claude-haiku-5-5-made-up-date"
    door = Door(serve(server, lambda body: message(json.dumps(ALARM_QUIET), named)), record, CLAUDE)
    result = door.ask("alarm", "made-up words")
    row = record.get(result.call_id)
    assert result.ok and (row["engine"], row["engine_version"], row["model_digest"]) == ("claude", ENGINE_VERSION, NO_DIGEST)
    assert row["model_tag"] == named                                                   # the reply's own name, not the name asked for
    assert ENGINE_VERSION == "anthropic-version 2026-10-21, effort default"
    assert MADE_KEY not in json.dumps(row) and json.loads(row["request"])["model"] == HAIKU
    # A call that never got a reply keeps the name it asked for.
    server.routes["/v1/messages"] = (500, {"type": "error", "error": {"type": "api_error", "message": "made up"}})
    failed = record.get(door.ask("alarm", "made-up words").call_id)
    assert failed["outcome"] == "unreachable" and failed["model_tag"] == HAIKU


@pytest.mark.parametrize("status, body", [(401, {"type": "error", "error": {"type": "authentication_error", "message": "made up"}}),
                                          (400, {"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}}),
                                          (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "made up"}})])
def test_details_of_9b_the_apps_engine_sends_no_call_twice_never_waits_and_tries_the_next_call_after_a_refusal(server, record, status, body):
    engine = serve(server)
    door = Door(engine, record, CLAUDE)
    server.routes["/v1/messages"] = (status, body, {"retry-after": "30"})
    refused = [door.ask("alarm", "made-up words") for _ in range(4)]
    assert all(not r.ok and r.failure == "unreachable" and f"HTTP {status}" in r.detail for r in refused)
    assert len(sent(server)) == 4                                                      # one request for each call: none sent twice
    assert all(r.wall_ms < 5000 for r in refused)                                      # and nothing waited for the rate
    assert not hasattr(engine, "stopped") and door.stopped is None                     # the bench's stop is the bench's alone
    server.routes["/v1/messages"] = lambda sent_body: message(json.dumps(ALARM_QUIET), sent_body["model"])
    assert door.ask("alarm", "made-up words").ok and len(sent(server)) == 5            # the next call is tried and answers
    assert all(headers["x-api-key"] == MADE_KEY for (path, _), headers in zip(server.received, server.headers))


def test_details_of_9b_nothing_of_the_engine_is_written_twice_the_bench_kind_is_a_class_on_top_of_the_apps():
    assert issubclass(bench_claude.ClaudeEngine, ClaudeEngine) and bench_claude.ClaudeEngine is not ClaudeEngine
    for name in ("ADDRESS", "VERSION", "KEY_NAME", "NO_DIGEST", "TAKEN_OFF", "sent_form", "engine_version"):
        assert getattr(bench_claude, name) is getattr(claude, name), name
    with pytest.raises(claude.own_address.__globals__["AddressRefused"]):
        ClaudeEngine("https://api.anthropic.com.example", MADE_KEY)
    assert ClaudeEngine(key=MADE_KEY).address == "https://api.anthropic.com"
