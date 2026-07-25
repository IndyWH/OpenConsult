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

Usage:
    uv run python scripts/manage_consultations.py list-voided
    uv run python scripts/manage_consultations.py show CID
    uv run python scripts/manage_consultations.py void CID --class clinical_safety
    uv run python scripts/manage_consultations.py unvoid CID   # break-glass
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import audit, consultations, schema  # noqa: E402


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
    args = parser.parse_args()

    if args.command == "list-voided":
        return asyncio.run(cmd_list_voided())
    if args.command == "show":
        return asyncio.run(cmd_show(args.cid))
    if args.command == "void":
        return asyncio.run(cmd_void(args.cid, args.reason, args.reason_class))
    return asyncio.run(cmd_unvoid(args.cid, args.reason))


if __name__ == "__main__":
    raise SystemExit(main())
