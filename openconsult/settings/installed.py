"""What the app has installed in the data folder, with its size on the
disk (spec 7.3, Local models; 15.13, ruling 57 and the details of run
9c). A list that is read: every download on a click arrives with the
installers, at stage 15. A folder of an install holds tens of thousands
of files, so its size is measured once in a run of the app, on a thread
of its own, begun at the first view of the list: a view never waits for
it, and says so until the size is there."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable


def folder_bytes(folder: Path) -> int:
    """The bytes of every file under a folder, as the disk holds them. A
    link is counted as a link, never followed; a file that cannot be read
    is passed over."""
    total = 0
    for root, _, files in os.walk(folder):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total


class Sizes:
    """The sizes of the installed folders, for one run of the app."""

    def __init__(self, measure: Callable[[Path], int] = folder_bytes):
        self._measure = measure
        self._found: dict[str, int] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def begin(self, folders: dict[str, Path]) -> None:
        """Measure each folder once; a second call changes nothing."""
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._all, args=(dict(folders),), name="installed-sizes", daemon=True)
        self._thread.start()

    def _all(self, folders: dict[str, Path]) -> None:
        for name, folder in folders.items():
            try:
                size = self._measure(folder)
            except OSError:
                continue
            with self._lock:
                self._found[name] = size

    def of(self, name: str) -> int | None:
        """The bytes of a folder, or None while it is not measured yet."""
        with self._lock:
            return self._found.get(name)

    def wait(self, timeout_s: float) -> bool:
        if self._thread is not None:
            self._thread.join(timeout_s)
        return self._thread is not None and not self._thread.is_alive()
