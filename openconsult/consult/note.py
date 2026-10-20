"""The note (spec 15.10, rulings 3, 5, 6 and 8; The note; R4; D3). What
the model reads: the frame of ruling 5 around the turns, one line a
turn, its number in square brackets, the speaker word, a colon and the
words. The three speaker words are the bench's (15.9 ruling 22), typed
here once and read by the bench too, so no word a model reads is new.
The turns are built by the bench's own rule from the transcript lines as
they stand after the label check and after any edit: neighbouring lines
of one label join, numbered from 0. No patient line is sent (D3)."""

from __future__ import annotations

from openconsult.prompts import loader

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
