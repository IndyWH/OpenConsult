"""The app factory. Everything is put together fresh at each start and
for each test (spec 5.1); nothing lives in process-wide state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from openconsult.db import Database, open_database
from openconsult.patients.audit import Audit, Clock, now_local
from openconsult.patients.logins import Logins
from openconsult.patients.users import Users
from openconsult.settings.machine import Machine, read_machine
from openconsult.settings.store import Settings
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


def build_app(settings: Settings, machine: Machine | None = None, clock: Clock = now_local) -> FastAPI:
    db = open_database(settings.database_path)
    audit = Audit(db, clock)
    users = Users(db, audit, clock)
    parts = Parts(
        settings=settings,
        db=db,
        audit=audit,
        users=users,
        logins=Logins(audit, clock),
        first_run=FirstRun(db, users, clock),
        machine=machine or read_machine(),
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.parts = parts
    guards.install(app, settings.port, settings.address)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(routes.router)
    return app
