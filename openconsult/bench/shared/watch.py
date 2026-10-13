"""What is read beside a setup of 5d, every 5 seconds (spec 15.9, the
details of 5d, line one): Ollama's list of loaded models on the service
and, for the together way, on the private Ollama; vLLM's health and its
list of models; and the card's own list of programs with their memory
(nvidia-smi, read only). Each reading is kept with its moment. A reader
that fails is kept as failed, never raised: the judge reads what is
there. Nothing here changes anything."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from typing import Callable

from openconsult.bench.shared.embed import _exchange, loaded_models

EVERY_S = 5.0
WAIT_SLICE_S = 0.5
NVIDIA_SMI = ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"]


def read_card(run: Callable = subprocess.run) -> dict:
    """The programs on the card, each with its memory in MiB, or not available."""
    try:
        done = run(NVIDIA_SMI, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as failed:
        return {"available": False, "error": f"{type(failed).__name__}: {failed}", "programs": []}
    if done.returncode != 0:
        return {"available": False, "error": (done.stderr or done.stdout or "").strip()[:300], "programs": []}
    programs = []
    for line in done.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[0].isdigit():
            try:
                programs.append({"pid": int(parts[0]), "name": ",".join(parts[1:-1]), "mib": int(parts[-1])})
            except ValueError:
                programs.append({"pid": int(parts[0]), "name": ",".join(parts[1:-1]), "mib": None})
    return {"available": True, "error": None, "programs": programs}


def read_ollama(address: str, urlopen: Callable = urllib.request.urlopen) -> dict:
    listed = loaded_models(address, urlopen)
    return {"available": listed is not None, "models": listed or []}


def read_vllm(address: str, urlopen: Callable = urllib.request.urlopen) -> dict:
    status, _ = _exchange(address.rstrip("/"), "/health", None, 5.0, urlopen)
    found, text = _exchange(address.rstrip("/"), "/v1/models", None, 5.0, urlopen)
    models = []
    if found == 200:
        try:
            models = [m.get("id") for m in (json.loads(text).get("data") or []) if isinstance(m, dict)]
        except ValueError:
            models = []
    return {"available": status == 200, "health": status, "models": models}


def one_reading(readers: dict[str, Callable], wall: Callable = time.time) -> dict:
    """One reading of every source, each kept as what it gave or as failed."""
    reading = {"at_epoch": wall()}
    for name, read in readers.items():
        try:
            reading[name] = read()
        except Exception as failed:  # noqa: BLE001 - a reading that fails is kept, never raised
            reading[name] = {"available": False, "failed": f"{type(failed).__name__}: {failed}"[:300]}
    return reading


def watch(readers: dict[str, Callable], until: Callable[[], bool], every_s: float = EVERY_S,
          sleep: Callable = time.sleep, clock: Callable = time.monotonic, wall: Callable = time.time) -> dict:
    """Readings every every_s seconds until the stop condition is true,
    then one last reading (the one after Stop)."""
    readings, t0, k = [], clock(), 0
    while True:
        readings.append(one_reading(readers, wall))
        if until():
            break
        k += 1
        due = t0 + k * every_s
        while clock() < due and not until():
            sleep(min(WAIT_SLICE_S, max(0.0, due - clock())))
    return {"every_s": every_s, "sources": sorted(readers), "readings": readings}
