"""Clock interface for injectable time control.

Production code uses RealClock. Tests use ManualClock to advance time
explicitly and deterministically.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Return current time in seconds (monotonic)."""
        ...


class RealClock:
    """Uses real monotonic time."""

    def now(self) -> float:
        return time.monotonic()


class ManualClock:
    """Test clock that only advances when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self._time = start

    def now(self) -> float:
        return self._time

    def advance(
        self,
        seconds: float = 0.0,
        minutes: float = 0.0,
        hours: float = 0.0,
    ) -> None:
        self._time += seconds + minutes * 60.0 + hours * 3600.0
