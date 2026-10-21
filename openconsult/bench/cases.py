"""The bench's cases (spec 15.7; V1_LESSONS 9.4, 9.5). They live outside
the repo, in a folder with a list beside them: for each case its file,
its sha256, the patient's age and sex, what is expected and where the
transcript is cut. The bench takes its cases from that list only, and
refuses a file whose checksum differs. The list of 7b (15.11 ruling 6)
is a plain list whose entries carry no sha256 but an earlier approved
note and its date: the hash is computed and carried with every result,
and the note becomes the block of ruling 5 as the app would send it.

The script parser and the live-transcript renderer are ported from v1
as plain functions (spec 6.1): a transcript the live pass sees has no
speaker labels and no stage directions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openconsult.consult.background import build_block
from openconsult.consult.earlier import ApprovedNote, sections_of
from openconsult.consult.messages import Patient

# Lines like: **DOCTOR:** Good morning. Stage directions like *(laughs)* are not spoken.
_TURN_RE = re.compile(r"^\*\*([A-Z]+):\*\*\s*(.+)$")
_STAGE_RE = re.compile(r"\*\([^)]*\)\*\s*")
TURNS_PER_UPDATE = 4


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str


def parse_script(text: str) -> list[Turn]:
    turns = []
    for line in text.splitlines():
        match = _TURN_RE.match(line.strip())
        if match:
            spoken = _STAGE_RE.sub("", match.group(2)).strip()
            if spoken:
                turns.append(Turn(match.group(1), spoken))
    return turns


def live_transcript(turns: list[Turn]) -> str:
    return "\n".join(t.text for t in turns)


def cuts(n_turns: int, step: int = TURNS_PER_UPDATE) -> list[int]:
    """The update points: every `step` turns, and the end."""
    return [min(c, n_turns) for c in range(step, n_turns + step, step)]


class CaseChanged(Exception):
    """A case file's checksum differs from the list."""


@dataclass(frozen=True)
class Case:
    name: str
    group: str          # 495, travel or script: which rules score it
    kind: str           # script (a scripted consultation) or passes (recorded live transcripts)
    path: Path
    sha256: str
    patient: Patient
    expected: dict
    consultation: int | None = None
    earlier_note: Path | None = None       # 7b: the earlier approved note's file
    earlier_note_date: date | None = None

    def background(self) -> str | None:
        """The block of 15.11 ruling 5 for the earlier note, laid out by the
        app's own code as for a patient with that one approved note, cut
        as the app cuts; None where the case has no earlier note."""
        if self.earlier_note is None:
            return None
        when = datetime(self.earlier_note_date.year, self.earlier_note_date.month, self.earlier_note_date.day)
        note = ApprovedNote(0, when, when, sections_of(self.earlier_note.read_text(encoding="utf-8")))
        return build_block([note])

    def points(self) -> list[tuple[int, str]]:
        """(point, transcript) for each pass: the turn the script is cut at,
        or the pass number of a recorded transcript."""
        text = self.path.read_text(encoding="utf-8")
        if self.kind == "passes":
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            mine = sorted((r for r in rows if r.get("consultation") == self.consultation),
                          key=lambda r: r["pass"])
            return [(r["pass"], r["transcript"]) for r in mine]
        turns = parse_script(text)
        return [(end, live_transcript(turns[:end])) for end in cuts(len(turns))]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(folder: Path, list_name: str = "cases.json") -> list[Case]:
    """The list, checked: every file present, with its checksum where the
    list gives one."""
    folder = Path(folder)
    listed = json.loads((folder / list_name).read_text(encoding="utf-8"))
    cases = []
    for entry in listed if isinstance(listed, list) else listed["cases"]:
        path = _present(folder, entry, entry["file"])
        found = sha256_of(path)
        if "sha256" in entry and found != entry["sha256"]:
            raise CaseChanged(f"{entry['name']}: {entry['file']} has sha256 {found}, "
                              f"not {entry['sha256']}")
        note = _present(folder, entry, entry["earlier_note"]) if entry.get("earlier_note") else None
        cases.append(Case(entry["name"], entry["group"], entry["kind"], path, found,
                          Patient(int(entry["age"]), entry["sex"]), entry.get("expected", {}),
                          entry.get("consultation"), note,
                          date.fromisoformat(entry["earlier_note_date"]) if note else None))
    return cases


def _present(folder: Path, entry: dict, name: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise CaseChanged(f"{entry['name']}: {name} is missing")
    return path


def case_named(cases: list[Case], name: str) -> Case:
    for case in cases:
        if case.name == name:
            return case
    raise KeyError(f"no case named {name} on the list")
