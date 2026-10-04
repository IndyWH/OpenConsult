"""The result writer (V1_LESSONS 9.4; R18). One file for each chain of
each case. It never writes over an existing result, never writes
anywhere but under its own folder, and refuses a folder inside the repo
or inside the app's data folder."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


class Refused(Exception):
    pass


class ResultWriter:
    def __init__(self, folder: Path, forbidden: Iterable[Path] = ()):
        self.folder = Path(folder).resolve()
        for place in forbidden:
            place = Path(place).resolve()
            if self.folder == place or self.folder.is_relative_to(place):
                raise Refused(f"results may not go under {place}")

    def path(self, case: str, chain: str) -> Path:
        target = (self.folder / "results" / case / f"{chain}.json").resolve()
        if not target.is_relative_to(self.folder):
            raise Refused(f"{case}/{chain} would leave the results folder")
        return target

    def exists(self, case: str, chain: str) -> bool:
        return self.path(case, chain).is_file()

    def write(self, case: str, chain: str, data: dict) -> Path:
        target = self.path(case, chain)
        if target.exists():
            raise Refused(f"{target} exists and is never written over")
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".part")
        partial.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, target)   # whole or absent, never half-written
        return target

    def read(self, case: str, chain: str) -> dict:
        return json.loads(self.path(case, chain).read_text(encoding="utf-8"))

    def read_all(self) -> dict[tuple[str, str], dict]:
        found = {}
        for path in sorted((self.folder / "results").glob("*/*.json")):
            found[(path.parent.name, path.stem)] = json.loads(path.read_text(encoding="utf-8"))
        return found
