"""The two ways to an embedding model in the test of 5d (spec 15.9,
rulings 24 and 25): the call to Ollama on the card and on the processor,
where a model sits by Ollama's own list, the worker of version 2 over the
frames, a failed call kept as failed (rule 22 of the stage), the number
format never float16, and the fetch with no token. Everything a server or
a worker says here is made up."""

import sys
from pathlib import Path

import pytest

from openconsult.bench.shared import embed
from tests.fakes import MadeUpServer

EMBEDDER = Path(__file__).parent / "made_up_embedder.py"
VECTOR = [0.5] * 768


@pytest.mark.parametrize("where, options", [("card", None), ("processor", {"num_gpu": 0})])
def test_15_9_ruling_24_the_ollama_call_on_the_card_and_on_the_processor(server, where, options):
    server.routes["/api/embed"] = (200, {"model": "embeddinggemma", "embeddings": [VECTOR, VECTOR],
                                         "total_duration": 7, "load_duration": 1, "prompt_eval_count": 9})
    embedder = embed.OllamaEmbedder(where, server.address)
    found = embedder.embed(["task: search result | query: Made-up A", "task: search result | query: Made-up B"])
    sent = server.received[-1][1]
    expected = {"model": "embeddinggemma", "input": ["task: search result | query: Made-up A", "task: search result | query: Made-up B"],
                "keep_alive": "30m"}
    if options:
        expected["options"] = options
    assert sent == expected
    assert found.ok and found.vectors == [VECTOR, VECTOR] and found.own["prompt_eval_count"] == 9


def test_15_9_ruling_24_a_refusal_or_an_odd_reply_is_a_failed_call_with_its_reason(server):
    server.routes["/api/embed"] = (500, {"error": "made-up: no room"})
    found = embed.OllamaEmbedder("card", server.address).embed(["x"])
    assert not found.ok and found.error.startswith("HTTP 500") and found.vectors == []
    server.routes["/api/embed"] = (200, {"made-up": True})
    assert not embed.OllamaEmbedder("card", server.address).embed(["x"]).ok
    assert not embed.OllamaEmbedder("card", "http://127.0.0.1:9").embed(["x"]).ok      # nothing listens
    with pytest.raises(ValueError):
        embed.OllamaEmbedder("cloud", server.address)


def test_15_9_ruling_24_where_a_model_sits_is_read_from_ollamas_list(server):
    listed = [{"name": "embeddinggemma:latest", "size": 1000, "size_vram": 1000, "context_length": 2048},
              {"name": "other:latest", "size": 1000, "size_vram": 0},
              {"name": "split:latest", "size": 1000, "size_vram": 400}]
    server.routes["/api/ps"] = (200, {"models": listed})
    found = embed.loaded_models(server.address)
    assert embed.where_is(found, "embeddinggemma")["placement"] == "card"
    assert embed.where_is(found, "other")["placement"] == "processor"
    assert embed.where_is(found, "split")["placement"] == "split"
    assert embed.where_is(found, "absent") is None
    assert embed.where_is([], "embeddinggemma") is None
    assert embed.loaded_models("http://127.0.0.1:9") is None                            # cannot be read
    info = embed.OllamaEmbedder("card", server.address).info()
    assert info["listed"]["placement"] == "card" and info["where_asked"] == "card"


def test_15_9_ruling_24_unload_asks_for_keep_alive_zero(server):
    server.routes["/api/embed"] = (200, {"embeddings": []})
    embed.OllamaEmbedder("card", server.address).unload()
    assert server.received[-1][1] == {"model": "embeddinggemma", "input": [], "keep_alive": 0}


def made_up(tmp_path, mode="ready", where="processor"):
    command = [sys.executable, "-u", str(EMBEDDER), mode, "--device", "cuda" if where == "card" else "cpu"]
    return embed.WorkerEmbedder(where, tmp_path / "data", command=command)


def test_15_9_ruling_25_the_worker_of_version_2_is_asked_and_answers_over_the_frames(tmp_path):
    worker = made_up(tmp_path, where="card")
    try:
        assert worker.start() is None
        info = worker.info()
        assert (info["device"], info["where_asked"], info["model"]) == ("cuda", "card", "made-up/embedder")
        found = worker.embed(["task: search result | query: Made-up A", "second"])
        assert found.ok and len(found.vectors) == 2 and len(found.vectors[0]) == 768
        assert found.own["seconds"] == 0.001
    finally:
        worker.close()
    assert worker.embed(["x"]).ok is False                                              # stopped: a failure, no raise


def test_15_9_ruling_25_a_dead_or_wrong_worker_is_a_failed_search_and_nothing_is_asked_again(tmp_path):
    worker = made_up(tmp_path, "die_at_second")
    try:
        assert worker.start() is None
        assert worker.embed(["one"]).ok
        second = worker.embed(["two"])
        assert not second.ok and "out of memory" in second.error.lower()
        third = worker.embed(["three"])
        assert not third.ok                                   # kept as failed; the worker is not started again
    finally:
        worker.close()
    refusing = made_up(tmp_path, "refuse")
    try:
        refusing.start()
        found = refusing.embed(["one"])
        assert not found.ok and found.error == "made-up: refused"
    finally:
        refusing.close()


def test_15_9_ruling_25_a_worker_that_will_not_start_gives_its_reason(tmp_path):
    worker = embed.WorkerEmbedder("processor", tmp_path / "data", command=[sys.executable, "-c", "import sys; sys.exit(2)"])
    assert worker.start() is not None
    worker.close()
    with pytest.raises(ValueError):
        embed.WorkerEmbedder("elsewhere", tmp_path / "data", command=["x"])


def test_15_9_5d_the_worker_command_and_its_environment_keep_the_hub_inside_the_data_folder(tmp_path):
    data = tmp_path / "data"
    assert not embed.installed(data)
    command = embed.worker_command(data, "card", system="Windows")
    assert Path(command[0]).parts[-3:] == (".venv", "Scripts", "python.exe") and command[-2:] == ["--device", "card"]
    assert Path(command[1]).name == "worker.py" and Path(command[3]) == embed.model_folder(data)
    env = embed.worker_env(data, {"PATH": "x", "SPEECHMATICS_API_KEY": "secret", "HF_HOME": "/elsewhere"})
    assert env["HF_HUB_OFFLINE"] == "1" and "SPEECHMATICS_API_KEY" not in env
    assert Path(env["HF_HOME"]).parts[-3:] == ("embedding", "embeddinggemma2", "hub")
