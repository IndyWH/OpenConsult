"""The embedding worker as a worker of the app (spec 15.12, The embedding
worker in the app; 15.8 ruling 32; 6.2; 10.4; ruling 9): started at app
start where the room check put it, not started when not installed, a
death said with its reason and never a restart by itself, the rerank
request over the frames. A made-up worker speaking the real frames; no
model loads."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from openconsult.app import build_app
from openconsult.guidelines import embedder as embedder_module
from openconsult.guidelines import environment
from openconsult.guidelines.embedder import NotInstalled, WorkerEmbedder, make_embedder
from openconsult.settings import store
from openconsult.settings.machine import Card, describe
from tests.conftest import ORIGIN, PORT
from tests.fakes import FakeEngine

MADE = Path(__file__).parent / "made_up_embedder.py"


def made_command(mode="ready", where="card", reranker=False):
    command = [sys.executable, str(MADE), mode, "--device", where]
    if reranker:
        command += ["--reranker", "x", "--reranker-device", "processor"]
    return command


def pretend_installed(monkeypatch, mode="ready"):
    """The data folder looks installed and the worker's command is the made one."""
    monkeypatch.setattr(environment, "installed", lambda data_folder, system=None: True)
    monkeypatch.setattr(environment, "worker_command", lambda data_folder, where, system=None, reranker=False, reranker_where=None:
                        made_command(mode, where, reranker))


def test_ruling_32_6_2_the_worker_is_started_at_app_start_where_the_room_check_put_it_and_not_when_not_installed(tmp_path, clock, machine, monkeypatch):
    # Not installed: the door with nothing behind it, no process.
    bare = build_app(store.build(tmp_path / "bare", PORT), machine=machine, clock=clock,
                     engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    assert isinstance(bare.state.parts.embedder, NotInstalled) and bare.state.parts.embedder.where == "card"
    # Installed, on a suitable card with room: started on the card, ready at the first use, the model named.
    pretend_installed(monkeypatch)
    app = build_app(store.build(tmp_path / "card", PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    worker = app.state.parts.embedder
    assert isinstance(worker, WorkerEmbedder) and worker.where == "card" and worker.state in ("starting", "ready")
    assert worker.ready() is None and worker.state == "ready" and worker.model_id == "made-up/embedder@0"
    assert worker.info()["device"] == "card" and worker.installed
    found = worker.embed(["task: search result | query: Made-up A", "second"])
    assert found.ok and len(found.vectors) == 2 and len(found.vectors[0]) == 768
    with TestClient(app, base_url=ORIGIN):
        pass                                                  # the lifespan: every worker ends with the app
    assert worker.state == "stopped" and not worker.embed(["x"]).ok
    # A card with no room beside the language model and the speech model: the processor (ruling 32).
    small = describe("Linux", "x86_64", [Card("Made-up card", 24564)])
    from openconsult.settings import room
    monkeypatch.setattr(room, "LANGUAGE_MODEL_MIB", {"vllm": 18316, "ollama": 22000, None: 0})
    other = build_app(store.build(tmp_path / "processor", PORT), machine=small, clock=clock,
                      engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine()})
    assert other.state.parts.decisions.guideline_search.green is False
    assert other.state.parts.embedder.where == "processor" and other.state.parts.embedder.ready() is None
    assert other.state.parts.embedder.info()["device"] == "processor"
    other.state.parts.embedder.close()


def test_10_4_a_dead_worker_is_a_failure_said_with_its_reason_and_nothing_starts_it_again(tmp_path):
    worker = WorkerEmbedder("card", tmp_path / "data", command=made_command("die_at_second"))
    worker.start()
    try:
        assert worker.ready() is None and worker.embed(["one"]).ok
        second = worker.embed(["two"])
        assert not second.ok and "out of memory" in second.error.lower() and worker.state == "failed"
        third = worker.embed(["three"])
        assert not third.ok and worker.state == "failed" and worker.reason and worker.ready() == worker.reason
        assert worker.model_id == "made-up/embedder@0"            # what it said when ready stays for the record
    finally:
        worker.close()
    refusing = WorkerEmbedder("processor", tmp_path / "data", command=made_command("refuse"))
    refusing.start()
    try:
        assert refusing.ready() is None and refusing.embed(["one"]).error == "made-up: refused"
    finally:
        refusing.close()
    never = WorkerEmbedder("processor", tmp_path / "data", command=[sys.executable, "-c", "import sys; sys.exit(2)"])
    never.start()
    assert never.ready() is not None and never.state == "failed"
    never.close()
    assert make_embedder(tmp_path / "nothing", "card").state == "not_installed"


def test_ruling_9_the_worker_reranks_over_the_frames_and_the_command_names_its_device(tmp_path):
    with_reranker = WorkerEmbedder("card", tmp_path / "data", command=made_command(reranker=True), reranker=True)
    with_reranker.start()
    try:
        assert with_reranker.ready() is None
        info = with_reranker.info()
        assert (info["reranker"], info["reranker_revision"], info["reranker_device"]) == ("made-up/reranker", "r0", "processor")
        scores = with_reranker.rerank("Made-up A; Made-up B", ["short", "a longer made text", "mid text"])
        assert scores.ok and scores.scores == [5.0, 18.0, 8.0]
    finally:
        with_reranker.close()
    without = WorkerEmbedder("card", tmp_path / "data", command=made_command())
    without.start()
    try:
        assert without.ready() is None and without.info()["reranker"] is None
        refused = without.rerank("q", ["a"])
        assert not refused.ok and refused.error == "no reranker is loaded"
    finally:
        without.close()
    command = environment.worker_command(tmp_path / "d", "card", system="Linux", reranker=True, reranker_where="processor")
    assert command[-4:] == ["--reranker", str(environment.reranker_folder(tmp_path / "d")), "--reranker-device", "processor"]
    assert "--reranker" not in environment.worker_command(tmp_path / "d", "card", system="Linux")
    assert Path(command[0]).parts[-3:] == (".venv", "bin", "python") and Path(command[1]).name == "worker.py"
    assert environment.WORKER_FOLDER.name == "embedding2" and environment.WORKER_FOLDER.parent.name == "guidelines"
    assert embedder_module.WORKER_READY_S == 300.0
