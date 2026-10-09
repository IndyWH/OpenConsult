"""Finds or fetches every model the worker loads, at install, so that
nothing downloads without a click (spec 6.4). Run by openconsult install-speech with the speech
environment's own Python. One JSON line for each model: found or
fetched, its size, its pinned revision or checksum, and ok or the error.
The model hub uses its own stored sign-in by itself; nothing here reads,
copies or prints a token."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    import models

    reports = models.fetch_all()
    for report in reports:
        print(json.dumps(report), flush=True)
    return 0 if all(r["ok"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
