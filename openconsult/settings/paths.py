"""Where the data lives: the user's data folder for the system, never
the source folder or the install folder (spec 6.4; V1_LESSONS 7.2)."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Mapping


def data_folder_for(system: str, home: Path, env: Mapping[str, str]) -> Path:
    """The data folder for a system, worked out from values passed in,
    so it can be tested for every system on any one of them."""
    if system == "Windows":
        local = env.get("LOCALAPPDATA")
        base = Path(local) if local else home / "AppData" / "Local"
        return base / "OpenConsult"
    if system == "Darwin":
        return home / "Library" / "Application Support" / "OpenConsult"
    xdg = env.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else home / ".local" / "share"
    return base / "openconsult"


def default_data_folder() -> Path:
    """The real one. Tests never call this; the guard fails them if they do."""
    return data_folder_for(platform.system(), Path.home(), os.environ)
