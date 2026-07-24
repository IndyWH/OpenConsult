"""Per-IP rate limiting for the auth endpoints (2026-07-24, public
exposure via Tailscale Funnel).

In-process sliding windows: a restart clears them, which is acceptable
for a single-process demo deployment — the audit log, which records the
source IP on every auth event, is the durable forensic record. 429s are
refusals, not errors, so they stay out of the pulse's errors_last_hour
(the count_errors middleware only counts 5xx).
"""

from __future__ import annotations

import os
import time
from collections import deque


class RateLimiter:
    def __init__(self, attempts: int, window_s: float):
        self.attempts = attempts
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}
        self._sweep_at = 0.0

    def retry_after(self, key: str, now: float | None = None) -> int | None:
        """Record one attempt for `key`. None = allowed; otherwise whole
        seconds until the oldest counted attempt leaves the window."""
        now = time.time() if now is None else now
        if now >= self._sweep_at:  # drop idle keys so memory stays bounded
            cutoff = now - self.window_s
            self._hits = {k: d for k, d in self._hits.items() if d and d[-1] > cutoff}
            self._sweep_at = now + self.window_s
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()
        if len(hits) >= self.attempts:
            return max(1, int(hits[0] + self.window_s - now) + 1)
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()


login_limiter = RateLimiter(
    int(os.getenv("AUTH_LOGIN_ATTEMPTS", "10")),
    float(os.getenv("AUTH_LOGIN_WINDOW_S", "60")),
)
register_limiter = RateLimiter(
    int(os.getenv("AUTH_REGISTER_ATTEMPTS", "5")),
    float(os.getenv("AUTH_REGISTER_WINDOW_S", "3600")),
)


def client_ip(request) -> str:
    """The direct peer address — except when the direct peer is the
    local proxy (Tailscale Serve/Funnel terminates on loopback), where
    the last X-Forwarded-For entry is the address the proxy actually
    saw. XFF from a non-loopback peer is ignored: it's spoofable."""
    peer = request.client.host if request.client else "unknown"
    if peer in ("127.0.0.1", "::1", "localhost"):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()[:64] or peer
    return peer
