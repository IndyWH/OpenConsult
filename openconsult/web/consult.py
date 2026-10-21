"""The pages of a consultation (spec 8.2; 15.10 rulings 9 and 12; R1,
R11, R15, R17): the new-patient form, the Start screen, Start itself,
and typing as use. The live page, Stop and the final page are in
web/live.py."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from openconsult import words
from openconsult.consult import earlier
from openconsult.consult.live import SPEAKERS, Consultation
from openconsult.llm.choose import SHORT_WAIT_S
from openconsult.patients.patients import parse_date, problem
from openconsult.speech.choices import NEMOTRON, WHISPERX_PYANNOTE
from openconsult.web import guards
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


def speech_choice_for(p) -> SpeechChoice:
    """The first usable of the two local choices (review point 2): Nemotron
    where installed, then the WhisperX choice where the room check offers
    it and it is installed. No cloud choice is chosen by the app in 6a: its
    statement and its mark are stage 9. A path check only; nothing starts."""
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


def start_problem(p, ask_engine: bool = True) -> str | None:
    """Why Start is not offered (R15; 10.4): the room check's element, the
    engine not answering the joint's short wait at this view, or no local
    speech choice usable. None when Start can act."""
    if not p.decisions.start_offered:
        return words.START_NO_MODEL.format(reason=p.decisions.language_model.sentence)
    if ask_engine and not p.engine.status(p.door.profile.tag, SHORT_WAIT_S).running:
        return words.START_MODEL_UNREACHABLE.format(engine=words.ENGINE_NAMES.get(p.engine.name, p.engine.name))
    choice = speech_choice_for(p)
    if choice.door is None:
        return words.START_NO_SPEECH.format(reason=choice.reason)
    return None


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


def _start_context(request: Request, user, patient, ask_engine: bool = True) -> dict:
    p = parts(request)
    choice = speech_choice_for(p)
    notes = earlier.approved_notes(p.notes, patient.id)
    return dict(user=user, active="new_patient", patient=patient, age=words.plain_age(patient.age_on(p.patients.today())),
                born=words.plain_date(patient.date_of_birth), sex=words.SEX_WORDS[patient.sex],
                minutes=INTENDED_MINUTES, chosen=p.consultations.last_intended() or DEFAULT_MINUTES,
                speech=choice.door.choice.title if choice.door else None,
                # A patient with an approved note gets the list and the switch, on by default (ruling 3; D25).
                earlier=earlier_lines(notes), switch=bool(notes),
                problem=start_problem(p, ask_engine), page_path=f"/consultations/start/{patient.id}")


@router.get("/consultations/start/{patient_id}")
async def start_page(request: Request, patient_id: int, user=Depends(guards.logged_in)):
    patient = _patient_or_404(request, patient_id)
    return render(request, "start.html", **_start_context(request, user, patient))


@router.post("/consultations/start/{patient_id}")
async def start(request: Request, patient_id: int, user=Depends(guards.logged_in)):
    """Start: the right patient and an acted consultation confirmed (R17,
    R1), the intended time picked (D38), the row made with its stamps
    (R20), the consultation object made and held for the run."""
    p = parts(request)
    patient = _patient_or_404(request, patient_id)
    fields = await form_fields(request)
    context = _start_context(request, user, patient)
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
    raise Redirect(f"/consultations/{consultation.id}")


def begin(p, patient, minutes: int, earlier_notes_shown: bool | None = None, earlier_notes: list[int] | None = None) -> Consultation:
    version, digest = p.door.identity()
    door = speech_choice_for(p).door
    cid = p.consultations.start(patient.id, minutes, door.choice.name, p.engine.name, version, p.door.profile.tag,
                                digest, SPEAKERS, earlier_notes_shown, earlier_notes)
    consultation = Consultation(cid, patient, minutes, p.clock(), door, p.door, p.consultations, p.audit,
                                p.settings.data_folder, p.clock, on_stop=p.finaliser, notes=p.notes, converter=p.converter)
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
