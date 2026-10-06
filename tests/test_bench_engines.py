"""The bench's two engines, llama.cpp and vLLM, against a made-up server
(spec 15.8; R19, R31; V1_LESSONS 3.3, 9.6). Everything the server says is
made up; nothing here is what a model or an engine said."""

import hashlib
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from openconsult.bench.cli import main
from openconsult.bench.llamacpp import LlamaCppEngine
from openconsult.bench.vllm import VllmEngine
from openconsult.bench.writer import ResultWriter
from openconsult.cli import main as app_main
from openconsult.llm.engine import Call
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.settings import paths
from tests.fakes import ALARM_QUIET, ASSESSMENT
from tests.test_bench import made_up_folder

FORM = {"type": "object", "required": ["ok"]}
CALL = Call(job="alarm", tag="made-up/model", system="SYSTEM WORDS", user="user words", form=FORM,
            temperature=0.5, seed=7, context=16384, max_tokens=1000, think=False, timeout_s=5.0)
REVISION = "0123456789abcdef0123456789abcdef01234567"
ENGINES = [LlamaCppEngine, VllmEngine]


class MadeUpServer:
    """A loopback server that answers each path from a table and keeps
    what it was sent. An answer is (status, body) or a function of the
    request's body that gives one."""

    def __init__(self):
        self.routes, self.received = {}, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self, body):
                outer.received.append((self.path, body))
                found = outer.routes.get(self.path, (404, {"error": "made-up: no such path"}))
                status, reply = found(body) if callable(found) else found
                data = (reply if isinstance(reply, str) else json.dumps(reply)).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._answer(None)

            def do_POST(self):
                self._answer(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.address = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, args=(0.01,), daemon=True)
        self._thread.start()

    def chats(self):
        return [body for path, body in self.received if path == "/v1/chat/completions"]

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


@pytest.fixture
def server():
    made = MadeUpServer()
    yield made
    made.stop()


def chat_reply(content, finish="stop", **extra):
    return 200, {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}],
                 "usage": {"prompt_tokens": 50, "completion_tokens": 20}, **extra}


def describe(server, engine_class, context=16384, model_path="/made-up/model.gguf", root=f"/made-up/snapshots/{REVISION}"):
    """What each engine's own pages give for the context, the version and the model."""
    if engine_class is LlamaCppEngine:
        server.routes["/props"] = (200, {"default_generation_settings": {"n_ctx": context},
                                         "build_info": "b1-made-up", "model_path": model_path})
    else:
        server.routes["/version"] = (200, {"version": "0.0-made-up"})
        server.routes["/v1/models"] = (200, {"data": [{"id": "another/model", "root": "/elsewhere", "max_model_len": 1},
                                                       {"id": CALL.tag, "root": root, "max_model_len": context}]})


@pytest.mark.parametrize("engine_class", ENGINES)
def test_15_8_a_bench_engine_sends_thinking_the_form_and_the_limits_its_own_way(server, engine_class):
    describe(server, engine_class)
    server.routes["/v1/chat/completions"] = chat_reply('{"ok": true}')
    engine = engine_class(server.address)
    engine.chat(CALL)
    engine.chat(Call(**{**CALL.__dict__, "think": True, "max_tokens": 1500}))
    off, on = server.chats()
    assert off["model"] == "made-up/model" and off["stream"] is False
    assert off["messages"] == [{"role": "system", "content": "SYSTEM WORDS"}, {"role": "user", "content": "user words"}]
    assert off["response_format"] == {"type": "json_schema", "json_schema": {"name": "alarm", "schema": FORM}}
    assert off["chat_template_kwargs"] == {"enable_thinking": False}
    assert on["chat_template_kwargs"] == {"enable_thinking": True}
    assert (off["temperature"], off["seed"], off["max_tokens"], on["max_tokens"]) == (0.5, 7, 1000, 1500)
    # The sampling settings an engine would fill in by itself are named, each in the engine's own word.
    assert (off["top_k"], off["top_p"], off["min_p"]) == (64, 0.95, 0.0)
    assert (off["presence_penalty"], off["frequency_penalty"]) == (0.0, 0.0)
    own, other = ("repeat_penalty", "repetition_penalty")[::1 if engine_class is LlamaCppEngine else -1]
    assert off[own] == 1.0 and other not in off
    # The context is fixed when such a server starts: it is checked, never sent.
    assert not {"n_ctx", "num_ctx", "max_model_len"} & set(off)


DID_NOT_FIT = {
    LlamaCppEngine: (400, {"error": {"code": 400, "type": "exceed_context_size_error",
                                     "message": "made-up: the request exceeds the context", "n_ctx": 16384}}),
    VllmEngine: (400, {"error": {"code": 400, "type": "BadRequestError",
                                 "message": "This model's maximum context length is 16384 tokens. Made-up."}}),
}
ENDINGS = [
    ("complete", lambda e: chat_reply('{"ok": true}')),
    ("cut", lambda e: chat_reply('{"ok": tr', finish="length")),
    ("did_not_fit", lambda e: DID_NOT_FIT[e]),
    ("error", lambda e: (500, {"error": {"message": "made-up: the engine fell over"}})),
    ("error", lambda e: (400, {"error": {"type": "invalid_request_error", "message": "made-up: another refusal"}})),
    ("error", lambda e: (200, {"made-up": "not a chat reply"})),
    ("error", lambda e: chat_reply("made-up", finish="abort")),
]


@pytest.mark.parametrize("engine_class", ENGINES)
@pytest.mark.parametrize("ended, answer", ENDINGS)
def test_15_8_a_bench_engine_reads_the_four_endings(server, engine_class, ended, answer):
    describe(server, engine_class)
    server.routes["/v1/chat/completions"] = answer(engine_class)
    reply = engine_class(server.address).chat(CALL)
    assert reply.ended == ended
    assert json.loads(reply.request)["messages"][1]["content"] == "user words"   # for the record
    if ended in ("complete", "cut"):
        assert reply.text.startswith('{"ok"') and (reply.prompt_tokens, reply.output_tokens) == (50, 20)
        assert json.loads(reply.raw)["choices"][0]["message"]["content"] == reply.text
    else:
        assert reply.text is None and reply.error and reply.raw


@pytest.mark.parametrize("engine_class, timed", [
    (LlamaCppEngine, {"timings": {"prompt_ms": 101.4, "predicted_ms": 900.6}}),
    (VllmEngine, {"metrics": {"time_to_first_token_ms": 101.4, "generation_time_ms": 900.6}}),
])
def test_15_8_a_bench_engine_keeps_the_engines_own_read_and_write_times(server, engine_class, timed):
    describe(server, engine_class)
    server.routes["/v1/chat/completions"] = chat_reply('{"ok": true}', **timed)
    reply = engine_class(server.address).chat(CALL)
    assert (reply.read_ms, reply.write_ms) == (101, 901) and reply.wall_ms >= 0


@pytest.mark.parametrize("engine_class", ENGINES)
def test_R19_a_bench_engine_refuses_a_server_started_at_another_context(server, engine_class):
    describe(server, engine_class, context=8192)
    server.routes["/v1/chat/completions"] = chat_reply('{"ok": true}')
    reply = engine_class(server.address).chat(CALL)
    assert reply.ended == "error" and "8192" in reply.error and "16384" in reply.error
    assert server.chats() == []                    # the call was never sent
    # The twin: at the call's own context it goes through.
    describe(server, engine_class, context=16384)
    assert engine_class(server.address).chat(CALL).ended == "complete"


def test_9_6_a_bench_engine_reports_its_version_and_the_model_it_runs(server, tmp_path):
    model = tmp_path / "made-up.gguf"
    model.write_bytes(b"made-up weights")
    describe(server, LlamaCppEngine, model_path=str(model))
    llama = LlamaCppEngine(server.address)
    assert llama.version() == "b1-made-up"
    assert llama.model_digest(CALL.tag) == hashlib.sha256(b"made-up weights").hexdigest()
    describe(server, LlamaCppEngine, model_path=str(tmp_path / "not-here.gguf"))
    assert LlamaCppEngine(server.address).model_digest(CALL.tag) is None   # a model it cannot name
    describe(server, VllmEngine)
    vllm = VllmEngine(server.address)
    assert vllm.version() == "0.0-made-up" and vllm.model_digest(CALL.tag) == REVISION
    status = vllm.status(CALL.tag)
    assert status.running and status.model_present and status.digest == REVISION
    describe(server, VllmEngine, root="/made-up/not-a-revision")
    assert VllmEngine(server.address).model_digest(CALL.tag) is None
    assert VllmEngine(server.address).model_digest("not-served") is None
    # An engine that is not there: none, and no hang.
    server.stop()
    for gone in (LlamaCppEngine(server.address), VllmEngine(server.address)):
        assert gone.version(timeout_s=0.5) is None and gone.status(CALL.tag, timeout_s=0.5).running is False


@pytest.fixture
def bench_folders(tmp_path, monkeypatch):
    """The command checks its folder against the app's data folder; here that is a made-up one."""
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "app-data")
    return made_up_folder(tmp_path), tmp_path / "out"


def answer_by_job(body):
    job = body["response_format"]["json_schema"]["name"]
    return chat_reply(json.dumps(ALARM_QUIET if job == "alarm" else ASSESSMENT))


def test_15_8_the_bench_is_pointed_at_an_engine_by_kind_address_and_model(server, bench_folders, capsys):
    cases, out = bench_folders
    describe(server, VllmEngine)
    server.routes["/v1/chat/completions"] = answer_by_job
    run = ["run", "--cases", str(cases), "--out", str(out), "--case", "seven", "--chains", "A1"]
    assert main([*run, "--kind", "vllm", "--engine", server.address, "--model", CALL.tag, "--digest", REVISION]) == 0
    result = ResultWriter(out).read("seven", "A1")
    assert (result["engine"], result["engine_version"]) == ("vllm", "0.0-made-up")
    assert (result["model_tag"], result["model_digest"]) == (CALL.tag, REVISION)
    assert result["failed"] is None and len(result["passes"]) == 2
    assert server.chats() and all(body["model"] == CALL.tag for body in server.chats())
    assert GEMMA_4_QAT.tag != CALL.tag and GEMMA_4_QAT.engine == "ollama"   # the app's profile is untouched
    # A model the engine does not serve, and a kind the bench does not know, are refused.
    assert main([*run, "--out", str(out) + "2", "--kind", "vllm", "--engine", server.address, "--model", "not-served"]) == 2
    with pytest.raises(SystemExit):
        main([*run, "--kind", "made-up-engine", "--engine", server.address])
    capsys.readouterr()


def test_R31_the_app_never_loads_the_bench_and_has_no_switch_for_an_engine(tmp_path):
    # A fresh Python, so no other test's imports are seen: the app as the command builds it.
    code = (
        "import sys\n"
        "import openconsult.cli\n"
        "from openconsult.app import build_app\n"
        "from openconsult.settings import store\n"
        "from openconsult.settings.machine import describe\n"
        "app = build_app(store.build(sys.argv[1], 8765), machine=describe('Linux', 'x86_64', []))\n"
        "print(type(app.state.parts.engine).__module__)\n"
        "print(sorted(name for name in sys.modules if name.startswith('openconsult.bench')))\n"
    )
    done = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["openconsult.llm.ollama", "[]"]
    for option in ("--engine", "--kind", "--model"):
        with pytest.raises(SystemExit):
            app_main([option, "made-up", "--data-folder", str(tmp_path), "--no-browser"], serve=lambda *a: None)
