"""The data folder for each system (V1_LESSONS 7.2; spec 6.4)."""

from pathlib import Path

import pytest

from openconsult.settings.paths import data_folder_for

HOME = Path("/home/example")

CASES = [
    ("Windows", {"LOCALAPPDATA": r"C:\Users\example\AppData\Local"},
     Path(r"C:\Users\example\AppData\Local") / "OpenConsult"),
    ("Windows", {}, HOME / "AppData" / "Local" / "OpenConsult"),
    ("Darwin", {}, HOME / "Library" / "Application Support" / "OpenConsult"),
    ("Linux", {"XDG_DATA_HOME": "/data/x"}, Path("/data/x") / "openconsult"),
    ("Linux", {}, HOME / ".local" / "share" / "openconsult"),
]


@pytest.mark.parametrize("system, env, expected", CASES)
def test_7_2_the_data_folder_for_each_system(system, env, expected):
    # Pins V1_LESSONS 7.2: v1's data folders were relative to wherever
    # the app was started. Here the folder follows the system's rule.
    assert data_folder_for(system, HOME, env) == expected
