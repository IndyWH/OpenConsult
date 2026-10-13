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


def test_15_6_the_store_holds_both_engine_addresses_fixed_at_start(tmp_path):
    """The two addresses of 3c (15.8, the details of 3c): Ollama's as in
    stage 3, and vLLM's, the address the bench and 5d used, so that port
    8000 stays v1's. Both are fixed when the app starts; no page changes
    them, and there is no setting to pick an engine by hand (ruling 37)."""
    from openconsult.settings import store
    built = store.build(tmp_path, 8765)
    assert built.ollama_address == "http://127.0.0.1:11434"
    assert built.vllm_address == "http://127.0.0.1:8172"
    assert "8000" not in built.vllm_address and "8001" not in built.vllm_address
    names = [setting.name for setting in store.SETTINGS]
    assert names == ["data_folder", "port", "ollama_address", "vllm_address"]
    assert all(setting.reason for setting in store.SETTINGS)
