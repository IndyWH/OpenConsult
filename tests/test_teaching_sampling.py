"""What each engine is sent for a fresh case (spec 15.14, the details of
run 10a: Sampling; 10.4; R20): the case's own temperature and seed on the
local engines, kept in the record; the profile's for every other job;
nothing of either to Claude. Made engines and a made service."""

import dataclasses
import json

import pytest

from openconsult.db import open_database
from openconsult.llm import claude
from openconsult.llm.claude import ClaudeEngine
from openconsult.llm.door import Door
from openconsult.llm.ollama import OllamaEngine
from openconsult.llm.profile import CLAUDE, GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.llm.vllm import VllmEngine
from openconsult.prompts import loader
from openconsult.teaching import frames
from tests.fakes import CALL, chat_reply, describe
from tests.made_teaching import FITS


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def test_15_14_the_cases_sampling_reaches_each_local_engine_and_the_record_and_claude_is_sent_none(server, record, monkeypatch):
    monkeypatch.setattr(frames.secrets, "randbelow", lambda below: 1234567)
    sampling = frames.case_sampling()
    words = frames.case_message("A made-up topic", "hidden")
    # vLLM: the temperature and the seed beside its fixed values.
    describe(server, VllmEngine)
    server.routes["/v1/chat/completions"] = lambda body: chat_reply(json.dumps(FITS[body["response_format"]["json_schema"]["name"]]))
    vllm = Door(VllmEngine(server.address), record, dataclasses.replace(GEMMA_4_QAT, tag=CALL.tag, engine="vllm"))
    assert vllm.ask("teaching_case", words, sampling).ok and vllm.ask("teaching_patient", "made-up words").ok
    case_body, patient_body = server.chats()
    assert (case_body["temperature"], case_body["seed"], case_body["max_tokens"]) == (0.7, 1234567, 4000)
    assert (patient_body["temperature"], patient_body["seed"], patient_body["max_tokens"]) == (0.0, 42, 300)       # the profile's (10.4)
    assert case_body["messages"] == [{"role": "system", "content": loader.prompt("teaching_case")}, {"role": "user", "content": words}]
    stored = json.loads(record.rows(newest_first=False)[0]["request"])
    assert (stored["temperature"], stored["seed"]) == (0.7, 1234567)                                                # kept in the record of the call (R20)
    # Ollama: the same two in its options.
    server.routes["/api/version"] = (200, {"version": "0.0-made-up"})
    server.routes["/api/tags"] = (200, {"models": [{"name": GEMMA_4_QAT.tag, "digest": "made-up-digest"}]})
    server.routes["/api/chat"] = lambda body: (200, {"message": {"content": json.dumps(FITS["teaching_case"])}, "done_reason": "stop"})
    ollama = Door(OllamaEngine(server.address), record, GEMMA_4_QAT)
    assert ollama.ask("teaching_case", words, sampling).ok
    options = [body for path, body in server.received if path == "/api/chat"][0]["options"]
    assert (options["temperature"], options["seed"], options["num_predict"]) == (0.7, 1234567, 4000)
    # Claude: no temperature and no seed, whatever sampling the case carries.
    server.routes["/v1/models?limit=1000"] = (200, {"data": [{"id": CLAUDE.tag, "type": "model", "max_input_tokens": 1000000}]})
    server.routes["/v1/messages"] = lambda body: (200, {"type": "message", "role": "assistant", "model": body["model"], "stop_reason": "end_turn",
                                                        "content": [{"type": "text", "text": json.dumps(FITS["teaching_case"])}],
                                                        "usage": {"input_tokens": 100, "output_tokens": 20}})
    cloud = Door(ClaudeEngine(server.address, "made-up-key-10a-0123456789", expected=server.address), record, CLAUDE)
    assert cloud.ask("teaching_case", words, sampling).ok
    sent = [body for path, body in server.received if path == "/v1/messages"][0]
    assert "temperature" not in sent and "seed" not in sent and sent["model"] == "claude-haiku-5-5" and sent["max_tokens"] == 4000
    assert sent["system"] == loader.prompt("teaching_case") and sent["messages"] == [{"role": "user", "content": words}]
    assert sent["output_config"]["format"]["schema"] == claude.sent_form(loader.form("teaching_case"))
