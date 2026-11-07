"""The DeepInfra kind of the bench, Gemma 4 26B through the door (spec
15.13, ruling 11 and the details for run 9a2; 7.3 rule 3; 10.4; R19;
R20; R30; R31). A made-up loopback server stands for the host; every key
here is made up; every reply is made up and nothing a model said is
asserted."""

import dataclasses
import json
import subprocess
import sys

import pytest

from openconsult import app as app_module
from openconsult.bench import deepinfra, guideline, letters
from openconsult.bench.cases import load_cases
from openconsult.bench.cli import KINDS, main
from openconsult.bench.deepinfra import ADDRESS, KEY_NAME, NO_DIGEST, NO_VERSION, AddressRefused, DeepInfraEngine
from openconsult.bench.replay import Chain, answer_text, run
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult.cds_pass import run_pass
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.llm import choose
from openconsult.llm.chat_engine import ChatEngine
from openconsult.llm.door import Door
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.llm.vllm import VllmEngine
from openconsult.settings import keys
from openconsult.settings.machine import Card, describe
from tests.fakes import ALARM_QUIET, ASSESSMENT, CALL, FakeEngine, chat_reply
from tests.test_bench import made_up_folder

MADE_KEY = "made-up-cloud-key-0123456789"
TAG = CALL.tag
# The fields of the gate's passing try, and the six the vLLM arm sends (the plan review, point 1).
GATE_FIELDS = {"model", "messages", "response_format", "chat_template_kwargs", "temperature", "seed", "max_tokens", "stream"}
SIX = {"top_k": 64, "top_p": 0.95, "min_p": 0.0, "repetition_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0}


def answer_by_form(body):
    """A reply that fits whichever job's form the request carries."""
    return chat_reply(json.dumps(ALARM_QUIET if body["response_format"]["json_schema"]["name"] == "alarm" else ASSESSMENT),
                      model=TAG)


def cloud_door(engine, record):
    """A door whose profile names the made model, as the bench command names it with --model."""
    return Door(engine, record, dataclasses.replace(GEMMA_4_QAT, tag=TAG, engine="deepinfra"))


def listed(context=262144, with_model=True):
    data = [{"id": "another/model", "object": "model", "metadata": {"context_length": 1}}]
    if with_model:
        data.append({"id": TAG, "object": "model", "created": 0, "owned_by": "made-up", "metadata": {"context_length": context}})
    return 200, {"object": "list", "data": data}


def serve(server, context=262144, with_model=True):
    server.routes["/v1/models"] = listed(context, with_model)
    server.routes["/v1/chat/completions"] = answer_by_form
    return DeepInfraEngine(server.address, MADE_KEY, expected=server.address)


def chats(server):
    return [(body, headers) for (path, body), headers in zip(server.received, server.headers) if path == "/v1/chat/completions"]


def holds_no_key(*texts) -> bool:
    return all(MADE_KEY not in (t or "") for t in texts)


def key_folder_with_key(where):
    folder = where / "keys"
    folder.mkdir()
    (folder / keys.KEY_FILE).write_text(f"{KEY_NAME}={MADE_KEY}\n", encoding="utf-8")
    return folder


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def test_rule_4_the_kind_sends_the_chat_engines_request_with_the_key_in_the_header_alone(server, record):
    engine = serve(server)
    door = cloud_door(engine, record)
    result = door.ask("alarm", "made-up words")
    assert result.ok
    (body, headers), = chats(server)
    call = door.call_for("alarm", "made-up words")
    assert body == ChatEngine.build_request(engine, call) == VllmEngine(server.address).build_request(call)   # the vLLM arm's body
    assert set(body) == GATE_FIELDS | set(SIX) and {k: body[k] for k in SIX} == SIX and DeepInfraEngine.sampling == VllmEngine.sampling
    assert body["chat_template_kwargs"] == {"enable_thinking": False} and body["stream"] is False
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "alarm", "schema": call.form}}
    assert headers["authorization"] == f"Bearer {MADE_KEY}" and headers["content-type"] == "application/json"
    row = record.get(result.call_id)
    assert holds_no_key(row["request"], row["reply"], row["detail"], json.dumps(row))
    assert "Authorization" not in row["request"] and "Bearer" not in row["request"]
    # The GET for the list carries the header too, and the kind is the chat engine.
    assert any(h.get("authorization") == f"Bearer {MADE_KEY}" for (p, _), h in zip(server.received, server.headers) if p == "/v1/models")
    assert issubclass(DeepInfraEngine, ChatEngine) and DeepInfraEngine.build_request is ChatEngine.build_request


def test_7_3_rule_3_the_key_is_read_from_the_key_folder_by_the_one_module_and_written_nowhere(server, bench_folders, capsys, tmp_path, monkeypatch):
    cases, out = bench_folders
    serve(server)
    monkeypatch.setattr(deepinfra, "ADDRESS", server.address)                              # the made host in the host's place
    key_folder = tmp_path / "keys"
    key_folder.mkdir()
    common = ["run", "--cases", str(cases), "--case", "seven", "--chains", "A1", "--kind", "deepinfra",
              "--engine", server.address, "--model", TAG, "--digest", NO_DIGEST]
    # No key file: the command stops before any request, naming the key's name and the folder and never a value.
    assert main([*common, "--out", str(out), "--key-folder", str(key_folder)]) == 10
    said = capsys.readouterr().out
    assert KEY_NAME in said and str(key_folder) in said and chats(server) == []
    assert main([*common, "--out", str(out)]) == 10                                       # and without the folder
    (key_folder / keys.KEY_FILE).write_text(f"{KEY_NAME}={MADE_KEY}\n", encoding="utf-8")
    # The key folder is refused as a results folder.
    assert main([*common, "--out", str(key_folder / "out"), "--key-folder", str(key_folder)]) == 6
    assert chats(server) == []
    assert main([*common, "--out", str(out), "--key-folder", str(key_folder)]) == 0
    said = capsys.readouterr().out
    assert chats(server) and all(h["authorization"] == f"Bearer {MADE_KEY}" for _, h in chats(server))
    assert holds_no_key(said)
    result = ResultWriter(out).read("seven", "A1")
    assert (result["engine"], result["engine_version"], result["model_tag"], result["model_digest"]) == (
        "deepinfra", NO_VERSION, TAG, NO_DIGEST)
    assert holds_no_key(json.dumps(result))
    for row in ModelCalls(open_database(out / "calls.db")).rows():
        assert holds_no_key(json.dumps(row)) and row["engine"] == "deepinfra"
    # The command line never holds the value: the folder is the only argument.
    assert all(MADE_KEY not in part for part in common)


def test_R20_a_cloud_call_records_the_host_the_model_and_the_lines_that_no_version_and_no_digest_are_given(server, record, bench_folders, capsys, monkeypatch):
    engine = serve(server)
    row = record.get(cloud_door(engine, record).ask("alarm", "words").call_id)
    assert (row["engine"], row["engine_version"], row["model_tag"], row["model_digest"]) == ("deepinfra", NO_VERSION, TAG, NO_DIGEST)
    assert engine.model_digest("not-listed") is None and engine.version() == NO_VERSION
    cases, out = bench_folders
    monkeypatch.setattr(deepinfra, "ADDRESS", server.address)
    key_folder = key_folder_with_key(out.parent)
    run_args = ["run", "--cases", str(cases), "--out", str(out), "--case", "seven", "--chains", "A1", "--kind", "deepinfra",
                "--engine", server.address, "--model", TAG, "--key-folder", str(key_folder)]
    sent = len(chats(server))
    assert main([*run_args, "--digest", "made-up-digest"]) == 3                           # not the line the host gets
    serve(server, with_model=False)
    assert main([*run_args, "--digest", NO_DIGEST]) == 2                                  # the host does not list the model
    assert len(chats(server)) == sent                                                     # nothing sent by either stop
    serve(server)
    assert main([*run_args, "--digest", NO_DIGEST]) == 0
    assert ResultWriter(out).read("seven", "A1")["model_digest"] == NO_DIGEST
    capsys.readouterr()


def test_R19_the_fit_rule_reads_the_hosts_context_from_its_list_and_the_arm_is_not_refused_for_it(server, record):
    engine = serve(server, context=100)                                                   # below the call's 16,384
    door = cloud_door(engine, record)
    small = door.ask("alarm", "words")
    assert not small.ok and small.failure == "unreachable" and "context of 100" in small.detail and chats(server) == []
    engine = serve(server, context=262144)
    assert engine.context(TAG) == 262144 and cloud_door(engine, record).ask("alarm", "words").ok and len(chats(server)) == 1
    status = engine.status(TAG)
    assert status.running and status.context is None and status.digest == NO_DIGEST and status.version == NO_VERSION
    assert not serve(server, with_model=False).status(TAG).running


def test_10_4_a_failed_cloud_call_fails_plainly_and_no_local_engine_is_tried(server, record):
    engine = serve(server)
    server.routes["/v1/chat/completions"] = (500, {"error": "made-up: the host fell over"})
    door = cloud_door(engine, record)
    failed = door.ask("alarm", "words")
    assert not failed.ok and failed.failure == "unreachable" and "HTTP 500" in failed.detail and holds_no_key(failed.detail)
    assert len(chats(server)) == 1                                                      # one try, no other engine
    assert engine.stopped is None                                                        # an ordinary failed call: the run goes on
    server.routes["/v1/chat/completions"] = (400, {"error": "made-up: this model's maximum context length is 100 tokens"})
    assert door.ask("alarm", "words").failure == "did_not_fit"
    server.stop()
    gone = door.ask("alarm", "words")
    assert gone.failure == "unreachable" and holds_no_key(gone.detail)
    assert record.get(gone.call_id)["outcome"] == "unreachable"


def test_R30_a_failed_cloud_call_never_stops_the_pass(server, record):
    engine = serve(server)

    def alarm_fails(body):
        if body["response_format"]["json_schema"]["name"] == "alarm":
            return 500, {"error": "made-up: the host fell over"}
        return chat_reply(json.dumps(ASSESSMENT))

    server.routes["/v1/chat/completions"] = alarm_fails
    result = run_pass(cloud_door(engine, record), "made-up transcript", Patient(40, "M"))
    assert not result.alarm.judged and result.alarm.failure == "unreachable"
    assert result.assessment.ok and [d["condition"] for d in result.assessment.differentials] == ["Made-up condition A", "Made-up condition B"]
    assert len(chats(server)) == 2


@pytest.mark.parametrize("status", deepinfra.STOP_STATUSES)
def test_rule_9_a_refused_key_or_used_up_credit_stops_the_run_and_the_chain_is_written_apart(server, record, tmp_path, status):
    engine = serve(server)
    server.routes["/v1/chat/completions"] = (status, {"error": "made-up: refused"})
    door = cloud_door(engine, record)
    first = door.ask("alarm", "words")
    assert first.failure == "unreachable" and f"HTTP {status}" in first.detail
    second = door.ask("alarm", "words")
    assert second.failure == "unreachable" and str(status) in second.detail and holds_no_key(second.detail)
    assert len(chats(server)) == 1 and door.stopped == engine.stopped and "nothing more is sent" in door.stopped
    # The replay: the chain in progress goes apart, never among the results, and the run stops there.
    engine = serve(server)
    server.routes["/v1/chat/completions"] = (status, {"error": "made-up: refused"})
    door = cloud_door(engine, record)
    cases = [c for c in load_cases(made_up_folder(tmp_path)) if c.name == "madeup"]
    writer = ResultWriter(tmp_path / "out")
    summary = run(door, cases, writer, [Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)], log=lambda line: None)
    assert summary["stopped"] == engine.stopped and summary["run"] == 0
    assert not writer.exists("madeup", "A1") and writer.path_apart("madeup", "A1").is_file() and writer.read_all() == {}
    apart = json.loads(writer.path_apart("madeup", "A1").read_text(encoding="utf-8"))
    assert apart["failed"] and holds_no_key(json.dumps(apart))
    # A later run of the same command runs that chain again and keeps nothing of the stopped one.
    done = run(cloud_door(serve(server), record), cases, writer, [Chain("A1", 0.0, 42)], log=lambda line: None)
    assert done["run"] == 1 and "stopped" not in done and writer.exists("madeup", "A1")
    with pytest.raises(Refused):
        writer.write_apart("madeup", "A1", {})                                           # never written over, apart either


class Stopping(FakeEngine):
    """A made engine that says stop after its first call, as the cloud kind does."""

    def __init__(self, script=None):
        super().__init__(script)
        self.stopped = None

    def chat(self, call):
        if self.stopped:
            from openconsult.llm.engine import EngineUnreachable
            raise EngineUnreachable(self.stopped)
        reply = super().chat(call)
        self.stopped = "made-up: the host refused"
        return reply


def test_rule_9_the_letters_and_guideline_benches_stop_the_same_way(tmp_path, clock, monkeypatch):
    from tests.test_letter_bench import LETTER_ANSWER, LIST_ANSWER, made_cases
    from tests.test_guideline_bench import axis, corpus, queries_file
    from tests.fakes import MadeUpEmbedder
    from openconsult.guidelines.search import Index
    db = open_database(tmp_path / "calls.db")
    door = Door(Stopping({"referrals": [LIST_ANSWER], "letter": [LETTER_ANSWER]}), ModelCalls(db, clock))
    writer = ResultWriter(tmp_path / "letters")
    summary = letters.run(door, load_cases(made_cases(tmp_path, with_a=False)), writer, {}, [Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)],
                          log=lambda line: None)
    assert summary == {"run": 0, "kept": 0, "stopped": "made-up: the host refused"}
    assert writer.read_all() == {} and writer.path_apart("C_made", "A1").is_file()
    path, sha = queries_file(tmp_path)
    corpus_db, sources = corpus(tmp_path / "data", clock)
    embedder = MadeUpEmbedder(vector_for=lambda t: axis(1))
    door = Door(Stopping({"guideline": [{"covered": True, "summary": "made [1].", "passages_cited": [1]}]}), ModelCalls(db, clock))
    writer = ResultWriter(tmp_path / "guideline")
    summary = guideline.run(door, Index(sources), embedder, guideline.read_queries(path, sha)[:1], writer, Patient(50, "F"),
                            chains=[Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)], queries_sha256=sha, log=lambda line: None)
    assert summary["stopped"] == "made-up: the host refused" and summary["run"] == 1          # the search alone is kept
    assert list(writer.read_all()) == [("Q01", "search")] and writer.path_apart("Q01", "A1").is_file()
    assert main(["letters-score", "--out", str(tmp_path / "letters"), "--write", str(tmp_path / "letters" / "marks")]) == 6
    db.close()


@pytest.mark.parametrize("machine", [describe("Linux", "x86_64", [Card("Made-up card", 24564)]), describe("Linux", "x86_64", []),
                                     describe("Windows", "AMD64", [Card("Made-up card", 24564)]), describe("Darwin", "arm64", [])])
def test_rule_6_the_app_cannot_reach_the_cloud_kind(machine, tmp_path):
    assert "deepinfra" not in choose.order_for(machine) and "deepinfra" not in choose.ORDER
    assert set(KINDS) == {"ollama", "llamacpp", "vllm", "deepinfra", "claude"} and "deepinfra" not in app_module.__dict__.get("KINDS", {})
    code = ("import sys\n"
            "from openconsult.app import build_app\n"
            "from openconsult.settings import store\n"
            "from openconsult.settings.machine import describe\n"
            "app = build_app(store.build(sys.argv[1], 8765), machine=describe('Linux', 'x86_64', []))\n"
            "print(sorted(name for name in sys.modules if name.startswith('openconsult.bench') or 'deepinfra' in name))\n")
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


@pytest.mark.parametrize("address", ["http://api.deepinfra.com", "https://api.deepinfra.com.example", "http://127.0.0.1:1",
                                     "https://api.deepinfra.com/v1"])
def test_15_13_the_kind_speaks_to_the_hosts_own_address_over_https_only(address, server):
    with pytest.raises(AddressRefused):
        DeepInfraEngine(address, MADE_KEY)
    with pytest.raises(AddressRefused):
        DeepInfraEngine(server.address, MADE_KEY)                                          # the made server is not the host
    assert server.received == []                                                          # refused before any connection
    assert DeepInfraEngine(ADDRESS, MADE_KEY).address == ADDRESS == "https://api.deepinfra.com"
    assert DeepInfraEngine(ADDRESS + "/", MADE_KEY).address == ADDRESS


def test_15_13_the_example_settings_file_names_the_language_model_key_with_no_value():
    from openconsult.bench.cli import REPO
    found = keys.parse_env((REPO / ".env.example").read_text(encoding="utf-8"))
    assert found[KEY_NAME] == "" and all(value == "" for value in found.values())
    assert set(found) == {"SPEECHMATICS_API_KEY", "ASSEMBLYAI_API_KEY", KEY_NAME, "ANTHROPIC_API_KEY"}   # and no OLLAMA_API_KEY (ruling 11)


def test_15_13_the_record_check_reads_thinking_in_a_reply_of_either_shape():
    assert answer_text(json.dumps({"message": {"content": "{}", "thinking": "made-up thought"}})) == ("{}", "made-up thought")
    assert answer_text(json.dumps({"choices": [{"message": {"content": "{}", "reasoning_content": "made-up"}}]})) == ("{}", "made-up")
    assert answer_text(json.dumps({"choices": [{"message": {"content": "{}", "reasoning_content": ""}}]})) == ("{}", None)
    assert answer_text(json.dumps({"message": {"content": "{}", "thinking": ""}})) == ("{}", None)
    assert answer_text("not json") == (None, None)
