"""The app opens the browser by itself once it answers, and --no-browser
(spec 15.7, ruling 2). No test opens a real browser."""

import importlib.util
from pathlib import Path

from openconsult import browser, words
from openconsult.cli import main
from tests.test_cli import Said


class Opener:
    def __init__(self, result=True, raises=False):
        self.calls, self.result, self.raises = [], result, raises

    def __call__(self, address):
        self.calls.append(address)
        if self.raises:
            raise OSError("no browser")
        return self.result


def test_ruling_2_the_browser_opens_once_the_app_answers():
    answers = iter([False, False, True])
    opener, said = Opener(), Said()
    seen_before_open = []

    def is_up():
        up = next(answers)
        seen_before_open.append((up, list(opener.calls)))
        return up

    opened = browser.open_when_answering("http://127.0.0.1:1", is_up, opener, say=said,
                                         sleep=lambda s: None)
    assert opened and opener.calls == ["http://127.0.0.1:1"]
    # It was not opened while the app was still not answering.
    assert all(calls == [] for up, calls in seen_before_open if not up)
    assert said.lines == []


def test_ruling_2_no_browser_opens_nothing_and_the_address_is_still_printed(tmp_path, machine):
    started = []
    said = Said()
    args = ["--data-folder", str(tmp_path), "--port", "0"]
    assert main([*args, "--no-browser"], say=said, serve=lambda *a: None, machine=machine,
                open_browser=started.append) == 0
    assert started == []
    assert words.RUNNING.format(address="http://127.0.0.1:0") in said.text
    assert main(args, say=said, serve=lambda *a: None, machine=machine,
                open_browser=started.append) == 0
    assert started == ["http://127.0.0.1:0"]


def test_ruling_2_no_screen_or_no_browser_is_not_an_error():
    said = Said()
    failing = Opener(result=False)
    assert browser.open_when_answering("http://127.0.0.1:1", lambda: True, failing, say=said) is False
    raising = Opener(raises=True)
    assert browser.open_when_answering("http://127.0.0.1:1", lambda: True, raising, say=said) is False
    assert said.lines == [words.BROWSER_NOT_OPENED] * 2
    # The app that never answers in time: said, not raised.
    assert browser.open_when_answering("http://127.0.0.1:1", lambda: False, Opener(), say=said,
                                       wait_s=0.01, sleep=lambda s: None) is False
    # Linux with no display does not try; the other two systems always have a screen.
    assert browser.has_screen("Linux", {}) is False
    assert browser.has_screen("Linux", {"WAYLAND_DISPLAY": "wayland-1"}) is True
    assert browser.has_screen("Windows", {}) is True and browser.has_screen("Darwin", {}) is True


def test_ruling_2_the_start_check_starts_without_a_browser():
    path = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "start_check.py"
    spec = importlib.util.spec_from_file_location("start_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "--no-browser" in module.command_for("folder", 1234)
