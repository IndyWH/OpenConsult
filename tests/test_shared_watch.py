"""What is read beside a setup of 5d (spec 15.9, the details of 5d, line
one): every reading kept with its moment, a reader that fails kept as
failed. Everything a server or nvidia-smi says here is made up."""

import subprocess

from openconsult.bench.shared import watch


class Done:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_15_9_5d_a_reading_holds_the_list_the_health_and_the_card_with_its_moment(server):
    server.routes["/api/ps"] = (200, {"models": [{"name": "made-up:latest", "size": 10, "size_vram": 10}]})
    server.routes["/health"] = (200, {})
    server.routes["/v1/models"] = (200, {"data": [{"id": "made-up/model"}]})
    card = Done("1234, /made-up/speech/nemotron/.venv/bin/python, 4022\n77, /x, y\nnot a line\n")
    readers = {"service": lambda: watch.read_ollama(server.address),
               "vllm": lambda: watch.read_vllm(server.address),
               "card": lambda: watch.read_card(run=lambda *a, **k: card),
               "broken": lambda: 1 / 0}
    clock = {"t": 0.0}
    taken = []

    def wall():
        taken.append(1)
        return 5.0 + 5.0 * len(taken)

    def sleep(s):
        clock["t"] += s

    found = watch.watch(readers, lambda: len(taken) >= 3, every_s=5.0, sleep=sleep, clock=lambda: clock["t"], wall=wall)
    first = found["readings"][0]
    assert first["at_epoch"] == 10.0 and first["service"] == {"available": True, "models": [{"name": "made-up:latest", "size": 10, "size_vram": 10}]}
    assert first["vllm"] == {"available": True, "health": 200, "models": ["made-up/model"]}
    assert first["card"]["programs"] == [{"pid": 1234, "name": "/made-up/speech/nemotron/.venv/bin/python", "mib": 4022},
                                          {"pid": 77, "name": "/x", "mib": None}]
    assert first["broken"]["available"] is False and "ZeroDivisionError" in first["broken"]["failed"]
    assert len(found["readings"]) == 3 and found["sources"] == ["broken", "card", "service", "vllm"]


def test_15_9_5d_a_machine_without_nvidia_smi_or_an_engine_is_a_reading_that_says_so():
    def no_such(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    assert watch.read_card(run=no_such) == {"available": False, "error": "FileNotFoundError: nvidia-smi", "programs": []}
    assert watch.read_card(run=lambda *a, **k: Done("", 1, "made-up: no card"))["available"] is False
    assert watch.read_ollama("http://127.0.0.1:9") == {"available": False, "models": []}
    assert watch.read_vllm("http://127.0.0.1:9")["available"] is False
    assert isinstance(subprocess.run, type(watch.subprocess.run))
