"""Runs a real cloud worker as a subprocess against the made-up service,
for the suite: the worker module is loaded by path and its main is given
a dial that opens the made-up address. This is Python code the test
writes, not a setting, a file the app reads or an environment value: the
worker's own main still dials its EU address and nothing else.

    python made_up_dial.py speechmatics ws://127.0.0.1:PORT
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

WORKERS = Path(__file__).resolve().parents[1] / "openconsult" / "speech"


def load_worker(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_worker", WORKERS / name / "worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str]) -> int:
    worker = load_worker(argv[0])
    address = argv[1]
    cloud = worker.cloud
    path = worker.ADDRESS[len("wss://" + worker.EU_HOST):]
    if argv[0] == "assemblyai":
        return worker.main(dial_with=lambda key, rate, speakers: cloud.open_connection(
            worker.address_for(rate, speakers, address + path), worker.headers(key)))
    return worker.main(dial=lambda key: cloud.open_connection(address + path, worker.headers(key)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
