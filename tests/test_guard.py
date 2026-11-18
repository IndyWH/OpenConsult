"""The guard that keeps tests inside their temporary folder (R18), and the
rule that a skipped test fails the run (V1_LESSONS 8.6)."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from openconsult.settings import paths, store


def test_r18_guard_refuses_a_database_outside_the_temporary_folder(tmp_path):
    # Pins R18 and V1_LESSONS 10.1: the suite once ran against the live
    # database. The twin: the guard must be able to fail.
    outside = Path(tempfile.gettempdir()) / "openconsult-r18-twin.db"
    assert not outside.is_relative_to(tmp_path.resolve())
    with pytest.raises(pytest.fail.Exception, match="R18"):
        sqlite3.connect(outside)
    assert not outside.exists()
    inside = sqlite3.connect(tmp_path / "allowed.db")
    inside.close()


def test_r18_guard_refuses_the_users_own_data_folder(tmp_path):
    # Pins R18 and V1_LESSONS 8.5: the suite once read the developer's
    # own settings. The twin: both doors to the real folder are shut.
    with pytest.raises(pytest.fail.Exception, match="R18"):
        paths.default_data_folder()
    with pytest.raises(pytest.fail.Exception, match="R18"):
        store.build()
    assert store.build(tmp_path, port=1).data_folder == tmp_path


def test_r18_the_guards_hold_after_a_test_undoes_its_own_patches(tmp_path, clock, machine, monkeypatch):
    """Pins the fault of run 9c. Two tests undo their own patches in their
    middle and build the app again. The guards were set by the same
    patcher, so they went too: that app had the machine's real secure
    store behind it, and as soon as the app read the store at its start
    (the boxes of This machine, written to the audit log), those tests
    asked the real store for the app's key names. The guards have a
    patcher of their own now."""
    import os

    import keyring

    from openconsult import app as app_module
    from tests.made_up_store import MadeStore
    monkeypatch.setattr(store, "DATABASE_FILE", "made-up.db")             # a patch of the test's own
    monkeypatch.undo()                                                    # ... undone in its middle, as those two tests do
    assert store.DATABASE_FILE == "openconsult.db"
    # Every guard still stands: the store, the package's own calls, the switch that goes with a fresh Python,
    # the data folder, the database, the engines and the tests of the connections.
    assert app_module.system_store is MadeStore and os.environ["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
    with pytest.raises(pytest.fail.Exception, match="R18"):
        keyring.get_password("OpenConsult", "ANTHROPIC_API_KEY")
    with pytest.raises(pytest.fail.Exception, match="R18"):
        paths.default_data_folder()
    with pytest.raises(pytest.fail.Exception, match="R18"):
        sqlite3.connect(Path(tempfile.gettempdir()) / "openconsult-r18-twin.db")
    assert Path.cwd() == tmp_path
    # An app built after the undo, as after a restart: a made store behind it, and reading it at start asks no real one.
    app = app_module.build_app(store.build(tmp_path, 8765), machine=machine, clock=clock)
    assert isinstance(app.state.parts.store, MadeStore) and ("get", "ANTHROPIC_API_KEY") in app.state.parts.store.calls
    with pytest.raises(pytest.fail.Exception, match="real service"):
        app_module.default_testers()["claude"]("made-up")


def test_8_6_a_skipped_test_fails_the_run(pytester):
    # Pins V1_LESSONS 8.6 and spec 5.2: a test skipped by accident fails
    # the check. A nested run in pytester's own temporary folder.
    pytester.makepyfile(
        "import pytest\n"
        "def test_skips():\n    pytest.skip('by accident')\n"
        "def test_passes():\n    pass\n"
    )
    result = pytester.runpytest("-p", "tests.noskip")
    assert result.ret == 1
    pytester.makepyfile("def test_passes():\n    pass\n")
    assert pytester.runpytest("-p", "tests.noskip").ret == 0
