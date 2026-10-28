"""The loader command of the bench kit (spec 15.12, ruling 18): every file
of a folder through the same loader the Guidelines section uses, the
title from each file's own title line, the publisher given once on the
command and never written into OpenConsult, the statement of ruling 5
recorded as the owner's by its flag. It writes into the data folder it is
given, never the default one or the repository (R18), and prints counts
only."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import openconsult
from openconsult import words
from openconsult.db import open_database
from openconsult.guidelines import embedder as embedder_module
from openconsult.guidelines import loading
from openconsult.guidelines.sources import Sources
from openconsult.patients.audit import Audit
from openconsult.settings import paths

REPO = Path(openconsult.__file__).resolve().parents[1]


def refused_folder(data_folder: Path) -> bool:
    folder = Path(data_folder).resolve()
    for place in (REPO, paths.default_data_folder()):
        place = Path(place).resolve()
        if folder == place or folder.is_relative_to(place):
            return True
    return False


def guideline_load(folder: Path, publisher: str, data_folder: Path, statement_accepted: bool, where: str = "card",
                   say: Callable = print, make_embedder: Callable = embedder_module.make_embedder) -> int:
    """Exit codes: 2 a missing publisher or statement, 6 a refused folder, 7 the worker, 1 a file not loaded."""
    if not (publisher or "").strip():
        say(words.LOAD_NEEDS_PUBLISHER)
        return 2
    if not statement_accepted:
        say(words.LOAD_NEEDS_STATEMENT)
        return 2
    if refused_folder(data_folder):
        say(words.LOAD_FOLDER_REFUSED)
        return 6
    embedder = make_embedder(Path(data_folder), where)
    not_ready = embedder.ready()
    if not_ready:
        say(words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=not_ready))
        embedder.close()
        return 7
    db = open_database(Path(data_folder) / "openconsult.db")
    sources = Sources(db, Audit(db))
    files = sorted(p for p in Path(folder).iterdir() if p.is_file())
    loaded, passages, outside, seconds = 0, 0, 0, 0.0
    try:
        for path in files:
            added = loading.add_document(sources, embedder, path.name, path.read_bytes(), publisher, "command")
            if isinstance(added, loading.Refused):
                say(words.LOAD_FILE_REFUSED.format(name=path.name, reason=f"{added.reason}: {added.detail or ''}".strip(": ")))
                continue
            loaded += 1
            passages, outside, seconds = passages + added.passages, outside + added.outside, seconds + added.seconds
            say(words.LOAD_FILE.format(name=path.name, kind=added.kind, passages=added.passages, outside=added.outside, seconds=added.seconds))
    finally:
        embedder.close()
        db.close()
    say(words.LOAD_DONE.format(files=loaded, given=len(files), passages=passages, outside=outside, seconds=round(seconds, 1)))
    return 0 if loaded == len(files) else 1
