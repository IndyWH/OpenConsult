"""The one settings store (spec 5.1, 15.6). No other code reads a setting
directly. It is built fresh at each start and for each test.

Stage 2 has only the two values its behaviour uses, both fixed when the
app starts. A setting a page can change, with its audited from-and-to,
arrives with the first stage that has one (plan review, a).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openconsult.settings import paths

# The app listens on this computer's own address only, as a colleague's
# install does (spec 6.4; 15.6 ruling 6). It is a named value, not a
# setting: there is no way to change it.
LISTEN_ON = "127.0.0.1"

DATABASE_FILE = "openconsult.db"


@dataclass(frozen=True)
class Setting:
    name: str
    default: object
    reason: str


SETTINGS = (
    Setting(
        "data_folder",
        None,
        "The user's data folder for the system (spec 6.4), so an update or a "
        "reinstall never touches the data. None means that default; a path "
        "overrides it for a development run (spec 15.6).",
    ),
    Setting(
        "port",
        8001,
        "8001 when run from source, beside v1 on 8000 (spec 14.1).",
    ),
)

_DEFAULTS = {setting.name: setting.default for setting in SETTINGS}


@dataclass(frozen=True)
class Settings:
    data_folder: Path
    port: int

    @property
    def database_path(self) -> Path:
        return self.data_folder / DATABASE_FILE

    @property
    def address(self) -> str:
        return f"http://{LISTEN_ON}:{self.port}"


def build(data_folder: Path | str | None = None, port: int | None = None) -> Settings:
    """A fresh store. Only the real default data folder is looked up, and
    only when no folder is given."""
    folder = Path(data_folder) if data_folder is not None else paths.default_data_folder()
    return Settings(data_folder=folder, port=port if port is not None else _DEFAULTS["port"])
