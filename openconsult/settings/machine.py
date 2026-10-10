"""This machine (spec 6.4, 15.6): the system, the graphics card and its
memory, and one sentence in plain words.

The card is found by asking the tool that comes with the NVIDIA driver,
with no heavy library (spec 5.1). A Mac, no card, and a card that could
not be read are each said plainly, and none of them stops the app.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from openconsult import words

# Everything local at once needs one card with this much memory
# (spec 6.4, measured in Task 13). With several cards the largest counts.
NEEDED_GB = 24

TOOL = "nvidia-smi"
TOOL_ARGS = ["--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
TOOL_TIMEOUT_S = 10


@dataclass(frozen=True)
class Card:
    name: str
    memory_mib: int

    @property
    def gb(self) -> int:
        # A card sold as 24 GB reports a little under 24 binary GB
        # (24564 MiB), so the figure is rounded (spec 6.4 counts 24 GB).
        return round(self.memory_mib / 1024)


@dataclass(frozen=True)
class Machine:
    system: str
    case: str  # suitable, smaller, none, mac or unreadable
    card: Card | None
    card_line: str
    sentence: str


def describe(system: str, arch: str, cards: list[Card] | None) -> Machine:
    """The sentence for what was found. cards is None when the tool was
    there but could not be read."""
    system_line = f"{_system_name(system)} ({arch})"
    if system == "Darwin":
        return Machine(system_line, "mac", None, words.CARD_NONE, words.MACHINE["mac"])
    if cards is None:
        return Machine(system_line, "unreadable", None, words.CARD_UNREADABLE, words.MACHINE["unreadable"])
    if not cards:
        return Machine(system_line, "none", None, words.CARD_NONE, words.MACHINE["none"])
    card = max(cards, key=lambda c: c.memory_mib)
    line = words.CARD_LINE.format(name=card.name, gb=card.gb)
    if card.gb >= NEEDED_GB:
        return Machine(system_line, "suitable", card, line, words.MACHINE["suitable"])
    sentence = words.MACHINE["smaller"].format(gb=card.gb, needed=NEEDED_GB)
    return Machine(system_line, "smaller", card, line, sentence)


def parse_cards(output: str) -> list[Card]:
    cards = []
    for line in output.splitlines():
        if not line.strip():
            continue
        name, _, memory = line.rpartition(",")
        cards.append(Card(name.strip(), int(memory.strip())))
    return cards


def read_cards(which: Callable = shutil.which, run: Callable = subprocess.run) -> list[Card] | None:
    """Ask the driver's tool. No tool means no NVIDIA card. A tool that
    fails, hangs or answers oddly means the card could not be read."""
    tool = which(TOOL)
    if tool is None:
        return []
    try:
        result = run([tool, *TOOL_ARGS], capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)
        if result.returncode != 0:
            return None
        return parse_cards(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def read_machine(system: str | None = None, arch: str | None = None,
                 which: Callable = shutil.which, run: Callable = subprocess.run) -> Machine:
    system = system or platform.system()
    arch = arch or platform.machine()
    cards = [] if system == "Darwin" else read_cards(which, run)
    return describe(system, arch, cards)


def _system_name(system: str) -> str:
    return {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(system, system)
