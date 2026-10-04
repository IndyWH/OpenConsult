"""The app opens the system's default browser by itself, once it really
answers on its address (spec 15.7, ruling 2). A machine with no browser
or no screen is not an error: the address is printed either way."""

from __future__ import annotations

import os
import platform
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Callable, Mapping

from openconsult import words

WAIT_S = 30.0
STEP_S = 0.25


def has_screen(system: str | None = None, env: Mapping[str, str] | None = None) -> bool:
    """On Linux with no desktop the webbrowser module would start a text
    browser inside the terminal, so there the app only tries when a
    display is there. Windows and macOS always have one for a user."""
    system = system or platform.system()
    env = os.environ if env is None else env
    if system != "Linux":
        return True
    return bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))


def answers(address: str) -> bool:
    """Any HTTP answer means the app is up; only no connection means not yet."""
    try:
        with urllib.request.urlopen(address, timeout=2):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def open_when_answering(address: str, is_up: Callable[[], bool], opener: Callable[[str], bool],
                        say: Callable = print, wait_s: float = WAIT_S,
                        sleep: Callable = time.sleep) -> bool:
    """Wait until the app answers, then open the browser once. Says so
    plainly when it could not."""
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if is_up():
            try:
                opened = bool(opener(address))
            except Exception:  # noqa: BLE001 - a browser that cannot start is not our error
                opened = False
            if not opened:
                say(words.BROWSER_NOT_OPENED)
            return opened
        sleep(STEP_S)
    say(words.BROWSER_NOT_OPENED)
    return False


def start(address: str, opener: Callable[[str], bool] = webbrowser.open,
          say: Callable = print) -> threading.Thread | None:
    """Start the wait in a thread that never holds the app up or back."""
    if not has_screen():
        say(words.BROWSER_NOT_OPENED)
        return None
    thread = threading.Thread(
        target=open_when_answering, args=(address, lambda: answers(address), opener, say),
        name="open-browser", daemon=True)
    thread.start()
    return thread
