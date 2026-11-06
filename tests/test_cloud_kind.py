"""The cloud kind of the bench, Ollama cloud through the door (spec 15.13,
rulings 3, 4 and 8 and the details for run 9a; 7.3 rule 3; 10.4; R20;
R30; R31). A made-up loopback server stands for the service; every key
here is made up; every reply is made up and nothing a model said is
asserted."""

import dataclasses
import json
import subprocess
import sys

import pytest

from openconsult import app as app_module
from openconsult.bench import guideline, letters, ollama_cloud
from openconsult.bench.cases import load_cases
from openconsult.bench.cli import KINDS, main
from openconsult.bench.ollama_cloud import ADDRESS, KEY_NAME, NO_DIGEST, AddressRefused, OllamaCloudEngine
from openconsult.bench.replay import Chain, answer_text, run
from openconsult.bench.writer import Refused, ResultWriter
from openconsult.consult.cds_pass import run_pass
from openconsult.consult.messages import Patient
from openconsult.db import open_database
from openconsult.llm import choose
from openconsult.llm.door import Door
from openconsult.llm.ollama import OllamaEngine, build_request
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.settings import keys
from openconsult.settings.machine import Card, describe
from tests.fakes import ALARM_QUIET, ASSESSMENT, CALL, FakeEngine
from tests.test_bench import made_up_folder

MADE_KEY = "made-up-cloud-key-0123456789"
TAG = CALL.tag


def ollama_reply(content, done_reason="stop"):
    return 200, {"model": TAG, "message": {"role": "assistant", "content": content}, "done": True, "done_reason": done_reason,
                 "prompt_eval_count": 50, "eval_count": 20, "total_duration": 4_000_000, "load_duration": 0,
                 "prompt_eval_duration": 1_000_000, "eval_duration": 3_000_000}


def answer_by_form(body):
    """A reply that fits whichever job's form the request carries."""
    alarm = "urgent_actions" in json.dumps(body["format"])
    return ollama_reply(json.dumps(ALARM_QUIET if alarm else ASSESSMENT))


def cloud_door(engine, record):
    """A door whose profile names the made model, as the bench command names it with --model."""
    return Door(engine, record, dataclasses.replace(GEMMA_4_QAT, tag=TAG, engine="ollama-cloud"))


def serve(server, digest="made-up-digest", tags=None):
    server.routes["/api/version"] = (200, {"version": "0.0-made-up"})
    server.routes["/api/tags"] = (200, {"models": tags if tags is not None else [{"name": TAG, "digest": digest}]})
    server.routes["/api/chat"] = answer_by_form
    return OllamaCloudEngine(server.address, MADE_KEY, expected=server.address)


def chats(server):
    return [(body, headers) for (path, body), headers in zip(server.received, server.headers) if path == "/api/chat"]


def holds_no_key(*texts) -> bool:
    return all(MADE_KEY not in (t or "") for t in texts)


@pytest.fixture
def record(tmp_path, clock):
    db = open_database(tmp_path / "calls.db")
    yield ModelCalls(db, clock)
    db.close()


def test_rule_4_the_cloud_kind_sends_the_local_ollamas_request_with_the_key_in_the_header_alone(server, record):
    engine = serve(server)
    door = Door(engine, record)
    result = door.ask("alarm", "made-up words")
    assert result.ok
    (body, headers), = chats(server)
    assert body == build_request(door.call_for("alarm", "made-up words"))                # the local Ollama body, byte for byte
    assert body["think"] is False and body["truncate"] is False and body["options"]["num_ctx"] == 16384
    assert headers["authorization"] == f"Bearer {MADE_KEY}" and headers["content-type"] == "application/json"
    row = record.get(result.call_id)
    assert holds_no_key(row["request"], row["reply"], row["detail"], json.dumps(row))
    assert "Authorization" not in row["request"] and "Bearer" not in row["request"]
    # The GET for the identity carries the header too, and nothing else of the engine differs from the local one.
    assert any(h.get("authorization") == f"Bearer {MADE_KEY}" for (p, _), h in zip(server.received, server.headers) if p == "/api/tags")
    assert OllamaCloudEngine.chat.__qualname__.startswith("OllamaCloudEngine") and issubclass(OllamaCloudEngine, OllamaEngine)


def test_7_3_rule_3_the_key_is_read_from_the_key_folder_by_the_one_module_and_written_nowhere(server, bench_folders, capsys, tmp_path, monkeypatch):
    cases, out = bench_folders
    serve(server)
    monkeypatch.setattr(ollama_cloud, "ADDRESS", server.address)                           # the made service in the service's place
    key_folder = tmp_path / "keys"
    key_folder.mkdir()
    common = ["run", "--cases", str(cases), "--case", "seven", "--chains", "A1", "--kind", "ollama-cloud",
              "--engine", server.address, "--model", TAG, "--digest", "made-up-digest"]
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
        "ollama-cloud", "0.0-made-up", TAG, "made-up-digest")
    assert holds_no_key(json.dumps(result))
    for row in ModelCalls(open_database(out / "calls.db")).rows():
        assert holds_no_key(json.dumps(row)) and row["engine"] == "ollama-cloud"
    # The command line never holds the value: the folder is the only argument, and the engine's address must be the service's.
    assert all(MADE_KEY not in part for part in common)


def test_R20_a_cloud_call_records_the_service_its_version_the_tag_and_the_digest_or_the_line_that_none_was_given(server, record, bench_folders, capsys, monkeypatch):
    engine = serve(server)
    door = cloud_door(engine, record)
    row = record.get(door.ask("alarm", "words").call_id)
    assert (row["engine"], row["engine_version"], row["model_tag"], row["model_digest"]) == ("ollama-cloud", "0.0-made-up", TAG, "made-up-digest")
    # A model the service lists without a digest: the fixed line, and the bench runs with that line as its --digest.
    engine = serve(server, tags=[{"name": TAG, "modified_at": "made-up"}])
    assert engine.model_digest(TAG) == NO_DIGEST and engine.model_digest("not-listed") is None
    row = record.get(cloud_door(engine, record).ask("alarm", "words").call_id)
    assert row["model_digest"] == NO_DIGEST
    cases, out = bench_folders
    monkeypatch.setattr(ollama_cloud, "ADDRESS", server.address)
    key_folder = out.parent / "keys"
    key_folder.mkdir()
    (key_folder / keys.KEY_FILE).write_text(f"{KEY_NAME}={MADE_KEY}\n", encoding="utf-8")
    run_args = ["run", "--cases", str(cases), "--out", str(out), "--case", "seven", "--chains", "A1", "--kind", "ollama-cloud",
                "--engine", server.address, "--model", TAG, "--key-folder", str(key_folder)]
    assert main([*run_args, "--digest", "made-up-digest"]) == 3                           # not the digest the service gives
    assert main([*run_args, "--digest", NO_DIGEST]) == 0
    assert ResultWriter(out).read("seven", "A1")["model_digest"] == NO_DIGEST
    capsys.readouterr()


def test_10_4_a_failed_cloud_call_fails_plainly_and_no_local_engine_is_tried(server, record):
    engine = serve(server)
    server.routes["/api/chat"] = (500, {"error": "made-up: the service fell over"})
    door = Door(engine, record)
    failed = door.ask("alarm", "words")
    assert not failed.ok and failed.failure == "unreachable" and "HTTP 500" in failed.detail and holds_no_key(failed.detail)
    assert len(chats(server)) == 1                                                      # one try, no other engine
    assert engine.stopped is None                                                        # an ordinary failed call: the run goes on
    server.stop()
    gone = door.ask("alarm", "words")
    assert gone.failure == "unreachable" and holds_no_key(gone.detail)
    assert record.get(gone.call_id)["outcome"] == "unreachable"


def test_R30_a_failed_cloud_call_never_stops_the_pass(server, record):
    engine = serve(server)

    def alarm_fails(body):
        if "urgent_actions" in json.dumps(body["format"]):
            return 500, {"error": "made-up: the service fell over"}
        return ollama_reply(json.dumps(ASSESSMENT))

    server.routes["/api/chat"] = alarm_fails
    result = run_pass(Door(engine, record), "made-up transcript", Patient(40, "M"))
    assert not result.alarm.judged and result.alarm.failure == "unreachable"
    assert result.assessment.ok and [d["condition"] for d in result.assessment.differentials] == ["Made-up condition A", "Made-up condition B"]
    assert len(chats(server)) == 2


@pytest.mark.parametrize("status", ollama_cloud.STOP_STATUSES)
def test_rule_9_a_refused_key_or_used_up_credit_stops_the_run_and_the_chain_is_written_apart(server, record, tmp_path, status):
    engine = serve(server)
    server.routes["/api/chat"] = (status, {"error": "made-up: refused"})
    door = Door(engine, record)
    first = door.ask("alarm", "words")
    assert first.failure == "unreachable" and f"HTTP {status}" in first.detail
    second = door.ask("alarm", "words")
    assert second.failure == "unreachable" and str(status) in second.detail and holds_no_key(second.detail)
    assert len(chats(server)) == 1 and door.stopped == engine.stopped and "nothing more is sent" in door.stopped
    # The replay: the chain in progress goes apart, never among the results, and the run stops there.
    engine = serve(server)
    server.routes["/api/chat"] = (status, {"error": "made-up: refused"})
    door = Door(engine, record)
    cases = [c for c in load_cases(made_up_folder(tmp_path)) if c.name == "madeup"]
    writer = ResultWriter(tmp_path / "out")
    summary = run(door, cases, writer, [Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)], log=lambda line: None)
    assert summary["stopped"] == engine.stopped and summary["run"] == 0
    assert not writer.exists("madeup", "A1") and writer.path_apart("madeup", "A1").is_file() and writer.read_all() == {}
    apart = json.loads(writer.path_apart("madeup", "A1").read_text(encoding="utf-8"))
    assert apart["failed"] and holds_no_key(json.dumps(apart))
    # A later run of the same command runs that chain again and keeps nothing of the stopped one.
    serve(server)
    done = run(Door(serve(server), record), cases, writer, [Chain("A1", 0.0, 42)], log=lambda line: None)
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
        self.stopped = "made-up: the service refused"
        return reply


def test_rule_9_the_letters_and_guideline_benches_stop_the_same_way(tmp_path, clock, monkeypatch):
    from tests.test_letter_bench import LETTER_ANSWER, LIST_ANSWER, made_cases
    from tests.test_guideline_bench import QUERIES, axis, corpus, queries_file
    from tests.fakes import MadeUpEmbedder
    from openconsult.guidelines.search import Index
    db = open_database(tmp_path / "calls.db")
    door = Door(Stopping({"referrals": [LIST_ANSWER], "letter": [LETTER_ANSWER]}), ModelCalls(db, clock))
    writer = ResultWriter(tmp_path / "letters")
    summary = letters.run(door, load_cases(made_cases(tmp_path, with_a=False)), writer, {}, [Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)],
                          log=lambda line: None)
    assert summary == {"run": 0, "kept": 0, "stopped": "made-up: the service refused"}
    assert writer.read_all() == {} and writer.path_apart("C_made", "A1").is_file()
    path, sha = queries_file(tmp_path)
    corpus_db, sources = corpus(tmp_path / "data", clock)
    embedder = MadeUpEmbedder(vector_for=lambda t: axis(1))
    door = Door(Stopping({"guideline": [{"covered": True, "summary": "made [1].", "passages_cited": [1]}]}), ModelCalls(db, clock))
    writer = ResultWriter(tmp_path / "guideline")
    summary = guideline.run(door, Index(sources), embedder, guideline.read_queries(path, sha)[:1], writer, Patient(50, "F"),
                            chains=[Chain("A1", 0.0, 42), Chain("A2", 0.0, 42)], queries_sha256=sha, log=lambda line: None)
    assert summary["stopped"] == "made-up: the service refused" and summary["run"] == 1          # the search alone is kept
    assert list(writer.read_all()) == [("Q01", "search")] and writer.path_apart("Q01", "A1").is_file()
    assert main(["letters-score", "--out", str(tmp_path / "letters"), "--write", str(tmp_path / "letters" / "marks")]) == 6
    db.close()


@pytest.mark.parametrize("machine", [describe("Linux", "x86_64", [Card("Made-up card", 24564)]), describe("Linux", "x86_64", []),
                                     describe("Windows", "AMD64", [Card("Made-up card", 24564)]), describe("Darwin", "arm64", [])])
def test_rule_6_the_app_cannot_reach_the_cloud_kind(machine, tmp_path):
    assert "ollama-cloud" not in choose.order_for(machine) and "ollama-cloud" not in choose.ORDER
    assert "ollama-cloud" in KINDS and "ollama-cloud" not in app_module.__dict__.get("KINDS", {})
    code = ("import sys\n"
            "from openconsult.app import build_app\n"
            "from openconsult.settings import store\n"
            "from openconsult.settings.machine import describe\n"
            "app = build_app(store.build(sys.argv[1], 8765), machine=describe('Linux', 'x86_64', []))\n"
            "print(sorted(name for name in sys.modules if 'cloud' in name and name.startswith('openconsult')))\n")
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "['openconsult.speech.common.cloud']" or done.stdout.strip() == "[]"


@pytest.mark.parametrize("address", ["http://ollama.com", "https://ollama.com.example", "http://127.0.0.1:1", "https://ollama.com/api"])
def test_15_13_the_cloud_kind_speaks_to_the_services_own_address_over_https_only(address, server):
    with pytest.raises(AddressRefused):
        OllamaCloudEngine(address, MADE_KEY)
    with pytest.raises(AddressRefused):
        OllamaCloudEngine(server.address, MADE_KEY)                                        # the made server is not the service
    assert server.received == []                                                          # refused before any connection
    assert OllamaCloudEngine(ADDRESS, MADE_KEY).address == ADDRESS == "https://ollama.com"
    assert OllamaCloudEngine(ADDRESS + "/", MADE_KEY).address == ADDRESS


def test_15_13_the_example_settings_file_names_the_language_model_key_with_no_value():
    from openconsult.bench.cli import REPO
    found = keys.parse_env((REPO / ".env.example").read_text(encoding="utf-8"))
    assert found[KEY_NAME] == "" and all(value == "" for value in found.values())
    assert {"SPEECHMATICS_API_KEY", "ASSEMBLYAI_API_KEY", KEY_NAME} <= set(found)


def test_15_13_the_record_check_reads_thinking_in_a_reply_of_either_shape():
    assert answer_text(json.dumps({"message": {"content": "{}", "thinking": "made-up thought"}})) == ("{}", "made-up thought")
    assert answer_text(json.dumps({"choices": [{"message": {"content": "{}", "reasoning_content": "made-up"}}]})) == ("{}", "made-up")
    assert answer_text(json.dumps({"message": {"content": "{}", "thinking": ""}})) == ("{}", None)
    assert answer_text("not json") == (None, None)
