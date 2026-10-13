"""Shared fixtures, and the guard of R18.

Every test builds what it needs fresh (spec 5.1). Nothing here reads the
user's own settings or data, and the guard fails any test that tries.
"""

from __future__ import annotations

import hashlib
import html
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openconsult import app as app_module
from openconsult import browser as browser_module
from openconsult.app import build_app
from openconsult.settings import paths, store
from openconsult.settings.machine import Card, describe
from tests.fakes import FakeEngine, MadeUpServer

pytest_plugins = ["pytester", "tests.noskip"]


@pytest.fixture(autouse=True)
def r18_guard(tmp_path, monkeypatch):
    """Fail a test that opens a database outside its temporary folder, reads
    the app's environment, or opens a real browser (R18; ruling 2;
    V1_LESSONS 8.5, 10.1, 12)."""
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

    def refuse_browser(address, *args, **kwargs):
        pytest.fail("ruling 2: a test tried to open a real browser")

    monkeypatch.setattr(browser_module, "start", refuse_browser)

    # The app asks its engines at start (3c): a test that builds an app
    # without naming them gets quiet stand-ins, never a real vLLM or Ollama.
    class Absent(FakeEngine):
        def __init__(self, address):
            super().__init__(version=None)
            self.address = address

        def chat(self, call):
            pytest.fail("a test sent a call to a real engine")

    monkeypatch.setattr(app_module, "VllmEngine", Absent)
    monkeypatch.setattr(app_module, "OllamaEngine", Absent)
    # And the card's programs are never read from the real card: an empty list stands in.
    monkeypatch.setattr(app_module.room, "read_programs", lambda: [])


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
def engine():
    return FakeEngine()


@pytest.fixture
def app(tmp_path, clock, machine, engine):
    """The made-up card is suitable and Linux, vLLM is absent, so the
    made-up Ollama is the engine chosen at start (3c)."""
    return build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                     engines={"vllm": FakeEngine(version=None), "ollama": engine})


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


# ---------------------------------------- where recordings are kept (R18)

def snapshot(folder: Path) -> dict:
    """Every file under the folder with its size, its time of change and the
    sha256 of its bytes: a file system's clock may move in coarse steps, and
    two writes within one step keep the same time, so content tells."""
    return {p.relative_to(folder).as_posix():
            (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(folder.rglob("*")) if p.is_file()}


def changes(before: dict, after: dict) -> list[str]:
    return sorted({name for name in set(before) | set(after) if before.get(name) != after.get(name)})


class KeptFolder:
    """A folder where recordings are kept: whatever a test puts in it at
    first is all it may ever hold. settle() takes the snapshot once the
    files are in place; check() fails the test by name for a file created,
    changed or removed since (R18; V1_LESSONS 12, 15.5)."""

    def __init__(self, folder: Path):
        self.folder = folder
        self._taken: dict = {}

    def settle(self) -> Path:
        self._taken = snapshot(self.folder)
        return self.folder

    def check(self) -> None:
        changed = changes(self._taken, snapshot(self.folder))
        if changed:
            pytest.fail(f"R18: a test wrote where recordings are kept: {', '.join(changed)}")


@pytest.fixture
def recordings_kept(tmp_path):
    kept = KeptFolder(tmp_path / "recordings")
    kept.folder.mkdir()
    yield kept
    kept.check()


# ------------------------------------------------- the bench's made-up server

@pytest.fixture
def server():
    made = MadeUpServer()
    yield made
    made.stop()


@pytest.fixture
def bench_folders(tmp_path, monkeypatch):
    """Made-up cases and a folder for results. The bench command checks its
    folder against the app's data folder; here that is a made-up one."""
    from tests.test_bench import made_up_folder
    monkeypatch.setattr(paths, "default_data_folder", lambda: tmp_path / "app-data")
    return made_up_folder(tmp_path), tmp_path / "out"
