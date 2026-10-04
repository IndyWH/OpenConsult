"""The one command (spec 15.6): openconsult starts the app, and
openconsult reset-password resets the password (D26)."""

from __future__ import annotations

import argparse
import getpass
import socket
from pathlib import Path
from typing import Callable

import uvicorn

from openconsult import words
from openconsult.app import build_app
from openconsult.db import NewerDatabase, open_database
from openconsult.patients.audit import Audit
from openconsult.patients.users import MIN_PASSWORD, Users, password_problem
from openconsult.settings import store
from openconsult.settings.machine import Machine
from openconsult.settings.store import LISTEN_ON


def main(argv: list[str] | None = None, say: Callable = print,
         ask: Callable = getpass.getpass, serve: Callable | None = None,
         machine: Machine | None = None) -> int:
    """say, ask, serve and machine are passed in so tests run the command
    with no terminal and the same result on every machine."""
    parser = argparse.ArgumentParser(prog="openconsult")
    parser.add_argument("command", nargs="?", choices=["run", "reset-password"], default="run")
    parser.add_argument("--data-folder", type=Path, help="where the data lives, for a development run")
    parser.add_argument("--port", type=int, help="the port to listen on; 8001 if not given")
    args = parser.parse_args(argv)
    if args.command == "reset-password":
        return reset_password(args.data_folder, say=say, ask=ask)
    return run(args.data_folder, args.port, say=say, serve=serve or _serve, machine=machine)


def run(data_folder: Path | None, port: int | None, say: Callable, serve: Callable,
        machine: Machine | None = None) -> int:
    settings = store.build(data_folder, port)
    # A taken port is said in plain words, and the app stops. It never
    # moves to another port by itself (spec 15.6; V1_LESSONS 7.6).
    if port_taken(LISTEN_ON, settings.port):
        say(words.PORT_TAKEN.format(port=settings.port))
        return 1
    try:
        app = build_app(settings, machine=machine)
    except NewerDatabase:
        say(words.NEWER_DATABASE)
        return 1
    say(words.RUNNING.format(address=settings.address))
    say(words.OPEN_IT)
    say(words.DATA_FOLDER.format(folder=settings.data_folder))
    serve(app, LISTEN_ON, settings.port)
    return 0


def port_taken(host: str, port: int) -> bool:
    """A plain socket with no reuse option, so every system refuses the
    bind when another program listens there."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        return True
    finally:
        probe.close()
    return False


def _serve(app, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


def reset_password(data_folder: Path | None, say: Callable, ask: Callable) -> int:
    """Asks twice without showing the password, and never takes it on
    the command line, so it is not kept in the terminal's history. It
    changes the password and nothing else (D26)."""
    settings = store.build(data_folder)
    if not settings.database_path.exists():
        say(words.RESET_NO_USER)
        return 1
    db = open_database(settings.database_path)
    users = Users(db, Audit(db))
    if not users.exists():
        say(words.RESET_NO_USER)
        return 1
    new, again = ask(words.ASK_NEW_PASSWORD), ask(words.ASK_NEW_PASSWORD_AGAIN)
    problem = password_problem(new, again)
    if problem == "short":
        say(words.RESET_SHORT.format(least=MIN_PASSWORD))
        return 1
    if problem == "differ":
        say(words.RESET_DIFFER)
        return 1
    users.reset_password(new)
    say(words.RESET_DONE)
    return 0
