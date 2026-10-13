"""The 250 pieces of public text for the side reading of 5d (spec 15.9,
the details: building an index). Cut from two public sources only, the
lessons file at the repo root and the public cases of the engine bench,
about 200 words each, in v1's form for a passage. No private text can
enter: a path outside the two sources is refused, and the result names
each file with its sha256."""

from __future__ import annotations

import hashlib
from pathlib import Path

import openconsult
from openconsult.bench.shared.searches import passage_text

REPO = Path(openconsult.__file__).resolve().parents[1]
LESSONS = REPO / "V1_LESSONS.md"
CASES = REPO / "engine-bench" / "cases"
WORDS = 200
LEAST = 100
COUNT = 250
BATCH = 16


class NotPublic(Exception):
    """A path that is not one of the two public sources."""


def public_files(lessons: Path = LESSONS, cases: Path = CASES) -> list[Path]:
    return [lessons] + sorted(Path(cases).glob("*.md"))


def allowed(path: Path, lessons: Path = LESSONS, cases: Path = CASES) -> bool:
    path = Path(path).resolve()
    return path == Path(lessons).resolve() or (path.is_relative_to(Path(cases).resolve()) and path.suffix == ".md")


def cut(files: list[Path], words: int = WORDS, least: int = LEAST, count: int = COUNT,
        lessons: Path = LESSONS, cases: Path = CASES) -> tuple[list[dict], list[dict]]:
    """The pieces, each {"title", "text", "passage"}, and the files used,
    each with its sha256 and how many pieces came from it."""
    pieces, used = [], []
    for path in files:
        if not allowed(path, lessons, cases):
            raise NotPublic(f"{Path(path).name} is not one of the public sources")
        data = Path(path).read_bytes()
        tokens = data.decode("utf-8").split()
        before = len(pieces)
        for start in range(0, len(tokens), words):
            run = tokens[start:start + words]
            if len(run) < least or len(pieces) >= count:
                break
            text = " ".join(run)
            pieces.append({"title": Path(path).name, "text": text, "passage": passage_text(Path(path).name, text)})
        used.append({"file": Path(path).name, "sha256": hashlib.sha256(data).hexdigest(), "pieces": len(pieces) - before})
        if len(pieces) >= count:
            break
    return pieces, used


def batches(pieces: list[dict], size: int = BATCH) -> list[list[dict]]:
    return [pieces[i:i + size] for i in range(0, len(pieces), size)]
