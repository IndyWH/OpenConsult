"""The first-run steps of run 9b (spec 7.1; 15.13, ruling 7 and the
details of the run; 15.8, ruling 37; D46): connect the language model
and connect transcription, each only when its path is the cloud; the
self-test, run from the page by the command's own code; and the
microphone test, with a meter. Each can be left with Not now: a step
left is not done, and Start names it on its control (R15).

What makes each done. A connect step: its service connected and the
statement of the path ticked. The self-test: a pass from the page; a
failed self-test leaves the step not done. The microphone test: the
page saw the level move; its sound is never stored and never sent.

During the first run these pages are read from this computer alone,
with no user; after it, behind the login, where a data folder that
finished its first run before these steps existed meets them once."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import APIRouter, Request

from openconsult import words
from openconsult.settings.path import CLAUDE, SPEECHMATICS
from openconsult.settings.statement import statement_for
from openconsult.speech import selftest
from openconsult.web import cloud as cloud_web
from openconsult.web.first_run import CONNECT_LANGUAGE_MODEL, CONNECT_TRANSCRIPTION, MICROPHONE, MIDDLE, SELF_TEST
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
# The clip is fed at the pace of real sound, as the live page will send it; the suite stands no waiting in its place.
pace = time.sleep
SERVICE_OF = {CONNECT_LANGUAGE_MODEL: CLAUDE, CONNECT_TRANSCRIPTION: SPEECHMATICS}
STEP_OF = {service: step for step, service in SERVICE_OF.items()}


def needed(p, step: str) -> bool:
    """A connect step is a step only when its path is the cloud (7.1)."""
    path = p.stored.path(p.machine.case)
    if step == CONNECT_LANGUAGE_MODEL:
        return path.claude
    if step == CONNECT_TRANSCRIPTION:
        return path.speechmatics_live
    return True


def is_done(p, step: str) -> bool:
    if step in SERVICE_OF:
        path = p.stored.path(p.machine.case)
        return p.connections.connected(SERVICE_OF[step]) and p.stored.ticked(statement_for(path))
    return step in p.first_run.done()


def walk_step(p) -> str | None:
    """The first step between This machine and the user that is needed,
    not done and not yet met: the step the walk shows next."""
    left = p.first_run.left()
    for step in MIDDLE:
        if needed(p, step) and not is_done(p, step) and step not in left:
            return step
    return None


def missing_step(p) -> str | None:
    """The first of the self-test and the microphone test that is not
    done, for the Start control (R15). The connect steps are said there
    by their own reasons."""
    done = p.first_run.done()
    return next((step for step in (SELF_TEST, MICROPHONE) if step not in done), None)


# ---------------------------------------------------------------- the pages

@dataclass
class SelfTesting:
    """The self-test asked for from the page, for one run of the app: it
    runs on a thread of its own, and the page waits by looking again."""
    state: str = "idle"            # idle, running, passed or failed
    reason: str | None = None
    thread: threading.Thread | None = None


def self_testing(p) -> SelfTesting:
    if getattr(p, "self_testing", None) is None:
        p.self_testing = SelfTesting()
    return p.self_testing


def step_page(request: Request, user, step: str, refused=None):
    p = parts(request)
    new = words.FIRST_RUN_NEW_STEPS if user is not None else None     # an older folder meets the steps once, and is told why
    if step in SERVICE_OF:
        return cloud_web.connect_page(request, user, SERVICE_OF[step], refused)
    if step == SELF_TEST:
        from openconsult.web.consult import speech_choice_for
        path = p.stored.path(p.machine.case)
        choice = speech_choice_for(p, path)
        running = self_testing(p)
        context = dict(user=user, active="settings", new_steps=new, done=is_done(p, SELF_TEST), running=running.state == "running",
                       cloud_line=(words.SELF_TEST_RUNNING_CLOUD.format(service=words.SERVICE_TITLES[SPEECHMATICS])
                                   if path.speechmatics_live else None),
                       cannot=None if choice.door is not None else choice.reason,
                       result=(words.SELF_TEST_STEP_PASSED if running.state == "passed" else
                               words.SELF_TEST_STEP_FAILED.format(reason=running.reason) if running.state == "failed" else None),
                       failed=running.state == "failed", page_path="/first-run/self-test",
                       refresh_every=2 if running.state == "running" else 0)
        template = "first_run_self_test.html"
    else:
        context = dict(user=user, active="settings", new_steps=new, done=is_done(p, MICROPHONE), page_path="/first-run/microphone",
                       refresh_every=0)
        template = "first_run_microphone.html"
    if refused:
        return refuse(request, template, refused[0], refused[1], **context)
    return render(request, template, **context)


@router.get("/first-run/self-test")
async def self_test_page(request: Request):
    return step_page(request, cloud_web.reader(request), SELF_TEST)


@router.get("/first-run/microphone")
async def microphone_page(request: Request):
    return step_page(request, cloud_web.reader(request), MICROPHONE)


def run_self_test(p, door) -> None:
    """The clip through the door of the path's speech choice, stored as
    the command stores it; a pass marks the step done."""
    state = self_testing(p)
    try:
        outcome = selftest.run_and_store(door, p.self_tests, sleep=pace)
    except selftest.ClipChanged:
        state.state, state.reason = "failed", words.SELF_TEST_CLIP_CHANGED
        return
    except Exception as broke:  # noqa: BLE001 - a step never raises into the app: what broke is said by its name
        state.state, state.reason = "failed", f"{type(broke).__name__}"
        return
    if outcome.passed:
        p.first_run.mark_done(SELF_TEST)
        p.audit.record("self_test.passed", door.choice.title)
        state.state, state.reason = "passed", None
    else:
        state.state, state.reason = "failed", outcome.reason or ""


@router.post("/first-run/self-test")
async def self_test(request: Request):
    """Run the self-test. Refused on the control while a consultation
    runs, since the speech choice has one session, and where no speech
    choice of the path can be used, with that reason."""
    from openconsult.web.consult import speech_choice_for
    user, p = cloud_web.reader(request), parts(request)
    state = self_testing(p)
    if state.state == "running":
        raise Redirect("/first-run/self-test")
    if any(c.state != "final" for c in p.running.values()):
        return step_page(request, user, SELF_TEST, ("run-self-test", words.SELF_TEST_BUSY))
    choice = speech_choice_for(p)
    if choice.door is None:
        return step_page(request, user, SELF_TEST, ("run-self-test", choice.reason))
    state.state, state.reason = "running", None
    state.thread = threading.Thread(target=run_self_test, args=(p, choice.door), name="self-test", daemon=True)
    state.thread.start()
    raise Redirect("/first-run/self-test")


@router.post("/first-run/microphone")
async def microphone(request: Request):
    """The page's script saw the level move. Nothing of the sound comes
    here: only that word."""
    user, p = cloud_web.reader(request), parts(request)
    if (await form_fields(request)).get("moved") != "yes":
        return step_page(request, user, MICROPHONE, ("continue", words.MIC_NO_SOUND))
    p.first_run.mark_done(MICROPHONE)
    p.audit.record("microphone.tested")
    raise Redirect("/first-run")


@router.post("/first-run/leave")
async def leave(request: Request):
    """Not now: the step is left, not done; the walk goes on, and Start
    names what is missing."""
    cloud_web.reader(request)
    p = parts(request)
    step = (await form_fields(request)).get("step", "")
    if step in MIDDLE:
        p.first_run.mark_left(step)
    raise Redirect("/first-run")
