"""Break-glass user administration — server shell only, never over HTTP.

For when the web UI can't help: a forgotten admin password, no admin left
active, a role that needs changing from the console. Passwords are always
prompted (getpass), never taken as arguments, so they stay out of shell
history.

Usage:
    uv run python scripts/manage_users.py list
    uv run python scripts/manage_users.py reset-password USERNAME
    uv run python scripts/manage_users.py set-role USERNAME ROLE
    uv run python scripts/manage_users.py set-display-name USERNAME "Display Name"
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import audit, auth, schema  # noqa: E402


async def cmd_list() -> int:
    users = await auth.list_users()
    if not users:
        print("No users.")
        return 0
    header = f"{'id':>3}  {'username':<20} {'display name':<20} {'role':<12} {'active':<8} {'last login':<16} created"
    print(header)
    print("-" * len(header))
    for u in users:
        print(f"{u['id']:>3}  {u['username']:<20} {u['display_name']:<20}"
              f" {u['role']:<12} {'yes' if u['active'] else 'NO':<8}"
              f" {u['last_login_at'] or '—':<16} {u['created_at']}")
    return 0


async def cmd_reset_password(username: str) -> int:
    new = getpass.getpass(f"New password for {username!r}: ")
    if len(new) < 8:
        print("Refused: password too short (min 8).", file=sys.stderr)
        return 1
    if getpass.getpass("Repeat to confirm: ") != new:
        print("Refused: passwords do not match.", file=sys.stderr)
        return 1
    if not await auth.reset_password(username, new):
        print(f"No such user {username!r}.", file=sys.stderr)
        return 1
    print(f"Password reset for {username!r}. Existing sessions stay valid"
          " until they expire; log in with the new password from now on.")
    return 0


async def cmd_set_role(username: str, role: str) -> int:
    if role not in auth.ROLES:
        print(f"Invalid role {role!r}; choose from {', '.join(auth.ROLES)}.",
              file=sys.stderr)
        return 1
    if not await auth.set_role(username, role):
        print(f"Refused: no such user {username!r}, or demoting them would"
              " leave no active admin.", file=sys.stderr)
        return 1
    print(f"{username!r} is now a {role}.")
    return 0


async def cmd_set_display_name(username: str, display_name: str) -> int:
    """The display name is SPOKEN ALOUD to a patient — the disclosure
    interpolates it server-side (`app/speech.py`). Consultation 448 ran on
    the admin account whose display name is "Doctor" and the room heard
    "Dr Doctor". Owner's decision 2026-07-28: fix the names, not the code.
    No title is invented from a name and that convention stands.

    Audited like the consultation break-glass CLI, with the old name in the
    row: a change to what a patient hears must be reconstructible afterwards.
    """
    try:
        changed = await auth.set_display_name(username, display_name)
    except ValueError as err:
        print(f"Refused: {err}.", file=sys.stderr)
        return 1
    if changed is None:
        print(f"No such user {username!r}.", file=sys.stderr)
        return 1
    await audit.log(None, "user.display_name_changed", "app_user", changed["id"],
                    {"from": changed["from"], "to": changed["to"],
                     "username": username, "via": "break-glass CLI"})
    print(f"{username!r}: display name {changed['from']!r} → {changed['to']!r}.")
    print("This is the name the disclosure speaks as \"Dr <name>\" —"
          " say it aloud once before the next consultation.")
    return 0


def main() -> int:
    # Every entry point applies the whole schema, in one order (app/schema.py)
    # — a script must not be able to leave the database in a state no other
    # code path produces.
    schema.ensure_all()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list all users with roles and status")
    reset = sub.add_parser("reset-password", help="set a new password (prompted)")
    reset.add_argument("username")
    setrole = sub.add_parser("set-role", help="promote/demote a user")
    setrole.add_argument("username")
    setrole.add_argument("role", choices=auth.ROLES)
    setname = sub.add_parser(
        "set-display-name",
        help="set the name shown in the app AND spoken in the disclosure")
    setname.add_argument("username")
    setname.add_argument("display_name", metavar="DISPLAY_NAME")
    args = parser.parse_args()

    if args.command == "list":
        return asyncio.run(cmd_list())
    if args.command == "reset-password":
        return asyncio.run(cmd_reset_password(args.username))
    if args.command == "set-display-name":
        return asyncio.run(cmd_set_display_name(args.username, args.display_name))
    return asyncio.run(cmd_set_role(args.username, args.role))


if __name__ == "__main__":
    raise SystemExit(main())
