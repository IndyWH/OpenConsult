"""The one module that reads a cloud service's key (spec 7.3, rule 3; 15.9,
the details of 5b). In 5b a developer's way only: the process environment
first, then the file .env in the data folder. The connect screen and the
system's secure store are stage 9 (7.2). A key is read here and handed
to its worker's environment; it is never logged, stamped, stored, put on
a command line or shown on a page."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

KEY_FILE = ".env"


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


def read_key(name: str, data_folder: Path, environ: Mapping[str, str] = os.environ) -> str | None:
    """The value under name, or None when there is none or it is empty."""
    value = environ.get(name)
    if not value:
        path = Path(data_folder) / KEY_FILE
        if path.is_file():
            value = parse_env(path.read_text(encoding="utf-8")).get(name)
    return value or None
