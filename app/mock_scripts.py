"""Parse the mock consultation scripts into spoken turns.

Used by the CDS simulation harness (Phase 3) and later for ASR/NLP
benchmarking: the scripts in mock_consultations/ are the ground truth the
whole pipeline is measured against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Lines like: **DOCTOR:** Good morning, come in.
_TURN_RE = re.compile(r"^\*\*([A-Z]+):\*\*\s*(.+)$")
# Stage directions like *(laughs)* are not spoken.
_STAGE_RE = re.compile(r"\*\([^)]*\)\*\s*")


@dataclass
class Turn:
    speaker: str  # DOCTOR / PATIENT / MOTHER
    text: str


def parse_script(path: str | Path) -> list[Turn]:
    turns: list[Turn] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = _TURN_RE.match(line.strip())
        if match:
            text = _STAGE_RE.sub("", match.group(2)).strip()
            if text:
                turns.append(Turn(speaker=match.group(1), text=text))
    return turns


def as_live_transcript(turns: list[Turn]) -> str:
    """Render turns the way the live pass sees them: plain text, NO speaker
    labels (live transcription has no diarisation, per the plan)."""
    return "\n".join(t.text for t in turns)
