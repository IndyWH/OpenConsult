"""Break-glass consultation governance — server shell only, never over HTTP.

Sibling of `manage_users.py`, same conventions: no HTTP surface, explicit
confirmation typed by hand, nothing destructive by accident.

Its reason for existing is the one operation the web API refuses outright:
reversing a **clinical_safety** void. A `test_data` void stays freely
reversible through the admin UI's Unvoid button; a `clinical_safety` void
cannot be undone there at all, because the written lesson "don't exercise
governance actions on real rows" failed twice on consultation #70 — it
was unvoided 2026-07-22, re-voided 2026-07-24, and unvoided again six
minutes later. The guard is code; this script is the deliberate way past
it.

The second such operation (added 2026-09-10, for consultation 469):
`purge-one` hard-deletes ONE voided consultation of ANY class. The web
purge skips clinical_safety voids by design, so a record voided in that
class and later judged to need deleting — 469 was the one recording that
could not be confirmed as acted — had no path off the disk. This is that
path: named id, typed back as confirmation, everything that cascades,
the orphaned patient row, the recording file(s), and a `data.purged`
audit row that names all of it. The original void audit row is left
where it is.

Usage:
    uv run python scripts/manage_consultations.py list-voided
    uv run python scripts/manage_consultations.py show CID
    uv run python scripts/manage_consultations.py void CID --class clinical_safety
    uv run python scripts/manage_consultations.py unvoid CID   # break-glass
    uv run python scripts/manage_consultations.py purge-one CID   # break-glass
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import audit, consultations, schema  # noqa: E402

# Same default as app/main.py, read here rather than imported so the
# script does not load the whole application to delete one row.
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "data/recordings"))


async def cmd_list_voided() -> int:
    rows = [c for c in await consultations.list_consultations(include_voided=True)
            if c["voided_at"]]
    if not rows:
        print("No voided consultations.")
        return 0
    header = (f"{'id':>4}  {'voided at':<17} {'class':<16} {'status':<20} reason")
    print(header)
    print("-" * max(len(header), 72))
    for c in rows:
        print(f"{c['id']:>4}  {c['voided_at'] or '—':<17}"
              f" {c['void_reason_class'] or '(unset)':<16} {c['status']:<20}"
              f" {c['void_reason'] or '—'}")
    return 0


async def cmd_show(cid: int) -> int:
    state = await consultations.void_state(cid)
    if state is None:
        print(f"No consultation #{cid}.", file=sys.stderr)
        return 1
    print(f"consultation #{cid}")
    print(f"  voided:       {'yes' if state['voided'] else 'no'}")
    print(f"  reason class: {state['reason_class'] or '(unset)'}")
    print(f"  reason:       {state['reason'] or '—'}")
    if state["reason_class"] == consultations.VOID_CLASS_CLINICAL_SAFETY:
        print("\n  This void CANNOT be reversed over HTTP. Use"
              " `unvoid` here if you really mean it.")
    return 0


async def cmd_void(cid: int, reason: str, reason_class: str) -> int:
    state = await consultations.void_state(cid)
    if state is None:
        print(f"No consultation #{cid}.", file=sys.stderr)
        return 1
    if state["voided"]:
        print(f"Consultation #{cid} is already voided"
              f" ({state['reason_class'] or 'unset'}).", file=sys.stderr)
        return 1
    voided = await consultations.void_consultation(cid, None, reason, reason_class)
    if voided is None:
        print(f"Refused: consultation #{cid} could not be voided.", file=sys.stderr)
        return 1
    await audit.log(None, "consultation.voided", "consultation", cid,
                    {"reason": reason, "reason_class": reason_class,
                     "from_status": voided["from_status"], "via": "break-glass CLI"})
    print(f"Consultation #{cid} voided as {reason_class}.")
    if reason_class == consultations.VOID_CLASS_CLINICAL_SAFETY:
        print("The admin UI will not offer Unvoid for it.")
    return 0


async def cmd_unvoid(cid: int, reason: str) -> int:
    """The operation the HTTP API refuses. Typed confirmation required."""
    state = await consultations.void_state(cid)
    if state is None:
        print(f"No consultation #{cid}.", file=sys.stderr)
        return 1
    if not state["voided"]:
        print(f"Consultation #{cid} is not voided.", file=sys.stderr)
        return 1

    print(f"Consultation #{cid} was voided as"
          f" {state['reason_class'] or '(unset)'} for this reason:\n")
    print(f"    {state['reason'] or '(no reason recorded)'}\n")
    if state["reason_class"] == consultations.VOID_CLASS_CLINICAL_SAFETY:
        print("This is a CLINICAL SAFETY void. Reversing it puts a record"
              " judged unsafe back into working clinical views.")
        typed = input(f"Type the consultation id ({cid}) to confirm: ").strip()
        if typed != str(cid):
            print("Refused: confirmation did not match.", file=sys.stderr)
            return 1

    reverted = await consultations.unvoid_consultation(cid, allow_clinical_safety=True)
    if reverted is None:
        print(f"Refused: consultation #{cid} could not be unvoided.", file=sys.stderr)
        return 1
    await audit.log(None, "consultation.unvoided", "consultation", cid,
                    {"reverted_reason": reverted["reverted_reason"],
                     "reverted_class": reverted["reverted_class"],
                     "reason": reason, "status": reverted["status"],
                     "via": "break-glass CLI"})
    print(f"Consultation #{cid} restored to working views"
          f" (status {reverted['status']}).")
    return 0


def recording_files(cid: int, audio_path: str | None,
                    recordings_dir: Path = RECORDINGS_DIR) -> list[Path]:
    """Every file on disk that belongs to this consultation's recording:
    the path the row names (wav, or flac after approval compressed it)
    and anything under the recordings directory named for the id — a
    wav the retention path renamed but the row lost, for instance."""
    found: dict[str, Path] = {}
    if audio_path:
        p = Path(audio_path)
        if p.exists():
            found[str(p.resolve())] = p
    if recordings_dir.is_dir():
        for p in sorted(recordings_dir.glob(f"consultation_{cid}.*")):
            found.setdefault(str(p.resolve()), p)
    return list(found.values())


async def cmd_purge_one(cid: int, confirm=input, operator: str | None = None,
                        recordings_dir: Path = RECORDINGS_DIR) -> int:
    """Hard-delete one already-voided consultation of any class.
    Typed confirmation required; refuses anything not voided."""
    state = await consultations.void_state(cid)
    if state is None:
        print(f"No consultation #{cid}.", file=sys.stderr)
        return 1
    if not state["voided"]:
        print(f"Refused: consultation #{cid} is not voided. Void it first;"
              " purge-one deletes voided rows only.", file=sys.stderr)
        return 1

    print(f"Consultation #{cid} is voided as"
          f" {state['reason_class'] or '(unset)'} for this reason:\n")
    print(f"    {state['reason'] or '(no reason recorded)'}\n")
    print("purge-one HARD-DELETES it: the consultation row and everything"
          " that cascades from it (turns, raw segments, system utterances,"
          " assessment snapshots, notes, letters), the patient row if no"
          " other consultation references it, and the recording file(s)."
          " The void audit row stays. This cannot be undone.")
    typed = confirm(f"Type the consultation id ({cid}) to confirm: ").strip()
    if typed != str(cid):
        print("Refused: confirmation did not match.", file=sys.stderr)
        return 1

    # Files are located BEFORE the delete: the row is the only record of
    # the audio path, and it is about to go.
    row = await consultations.get_consultation(cid)
    files = recording_files(cid, row["audio_path"] if row else None, recordings_dir)

    purged = await consultations.purge_one(cid)
    if purged is None:
        print(f"Refused: consultation #{cid} was not deleted (gone, or"
              " unvoided since the check).", file=sys.stderr)
        return 1

    removed: list[str] = []
    failed: list[str] = []
    for path in files:
        try:
            path.unlink()
            removed.append(str(path))
        except OSError as exc:
            failed.append(f"{path}: {exc}")

    operator = operator or getpass.getuser()
    await audit.log(None, "data.purged", "consultation", cid,
                    {"consultation_id": cid,
                     "void_reason_class": purged["void_reason_class"],
                     "void_reason": purged["void_reason"],
                     "status": purged["status"],
                     "operator": operator,
                     "cascaded_rows": purged["cascaded_rows"],
                     "patient_id": purged["patient_id"],
                     "patient_purged": purged["patient_purged"],
                     "files_removed": removed,
                     "files_failed": failed,
                     "via": "break-glass CLI purge-one"})

    print(f"Consultation #{cid} purged ({purged['void_reason_class']}).")
    for table, n in purged["cascaded_rows"].items():
        if n:
            print(f"  {table}: {n} row(s) removed")
    if purged["patient_purged"]:
        print(f"  patient #{purged['patient_id']} removed (no other consultation)")
    elif purged["patient_id"] is not None:
        print(f"  patient #{purged['patient_id']} kept (other consultations)")
    for f in removed:
        print(f"  removed {f}")
    for f in failed:
        print(f"  COULD NOT remove {f}", file=sys.stderr)
    print(f"  data.purged audit row written (operator {operator}).")
    return 2 if failed else 0


def main() -> int:
    # Every entry point applies the whole schema, in one order (app/schema.py).
    schema.ensure_all()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-voided", help="list voided consultations and their classes")
    show = sub.add_parser("show", help="show one consultation's void state")
    show.add_argument("cid", type=int)
    void = sub.add_parser("void", help="void a consultation")
    void.add_argument("cid", type=int)
    void.add_argument("--reason", required=True)
    void.add_argument("--class", dest="reason_class",
                      choices=consultations.VOID_CLASSES,
                      default=consultations.VOID_CLASS_TEST_DATA)
    unvoid = sub.add_parser(
        "unvoid", help="reverse a void, including clinical_safety (break-glass)")
    unvoid.add_argument("cid", type=int)
    unvoid.add_argument("--reason", required=True)
    purge = sub.add_parser(
        "purge-one", help="hard-delete one voided consultation of any class,"
        " its cascading rows, orphaned patient and recording (break-glass)")
    purge.add_argument("cid", type=int)
    args = parser.parse_args()

    if args.command == "list-voided":
        return asyncio.run(cmd_list_voided())
    if args.command == "show":
        return asyncio.run(cmd_show(args.cid))
    if args.command == "void":
        return asyncio.run(cmd_void(args.cid, args.reason, args.reason_class))
    if args.command == "purge-one":
        return asyncio.run(cmd_purge_one(args.cid))
    return asyncio.run(cmd_unvoid(args.cid, args.reason))


if __name__ == "__main__":
    raise SystemExit(main())
