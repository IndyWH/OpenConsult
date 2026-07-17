"""Break-glass user administration — server shell only, never over HTTP.

For when the web UI can't help: a forgotten admin password, no admin left
active, a role that needs changing from the console. Passwords are always
prompted (getpass), never taken as arguments, so they stay out of shell
history.

Usage:
    uv run python scripts/manage_users.py list
    uv run python scripts/manage_users.py reset-password USERNAME
    uv run python scripts/manage_users.py set-role USERNAME ROLE
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import auth  # noqa: E402


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list all users with roles and status")
    reset = sub.add_parser("reset-password", help="set a new password (prompted)")
    reset.add_argument("username")
    setrole = sub.add_parser("set-role", help="promote/demote a user")
    setrole.add_argument("username")
    setrole.add_argument("role", choices=auth.ROLES)
    args = parser.parse_args()

    if args.command == "list":
        return asyncio.run(cmd_list())
    if args.command == "reset-password":
        return asyncio.run(cmd_reset_password(args.username))
    return asyncio.run(cmd_set_role(args.username, args.role))


if __name__ == "__main__":
    raise SystemExit(main())
