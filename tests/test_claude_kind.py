"""The Claude kind of the bench, Claude Haiku 5.5 through the door (spec
15.13, rulings 14 to 17 and the details for run 9d; 7.3 rule 3; 10.4;
R19; R20; R30; R31). A made-up loopback server stands for the service;
every key here is made up; every reply is made up and nothing a model
said is asserted."""

import dataclasses
import json
import math
import subprocess
import sys
import threading
import time

import pytest

from openconsult.bench import claude, cloud, deepinfra
from openconsult.bench.cases import load_cases
from openconsult.bench.claude import ADDRESS, ENGINE_VERSION, KEY_NAME, NO_DIGEST, VERSION, ClaudeEngine, sent_form
from openconsult.bench.cli import CLOUD, KINDS, main
from openconsult.bench.cloud import AddressRefused
from openconsult.bench.replay import Chain, answer_text, run
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult.cds_pass import run_pass
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.llm import choose, forms
from openconsult.llm.door import Door
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.prompts import loader
from openconsult.settings import keys
from tests.fakes import ALARM_FIRES, ALARM_QUIET, ASSESSMENT, CALL, FakeEngine
from tests.test_bench import made_up_folder

MADE_KEY = "made-up-claude-key-0123456789"
TAG = CALL.tag
LIST_PATH = "/v1/models?limit=1000"
FORMS = ("alarm", "assessment", "referrals", "letter", "guideline", "label_check", "note")


def message_reply(text, stop="end_turn", thinking=None, input_tokens=100, output_tokens=20, headers=None, model=TAG):
    """A made reply in the Messages API shape."""
    content = ([{"type": "thinking", "thinking": thinking, "signature": "made-up"}] if thinking else []) + [{"type": "text", "text": text}]
    body = {"id": "msg_made_up", "type": "message", "role": "assistant", "model": model, "content": content, "stop_reason": stop,
            "stop_sequence": None, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                                             "output_tokens_details": {"thinking_tokens": 0}}}
    return (200, body, headers) if headers else (200, body)


def answer_by_form(body):
    """A reply that fits whichever job's form the request carries."""
    schema = body["output_config"]["format"]["schema"]
    return message_reply(json.dumps(ASSESSMENT if "differentials" in schema["properties"] else ALARM_QUIET))


def cloud_door(engine, record):
    return Door(engine, record, dataclasses.replace(GEMMA_4_QAT, tag=TAG, engine="claude"))


def listed(context=1000000, with_model=True):
    data = [{"id": "another-model", "type": "model", "max_input_tokens": 1}]
    if with_model:
        data.append({"id": TAG, "type": "model", "display_name": "Made-up", "created_at": "2026-10-07T18:00:00Z", "max_input_tokens": context})
    return 200, {"data": data, "has_more": False, "first_id": data[0]["id"], "last_id": data[-1]["id"]}


def serve(server, context=1000000, with_model=True, sleep=time.sleep):
    server.routes[LIST_PATH] = listed(context, with_model)
    server.routes["/v1/messages"] = answer_by_form
    return ClaudeEngine(server.address, MADE_KEY, expected=server.address, sleep=sleep)


def messages(server):
    return [(body, headers) for (path, body), headers in zip(server.received, server.headers) if path == "/v1/messages"]


def holds_no_key(*texts) -> bool:
    return all(MADE_KEY not in (t or "") for t in texts)


def key_folder_with_key(where):
    folder = where / "keys"
    folder.mkdir()
    (folder / keys.KEY_FILE).write_text(f"{KEY_NAME}={MADE_KEY}\n", encoding="utf-8")
    return folder


def strip_marks_and_put_back(sent: dict, original: dict) -> dict:
    """The sent form with the marks removed and the taken constraints put back from the original, path by path."""
    out = json.loads(json.dumps(sent))

    def walk(node, source):
        if not isinstance(node, dict):
            return
        node.pop("additionalProperties", None)
        for key in claude.TAKEN_OFF:
            if key in source:
                node[key] = source[key]
        for name, sub in node.get("properties", {}).items():
            walk(sub, source["properties"][name])
        if "items" in node:
            walk(node["items"], source["items"])

    walk(out, original)
    return out


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def test_15_13_the_kind_sends_the_messages_api_request_with_the_apps_words_and_the_passing_trys_fields(server, record):
    engine = serve(server)
    door = cloud_door(engine, record)
    result = door.ask("alarm", "made-up words")
    assert result.ok
    (body, headers), = messages(server)
    call = door.call_for("alarm", "made-up words")
    assert body == engine.build_request(call)
    assert set(body) == {"model", "max_tokens", "system", "messages", "output_config", "thinking"}   # the passing try's fields, nothing else
    assert body["system"] == call.system and body["messages"] == [{"role": "user", "content": call.user}]
    assert body["output_config"] == {"format": {"type": "json_schema", "schema": sent_form(call.form)}}
    assert body["thinking"] == {"type": "disabled"} and body["max_tokens"] == call.max_tokens == 1000 and body["model"] == TAG
    assert "effort" not in body["output_config"]                                               # the service's default stands (ruling 22)
    for absent in ("temperature", "seed", "top_k", "top_p", "min_p", "repetition_penalty", "presence_penalty", "frequency_penalty", "stream"):
        assert absent not in body
    assert headers["x-api-key"] == MADE_KEY and headers["anthropic-version"] == VERSION and headers["content-type"] == "application/json"
    # The GET for the list carries the key and the version too.
    assert all(h["x-api-key"] == MADE_KEY and h["anthropic-version"] == VERSION for (p, _), h in zip(server.received, server.headers) if p == LIST_PATH)
    row = record.get(result.call_id)
    assert holds_no_key(row["request"], row["reply"], row["detail"], json.dumps(row))
    assert "x-api-key" not in row["request"] and "x-api-key" not in (row["reply"] or "")
    assert row["prompt_tokens"] == 100 and row["output_tokens"] == 20 and row["load_ms"] == 0 and row["total_ms"] is not None


@pytest.mark.parametrize("name", FORMS)
def test_15_13_ruling_19_the_wire_copy_takes_off_only_maxItems_adds_only_the_marks_and_is_unchanged_in_effect(name, server, record):
    original = loader.form(name)
    sent = sent_form(original)
    objects, lists = [], []

    def walk(node, path="$"):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            objects.append(path)
            assert node["additionalProperties"] is False
        if node.get("type") == "array":
            lists.append(path)
        assert "maxItems" not in node
        for key, sub in node.get("properties", {}).items():
            walk(sub, f"{path}.{key}")
        walk(node.get("items"), path + "[]")

    walk(sent)
    assert objects                                                                # every form is an object
    assert strip_marks_and_put_back(sent, original) == original                   # nothing else was touched
    assert sent_form(original) == sent and loader.form(name) == original          # the file's own form is not changed
    if name == "alarm":
        # Ruling 19: the alarm form carries no maxItems, so nothing is taken off its list for the wire; the marks alone are added.
        assert "maxItems" not in original["properties"]["urgent_actions"]
        assert {k: v for k, v in sent["properties"]["urgent_actions"].items() if k != "items"} == {
            k: v for k, v in original["properties"]["urgent_actions"].items() if k != "items"}
    if name == "letter":
        # The service holds no maxItems and the door no longer judges it: a reply past the file's number is an answer.
        engine = serve(server)
        over = {"reasoning": "made", "paragraphs": [{"text": "Made up.", "note_lines": [2]}] * (original["properties"]["paragraphs"]["maxItems"] + 1)}
        server.routes["/v1/messages"] = message_reply(json.dumps(over))
        result = cloud_door(engine, record).ask("letter", "words")
        assert result.ok and result.answer == over and forms.misfit(over, original) is None
        assert record.get(result.call_id)["outcome"] == "ok"


def test_7_3_rule_3_the_key_is_read_from_the_key_folder_by_the_one_module_and_written_nowhere(server, bench_folders, capsys, tmp_path, monkeypatch):
    cases, out = bench_folders
    serve(server)
    monkeypatch.setattr(claude, "ADDRESS", server.address)                                 # the made service in the service's place
    key_folder = tmp_path / "keys"
    key_folder.mkdir()
    common = ["run", "--cases", str(cases), "--case", "seven", "--chains", "A1", "--kind", "claude",
              "--engine", server.address, "--model", TAG, "--digest", NO_DIGEST]
    assert main([*common, "--out", str(out), "--key-folder", str(key_folder)]) == 10
    said = capsys.readouterr().out
    assert KEY_NAME in said and str(key_folder) in said and messages(server) == []
    assert main([*common, "--out", str(out)]) == 10
    (key_folder / keys.KEY_FILE).write_text(f"{KEY_NAME}={MADE_KEY}\n", encoding="utf-8")
    assert main([*common, "--out", str(key_folder / "out"), "--key-folder", str(key_folder)]) == 6
    assert messages(server) == []
    assert main([*common, "--out", str(out), "--key-folder", str(key_folder)]) == 0
    said = capsys.readouterr().out
    assert messages(server) and all(h["x-api-key"] == MADE_KEY for _, h in messages(server))
    assert holds_no_key(said)
    result = ResultWriter(out).read("seven", "A1")
    assert (result["engine"], result["engine_version"], result["model_tag"], result["model_digest"]) == ("claude", ENGINE_VERSION, TAG, NO_DIGEST)
    assert holds_no_key(json.dumps(result))
    for row in ModelCalls(open_database(out / "calls.db")).rows():
        assert holds_no_key(json.dumps(row)) and row["engine"] == "claude"
    assert all(MADE_KEY not in part for part in common)


def test_R20_a_cloud_call_records_the_service_the_api_version_the_model_and_the_line_that_no_digest_is_given(server, record, bench_folders, capsys, monkeypatch):
    engine = serve(server)
    row = record.get(cloud_door(engine, record).ask("alarm", "words").call_id)
    assert (row["engine"], row["engine_version"], row["model_tag"], row["model_digest"]) == ("claude", ENGINE_VERSION, TAG, NO_DIGEST)
    assert ENGINE_VERSION == "anthropic-version 2026-10-21, effort default" and engine.model_digest("not-listed") is None
    cases, out = bench_folders
    monkeypatch.setattr(claude, "ADDRESS", server.address)
    key_folder = key_folder_with_key(out.parent)
    run_args = ["run", "--cases", str(cases), "--out", str(out), "--case", "seven", "--chains", "A1", "--kind", "claude",
                "--engine", server.address, "--model", TAG, "--key-folder", str(key_folder)]
    sent = len(messages(server))
    assert main([*run_args, "--digest", "made-up-digest"]) == 3
    serve(server, with_model=False)
    assert main([*run_args, "--digest", NO_DIGEST]) == 2
    assert len(messages(server)) == sent
    serve(server)
    assert main([*run_args, "--digest", NO_DIGEST]) == 0
    assert ResultWriter(out).read("seven", "A1")["model_digest"] == NO_DIGEST
    capsys.readouterr()


def test_R19_the_fit_rule_reads_the_services_context_from_its_list_and_the_arm_is_not_refused_for_it(server, record):
    engine = serve(server, context=100)
    small = cloud_door(engine, record).ask("alarm", "words")
    assert not small.ok and small.failure == "unreachable" and "context of 100" in small.detail and messages(server) == []
    engine = serve(server)
    door = cloud_door(engine, record)
    assert engine.context(TAG) == 1000000 and door.ask("alarm", "words").ok and len(messages(server)) == 1
    status = engine.status(TAG)
    assert status.running and status.context is None and status.digest == NO_DIGEST and status.version == ENGINE_VERSION
    assert not serve(server, with_model=False).status(TAG).running
    engine = serve(server)
    server.routes["/v1/messages"] = (400, {"type": "error", "error": {"type": "invalid_request_error", "message": "made-up: prompt is too long"}})
    assert cloud_door(engine, record).ask("alarm", "words").failure == "did_not_fit"


def test_10_4_a_failed_cloud_call_fails_plainly_and_no_local_engine_is_tried(server, record):
    engine = serve(server)
    door = cloud_door(engine, record)
    for status in (500, 529):
        server.routes["/v1/messages"] = (status, {"type": "error", "error": {"type": "made-up", "message": "the service fell over"}})
        failed = door.ask("alarm", "words")
        assert not failed.ok and failed.failure == "unreachable" and f"HTTP {status}" in failed.detail and holds_no_key(failed.detail)
        assert engine.stopped is None
    assert len(messages(server)) == 2                                                   # one try each, no other engine
    server.routes["/v1/messages"] = message_reply("I cannot help with that.", stop="refusal")
    refused = door.ask("alarm", "words")
    assert refused.failure == "unreachable" and "stop_reason refusal" in refused.detail and engine.stopped is None
    server.routes["/v1/messages"] = message_reply('{"reasoning": "cut off', stop="max_tokens")
    cut = door.ask("alarm", "words")
    assert cut.failure == "too_long" and "1000 tokens" in cut.detail
    server.stop()
    gone = door.ask("alarm", "words")
    assert gone.failure == "unreachable" and holds_no_key(gone.detail)
    assert record.get(gone.call_id)["outcome"] == "unreachable"


def test_R30_a_failed_cloud_call_never_stops_the_pass(server, record):
    engine = serve(server)

    def alarm_fails(body):
        if "differentials" not in body["output_config"]["format"]["schema"]["properties"]:
            return 500, {"type": "error", "error": {"message": "made-up: the service fell over"}}
        return message_reply(json.dumps(ASSESSMENT))

    server.routes["/v1/messages"] = alarm_fails
    result = run_pass(cloud_door(engine, record), "made-up transcript", Patient(40, "M"))
    assert not result.alarm.judged and result.alarm.failure == "unreachable"
    assert result.assessment.ok and [d["condition"] for d in result.assessment.differentials] == ["Made-up condition A", "Made-up condition B"]
    assert len(messages(server)) == 2


@pytest.mark.parametrize("answer", [(401, {"type": "error", "error": {"type": "authentication_error", "message": "made-up: invalid key"}}),
                                    (403, {"type": "error", "error": {"type": "permission_error", "message": "made-up: not allowed"}}),
                                    (400, {"type": "error", "error": {"type": "invalid_request_error", "message": "made-up: your credit balance is too low"}})])
def test_15_13_a_refused_key_or_used_up_credit_stops_the_run_and_the_chain_is_written_apart(server, record, tmp_path, answer):
    engine = serve(server)
    server.routes["/v1/messages"] = answer
    door = cloud_door(engine, record)
    first = door.ask("alarm", "words")
    assert first.failure == "unreachable" and f"HTTP {answer[0]}" in first.detail
    second = door.ask("alarm", "words")
    assert second.failure == "unreachable" and str(answer[0]) in second.detail and holds_no_key(second.detail)
    assert len(messages(server)) == 1 and door.stopped == engine.stopped == cloud.stop_line(answer[0])
    engine = serve(server)
    server.routes["/v1/messages"] = answer
    cases = [c for c in load_cases(made_up_folder(tmp_path)) if c.name == "madeup"]
    writer = ResultWriter(tmp_path / "out")
    summary = run(cloud_door(engine, record), cases, writer, [Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)], log=lambda line: None)
    assert summary["stopped"] == engine.stopped and summary["run"] == 0
    assert not writer.exists("madeup", "A1") and writer.path_apart("madeup", "A1").is_file() and writer.read_all() == {}
    done = run(cloud_door(serve(server), record), cases, writer, [Chain("A1", 0.0, 42)], log=lambda line: None)
    assert done["run"] == 1 and "stopped" not in done and writer.exists("madeup", "A1")
    with pytest.raises(Refused):
        writer.write_apart("madeup", "A1", {})


def reset_in(seconds: float) -> str:
    """A reset header at least that far ahead: the service gives whole seconds, so the moment is rounded up."""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(math.ceil(time.time() + seconds))) + "Z"


def test_15_13_the_rate_is_kept_by_waiting_before_a_call_by_the_services_own_headers_and_no_call_is_sent_twice(server, record):
    slept = []
    engine = serve(server, sleep=lambda s: (slept.append(s), time.sleep(s)))
    door = cloud_door(engine, record)
    # A reply whose headers say one request remains, with the reset 0.4 s away: the next call waits until then.
    server.routes["/v1/messages"] = message_reply(json.dumps(ALARM_QUIET), headers={
        "anthropic-ratelimit-requests-limit": "4000", "anthropic-ratelimit-requests-remaining": "1",
        "anthropic-ratelimit-requests-reset": reset_in(0.4), "anthropic-ratelimit-tokens-remaining": "2000000"})
    first = door.ask("alarm", "words")
    assert first.ok and record.get(first.call_id)["load_ms"] == 0 and slept == []
    server.routes["/v1/messages"] = message_reply(json.dumps(ALARM_QUIET))
    before = time.time()
    second = door.ask("alarm", "words")
    row = record.get(second.call_id)
    assert second.ok and len(slept) == 1 and 0.3 <= slept[0] <= 2.0 and row["load_ms"] >= 300 and time.time() - before >= 0.3
    assert row["total_ms"] is not None and row["total_ms"] < row["load_ms"]                # the exchange alone, apart from the wait
    assert len(messages(server)) == 2
    # A 429 is one failed call, stored and counted, never resent; the next call waits the retry-after.
    slept.clear()
    server.routes["/v1/messages"] = (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "made-up: too fast"}}, {"retry-after": "0.3"})
    refused = door.ask("alarm", "words")
    assert refused.failure == "unreachable" and "HTTP 429" in refused.detail and len(messages(server)) == 3 and engine.stopped is None
    assert record.get(refused.call_id)["outcome"] == "unreachable"
    server.routes["/v1/messages"] = message_reply(json.dumps(ALARM_QUIET))
    ok = door.ask("alarm", "words")
    assert ok.ok and len(slept) == 1 and 0.2 <= slept[0] <= 1.5 and record.get(ok.call_id)["load_ms"] >= 200
    # Two 429 then a 200 reset the count; three in a row stop the run and a fourth call is not sent.
    server.routes["/v1/messages"] = (429, {"type": "error", "error": {"message": "made-up: too fast"}}, {"retry-after": "0"})
    door.ask("alarm", "words"), door.ask("alarm", "words")
    assert engine.stopped is None
    server.routes["/v1/messages"] = message_reply(json.dumps(ALARM_QUIET))
    assert door.ask("alarm", "words").ok
    server.routes["/v1/messages"] = (429, {"type": "error", "error": {"message": "made-up: too fast"}}, {"retry-after": "0"})
    for _ in range(3):
        door.ask("alarm", "words")
    sent = len(messages(server))
    assert engine.stopped and "3 times in a row" in engine.stopped and door.stopped == engine.stopped
    assert door.ask("alarm", "words").failure == "unreachable" and len(messages(server)) == sent


def test_15_13_ruling_22_the_effort_is_one_field_of_the_request_held_in_the_record_and_the_claude_kinds_alone(server, record, bench_folders, capsys, monkeypatch):
    """The effort test of run 9d2 (15.13, ruling 22): the two arms differ in output_config.effort alone; the record
    holds the effort in engine_version beside the API version on every call; the setting is the Claude kind's."""
    plain, low = serve(server), ClaudeEngine(server.address, MADE_KEY, expected=server.address, effort="low")
    call = cloud_door(plain, record).call_for("alarm", "made-up words")
    a, b = plain.build_request(call), low.build_request(call)
    assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} == {"output_config"}
    assert {k for k in set(a["output_config"]) | set(b["output_config"]) if a["output_config"].get(k) != b["output_config"].get(k)} == {"effort"}
    assert "effort" not in a["output_config"] and b["output_config"]["effort"] == "low" and b["output_config"]["format"] == a["output_config"]["format"]
    low_row = record.get(cloud_door(low, record).ask("alarm", "made-up words").call_id)
    plain_row = record.get(cloud_door(plain, record).ask("alarm", "made-up words").call_id)
    assert low_row["engine_version"] == "anthropic-version 2026-10-21, effort low" and json.loads(low_row["request"])["output_config"]["effort"] == "low"
    assert plain_row["engine_version"] == ENGINE_VERSION == "anthropic-version 2026-10-21, effort default"
    assert "effort" not in json.loads(plain_row["request"])["output_config"]
    assert low.status(TAG).version == low_row["engine_version"] and claude.engine_version("high") == "anthropic-version 2026-10-21, effort high"
    with pytest.raises(ValueError):
        ClaudeEngine(server.address, MADE_KEY, expected=server.address, effort="loud")
    # The bench: --effort low on every request and in the stamp of every result; another kind refuses the flag before any call.
    cases, out = bench_folders
    monkeypatch.setattr(claude, "ADDRESS", server.address)
    key_folder = key_folder_with_key(out.parent)
    common = ["run", "--cases", str(cases), "--case", "seven", "--chains", "A1", "--engine", server.address, "--model", TAG]
    sent = len(messages(server))
    assert main([*common, "--kind", "vllm", "--out", str(out / "vllm"), "--effort", "low"]) == 10
    assert "--effort" in capsys.readouterr().out and len(messages(server)) == sent
    assert main([*common, "--kind", "claude", "--out", str(out), "--digest", NO_DIGEST, "--key-folder", str(key_folder), "--effort", "low"]) == 0
    assert ResultWriter(out).read("seven", "A1")["engine_version"] == "anthropic-version 2026-10-21, effort low"
    assert all(body["output_config"]["effort"] == "low" for body, _ in messages(server)[sent:]) and len(messages(server)) > sent
    capsys.readouterr()


def test_15_13_the_two_calls_of_a_pass_are_still_sent_together(server, record):
    engine = serve(server)
    arrived, alarm_answered = {}, threading.Event()

    def hold_the_alarm(body):
        if "differentials" in body["output_config"]["format"]["schema"]["properties"]:
            arrived["assessment"] = time.perf_counter()
            return message_reply(json.dumps(ASSESSMENT))
        arrived["alarm"] = time.perf_counter()
        time.sleep(0.3)
        alarm_answered.set()
        return message_reply(json.dumps(ALARM_QUIET))

    server.routes["/v1/messages"] = hold_the_alarm
    result = run_pass(cloud_door(engine, record), "made-up transcript", Patient(40, "M"))
    assert result.alarm.judged and result.assessment.ok
    assert abs(arrived["assessment"] - arrived["alarm"]) < 0.25                           # both left before the alarm's reply


@pytest.mark.parametrize("machine", ["linux-card", "linux-none", "windows-card", "mac"])
def test_rule_6_the_app_cannot_reach_the_cloud_kinds(machine, tmp_path):
    from openconsult.settings.machine import Card, describe
    described = {"linux-card": describe("Linux", "x86_64", [Card("Made-up card", 24564)]), "linux-none": describe("Linux", "x86_64", []),
                 "windows-card": describe("Windows", "AMD64", [Card("Made-up card", 24564)]), "mac": describe("Darwin", "arm64", [])}[machine]
    assert not {"claude", "deepinfra"} & set(choose.order_for(described)) and not {"claude", "deepinfra"} & set(choose.ORDER)
    assert set(KINDS) == {"ollama", "llamacpp", "vllm", "deepinfra", "claude"} and set(CLOUD) == {"deepinfra", "claude"}
    code = ("import sys\n"
            "from openconsult.app import build_app\n"
            "from openconsult.settings import store\n"
            "from openconsult.settings.machine import describe\n"
            "app = build_app(store.build(sys.argv[1], 8765), machine=describe('Linux', 'x86_64', []))\n"
            "print(sorted(name for name in sys.modules if name.startswith('openconsult.bench') or 'claude' in name))\n")
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


@pytest.mark.parametrize("address", ["http://api.anthropic.com", "https://api.anthropic.com.example", "http://127.0.0.1:1",
                                     "https://api.anthropic.com/v1"])
def test_15_13_the_kind_speaks_to_the_services_own_address_over_https_only(address, server):
    with pytest.raises(AddressRefused):
        ClaudeEngine(address, MADE_KEY)
    with pytest.raises(AddressRefused):
        ClaudeEngine(server.address, MADE_KEY)
    assert server.received == []
    assert ClaudeEngine(ADDRESS, MADE_KEY).address == ADDRESS == "https://api.anthropic.com"
    assert ClaudeEngine(ADDRESS + "/", MADE_KEY).address == ADDRESS


def test_15_13_what_the_two_cloud_kinds_share_is_in_one_place():
    assert claude.AddressRefused is deepinfra.AddressRefused is cloud.AddressRefused if hasattr(claude, "AddressRefused") else True
    assert issubclass(ClaudeEngine, cloud.Stops) and issubclass(deepinfra.DeepInfraEngine, cloud.Stops)
    for module in (claude, deepinfra):
        assert module.own_address is cloud.own_address and module.stop_line is cloud.stop_line
    assert CLOUD == {"deepinfra": cloud.CloudKind(deepinfra.DeepInfraEngine, "DEEPINFRA_API_KEY"), "claude": cloud.CloudKind(ClaudeEngine, "ANTHROPIC_API_KEY")}
    for address, expected in (("https://api.anthropic.com/", "https://api.anthropic.com"), ("https://api.deepinfra.com", "https://api.deepinfra.com")):
        assert cloud.own_address(address, expected) == expected
    with pytest.raises(AddressRefused):
        cloud.own_address("https://api.anthropic.com", "https://api.deepinfra.com")


def test_15_13_the_example_settings_file_names_the_two_language_model_keys_with_no_value():
    from openconsult.bench.cli import REPO
    found = keys.parse_env((REPO / ".env.example").read_text(encoding="utf-8"))
    assert found[KEY_NAME] == "" and found[deepinfra.KEY_NAME] == "" and all(value == "" for value in found.values())
    assert set(found) == {"SPEECHMATICS_API_KEY", "ASSEMBLYAI_API_KEY", deepinfra.KEY_NAME, KEY_NAME}


def test_15_13_the_record_check_reads_thinking_in_a_reply_of_any_of_the_three_shapes():
    made = message_reply("{}", thinking="made-up thought")[1]
    assert answer_text(json.dumps(made)) == ("{}", "made-up thought")
    assert answer_text(json.dumps(message_reply("{}")[1])) == ("{}", None)
    redacted = {"type": "message", "content": [{"type": "redacted_thinking", "data": "made-up"}, {"type": "text", "text": "{}"}]}
    assert answer_text(json.dumps(redacted)) == ("{}", "redacted thinking")
    assert answer_text(json.dumps({"type": "message", "content": [{"type": "thinking", "thinking": "only"}]})) == (None, "only")
    assert answer_text(json.dumps({"message": {"content": "{}", "thinking": "made-up thought"}})) == ("{}", "made-up thought")
    assert answer_text(json.dumps({"choices": [{"message": {"content": "{}", "reasoning_content": "made-up"}}]})) == ("{}", "made-up")
    assert answer_text("not json") == (None, None)
    # A made engine of the suite is untouched by the new shape.
    assert FakeEngine().name == "made-up"
