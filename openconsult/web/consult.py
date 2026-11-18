"""The pages of a consultation (spec 8.2; 15.10 rulings 9 and 12; R1,
R11, R15, R17): the new-patient form, the Start screen, Start itself,
and typing as use. The live page, Stop and the final page are in
web/live.py."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from openconsult import words
from openconsult.consult import background, earlier
from openconsult.consult.live import SPEAKERS, Consultation
from openconsult.llm import claude
from openconsult.llm.choose import SHORT_WAIT_S
from openconsult.patients.patients import parse_date, problem
from openconsult.settings.connections import LIMIT_S
from openconsult.settings.path import CLAUDE, SPEECHMATICS, ChosenPath
from openconsult.settings.statement import mark_lines, statement_for
from openconsult.speech.choices import NEMOTRON, SPEECHMATICS as SPEECHMATICS_CHOICE, WHISPERX_PYANNOTE
from openconsult.web import guards, steps as steps_web
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
INTENDED_MINUTES = (15, 30, 45, 60)      # D38
DEFAULT_MINUTES = 15
PATIENT_PROBLEMS = {"name": words.PATIENT_NAME_MISSING, "date_missing": words.DATE_OF_BIRTH_MISSING,
                    "date_bad": words.DATE_OF_BIRTH_BAD, "sex": words.SEX_MISSING}


# ------------------------------------------------------- the speech choice

@dataclass(frozen=True)
class SpeechChoice:
    door: object | None
    reason: str | None        # why none can be used


def speech_choice_for(p, path: ChosenPath | None = None) -> SpeechChoice:
    """The speech choice of a path (15.13, the details of run 9b). In the
    cloud: the Speechmatics worker of 5b. On this computer, as since 6a,
    the first usable of the two local choices (review point 2): Nemotron
    where installed, then the WhisperX choice where the room check offers
    it and it is installed. A path check only; nothing starts, and nothing
    is ever chosen in another's place."""
    path = path or p.stored.path(p.machine.case)
    if path.speechmatics_live:
        return SpeechChoice(p.doors[SPEECHMATICS_CHOICE.name], None)
    if p.machine.case != "suitable":
        return SpeechChoice(None, words.SPEECH_REASONS["no_card"])
    nemotron = p.doors[NEMOTRON.name]
    if nemotron.installed:
        return SpeechChoice(nemotron, None)
    reasons = [words.SPEECH_REASONS["nemotron_not_installed"]]
    whisperx = p.doors[WHISPERX_PYANNOTE.name]
    if not p.decisions.whisperx_choice.green:
        reasons.append(words.SPEECH_REASONS["whisperx_no_room"])
    elif not whisperx.installed:
        reasons.append(words.SPEECH_REASONS["whisperx_not_installed"])
    else:
        return SpeechChoice(whisperx, None)
    return SpeechChoice(None, " ".join(reasons))


@dataclass(frozen=True)
class StartState:
    problem: str | None = None          # why Start is not offered, for the control itself (R15)
    lead: tuple[str, str] | None = None  # where the doctor mends it: an address and its words
    tests: dict | None = None           # the tests of the connections made for this view
    notice: str | None = None           # said on the screen while Start is still offered


def start_state(p, ask_engine: bool = True, read_tests: bool = True) -> StartState:
    """Why Start is not offered (R15; 10.4; 7.2), by the path as chosen.
    This computer, as since 6a: the room check's element, the engine not
    answering the joint's short wait at this view, or no local speech
    choice usable. A cloud service: not connected; the statement of the
    path not ticked, or ticked for other words; or the test of a
    connection the consultation needs while it runs failing now, with its
    reason. A consultation never begins on a connection that is down.
    ask_engine False: nothing is asked and no connection is tested; the
    last test of each connection is read (the Consultation box of This
    machine). read_tests False as well: no test is read either, so only
    what the app knows at once is said (the Start screen shown at once,
    ruling 51)."""
    path = p.stored.path(p.machine.case)
    missing = steps_web.missing_step(p)
    if missing is not None:
        # A set-up step that is not done: named on the control, with the way to it (7.1; R15).
        return StartState(words.START_STEP_MISSING[missing], (f"/first-run/{missing.replace('_', '-')}", words.FIRST_RUN_SELF_TEST_TITLE
                                                              if missing == "self_test" else words.FIRST_RUN_MIC_TITLE))
    if path.claude:
        if not p.connections.state(CLAUDE).has_key:
            return StartState(words.START_NOT_CONNECTED.format(service=words.SERVICE_TITLES[CLAUDE]), ("/connect/claude", words.CONNECT_CLAUDE_TITLE))
    elif not p.decisions.start_offered:
        # No local model runs: the control says so, and where Claude is not connected either it leads to the connect screen (15.8, ruling 37).
        return StartState(words.START_NO_MODEL.format(reason=p.decisions.language_model.sentence),
                          None if p.connections.state(CLAUDE).has_key else ("/connect/claude", words.CONNECT_CLAUDE_TITLE))
    elif ask_engine and not p.engine.status(p.door.profile.tag, SHORT_WAIT_S).running:
        return StartState(words.START_MODEL_UNREACHABLE.format(engine=words.ENGINE_NAMES.get(p.engine.name, p.engine.name)))
    if path.speechmatics_live:
        if not p.connections.state(SPEECHMATICS).has_key:
            return StartState(words.START_NOT_CONNECTED.format(service=words.SERVICE_TITLES[SPEECHMATICS]),
                              ("/connect/speechmatics", words.CONNECT_SPEECHMATICS_TITLE))
    else:
        choice = speech_choice_for(p, path)
        if choice.door is None:
            return StartState(words.START_NO_SPEECH.format(reason=choice.reason))
    # Ticked itself, or sending less than the statement that was ticked (15.13, ruling 48).
    if not p.stored.covers(statement_for(path)):
        return StartState(words.START_STATEMENT, ("/settings#cloud-statement", words.NAV_SETTINGS))
    if not read_tests:
        return StartState()
    tests = p.connections.test_all(path.services) if ask_engine else {
        service: p.connections.state(service).last for service in path.services}
    for service in path.needed_while_it_runs:
        tested = tests.get(service)
        if tested is not None and not tested.ok:
            return StartState(words.START_TEST_FAILED.format(reason=tested.sentence), (f"/connect/{service}", words.SERVICE_TITLES[service]), tests)
    # The tick for better accuracy needs its service only after Stop (the owner's word, 16 Nov 2026): Start is offered,
    # and the screen says plainly that the better transcript may not be made.
    notice = None
    if path.recording_after_stop:
        tested = tests.get(SPEECHMATICS)
        if tested is None and not p.connections.state(SPEECHMATICS).has_key:
            notice = words.START_BETTER_MAY_FAIL.format(reason=words.NOT_CONNECTED_SERVICE.format(service=words.SERVICE_TITLES[SPEECHMATICS]))
        elif tested is not None and not tested.ok:
            notice = words.START_BETTER_MAY_FAIL.format(reason=tested.sentence)
    return StartState(tests=tests, notice=notice)


def start_problem(p, ask_engine: bool = True) -> str | None:
    return start_state(p, ask_engine).problem


# --------------------------------------------------------- the new patient

@router.get("/patients/new")
async def new_patient_page(request: Request, user=Depends(guards.logged_in)):
    return render(request, "patient_new.html", user=user, active="new_patient", timed_by_script=True)


@router.post("/patients")
async def save_patient(request: Request, user=Depends(guards.logged_in)):
    p = parts(request)
    fields = await form_fields(request)
    found = problem(fields.get("name", ""), fields.get("date_of_birth", ""), fields.get("sex", ""), p.patients.today())
    if found:
        return refuse(request, "patient_new.html", "save-patient", PATIENT_PROBLEMS[found], user=user,
                      active="new_patient", fields=fields, timed_by_script=True, page_path="/patients/new")
    patient = p.patients.add(fields["name"], parse_date(fields["date_of_birth"]), fields["sex"])
    raise Redirect(f"/consultations/start/{patient.id}")


# ---------------------------------------------------------- the Start screen

def _patient_or_404(request: Request, patient_id: int):
    patient = parts(request).patients.get(patient_id)
    if patient is None:
        raise Redirect("/patients/new")
    return patient


def earlier_lines(notes: list) -> list[dict]:
    """The Start screen's list of a patient's approved notes (ruling 3;
    8.2): the consultation's number, its date, the assessment or the
    first plan entry."""
    return [{"id": note.consultation_id, "line": words.EARLIER_NOTE_LINE.format(
        number=note.consultation_id, date=words.plain_date(note.started_at), line=note.headline())} for note in notes]


def _start_context(request: Request, user, patient, state: StartState, run=None, testing: bool = False, poll: bool = False) -> dict:
    """run: the tests that run beside this view, named by the page so that
    its script can ask for their result and Start can read it. testing:
    the control waits for them, disabled, and says so (ruling 51)."""
    p = parts(request)
    path = p.stored.path(p.machine.case)
    choice = speech_choice_for(p, path)
    notes = earlier.approved_notes(p.notes, patient.id)
    return dict(user=user, active="new_patient", patient=patient, age=words.plain_age(patient.age_on(p.patients.today())),
                born=words.plain_date(patient.date_of_birth), sex=words.SEX_WORDS[patient.sex],
                minutes=INTENDED_MINUTES, chosen=p.consultations.last_intended() or DEFAULT_MINUTES,
                speech=(words.CHOICE_SPEECHMATICS if path.speechmatics_live else choice.door.choice.title) if choice.door else None,
                # The path in two rows (7.3; 9b): where the language model runs, beside the speech choice.
                model=words.CHOICE_CLAUDE if path.claude else words.CHOICE_THIS_COMPUTER, lead=state.lead, tests=state.tests,
                mark=mark_lines(path), start_notice=state.notice, run=run.id if run is not None else None, testing=testing, poll=poll,
                # A patient with an approved note gets the list and the switch, on by default (ruling 3; D25).
                earlier=earlier_lines(notes), switch=bool(notes),
                problem=state.problem, page_path=f"/consultations/start/{patient.id}")


# How long a page with no script waits for the tests it asked the result of: their own limits, and a little more.
RESULT_WAIT_S = LIMIT_S + SHORT_WAIT_S + 2.0


async def start_view(p, named: str | None = None) -> tuple[StartState, object, bool, bool]:
    """What a view of the Start screen is made from: the control's state,
    the run of tests beside it, and whether the control waits for them
    (15.13, ruling 51). A path on this computer alone is as it was: all
    is asked before the page is sent. On any other path, what the app
    knows at once is said at once, and nothing is tested for it. Else
    the tests run beside the page. The control waits for them where the
    consultation needs a service while it runs. Where it needs none
    until after Stop (ruling 37), Start is offered at once, the engine
    asked as on this computer, and the test of the service only brings
    the notice. named: the run a page with no script asks the result of."""
    path = p.stored.path(p.machine.case)
    if not path.services:
        return start_state(p), None, False, False
    known = start_state(p, ask_engine=False, read_tests=False)
    if known.problem:
        return known, None, False, False
    run = p.start_tests.get(named, path.key())
    if run is not None:
        await asyncio.to_thread(run.answered.wait, RESULT_WAIT_S)
        if p.start_tests.fresh(run):
            return run.state, run, False, False
    run = p.start_tests.begin(path.key(), lambda: start_state(p))
    if path.needed_while_it_runs:
        return StartState(), run, True, True
    return start_state(p, ask_engine=True, read_tests=False), run, False, True


def press_state(p, named: str | None) -> StartState | None:
    """The state a press of Start is judged by. The rule that a
    consultation never begins on a connection that is down is kept here,
    by the app, and not by the page alone (ruling 51). The run the page
    named: still running, the press is refused (None) where the
    consultation needs a service while it runs; answered a short while
    ago, it is used; older, or none named, the connections are tested at
    the press itself, as in run 9b."""
    path = p.stored.path(p.machine.case)
    if not path.services:
        return start_state(p)
    known = start_state(p, ask_engine=False, read_tests=False)
    if known.problem:
        return known
    run = p.start_tests.get(named, path.key())
    if run is None:
        return start_state(p)
    if not run.answered.is_set():
        return None if path.needed_while_it_runs else start_state(p, ask_engine=True, read_tests=False)
    if p.start_tests.fresh(run):
        return run.state
    return start_state(p)


@router.get("/consultations/start/{patient_id}")
async def start_page(request: Request, patient_id: int, user=Depends(guards.logged_in)):
    patient = _patient_or_404(request, patient_id)
    state, run, testing, poll = await start_view(parts(request), request.query_params.get("tests"))
    return render(request, "start.html", **_start_context(request, user, patient, state, run, testing, poll))


@router.get("/consultations/start/{patient_id}/tests")
async def start_tests_result(request: Request, patient_id: int, user=Depends(guards.logged_in_not_use)):
    """What the page's script asks while the tests run: running, or their
    answer in the app's own sentences, which the script writes into the
    places the page has. Read only, and no use of the page (15.10,
    ruling 41). gone: the run is not the one for the path as it stands."""
    p = parts(request)
    run = p.start_tests.get(request.query_params.get("run"), p.stored.path(p.machine.case).key())
    if run is None:
        return JSONResponse({"state": "gone"})
    if not run.answered.is_set() or run.state is None:
        return JSONResponse({"state": "running"})
    state = run.state
    return JSONResponse({"state": "answered", "problem": state.problem, "lead": list(state.lead) if state.problem and state.lead else None,
                         "notice": None if state.problem else state.notice})


@router.post("/consultations/start/{patient_id}")
async def start(request: Request, patient_id: int, user=Depends(guards.logged_in)):
    """Start: the right patient and an acted consultation confirmed (R17,
    R1), the intended time picked (D38), the row made with its stamps
    (R20), the consultation object made and held for the run."""
    p = parts(request)
    patient = _patient_or_404(request, patient_id)
    fields = await form_fields(request)
    state = press_state(p, fields.get("tests"))
    run = p.start_tests.get(fields.get("tests"), p.stored.path(p.machine.case).key())
    if state is None:
        # The tests of the page that was pressed have not answered: refused, and the page goes on waiting for them.
        return refuse(request, "start.html", "start", words.START_STILL_TESTING,
                      **_start_context(request, user, patient, StartState(), run, True, True))
    # A page sent back for a tick that is missing still names its run, so the next press need not test again.
    context = _start_context(request, user, patient, state, run if run is not None and p.start_tests.fresh(run) else None)
    if context["problem"]:
        return refuse(request, "start.html", "start", context["problem"], **context)
    if fields.get("right_patient") != "yes" or fields.get("acted") != "yes":
        return refuse(request, "start.html", "start", words.TICK_BOTH, **context)
    minutes = int(fields.get("intended", 0) or 0)
    if minutes not in INTENDED_MINUTES:
        return refuse(request, "start.html", "start", words.TICK_BOTH, **context)
    # The switch's setting is stored with the consultation (ruling 3): on, off, or none where no switch was offered.
    shown = (fields.get("earlier_notes") == "yes") if context["switch"] else None
    consultation = begin(p, patient, minutes, shown, [row["id"] for row in context["earlier"]])
    # The test of a connection made for this Start is a call to a model: its rows belong to the consultation it began.
    for tested in (context["tests"] or {}).values():
        if tested is not None:
            p.calls.tie(tested.call_ids, consultation.id)
    p.start_tests.spent(fields.get("tests"))         # its tests began this consultation: a later press is tested afresh
    raise Redirect(f"/consultations/{consultation.id}")


def begin(p, patient, minutes: int, earlier_notes_shown: bool | None = None, earlier_notes: list[int] | None = None) -> Consultation:
    """The path is read here, once, and written on the consultation's row:
    the consultation holds it to its end, whatever the settings become
    (7.3). Its language model door and its speech door are those of that
    path, and no other is ever tried in their place (10.4)."""
    path = p.stored.path(p.machine.case)
    llm = p.door_of(path.language_model)
    # The service's own lines for the record, with no call to it at Start (R20): no build version, no digest.
    version, digest = (claude.ENGINE_VERSION, claude.NO_DIGEST) if path.claude else llm.identity()
    door = speech_choice_for(p, path).door
    cid = p.consultations.start(patient.id, minutes, door.choice.name, llm.engine_name, version, llm.profile.tag,
                                digest, SPEAKERS, earlier_notes_shown, earlier_notes, path=path,
                                # The checksum of the statement of its own path, which may stand under a wider tick (ruling 48).
                                statement_sha256=statement_for(path).sha256 if path.holds_cloud else None)
    started_at = p.clock()
    # The block of 15.11 ruling 5 goes to the two calls of every pass while the switch is on (8.4); off or none sends nothing.
    block = background.block_for(p.notes, patient.id, started_at, cid) if earlier_notes_shown else None
    consultation = Consultation(cid, patient, minutes, started_at, door, llm, p.consultations, p.audit,
                                p.settings.data_folder, p.clock, on_stop=p.finaliser, notes=p.notes, converter=p.converter,
                                background=block, guidelines=p.guidelines, whole=p.whole)
    consultation.on_final = _on_final(p)
    p.running[cid] = consultation
    p.audit.record("consultation.started", f"consultation {cid}, patient {patient.id}, {minutes} minutes")
    p.logins.consultation_running = True
    return consultation


def _on_final(p):
    def done(consultation) -> None:
        p.logins.consultation_running = any(c.state != "final" for c in p.running.values())
    return done


# ---------------------------------------------------------- typing as use

@router.post("/use")
async def use(request: Request, user=Depends(guards.logged_in)):
    """Ruling 12: a keystroke is use. The guard has touched the login; the
    page learns how long is left."""
    return JSONResponse({"seconds_left": request.state.seconds_left})
