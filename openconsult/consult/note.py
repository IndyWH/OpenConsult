"""The note (spec 15.10, rulings 3, 5, 6 and 8; The note; R4; D3). What
the model reads: the frame of ruling 5 around the turns, one line a
turn, its number in square brackets, the speaker word, a colon and the
words. The three speaker words are the bench's (15.9 ruling 22), typed
here once and read by the bench too, so no word a model reads is new.
The turns are built by the bench's own rule from the transcript lines as
they stand after the label check and after any edit: neighbouring lines
of one label join, numbered from 0. No patient line is sent (D3). After
the call, v1's citation check with its half line (ruling 8; R4), as plain
functions apart from the call (V1_LESSONS 6.2)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from openconsult import words
from openconsult.consult.note_rows import DraftRow, Notes
from openconsult.llm.door import Door
from openconsult.patients.audit import Audit
from openconsult.prompts import loader
from openconsult.speech.matching import normalise

# v1's two role words (V1/app/finalize.py) and the owner's word for a turn
# with no speaker (15.9 ruling 22).
DOCTOR, PATIENT, UNKNOWN = "Doctor", "Patient", "Unknown"
ROLE_WORDS = {"doctor": DOCTOR, "patient": PATIENT, "unsure": UNKNOWN}


def turns_of(rows: list[dict]) -> list[dict]:
    """Turns {n, label, text, lines} from the numbered transcript rows in
    order: neighbouring lines of the same label join, numbered from 0 as
    v1 numbered them and as the bench's turns_of does."""
    turns: list[dict] = []
    for row in rows:
        if row.get("n") is None:
            continue
        if turns and turns[-1]["label"] == row["label"]:
            turns[-1]["text"] += " " + row["text"]
            turns[-1]["lines"].append(row["n"])
        else:
            turns.append({"n": len(turns), "label": row["label"], "text": row["text"], "lines": [row["n"]]})
    return turns


def turns_text(turns: list[dict]) -> str:
    """The user text: the frame file's words around one line for each
    turn. Nothing else: no patient line (D3), no differentials (R4)."""
    lines = "\n".join(f"[{turn['n']}] {ROLE_WORDS[turn['label']]}: {turn['text']}" for turn in turns)
    return loader.fill(loader.frame("note"), transcript=lines)


# ----------------------------------------------------- the citation check

# v1's MIN_CITED_FRACTION: a note in which fewer than half the entries cite
# a real line is refused, with the count shown and the draft discarded
# (consultation 78; ruling 8). A design choice from v1, not a measurement;
# the room may move it.
CITATION_HALF = 0.5
# The letter's half (15.12 ruling 4): the same shape as the note gate, a
# letter with fewer than half its sentences grounded in the note refused.
LETTER_GROUNDED_HALF = 0.5
SECTIONS = ("subjective", "objective", "assessment", "plan")
_BRACKETS = re.compile(r"\[([^\[\]]+)\]")


@dataclass(frozen=True)
class Checked:
    entries: list          # each: section, text, turns, lines, uncited
    total: int
    cited: int
    refused: bool


def _numbers_in_brackets(text: str) -> list[int]:
    """Citations written inside an entry's words, in square brackets, as
    numerals or number words (V1_LESSONS 3.6: checks read number words):
    only brackets whose every word reads as a number count."""
    found = []
    for inside in _BRACKETS.findall(str(text or "")):
        words = normalise(inside)
        if words and all(w.isdigit() for w in words):
            found += [int(w) for w in words]
    return found


def cited_turns(entry: dict) -> list[int]:
    """The turn numbers an entry cites: its turns field (integers; a
    boolean is not a number), or, where that is empty, the citations
    written in its words."""
    turns = [t for t in (entry.get("turns") or []) if isinstance(t, int) and not isinstance(t, bool)]
    return turns or _numbers_in_brackets(entry.get("text", ""))


def check_citations(note: dict, turns: list[dict]) -> Checked:
    """Every entry's cited turns read back to the transcript lines they
    hold; an entry none of whose cited turns exists is kept and marked
    uncited; the note is refused when fewer than half the entries cite a
    real turn, or there is none. The check proves that a cited line
    exists, not that the entry is true to it (V1_LESSONS 3.6)."""
    lines_of = {turn["n"]: list(turn["lines"]) for turn in turns}
    entries, cited = [], 0
    for section in SECTIONS:
        for entry in note.get(section) or []:
            numbers = cited_turns(entry)
            lines = sorted({n for t in numbers for n in lines_of.get(t, [])})
            uncited = not lines
            cited += not uncited
            entries.append({"section": section, "text": str(entry.get("text", "")), "turns": numbers,
                            "lines": lines, "uncited": uncited})
    total = len(entries)
    return Checked(entries, total, cited, total == 0 or cited / total < CITATION_HALF)


def strip_citations(text: str) -> str:
    """The words without a bracketed citation the check would read as a
    turn; other brackets stay (the plan review, point 2)."""
    def drop(match):
        words = normalise(match.group(1))
        return "" if words and all(w.isdigit() for w in words) else match.group(0)
    return re.sub(r" {2,}", " ", _BRACKETS.sub(drop, str(text))).strip()


def plain_text(entries: list[dict]) -> str:
    """The copy text (ruling 4): the four sections under their headings,
    each entry's words as they stand less any bracketed citation, one a
    line; nothing else."""
    blocks = []
    for section in SECTIONS:
        lines = [words.SECTION_WORDS[section]] + [strip_citations(e["text"]) for e in entries if e["section"] == section]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def last_shown_differentials(pass_rows: list[dict]) -> list:
    """The differentials of the last pass that was shown and whose
    assessment answered, as the live page last showed them (ruling 4;
    ruling 2: a failed pass keeps the earlier lists, and a kept list is
    already resolved in the stored result)."""
    found: list = []
    for row in pass_rows:
        result = row.get("result") or {}
        assessment = result.get("assessment") or {}
        if row.get("shown") and assessment.get("ok"):
            found = list(assessment.get("differentials") or [])
    return found


# ---------------------------------------------------------------- the draft

def draft(door: Door, rows_table, notes: Notes, audit: Audit, consultation_id: int, asked_by: str) -> dict:
    """One call for the note from the lines as they stand, the citation
    check, and the rows: the draft with its stamp (from the consultation
    row, R20), its prompt hash, what the model read, its entries and its
    count; a refused draft keeps no entry; a failed call is kept as
    failed, said plainly, and nothing is asked a second time by itself
    (R30; 10.4). Returns the draft row."""
    rows = [r for r in rows_table.transcript_lines(consultation_id) if r["n"] is not None]
    row = rows_table.get(consultation_id)
    turns = turns_of(rows)
    text = turns_text(turns)
    result = door.ask("note", text, consultation_id=consultation_id)
    reasoning, entries, total, cited, refused, failure = None, [], 0, 0, False, None
    if result.ok:
        checked = check_citations(result.answer, turns)
        reasoning = str(result.answer.get("reasoning") or "")
        total, cited, refused = checked.total, checked.cited, checked.refused
        entries = [] if refused else checked.entries
    else:
        failure = f"{result.failure}: {result.detail}"
    draft_id = notes.add_draft(DraftRow(
        consultation_id, asked_by, result.call_id, row["engine"], row["engine_version"], row["model_tag"],
        row["model_digest"], hashlib.sha256(loader.prompt_bytes("note")).hexdigest(), text,
        rows_table.last_edit_id(consultation_id), reasoning, total, cited, refused, failure, result.wall_ms, entries))
    if failure:
        audit.record("note.failed", f"consultation {consultation_id}: {failure}")
    elif refused:
        audit.record("note.refused_by_check", f"consultation {consultation_id}: {cited} of {total} entries cite a line")
    else:
        audit.record("note.drafted", f"consultation {consultation_id}: draft {notes.draft(draft_id)['n']}, "
                                     f"{total} entries, {cited} cited, {result.wall_ms} ms")
    return notes.draft(draft_id)
