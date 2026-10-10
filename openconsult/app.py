"""The app factory. Everything is put together fresh at each start and
for each test (spec 5.1); nothing lives in process-wide state."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from openconsult.db import Database, open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import Engine
from openconsult.llm.ollama import OllamaEngine
from openconsult.llm.record import ModelCalls
from openconsult.patients.audit import Audit, Clock, now_local
from openconsult.patients.logins import Logins
from openconsult.patients.users import Users
from openconsult.settings.machine import Machine, read_machine
from openconsult.settings.store import Settings
from openconsult.speech.choices import CHOICES, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor, make_door
from openconsult.speech.selftest import SelfTests
from openconsult.web import guards, routes
from openconsult.web.first_run import FirstRun

STATIC = Path(__file__).parent / "web" / "static"


@dataclass
class Parts:
    settings: Settings
    db: Database
    audit: Audit
    users: Users
    logins: Logins
    first_run: FirstRun
    machine: Machine
    engine: Engine
    door: Door
    speech: SpeechDoor             # the WhisperX with pyannote door, as 5a built it
    self_tests: SelfTests
    doors: dict = field(default_factory=dict)      # one door for each choice, by name (15.9)


def build_app(settings: Settings, machine: Machine | None = None, clock: Clock = now_local,
              engine: Engine | None = None, speech: SpeechDoor | None = None,
              doors: dict | None = None) -> FastAPI:
    """engine, speech and doors are passed in by tests, so the suite needs
    no Ollama and no speech worker (spec 15.7, 15.9). Building a door
    starts nothing and reads nothing but a path."""
    db = open_database(settings.database_path)
    audit = Audit(db, clock)
    users = Users(db, audit, clock)
    engine = engine or OllamaEngine(settings.engine_address)
    doors = dict(doors or {})
    if speech is not None:
        doors.setdefault(WHISPERX_PYANNOTE.name, speech)
    for name, choice in CHOICES.items():
        doors.setdefault(name, make_door(settings.data_folder, choice))
    parts = Parts(
        settings=settings,
        db=db,
        audit=audit,
        users=users,
        logins=Logins(audit, clock),
        first_run=FirstRun(db, users, clock),
        machine=machine or read_machine(),
        engine=engine,
        door=Door(engine, ModelCalls(db, clock)),
        speech=doors[WHISPERX_PYANNOTE.name],
        self_tests=SelfTests(db, clock),
        doors=doors,
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)
    app.state.parts = parts
    guards.install(app, settings.port, settings.address)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(routes.router)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Every speech worker that was started ends with the app."""
    yield
    for door in app.state.parts.doors.values():
        door.close()
