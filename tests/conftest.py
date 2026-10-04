"""Shared fixtures, and the guard of R18.

Every test builds what it needs fresh (spec 5.1). Nothing here reads the
user's own settings or data, and the guard fails any test that tries.
"""

from __future__ import annotations

import html
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openconsult.app import build_app
from openconsult.settings import paths, store
from openconsult.settings.machine import Card, describe

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

    def refuse_real_data_folder():
        pytest.fail("R18: a test tried to read the user's own data folder")

    monkeypatch.setattr(paths, "default_data_folder", refuse_real_data_folder)


# ------------------------------------------------------------ the fake clock

class FakeClock:
    """A clock the test moves, so no test ever waits (V1_LESSONS 8.4)."""

    def __init__(self):
        self.now = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock():
    return FakeClock()


# ------------------------------------------------- the app and its browsers

PORT = 8765
ORIGIN = f"http://127.0.0.1:{PORT}"
PASSWORD = "example-password"


@pytest.fixture
def machine():
    return describe("Linux", "x86_64", [Card("Made-up card", 24564)])


@pytest.fixture
def app(tmp_path, clock, machine):
    return build_app(store.build(tmp_path, PORT), machine=machine, clock=clock)


def browser(app, address="127.0.0.1", origin=ORIGIN):
    """A fresh browser: its own cookies, from this computer unless told
    otherwise, sending the app's own Origin on every post."""
    return TestClient(
        app,
        base_url=ORIGIN,
        client=(address, 50000),
        headers={"Origin": origin},
        follow_redirects=False,
    )


@pytest.fixture
def client(app):
    return browser(app)


def set_up(client, title="Dr", name="Example", password=PASSWORD):
    """Walk the first run."""
    client.post("/first-run/statement", data={"agree": "yes"})
    client.post("/first-run/machine", data={})
    return client.post(
        "/first-run/user",
        data={"title": title, "name": name, "password": password, "password_again": password},
    )


def log_in(client, password=PASSWORD):
    return client.post("/login", data={"password": password})


@pytest.fixture
def logged_in(client):
    set_up(client)
    log_in(client)
    return client


def text_of(response) -> str:
    """A page as the reader sees it, with HTML escapes undone."""
    return html.unescape(response.text)


def refusal_on(page: str, control: str) -> str:
    """The text in the refusal slot that the control points at (R15)."""
    finder = _RefusalFinder(control)
    finder.feed(page)
    assert finder.described_by == f"{control}-refusal", f"control {control} points at no slot"
    return finder.text.strip()


class _RefusalFinder(HTMLParser):
    def __init__(self, control):
        super().__init__()
        self.control = control
        self.described_by = None
        self.text = ""
        self._in_slot = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") == self.control:
            self.described_by = attrs.get("aria-describedby")
        if attrs.get("id") == f"{self.control}-refusal":
            self._in_slot = True

    def handle_endtag(self, tag):
        if self._in_slot and tag == "p":
            self._in_slot = False

    def handle_data(self, data):
        if self._in_slot:
            self.text += data
