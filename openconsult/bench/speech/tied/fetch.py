"""Finds or fetches the two models of the tied pair at their pinned
revisions, run by openconsult-bench speech-fetch with the Nemotron
environment's Python. The 3.5 model is v1's, at v1's revision; the
speaker model is the one of the Nemotron choice. One JSON line for each.
The hub uses its own stored sign-in by itself; nothing here reads,
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
