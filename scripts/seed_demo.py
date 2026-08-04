"""Seed the demo's own data — clearly-marked synthetic rows only.

DOCKER_DEMO_SPEC.md §2.1: no governance action touches a real row, and
the demo is the highest-risk place for that rule because it runs under
time pressure in front of an audience. So the demo gets its own data:
every patient this script creates carries the visible "DEMO — " name
marker, the approve-to-activate beat gets its own pending account, and
everything created is recorded in a manifest that scripts/reset_demo.py
tears down — and ONLY that (the sweep_expired_audio(only_ids=…)
convention: explicit ids, never a pattern sweep over live data).

Seeds: three marked patients on today's walk-in queue, and one pending
demo account for the approve-to-activate beat (decision 4: shown, on
seeded data only). The pre-recorded urgency consultation is NOT seeded
here — it is owner-supplied (decision 2), chosen from real mock runs.

Refuses to run when a manifest already exists: reset first, so two
seedings can never blur what belongs to which demo.

Usage:
    uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg  # noqa: E402

from app import audit, auth, schema  # noqa: E402

MARKER = "DEMO — "
DEMO_PATIENTS = [
    (MARKER + "Amal Perera", 54, "M"),
    (MARKER + "Nadia Silva", 31, "F"),
    (MARKER + "Rohan Fernando", 67, "M"),
]
DEMO_ACCOUNT_PREFIX = "demo.applicant."
DEMO_ACCOUNT_PASSWORD = "demo-password-123"  # synthetic account, spoken aloud in the demo

MANIFEST_PATH = Path(os.getenv("DEMO_SEED_MANIFEST", "data/demo_seed.json"))


def seed(manifest_path: Path = MANIFEST_PATH) -> dict:
    if manifest_path.exists():
        raise SystemExit(
            f"Refused: {manifest_path} already exists — a previous seeding"
            " has not been reset. Run scripts/reset_demo.py first."
        )
    schema.ensure_all()

    patients: list[int] = []
    queue_entries: list[int] = []
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for name, age, sex in DEMO_PATIENTS:
            pid = conn.execute(
                "INSERT INTO patient (name, age, sex) VALUES (%s, %s, %s)"
                " RETURNING id", (name, age, sex),
            ).fetchone()[0]
            patients.append(pid)
            qid = conn.execute(
                "INSERT INTO queue_entry (patient_id, position) VALUES (%s,"
                " (SELECT coalesce(max(position), 0) + 1 FROM queue_entry"
                "  WHERE queue_date = CURRENT_DATE)) RETURNING id", (pid,),
            ).fetchone()[0]
            queue_entries.append(qid)

    # The approve-to-activate beat's applicant: pending, exactly as a
    # public registration would be. The random suffix keeps repeated
    # demo cycles from colliding (reset deactivates, never deletes).
    username = DEMO_ACCOUNT_PREFIX + secrets.token_hex(2)
    account = asyncio.run(auth.create_user(
        username, DEMO_ACCOUNT_PASSWORD, MARKER + "Demo Applicant",
        "receptionist", pending=True,
    ))

    manifest = {
        "seeded_at": datetime.now(timezone.utc).isoformat(),
        "marker": MARKER,
        "patients": patients,
        "queue_entries": queue_entries,
        "demo_user_id": account["id"],
        "demo_username": username,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=1))
    asyncio.run(audit.log(None, "demo.seeded", "demo", None, {
        "patients": patients, "queue_entries": queue_entries,
        "demo_user_id": account["id"], "via": "scripts/seed_demo.py"}))
    return manifest


def main() -> int:
    manifest = seed()
    print(f"Seeded {len(manifest['patients'])} demo patients on today's queue"
          f" (ids {manifest['patients']}), and pending demo account"
          f" {manifest['demo_username']!r} (password {DEMO_ACCOUNT_PASSWORD!r})"
          f" for the approve-to-activate beat.")
    print(f"Manifest: {MANIFEST_PATH} — scripts/reset_demo.py tears down"
          " exactly these rows and nothing else.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
