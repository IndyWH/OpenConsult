"""The app factory. Everything is put together fresh at each start and
for each test (spec 5.1); nothing lives in process-wide state."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Callable

from fastapi import FastAPI

import asyncio

from openconsult.consult import opus, retention, stop
from openconsult.consult.who_check import WhoChecks
from openconsult.consult.whole import WholeRecording
from openconsult.consult.consultations import Consultations
from openconsult.consult.letter_rows import Letters
from openconsult.consult.note_rows import Notes
from openconsult.db import Database, open_database
from openconsult.guidelines.embedder import make_embedder
from openconsult.guidelines.panel import Guidelines
from openconsult.guidelines.search import Index
from openconsult.guidelines.sources import Sources
from openconsult.llm.choose import NoEngine, choose
from openconsult.llm.claude import ClaudeEngine
from openconsult.llm.cloud_door import ClaudeDoors
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
from openconsult.settings.connections import Connections
from openconsult.settings.decisions import Decisions, converter_element, language_model_element
from openconsult.settings.machine import Machine, read_machine
from openconsult.settings.path import CLAUDE, SPEECHMATICS, THIS_COMPUTER
from openconsult.settings.secure import SystemStore
from openconsult.settings.store import Settings
from openconsult.settings.stored import Stored
from openconsult.speech.choices import CHOICES, WHISPERX_PYANNOTE
from openconsult.speech.door import Door as SpeechDoor, make_door
from openconsult.speech.selftest import SelfTests
from openconsult.web import settings_local, steps as steps_web
from openconsult.web import calls as calls_web, cloud as cloud_web, consult, guards, guidelines as guidelines_web, letters as letters_web, live, pages, patients as patients_web, review, routes, who_check as who_check_web
from openconsult.web.first_run import FirstRun
from openconsult.web.start_tests import StartTests

# The finder the app uses at start; tests stand a quiet one in its place.
find_converter_at_start = opus.find_converter
# The system's secure store for the keys (7.2); the suite stands a made one in its place and never touches a real one.
system_store = SystemStore


def make_claude_engine(key: str):
    """The Claude engine with a key, to the service's own address. The suite
    puts an engine in this function's place that fails a test which would
    call the real service."""
    return ClaudeEngine(key=key)


def default_upload_send():
    """How a recording is sent after Stop: none named here, so the upload's
    own sender to the service's EU address stands. The suite puts a
    sender in this function's place that fails a test which would reach
    the real service."""
    return None


def default_testers() -> dict:
    """The tests of the two connections as the app runs them: none named
    here, so the real ones of settings/connections.py stand. The suite
    puts testers in this function's place that fail a test which would
    reach a real service."""
    return {}


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
    who_checks: object = None                      # the runs of the who-spoke check asked for on the review page (6c)
    running: dict = field(default_factory=dict)    # the live consultations, by id, held for the run
    store: object = None                           # the system's secure store for the keys of the cloud services (9b)
    connections: Connections = None                # the key in use and the last test of each cloud service (9b)
    calls: ModelCalls = None                       # the record of every model call
    claude_doors: ClaudeDoors = None               # the door to Claude with the key in use (9b)
    whole: WholeRecording = None                   # the sender of a recording after Stop, with the key in use (9b)
    self_testing: object = None                    # the self-test asked for from its first-run step, while it runs (9b)
    start_tests: StartTests = None                 # the tests that run beside a view of the Start screen (9c)
    clock: Clock = now_local
    finaliser: Callable | None = None              # Stop in order (stop.py), given to each consultation

    def door_of(self, language_model: str) -> Door:
        """The door of a path's language model: this computer's, chosen at
        start and held for the run, or the door to Claude. Nothing ever
        answers in the other's place (10.4)."""
        return self.claude_doors.door() if language_model == CLAUDE else self.door

    def door_for(self, consultation_id: int) -> Door:
        """The door every later call of a consultation goes by: the path the
        consultation started with, read from its own row, never the
        setting as it stands now (7.3)."""
        row = self.consultations.get(consultation_id)
        return self.door_of(row["language_model_path"] if row else THIS_COMPUTER)


def build_app(settings: Settings, machine: Machine | None = None, clock: Clock = now_local,
              engines: dict | None = None, speech: SpeechDoor | None = None,
              doors: dict | None = None, card_programs: Callable | None = None,
              find_converter: Callable | None = None, embedder=None, secure_store=None, testers: dict | None = None,
              claude_engine: Callable | None = None, upload_send: Callable | None = None) -> FastAPI:
    """engines, speech, doors, card_programs, find_converter, embedder and
    secure_store are passed in by tests, and testers, the tests of the
    two cloud connections, so the suite needs no vLLM, no Ollama, no
    speech worker, no card, no converter, no embedding worker, no secure
    store and no cloud service (spec 15.7, 15.8, 15.9, 15.11, 15.12, 15.13).
    Building a store asks nothing of the system. Building a
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
    secure_store = secure_store if secure_store is not None else system_store()
    if speech is not None:
        doors.setdefault(WHISPERX_PYANNOTE.name, speech)
    for name, choice in CHOICES.items():
        doors.setdefault(name, make_door(settings.data_folder, choice, store=secure_store))
    sources = Sources(db, audit, clock)
    calls = ModelCalls(db, clock)
    door = Door(engine, calls, profile)
    stored = Stored(db, audit, clock)
    connections = Connections(settings.data_folder, secure_store, audit, calls, clock, testers={**default_testers(), **(testers or {})})
    claude_doors = ClaudeDoors(lambda: connections.key(CLAUDE), calls, claude_engine or make_claude_engine)
    # The test of a connection runs at each start, for each service the chosen path uses that has a key (7.2).
    connections.test_all(stored.path(machine.case).services)
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
        stored=stored,
        connections=connections,
        calls=calls,
        claude_doors=claude_doors,
        whole=WholeRecording(lambda: connections.key(SPEECHMATICS), upload_send or default_upload_send()),
        sources=sources,
        embedder=embedder,
        guidelines=Guidelines(sources, Index(sources), embedder, door, audit, door_for=lambda cid: parts.door_for(cid)),
        converter=converter,
        store=secure_store,
        start_tests=StartTests(),
        clock=clock,
        finaliser=_finalise,
    )
    # A check of who spoke left running by the last run is ended as failed: no label had changed (6c).
    parts.who_checks = WhoChecks(door, parts.consultations, audit, door_for=parts.door_for)
    parts.who_checks.sweep()
    # A consultation left live or stopping by the last run goes on (review point 3).
    for consultation in stop.sweep(parts):
        consultation.on_final = consult._on_final(parts)
    # The sweeps of 7a: orphan files reported, old recordings deleted (ruling 7; ruling 8).
    retention.orphans(parts)
    retention.sweep(parts)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)
    app.state.parts = parts
    guards.install(app, settings.port, settings.address)
    app.mount("/static", pages.AskedEachTime(directory=pages.STATIC), name="static")
    for module in (routes, consult, live, review, who_check_web, patients_web, letters_web, guidelines_web, calls_web, cloud_web, steps_web,
                   settings_local):
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
    app.state.parts.who_checks.close()
    for consultation in app.state.parts.running.values():
        consultation.close()
    for door in app.state.parts.doors.values():
        door.close()
    app.state.parts.embedder.close()
