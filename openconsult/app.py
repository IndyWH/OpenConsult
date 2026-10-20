"""The app factory. Everything is put together fresh at each start and
for each test (spec 5.1); nothing lives in process-wide state."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from openconsult.consult.consultations import Consultations
from openconsult.db import Database, open_database
from openconsult.llm.choose import NoEngine, choose
from openconsult.llm.door import Door
from openconsult.llm.engine import Engine
from openconsult.llm.ollama import OllamaEngine
from openconsult.llm.profile import GEMMA_4_QAT
from openconsult.llm.record import ModelCalls
from openconsult.llm.vllm import VllmEngine
from openconsult.patients.audit import Audit, Clock, now_local
from openconsult.patients.logins import Logins
from openconsult.patients.patients import Patients
from openconsult.patients.users import Users
from openconsult.settings import room
from openconsult.settings.decisions import Decisions, language_model_element
from openconsult.settings.machine import Machine, read_machine
from openconsult.settings.store import Settings
from openconsult.speech.choices import CHOICES, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor, make_door
from openconsult.speech.selftest import SelfTests
from openconsult.web import consult, guards, routes
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
    engine: Engine                 # the one chosen at start, held for the run (ruling 37)
    door: Door
    decisions: Decisions
    speech: SpeechDoor             # the WhisperX with pyannote door, as 5a built it
    self_tests: SelfTests
    doors: dict = field(default_factory=dict)      # one door for each choice, by name (15.9)
    patients: Patients = None
    consultations: Consultations = None            # the rows (15.10)
    running: dict = field(default_factory=dict)    # the live consultations, by id, held for the run
    clock: Clock = now_local
    finaliser: Callable | None = None              # Stop in order (stop.py), given to each consultation


def build_app(settings: Settings, machine: Machine | None = None, clock: Clock = now_local,
              engines: dict | None = None, speech: SpeechDoor | None = None,
              doors: dict | None = None, card_programs: Callable | None = None) -> FastAPI:
    """engines, speech, doors and card_programs are passed in by tests, so
    the suite needs no vLLM, no Ollama, no speech worker and no card (spec
    15.7, 15.8, 15.9). Building a door starts nothing and reads nothing
    but a path. The engine is chosen here, once, the room on the card is
    read once, and the decisions are written to the audit log once
    (rulings 36 to 38)."""
    db = open_database(settings.database_path)
    audit = Audit(db, clock)
    users = Users(db, audit, clock)
    machine = machine or read_machine()
    engines = {"vllm": VllmEngine(settings.vllm_address), "ollama": OllamaEngine(settings.ollama_address),
               **(engines or {})}
    choice = choose(machine, engines, GEMMA_4_QAT)
    engine = engines[choice.name] if choice.name else NoEngine()
    profile = GEMMA_4_QAT.for_engine(choice.name) if choice.name else GEMMA_4_QAT
    programs = (card_programs or room.read_programs)() if machine.card else None   # no tool is run on a Mac or with no card
    decisions = Decisions({"language_model": language_model_element(choice, profile.tag if choice.name else None),
                           **room.check(machine, choice.name, programs)})
    for element in decisions.elements.values():
        audit.record(f"decision.{element.name}", element.audit_detail)
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
        machine=machine,
        engine=engine,
        door=Door(engine, ModelCalls(db, clock), profile),
        decisions=decisions,
        speech=doors[WHISPERX_PYANNOTE.name],
        self_tests=SelfTests(db, clock),
        doors=doors,
        patients=Patients(db, audit, clock),
        consultations=Consultations(db, clock),
        clock=clock,
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)
    app.state.parts = parts
    guards.install(app, settings.port, settings.address)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(routes.router)
    app.include_router(consult.router)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Every speech worker that was started ends with the app."""
    yield
    for consultation in app.state.parts.running.values():
        consultation.close()
    for door in app.state.parts.doors.values():
        door.close()
