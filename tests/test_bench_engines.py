"""The bench's two engines, llama.cpp and vLLM, against a made-up server
(spec 15.8; R19, R31; V1_LESSONS 3.3, 9.6). Everything the server says is
made up; nothing here is what a model or an engine said."""

import hashlib
import json
import subprocess
import sys

import pytest

from openconsult.bench.cli import main
from openconsult.bench.llamacpp import LlamaCppEngine
from openconsult.bench.vllm import VllmEngine
from openconsult.bench.writer import ResultWriter
from openconsult.cli import main as app_main
from openconsult.llm.engine import Call
from openconsult.llm.profile import GEMMA_4_QAT
from tests.fakes import CALL, REVISION, answer_by_job, chat_reply, describe

FORM = CALL.form
ENGINES = [LlamaCppEngine, VllmEngine]


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
