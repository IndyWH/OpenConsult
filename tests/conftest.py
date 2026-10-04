"""Shared fixtures, and the guard of R18.

Every test builds what it needs fresh (spec 5.1). Nothing here reads the
user's own settings or data, and the guard fails any test that tries.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

pytest_plugins = ["pytester", "tests.noskip"]


@pytest.fixture(autouse=True)
def r18_guard(tmp_path, monkeypatch):
    """Fail a test that opens a database outside its temporary folder, or
    reads the app's environment (R18; V1_LESSONS 8.5, 10.1, 12)."""
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith("OPENCONSULT"):
            monkeypatch.delenv(name)
    allowed = tmp_path.resolve()
    real_connect = sqlite3.connect

    def guarded_connect(database, *args, **kwargs):
        if str(database) != ":memory:":
            where = Path(database).resolve()
            if not where.is_relative_to(allowed):
                pytest.fail(f"R18: a test tried to open a database outside its temporary folder: {where}")
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
