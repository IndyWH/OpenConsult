"""The loader command of the bench kit (spec 15.12, ruling 18): every file
of a folder through the same loader the Guidelines section uses, the
title from each file's own title line, the publisher given once on the
command and never written into OpenConsult, the statement of ruling 5
recorded as the owner's by its flag. It writes into the data folder it is
given: a bench folder by its path, or the owner's own data folder when he
names it by its path and asks with --into-my-data-folder (the plan review
of 28 Oct, point 3), with the app closed; never the repository. It prints
counts only."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import openconsult
from openconsult import words
from openconsult.consult.consultations import Consultations
from openconsult.db import open_database
from openconsult.guidelines import embedder as embedder_module
from openconsult.guidelines import loading
from openconsult.guidelines.sources import Sources
from openconsult.patients.audit import Audit
from openconsult.settings import paths

REPO = Path(openconsult.__file__).resolve().parents[1]


def _under(folder: Path, place: Path) -> bool:
    folder, place = Path(folder).resolve(), Path(place).resolve()
    return folder == place or folder.is_relative_to(place)


def is_repo(data_folder: Path) -> bool:
    return _under(data_folder, REPO)


def is_own(data_folder: Path) -> bool:
    """The app's default data folder on this computer: the owner's own."""
    return _under(data_folder, paths.default_data_folder())


def refused_folder(data_folder: Path, into_my_data_folder: bool = False) -> str | None:
    """The sentence of the refusal, or None: the repository always; the
    owner's own folder unless he asked for it by name; the flag does
    nothing for any other folder."""
    if is_repo(data_folder):
        return words.LOAD_REPO_REFUSED
    if is_own(data_folder) and not into_my_data_folder:
        return words.LOAD_FOLDER_REFUSED
    return None


def app_running(db) -> bool:
    """Whether the app looks to be running on this folder: a consultation
    live or stopping. The app keeps no lock or pid file, so this is the
    one sign there is."""
    rows = Consultations(db)
    return bool(rows.in_state("live") or rows.in_state("stopping"))


def guideline_load(folder: Path, publisher: str, data_folder: Path, statement_accepted: bool, where: str = "card",
                   say: Callable = print, make_embedder: Callable = embedder_module.make_embedder,
                   into_my_data_folder: bool = False) -> int:
    """Exit codes: 2 a missing publisher or statement, 6 a refused folder, 8 the app running on the owner's
    folder, 7 the worker, 1 a file not loaded."""
    if not (publisher or "").strip():
        say(words.LOAD_NEEDS_PUBLISHER)
        return 2
    if not statement_accepted:
        say(words.LOAD_NEEDS_STATEMENT)
        return 2
    refusal = refused_folder(data_folder, into_my_data_folder)
    if refusal:
        say(refusal)
        return 6
    db = open_database(Path(data_folder) / "openconsult.db")
    if is_own(data_folder) and app_running(db):
        say(words.LOAD_APP_RUNNING)       # the owner's folder is loaded only with the app closed (7.3 rule 4)
        db.close()
        return 8
    embedder = make_embedder(Path(data_folder), where)
    not_ready = embedder.ready()
    if not_ready:
        say(words.GUIDELINE_ADD_NEEDS_WORKER.format(reason=not_ready))
        embedder.close()
        db.close()
        return 7
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
