"""The background block (spec 15.11 ruling 5; 8.3; 8.5; R25; D23): the
last three approved notes of the patient, newest first, each laid out
by background.note.txt with its date in words, none for an empty
section, the entries' words with bracketed citations stripped, one
entry a line; a note over BACKGROUND_NOTE_MAX_WORDS is cut at the end of
the last entry that fits and ends with the line of background.cut.txt;
the notes go into background.frame.txt. Every word a model would read
comes from those three files; only the date and the entries are filled
by code. In 7a this is built and tested and no call carries it: cds_pass
places it between the patient line and each frame in 7b, once the bench
of 8.6 has passed. Alba's calls take the same block at stage 12."""

from __future__ import annotations

from datetime import date, datetime

from openconsult.consult.earlier import ApprovedNote, panel_notes
from openconsult.consult.note import SECTIONS
from openconsult.prompts import loader

# The cut of D23, in words of the entries (the labels and the date line
# are not counted). The longest note of 5c part two (the rehearsal of 11
# Oct 2026, 36 notes) held 228 words of entries over 26 entries, and the
# longest of the 6b bench of the new prompt 317; 400 leaves a margin over
# both, so no note the room has yet produced is cut, and three notes at
# the limit are about 1,200 words, a tenth of the context beside today's
# transcript. A design choice; the room may move it.
BACKGROUND_NOTE_MAX_WORDS = 400
# The model's word for an empty section (ruling 5), the one word of the
# block that is neither in a file nor from the note.
NONE = "none"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


def date_in_words(day: date | datetime) -> str:
    """12 March 2026 (ruling 5), the same on every system."""
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def words_in(entries: list[str]) -> int:
    return sum(len(entry.split()) for entry in entries)


def lay_out(note: ApprovedNote, max_words: int = BACKGROUND_NOTE_MAX_WORDS) -> str:
    """One note by background.note.txt. Where the entries' words pass the
    limit, the laid-out lines after the last whole entry that fits are
    dropped and the cut line stands last (the plan review, point 4)."""
    sections = {s: list(note.sections.get(s) or []) for s in SECTIONS}
    laid = loader.fill(loader.file_text("background.note"), date=date_in_words(note.started_at),
                       **{s: "\n".join(sections[s]) or NONE for s in SECTIONS})
    if words_in([e for s in SECTIONS for e in sections[s]]) <= max_words:
        return laid
    kept, count = [], 0
    for section in SECTIONS:
        label = loader.file_text("background.note").split("{" + section + "}")[0].rsplit("\n", 1)[-1]
        for position, entry in enumerate(sections[section]):
            if count + len(entry.split()) > max_words:
                return "\n".join(_cut_lines(laid, kept)) + "\n" + loader.file_text("background.cut")
            count += len(entry.split())
            kept.append((label + entry) if position == 0 else entry)
        if not sections[section]:
            kept.append(label + NONE)
    return laid


def _cut_lines(laid: str, kept: list[str]) -> list[str]:
    """The laid-out lines up to the last kept entry: the date line, then
    exactly the lines the kept entries made."""
    lines = laid.split("\n")
    return lines[:1] + lines[1:1 + len(kept)]


def build_block(notes: list[ApprovedNote], max_words: int = BACKGROUND_NOTE_MAX_WORDS) -> str:
    """The frame filled with the laid-out notes, one blank line between."""
    return loader.fill(loader.file_text("background.frame"), notes="\n\n".join(lay_out(n, max_words) for n in notes))


def block_for(notes_table, patient_id: int, started_at: datetime, consultation_id: int) -> str | None:
    """The block for one consultation, or None where the patient has no
    note approved before it started (ruling 5; 8.3). Called by nothing in
    the pass in 7a."""
    found = panel_notes(notes_table, patient_id, started_at, consultation_id)
    return build_block(found) if found else None
