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
