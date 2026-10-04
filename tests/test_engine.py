"""The Ollama engine behind the joint (spec 15.7): the request it builds
and that it never hangs (V1_LESSONS 3.3; This machine)."""

import json
import socket
import threading
import time

import pytest

from openconsult.llm.engine import Call, EngineTimeout
from openconsult.llm.ollama import OllamaEngine, build_request, encode

CALL = Call(job="alarm", tag="made-up:tag", system="SYSTEM WORDS", user="user words",
            form={"type": "object", "required": ["ok"]}, temperature=0.0, seed=42,
            context=16384, max_tokens=1000, think=False, timeout_s=0.5)


@pytest.fixture
def silent_server():
    """A loopback socket that accepts and never answers."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    held = []
    stop = threading.Event()

    def accept():
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                held.append(server.accept()[0])
            except OSError:
                pass

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}"
    stop.set()
    thread.join()
    for conn in held:
        conn.close()
    server.close()


def test_15_7_the_page_does_not_hang_when_ollama_does_not_answer(silent_server):
    engine = OllamaEngine(silent_server)
    started = time.monotonic()
    status = engine.status("made-up:tag", timeout_s=0.3)
    assert time.monotonic() - started < 1.5
    assert status.running is False and status.version is None and status.model_present is None
    # And a chat call to it is a timeout, not a hang.
    started = time.monotonic()
    with pytest.raises(EngineTimeout):
        engine.chat(CALL)
    assert time.monotonic() - started < 1.5


def test_3_3_the_request_carries_truncate_false_and_the_parts_in_v1s_order():
    body = build_request(CALL)
    assert list(body) == ["model", "messages", "format", "stream", "keep_alive", "options", "think", "truncate"]
    assert body["truncate"] is False and body["stream"] is False
    assert body["messages"] == [{"role": "system", "content": "SYSTEM WORDS"},
                                {"role": "user", "content": "user words"}]
    assert body["options"] == {"temperature": 0.0, "seed": 42, "num_ctx": 16384, "num_predict": 1000}
    assert body["think"] is False and body["model"] == "made-up:tag"
    # Compact bytes, not ASCII-escaped, so they can be compared with v1's.
    assert encode({"a": "é", "b": [1, 2]}) == '{"a":"é","b":[1,2]}'.encode("utf-8")
    assert json.loads(encode(body)) == body
