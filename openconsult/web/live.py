"""The live page and its socket (spec 15.10, The live page, The
recording; R15, R18; 11.5 rule 3). The page is rendered by the
consultation's state; the socket carries the sound in and the page's
state out. Nothing waits on a model call here: the sound goes to the
consultation on a thread, and the state is sent whenever it has changed.
Stop is a form post, so it acts with or without the socket."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from openconsult import words
from openconsult.consult import speakers, stop as stop_module
from openconsult.consult.gate import LOW_CONFIDENCE
from openconsult.consult.live import FINAL, LIVE, Capture
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
PIECE_S = 0.25           # the size the page sends, as the self-test and the bench send it

# The sentences the page script renders, handed to it as data so that no
# sentence lives in a script (15.6: every sentence in one file).
SCRIPT_WORDS = ("LISTENING", "WAITING_FOR_WORDS", "PASS_RUNNING", "FROM_EARLIER_PASS", "PASS_FAILED", "ALARM_NONE",
                "ALARM_FIRED", "ALARM_NO_ACTION", "ALARM_NOT_JUDGED", "ALARM_ARRANGED", "SHOW_REASONING",
                "EARLIER_ALARMS", "ACKNOWLEDGE", "ACKNOWLEDGED", "CLOCK_USED", "CLOCK_OVER", "SPEECH_STOPPED",
                "SPEECH_STARTING", "MIC_REFUSED", "SOCKET_LOST", "SOCKET_BACK", "QUESTIONS", "SIGNS", "DIFFERENTIALS",
                "SPEAKER_WORD")


def script_words() -> dict:
    return {name: getattr(words, name) for name in SCRIPT_WORDS}


def running(request: Request, consultation_id: int):
    consultation = parts(request).running.get(consultation_id)
    if consultation is None:
        raise Redirect("/")
    return consultation


def model_line(request: Request, consultation) -> str:
    p = parts(request)
    return words.MODEL_LINE.format(speech=consultation.speech_door.choice.title, model=p.door.profile.tag,
                                   engine=words.ENGINE_NAMES.get(p.engine.name, p.engine.name),
                                   version=p.door.identity()[0] or "")


@router.get("/consultations/{consultation_id}")
async def consultation_page(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """The page by the consultation's state: live, stopping or final."""
    consultation = running(request, consultation_id)
    if consultation.state == LIVE:
        return live_page(request, user, consultation)
    stop_module.continue_resumed(consultation)     # a consultation found stopping at a restart goes on when opened
    if consultation.state == FINAL:
        return final_page(request, user, consultation)
    return stopping_page(request, user, consultation)


def live_page(request: Request, user, consultation, refused=None):
    state = consultation.page_state()
    return render(request, "live.html", user=user, active="new_patient", consultation=consultation, state=state,
                  state_json=json.dumps(state), words_json=json.dumps(script_words()),
                  model_line=model_line(request, consultation), patient=consultation.patient, piece_s=PIECE_S)


def stopping_page(request: Request, user, consultation, refused=None):
    """While Stop runs: the named stage, with a quiet refresh each second
    (a spinner only for a named in-progress state, V1_LESSONS 5.3); at the
    who-spoke stage the question, which waits (ruling 7)."""
    state = consultation.page_state()
    asking = state["stop_stage"] == "who_spoke"
    context = dict(user=user, active="new_patient", consultation=consultation, state=state,
                   stage_line=words.STAGE_LINES.get(state["stop_stage"] or "", ""), patient=consultation.patient,
                   page_path=f"/consultations/{consultation.id}", refresh_every=0 if asking else 1,
                   options=speakers.options(consultation.rows.transcript_lines(consultation.id)) if asking else [])
    if refused:
        return refuse(request, "stopping.html", refused[0], refused[1], **context)
    return render(request, "stopping.html", **context)


@router.post("/consultations/{consultation_id}/speakers")
async def answer(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Which speaker was you (ruling 7): the answer sets the labels and the
    finaliser goes on. A second answer, or none picked, is refused on the
    control (R15)."""
    consultation = running(request, consultation_id)
    fields = await form_fields(request)
    picked = fields.get("speaker", "")
    if consultation.stop_stage != "who_spoke" or consultation.doctor_speaker is not None:
        raise Redirect(f"/consultations/{consultation.id}")     # answered already: the page has moved on
    if not picked or not stop_module.answer(consultation, picked):
        return stopping_page(request, user, consultation, refused=("answer", words.PICK_ONE))
    raise Redirect(f"/consultations/{consultation.id}")


def final_page(request: Request, user, consultation):
    lines = [dict(row) for row in consultation.final.lines if row["n"] is not None]
    for line in lines:
        score = line.get("confidence")
        line["low_confidence"] = (words.LOW_CONFIDENCE_MARK.format(score=f"{score:.2f}")
                                  if score is not None and score < LOW_CONFIDENCE else None)
    return render(request, "final.html", user=user, active="new_patient", consultation=consultation,
                  patient=consultation.patient, lines=lines, warnings=warning_lines(consultation),
                  passes=consultation.passes.state(), model_line=model_line(request, consultation))


def warning_lines(consultation) -> list[str]:
    """Each stored warning as its sentence (ruling 8)."""
    found = []
    for w in consultation.final.warnings:
        kind, detail = w["kind"], w["detail"] or ""
        if kind == "speech_failed":
            found.append(words.WARN_SPEECH_FAILED.format(reason=detail) if detail != words.APP_RESTARTED else detail)
        elif kind == "label_check_refused":
            found.append(words.WARN_LABEL_CHECK_REFUSED.format(reason=detail))
        elif kind == "label_check_failed":
            found.append(words.WARN_LABEL_CHECK_FAILED.format(reason=detail))
        else:
            found.append(words.WARNING_SENTENCES.get(kind, "{detail}").format(
                start=w["start_s"], end=w["end_s"], n=w["line_n"], detail=detail, words=detail, score=detail,
                choice=consultation.speech_door.choice.title))
    return found


@router.post("/consultations/{consultation_id}/stop")
async def stop(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Stop: the first press stops the consultation; a second press while
    one is finalising waits for it and is answered with the page as it
    stands (V1_LESSONS 1.12; R15: never swallowed)."""
    consultation = running(request, consultation_id)
    consultation.stop()
    raise Redirect(f"/consultations/{consultation.id}")


# ------------------------------------------------------------- the socket

def capture_from(message: dict) -> Capture | None:
    """The page's first message: the three values as the browser applied
    them (true, false or null when it could not say) and the rate."""
    try:
        rate = int(message["rate"])
    except (KeyError, TypeError, ValueError):
        return None
    if rate <= 0:
        return None
    return Capture(_three(message.get("echo_cancellation")), _three(message.get("noise_suppression")),
                   _three(message.get("auto_gain")), rate)


def _three(value) -> bool | None:
    return None if value is None else bool(value)


@router.websocket("/consultations/{consultation_id}/sound")
async def sound(websocket: WebSocket, consultation_id: int):
    if not guards.socket_allowed(websocket) or guards.socket_user(websocket) is None:
        await websocket.close(code=1008)
        return
    consultation = websocket.app.state.parts.running.get(consultation_id)
    if consultation is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    sent = -1
    try:
        sent = await _send_state(websocket, consultation, sent)
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            await _handle(consultation, message)
            sent = await _send_state(websocket, consultation, sent)
    except WebSocketDisconnect:
        pass


async def _handle(consultation, message: dict) -> None:
    if message.get("bytes"):
        await asyncio.to_thread(consultation.sound, message["bytes"])
        return
    try:
        data = json.loads(message.get("text") or "")
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    if data.get("type") == "capture":
        capture = capture_from(data)
        if capture is not None:
            await asyncio.to_thread(consultation.begin_sound, capture)
    elif data.get("type") == "acknowledge":
        consultation.acknowledge(str(data.get("key", "")))


async def _send_state(websocket: WebSocket, consultation, sent: int) -> int:
    if consultation.version == sent and consultation.state == LIVE:
        return sent
    state = consultation.page_state()
    await websocket.send_text(json.dumps({"type": "state", "state": state}))
    return state["version"]
