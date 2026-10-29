"""The app factory. Everything is put together fresh at each start and
for each test (spec 5.1); nothing lives in process-wide state."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import asyncio

from openconsult.consult import opus, retention, stop
from openconsult.consult.consultations import Consultations
from openconsult.consult.letter_rows import Letters
from openconsult.consult.note_rows import Notes
from openconsult.db import Database, open_database
from openconsult.guidelines.embedder import make_embedder
from openconsult.guidelines.panel import Guidelines
from openconsult.guidelines.search import Index
from openconsult.guidelines.sources import Sources
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
from openconsult.settings.decisions import Decisions, converter_element, language_model_element
from openconsult.settings.machine import Machine, read_machine
from openconsult.settings.store import Settings
from openconsult.settings.stored import Stored
from openconsult.speech.choices import CHOICES, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor, make_door
from openconsult.speech.selftest import SelfTests
from openconsult.web import consult, guards, guidelines as guidelines_web, letters as letters_web, live, patients as patients_web, review, routes
from openconsult.web.first_run import FirstRun

STATIC = Path(__file__).parent / "web" / "static"
# The finder the app uses at start; tests stand a quiet one in its place.
find_converter_at_start = opus.find_converter


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
    notes: Notes = None                            # the note's rows (6b)
    letters: Letters = None                        # the referral letters' rows (8a)
    stored: Stored = None                          # the settings a page can change (7a)
    sources: Sources = None                        # the corpus's rows (8b)
    embedder: object = None                        # the door to the embedding worker, where the room check put it (8b)
    guidelines: Guidelines = None                  # the panel's service: the index, the worker, the door, the floor (8b)
    converter: object = None                       # the recording converter found at start, or None (7a)
    running: dict = field(default_factory=dict)    # the live consultations, by id, held for the run
    clock: Clock = now_local
    finaliser: Callable | None = None              # Stop in order (stop.py), given to each consultation


def build_app(settings: Settings, machine: Machine | None = None, clock: Clock = now_local,
              engines: dict | None = None, speech: SpeechDoor | None = None,
              doors: dict | None = None, card_programs: Callable | None = None,
              find_converter: Callable | None = None, embedder=None) -> FastAPI:
    """engines, speech, doors, card_programs, find_converter and embedder
    are passed in by tests, so the suite needs no vLLM, no Ollama, no
    speech worker, no card, no converter and no embedding worker (spec
    15.7, 15.8, 15.9, 15.11, 15.12). Building a
    door starts nothing and reads nothing but a path. The engine is chosen
    here, once, the room on the card is read once, the converter is found
    once, and the decisions are written to the audit log once (rulings 36
    to 38)."""
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
    converter = (find_converter or find_converter_at_start)()
    decisions = Decisions({"language_model": language_model_element(choice, profile.tag if choice.name else None),
                           **room.check(machine, choice.name, programs), "converter": converter_element(converter)})
    for element in decisions.elements.values():
        audit.record(f"decision.{element.name}", element.audit_detail)
    # The embedding worker sits where the room check put it (ruling 32); a folder with no install gets the door with nothing behind it.
    where = "card" if decisions.guideline_search.green else "processor"
    embedder = embedder or make_embedder(settings.data_folder, where)
    doors = dict(doors or {})
    if speech is not None:
        doors.setdefault(WHISPERX_PYANNOTE.name, speech)
    for name, choice in CHOICES.items():
        doors.setdefault(name, make_door(settings.data_folder, choice))
    sources = Sources(db, audit, clock)
    door = Door(engine, ModelCalls(db, clock), profile)
    parts = Parts(
        settings=settings,
        db=db,
        audit=audit,
        users=users,
        logins=Logins(audit, clock),
        first_run=FirstRun(db, users, clock),
        machine=machine,
        engine=engine,
        door=door,
        decisions=decisions,
        speech=doors[WHISPERX_PYANNOTE.name],
        self_tests=SelfTests(db, clock),
        doors=doors,
        patients=Patients(db, audit, clock),
        consultations=Consultations(db, clock),
        notes=Notes(db, clock),
        letters=Letters(db, clock),
        stored=Stored(db, audit, clock),
        sources=sources,
        embedder=embedder,
        guidelines=Guidelines(sources, Index(sources), embedder, door, audit),
        converter=converter,
        clock=clock,
        finaliser=_finalise,
    )
    # A consultation left live or stopping by the last run goes on (review point 3).
    for consultation in stop.sweep(parts):
        consultation.on_final = consult._on_final(parts)
    # The sweeps of 7a: orphan files reported, old recordings deleted (ruling 7; ruling 8).
    retention.orphans(parts)
    retention.sweep(parts)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)
    app.state.parts = parts
    guards.install(app, settings.port, settings.address)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    for module in (routes, consult, live, review, patients_web, letters_web, guidelines_web):
        app.include_router(module.router)
    return app


def _finalise(consultation) -> None:
    stop.finalise(consultation)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """The retention sweep runs in the app's own loop while it runs
    (ruling 7); every speech worker that was started ends with the app."""
    sweeping = asyncio.create_task(retention.loop(app.state.parts))
    yield
    sweeping.cancel()
    for consultation in app.state.parts.running.values():
        consultation.close()
    for door in app.state.parts.doors.values():
        door.close()
    app.state.parts.embedder.close()
