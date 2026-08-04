"""Tear down exactly what scripts/seed_demo.py created — and nothing else.

DOCKER_DEMO_SPEC.md §2.1. The scope is the seed manifest's explicit ids
(the sweep_expired_audio(only_ids=…) convention), double-locked against
the visible "DEMO — " marker: a manifest id whose row no longer carries
the marker is REFUSED and left untouched, because a row that lost its
marker can no longer be proven synthetic — refusal is the feature, the
same reasoning as the finalisation gate.

What teardown covers, all scoped to manifest patients that pass the
marker check: consultations recorded against them DURING the demo (with
their audio files, only ever inside RECORDINGS_DIR), their queue entries
(cascade), and the patient rows. The demo account is DEACTIVATED, never
deleted — accounts keep their rows for the audit trail, the same
governance rule as everywhere else.

Usage:
    uv run python scripts/reset_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg  # noqa: E402

from app import audit  # noqa: E402
from scripts.seed_demo import DEMO_ACCOUNT_PREFIX, MANIFEST_PATH, MARKER  # noqa: E402

RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "data/recordings")).resolve()


def reset(manifest_path: Path = MANIFEST_PATH) -> dict:
    if not manifest_path.exists():
        raise SystemExit(
            f"Refused: no manifest at {manifest_path} — nothing was seeded,"
            " so there is nothing this script is allowed to touch."
        )
    manifest = json.loads(manifest_path.read_text())
    report = {"patients_deleted": [], "consultations_deleted": [],
              "audio_files_deleted": [], "refused": [],
              "demo_user_deactivated": None}

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        # The double lock: manifest id AND the marker still on the row.
        verified: list[int] = []
        for pid in manifest["patients"]:
            row = conn.execute(
                "SELECT name FROM patient WHERE id = %s", (pid,)).fetchone()
            if row is None:
                continue  # already gone; nothing to touch
            if not row[0].startswith(MARKER):
                report["refused"].append(
                    {"patient_id": pid, "reason": "row does not carry the"
                     f" {MARKER!r} marker — cannot be proven synthetic"})
                continue
            verified.append(pid)

        if verified:
            # Demo-time consultations against verified demo patients.
            # Children (turns, notes, letters, segments, utterances)
            # cascade; audio files are removed only from RECORDINGS_DIR.
            rows = conn.execute(
                "DELETE FROM consultation WHERE patient_id = ANY(%s)"
                " RETURNING id, audio_path", (verified,)).fetchall()
            for cid, audio_path in rows:
                report["consultations_deleted"].append(cid)
                if audio_path:
                    p = Path(audio_path).resolve()
                    if p.is_relative_to(RECORDINGS_DIR) and p.exists():
                        p.unlink()
                        report["audio_files_deleted"].append(str(p))
            conn.execute("DELETE FROM patient WHERE id = ANY(%s)", (verified,))
            report["patients_deleted"] = verified

        # The demo account: deactivate, never delete. Same double lock —
        # the manifest id must still be the demo-prefixed username.
        row = conn.execute(
            "SELECT username FROM app_user WHERE id = %s",
            (manifest["demo_user_id"],)).fetchone()
        if row and row[0].startswith(DEMO_ACCOUNT_PREFIX):
            conn.execute(
                "UPDATE app_user SET active = false, pending_approval = false"
                " WHERE id = %s", (manifest["demo_user_id"],))
            report["demo_user_deactivated"] = row[0]
        elif row:
            report["refused"].append(
                {"user_id": manifest["demo_user_id"],
                 "reason": f"username does not start with"
                           f" {DEMO_ACCOUNT_PREFIX!r}"})

    # The manifest survives only if something was refused: the refused
    # rows remain the seeding's responsibility until a human looks.
    if report["refused"]:
        print(f"REFUSED {len(report['refused'])} row(s) — manifest kept at"
              f" {manifest_path} for inspection:", file=sys.stderr)
        for r in report["refused"]:
            print(f"  {r}", file=sys.stderr)
    else:
        manifest_path.unlink()
    asyncio.run(audit.log(None, "demo.reset", "demo", None, {
        **{k: v for k, v in report.items() if k != "audio_files_deleted"},
        "audio_files_deleted": len(report["audio_files_deleted"]),
        "via": "scripts/reset_demo.py"}))
    return report


def main() -> int:
    report = reset()
    print(f"Deleted {len(report['patients_deleted'])} demo patients,"
          f" {len(report['consultations_deleted'])} demo consultations,"
          f" {len(report['audio_files_deleted'])} audio files;"
          f" demo account deactivated: {report['demo_user_deactivated']}.")
    return 1 if report["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
