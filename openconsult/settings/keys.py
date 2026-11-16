"""The one module that reads a cloud service's key (spec 7.2; 7.3, rule
3; 15.9, the details of 5b; 15.13, the details of run 9b). The order of
reading: the system's secure store, where the connect screen puts a key
that has passed its test; then the process environment; then the file
.env in the data folder, which stays the developer's way. A caller that
gives no store reads no store: the bench gives none, so no bench
command can ever read a secure store. A key is read here and handed to
its engine or its worker's environment; it is never logged, stamped,
written to the database, put on a command line or shown on a page."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from openconsult.settings.secure import NoStore

KEY_FILE = ".env"
# Every name a key is read by, the app's and the bench's: the names the example settings file holds. A worker's
# environment is cleared of all of them before its own one key goes in, so no process holds another's key.
NAMES = ("ANTHROPIC_API_KEY", "SPEECHMATICS_API_KEY", "ASSEMBLYAI_API_KEY", "DEEPINFRA_API_KEY")


def parse_env(text: str) -> dict[str, str]:
    """NAME=VALUE lines; quotes around a value are stripped; a line that
    starts with # and a line with no = are skipped; nothing is expanded."""
    found = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        found[name.strip()] = value
    return found


STORE, ENVIRONMENT, FILE = "store", "environment", "file"


def find_key(name: str, data_folder: Path, environ: Mapping[str, str] = os.environ, store=None) -> tuple[str | None, str | None]:
    """The value under name and where it came from: the store, the
    environment or the file; (None, None) when there is none or it is
    empty. A store that does not answer holds nothing."""
    if store is not None:
        try:
            value = store.get(name)
        except NoStore:
            value = None
        if value:
            return value, STORE
    if environ.get(name):
        return environ[name], ENVIRONMENT
    path = Path(data_folder) / KEY_FILE
    if path.is_file():
        value = parse_env(path.read_text(encoding="utf-8")).get(name)
        if value:
            return value, FILE
    return None, None


def read_key(name: str, data_folder: Path, environ: Mapping[str, str] = os.environ, store=None) -> str | None:
    """The value under name, or None when there is none or it is empty."""
    return find_key(name, data_folder, environ, store)[0]
