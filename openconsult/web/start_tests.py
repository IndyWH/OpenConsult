"""The tests of the Start screen, run beside the page (spec 15.13, ruling
51; 7.2; the details of run 9c). As built in run 9b the Start screen
tested each connection its path needs every time it was shown and
showed nothing until the tests had answered: about 2 seconds with the
real services, 10 when one did not answer, a blank page with a patient
in the room. Now the page is sent at once and the tests run here, on a
thread of their own; the page's script asks for the result and writes
it into the places the page has.

The rule that a consultation never begins on a connection that is down
is the app's, not the page's: Start reads the run the page named. A
run still running refuses the press; a run that answered a short while
ago is used; an older one is tested again at the press itself.
Nothing here is kept beyond the app's run, and only the last few runs."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

# How long an answered run may be used by a press: a design choice. A doctor reads the patient's details, ticks two
# boxes and presses Start within it; after it, the connection is tested again at the press, as run 9b tested it.
FRESH_S = 60.0
KEPT = 8


@dataclass
class Run:
    id: str
    path: str                            # the path it was made for, in the audit log's own words
    started: float
    answered: threading.Event = field(default_factory=threading.Event)
    state: object = None                 # the Start control's state, once the tests have answered
    answered_at: float | None = None


class StartTests:
    def __init__(self, timer: Callable = time.monotonic):
        self._timer = timer
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self._made = 0

    def begin(self, path: str, work: Callable) -> Run:
        """A run for a view of the Start screen. A run for the same path
        that is still running is joined, so that a page loaded again does
        not pile test on test."""
        with self._lock:
            for run in self._runs.values():
                if run.path == path and not run.answered.is_set():
                    return run
            self._made += 1
            run = Run(str(self._made), path, self._timer())
            self._runs[run.id] = run
            for old in list(self._runs)[:-KEPT]:
                del self._runs[old]
        threading.Thread(target=self._do, args=(run, work), name=f"start-tests-{run.id}", daemon=True).start()
        return run

    def _do(self, run: Run, work: Callable) -> None:
        try:
            run.state = work()
        finally:
            run.answered_at = self._timer()
            run.answered.set()

    def get(self, run_id: str | None, path: str) -> Run | None:
        """The run a page named, when it was made for the path as it stands now."""
        with self._lock:
            run = self._runs.get(run_id or "")
        return run if run is not None and run.path == path else None

    def spent(self, run_id: str | None) -> None:
        """A run whose tests began a consultation is forgotten."""
        with self._lock:
            self._runs.pop(run_id or "", None)

    def fresh(self, run: Run) -> bool:
        return run.answered.is_set() and run.state is not None and self._timer() - run.answered_at <= FRESH_S
