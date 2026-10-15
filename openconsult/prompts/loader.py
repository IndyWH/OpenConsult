"""The one loader for the prompts folder (spec 5.1, 15.7). One prompt in
one file; the app and every bench read the same files. The fixed words
around the transcript live here too, as frames with {transcript} and
{stale} slots, so no sentence the model reads is typed in the code,
except the patient line.

A file's text is what it holds less its final line break, so an editor
that ends files with one does not change what the model reads.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).parent

# The spec's approved wording of the two prompts, as sha256 of the text as it
# is read here (15.8, rulings 41 and 42). The word check compares the prompt
# sent against these; the test pins the files to them.
APPROVED = {
    "assessment": "437d7f32b3b020f8757ce96fdcf31ae4b85aef0b949e56f81546b3e200e1c6bb",
    "alarm": "1e05ffc8634b4093897ec53cd590111fbb2bdeac0abbd4462c8298f5582c9451",
}


def _text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text


def prompt(name: str) -> str:
    return _text(FOLDER / f"{name}.prompt.txt")


def form(name: str) -> dict:
    return json.loads(_text(FOLDER / f"{name}.form.json"))


def frame(name: str) -> str:
    return _text(FOLDER / f"{name}.frame.txt")


def fill(frame_text: str, **slots: str) -> str:
    """Put the words into the slots. Plain replacement, so braces in a
    transcript are never read as slots."""
    for slot, value in slots.items():
        frame_text = frame_text.replace("{" + slot + "}", value)
    return frame_text


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def every_prompt_file() -> list[Path]:
    """Every file the model may read, for the checks of R13 and R21."""
    return sorted(p for p in FOLDER.iterdir() if p.suffix in (".txt", ".json"))
