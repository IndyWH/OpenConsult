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
