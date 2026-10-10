"""The one command (spec 15.6): openconsult starts the app, openconsult
reset-password resets the password (D26), openconsult install-speech
builds a speech choice's environment and fetches its models, and
openconsult self-test runs a speech choice's self-test (15.9). Both name
their choice with --choice; with none named they take WhisperX with
pyannote, as before 5b."""

from __future__ import annotations

import argparse
import getpass
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Callable

import uvicorn

from openconsult import browser, words
from openconsult.app import build_app
from openconsult.db import NewerDatabase, open_database
from openconsult.patients.audit import Audit
from openconsult.patients.users import MIN_PASSWORD, Users, password_problem
from openconsult.settings import store
from openconsult.settings.machine import Machine
from openconsult.settings.store import LISTEN_ON
from openconsult.speech import environment, selftest
from openconsult.speech.choices import CHOICES, WHISPERX_PYANNOTE, Choice
from openconsult.speech.door import make_door


def main(argv: list[str] | None = None, say: Callable = print,
         ask: Callable = getpass.getpass, serve: Callable | None = None,
         machine: Machine | None = None, open_browser: Callable | None = None,
         run_process: Callable = subprocess.run, which: Callable = shutil.which,
         make_speech: Callable = make_door, sleep: Callable = time.sleep) -> int:
    """say, ask, serve, machine, open_browser, run_process, which, make_speech
    and sleep are passed in so tests run the command with no terminal, no
    browser, no uv, no speech worker and no waiting, the same on every
    machine."""
    parser = argparse.ArgumentParser(prog="openconsult")
    parser.add_argument("command", nargs="?",
                        choices=["run", "reset-password", "install-speech", "self-test"], default="run")
    parser.add_argument("--data-folder", type=Path, help="where the data lives, for a development run")
    parser.add_argument("--port", type=int, help="the port to listen on; 8001 if not given")
    parser.add_argument("--no-browser", action="store_true", help="start without opening the browser")
    parser.add_argument("--choice", choices=sorted(CHOICES), default=WHISPERX_PYANNOTE.name,
                        help="the speech choice for install-speech and self-test")
    args = parser.parse_args(argv)
    if args.command == "reset-password":
        return reset_password(args.data_folder, say=say, ask=ask)
    if args.command == "install-speech":
        return install_speech(args.data_folder, CHOICES[args.choice], say=say, run=run_process, which=which)
    if args.command == "self-test":
        return self_test(args.data_folder, CHOICES[args.choice], say=say, make_speech=make_speech, sleep=sleep)
    return run(args.data_folder, args.port, say=say, serve=serve or _serve, machine=machine,
               open_browser=None if args.no_browser else (open_browser or browser.start))


def run(data_folder: Path | None, port: int | None, say: Callable, serve: Callable,
        machine: Machine | None = None, open_browser: Callable | None = None) -> int:
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
    say(words.OPEN_IT if open_browser is None else words.BROWSER_WILL_OPEN)
    say(words.DATA_FOLDER.format(folder=settings.data_folder))
    # The browser opens only once the app really answers (ruling 2), so
    # the wait runs beside the server, never before it.
    if open_browser is not None:
        open_browser(settings.address)
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


BUILDING = {"whisperx_pyannote": words.SPEECH_BUILDING, "nemotron": words.SPEECH_BUILDING_NEMOTRON}


def install_speech(data_folder: Path | None, choice: Choice, say: Callable, run: Callable, which: Callable) -> int:
    """Builds a speech choice's environment in the data folder from the
    committed lock file, then finds or fetches its models (15.9; 6.4).
    Nothing else downloads a model. A cloud choice has nothing to build."""
    settings = store.build(data_folder)
    if not choice.environment:
        say(words.CLOUD_NEEDS_NO_INSTALL.format(service=choice.title))
        return 0
    say(BUILDING[choice.name].format(folder=environment.folder(settings.data_folder, choice)))
    report = environment.build(settings.data_folder, choice, say=say, run=run, which=which)
    return 0 if report.ok else 1


def self_test(data_folder: Path | None, choice: Choice, say: Callable, make_speech: Callable, sleep: Callable) -> int:
    """The clip through the door, then Stop; the result stored and said
    (D46; 15.9). Nothing starts when the choice is not installed. For a
    cloud choice this is also the test of the connection (7.2), and the
    clip leaves the computer: the running sentence says so."""
    settings = store.build(data_folder)
    door = make_speech(settings.data_folder, choice)
    if not door.installed:
        say(words.SPEECH_NEEDS_INSTALL)
        return 1
    say(words.SELF_TEST_RUNNING_CLOUD.format(service=choice.title) if choice.key else words.SELF_TEST_RUNNING)
    try:
        outcome = selftest.run(door, sleep=sleep)
    except selftest.ClipChanged:
        say(words.SELF_TEST_CLIP_CHANGED)
        return 1
    finally:
        door.close()
    db = open_database(settings.database_path)
    selftest.SelfTests(db).add(door.choice.name, outcome)
    live, stop = " ".join(outcome.live_words), " ".join(outcome.stop_words)
    if outcome.passed:
        say(words.SELF_TEST_RESULT_PASSED.format(live=live, stop=stop))
        if door.one_transcript:
            say(words.SELF_TEST_SAME_LINES)
        return 0
    say(words.SELF_TEST_RESULT_FAILED.format(reason=outcome.reason, live=live, stop=stop))
    return 1
