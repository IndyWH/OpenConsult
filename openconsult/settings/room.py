"""The room on the graphics card, read once at start (spec 15.8, rulings
32, 33 and 36; the details of 3c). It reads the card's total and what
programs other than the app's own engines hold at that moment, with the
tool This machine already uses, and reckons with what each program
needs, not with what happens to be loaded: Ollama loads its model at
the first call and lets it go when idle. Two sums decide where
EmbeddingGemma 2 sits and whether the WhisperX choice is offered. It
reads again only at the next start, never during a consultation.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from openconsult.settings.decisions import GUIDELINE_SEARCH, WHISPERX_CHOICE, Element
from openconsult.settings.machine import TOOL, TOOL_TIMEOUT_S, Machine

# The needs in MiB: each the highest reading of 5d on this card (the
# report of 5d, 13 Oct 2026, the card's memory at each step), so that a
# sum is never short of what was seen. None: no language model on the
# card, the cloud or no local engine, whose need is 0.
LANGUAGE_MODEL_MIB = {"vllm": 18316, "ollama": 16568, None: 0}
NEMOTRON_MIB = 3384
WHISPERX_LIVE_MIB = 2452
WHISPERX_STOP_MIB = 9464
EMBEDDING_2_MIB = 1010
# Below the 1,313 that 5d's fullest setup left (the details of 3c).
MARGIN_MIB = 1000
# The app's own engines, told apart from other programs by name: 5d's
# sampler recorded vLLM's process as VLLM::EngineCore and Ollama's runner
# under its own folder (/usr/lib/ollama/llama-server). Their need is the
# constant above, never what they hold at the moment.
OWN_ENGINE_WORDS = ("vllm", "ollama")
PROGRAMS_ARGS = ["--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"]


@dataclass(frozen=True)
class Program:
    pid: int
    name: str
    mib: int


def is_own(name: str) -> bool:
    low = name.lower()
    return any(word in low for word in OWN_ENGINE_WORDS)


def parse_programs(output: str) -> list[Program]:
    found = []
    for line in output.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[0].isdigit() and parts[-1].isdigit():
            found.append(Program(int(parts[0]), ",".join(parts[1:-1]), int(parts[-1])))
    return found


def read_programs(which: Callable = shutil.which, run: Callable = subprocess.run) -> list[Program] | None:
    """The programs on the card with their memory, or None when the tool
    is absent or could not be read; the check then counts nothing else."""
    tool = which(TOOL)
    if tool is None:
        return None
    try:
        done = run([tool, *PROGRAMS_ARGS], capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return parse_programs(done.stdout) if done.returncode == 0 else None


def others_mib(programs: list[Program] | None) -> int:
    return sum(p.mib for p in programs or [] if not is_own(p.name))


def check(machine: Machine, engine: str | None, programs: list[Program] | None) -> dict[str, Element]:
    """The two elements: where the guideline search sits, and whether the
    WhisperX choice is offered. engine is the engine chosen at start, or
    None when no local engine holds the card."""
    total = machine.card.memory_mib if machine.card else 0
    others = others_mib(programs)
    model = LANGUAGE_MODEL_MIB[engine]
    shared = {"card total": total, "other programs": others, "free": total - others,
              "language model": f"{model} ({engine or 'none'})"}
    if total == 0:
        return {GUIDELINE_SEARCH: Element(GUIDELINE_SEARCH, False, "guideline_no_card", {}, shared),
                WHISPERX_CHOICE: Element(WHISPERX_CHOICE, False, "whisperx_no_card", {}, shared)}
    first = others + model + NEMOTRON_MIB + EMBEDDING_2_MIB + MARGIN_MIB
    on_card = first <= total
    guideline = Element(GUIDELINE_SEARCH, on_card, "guideline_card" if on_card else "guideline_processor", {}, {
        **shared, "Nemotron": NEMOTRON_MIB, "EmbeddingGemma 2": EMBEDDING_2_MIB, "margin": MARGIN_MIB,
        "sum": first, "spare": total - first})
    embedding = EMBEDDING_2_MIB if on_card else 0
    second = others + model + embedding + WHISPERX_STOP_MIB + MARGIN_MIB
    offered = second <= total
    whisperx = Element(WHISPERX_CHOICE, offered, "whisperx_available" if offered else "whisperx_no_room", {}, {
        **shared, "EmbeddingGemma 2 on the card": embedding, "WhisperX at Stop": WHISPERX_STOP_MIB,
        "WhisperX live": WHISPERX_LIVE_MIB, "margin": MARGIN_MIB, "sum": second, "spare": total - second})
    return {GUIDELINE_SEARCH: guideline, WHISPERX_CHOICE: whisperx}
