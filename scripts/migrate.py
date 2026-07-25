#!/usr/bin/env python
"""Apply the database schema, or report drift without touching anything.

    uv run python scripts/migrate.py            # apply (idempotent)
    uv run python scripts/migrate.py --check    # report drift, exit 1 if any

`--check` is the one for the after-reboot checklist and for CI-style use:
it runs the DDL inside a transaction, compares an information_schema
snapshot either side, and rolls back. It never writes.

This exists because the schema used to be applied only by the app's
lifespan and by tests/conftest.py, so a database could drift from the code
with nothing to say so until something failed at query time. See
`app/schema.py` for the full reasoning.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import schema  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="report drift and exit non-zero; make no changes")
    args = parser.parse_args(argv)

    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL is not set (see .env / .env.example)", file=sys.stderr)
        return 2
    # Never print credentials — just the database name.
    target = url.rsplit("/", 1)[-1].split("?")[0]

    if args.check:
        drift = schema.check_drift(url)
        if not drift:
            print(f"{target}: schema matches the code — no drift")
            return 0
        print(f"{target}: schema drift — {len(drift)} item(s) the code expects "
              f"and the database does not have:")
        for line in drift:
            print(f"  {line}")
        print("\nRun without --check (or restart the app) to apply.")
        return 1

    schema.ensure_all()
    print(f"{target}: schema applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
