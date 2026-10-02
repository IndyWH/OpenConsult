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


# The patient of each script, for the patient line the live app sends
# (Task 5b, owner ruling 2026-10-02: the alarm harness must have age and
# sex). Age from each script's own **Fictional patient:** header; sex from
# its title there (Mr → M; Mrs, Miss, Ms → F; 10 is "schoolboy" → M).
# Every script in mock_consultations/ has an entry — a test checks it.
SCRIPT_PATIENTS: dict[str, tuple[int, str]] = {
    "01_chest_pain_en.md": (52, "M"),
    "03_diabetes_review_en.md": (58, "F"),
    "04_asthma_en.md": (24, "F"),
    "05_epigastric_pain_en.md": (35, "M"),
    "06_tia_funny_turn_en.md": (72, "M"),
    "07_gi_bleed_en.md": (35, "M"),
    "08_pulmonary_embolism_en.md": (41, "F"),
    "10_testicular_torsion_en.md": (15, "M"),
    "11_tired_all_the_time_uk.md": (34, "F"),
    "12_dizziness_uk.md": (45, "M"),
    "13_migraine_uk.md": (29, "F"),
    "14_giant_cell_arteritis_uk.md": (71, "F"),
    "15_cauda_equina_uk.md": (40, "M"),
    "16_urti_antibiotic_demand_auto.md": (47, "M"),
    "17_perimenopause_auto.md": (48, "F"),
    "18_ectopic_pregnancy_auto.md": (31, "F"),
}


def script_patient(name: str) -> dict | None:
    """The patient of script `name` (a file name in mock_consultations/) in
    the form CDSEngine.update takes, {"age", "sex"}; None for a script not
    in the table."""
    if name not in SCRIPT_PATIENTS:
        return None
    age, sex = SCRIPT_PATIENTS[name]
    return {"age": age, "sex": sex}
