"""Consultation AI — application entry point.

Phase 0: a minimal FastAPI app proving the environment works.
Later phases add the audio gateway, live transcription, and the
patient/consultation views described in PROJECT_PLAN.md.
"""

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fastapi import Depends
from pydantic import BaseModel

from app import audit, auth, consultations, frontdesk
from app.auth import COOKIE_NAME, CLINICAL_ROLES, api_user, page_user
from app.cds import CDSEngine
from app.finalize import finalize_consultation, regenerate_note
from app.live import PROCESS_INTERVAL_S, LiveSession
from app.notes import note_as_plain_text
from app.rag import RAGService
from app.transcription import LiveTranscriber

# Run a CDS pass once this much new confirmed text has accumulated.
CDS_MIN_NEW_CHARS = 150
# Stop trying after this many consecutive failures (e.g. Ollama not running).
CDS_MAX_FAILURES = 2

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")
STATIC_DIR = Path(__file__).parent / "static"
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "data/recordings"))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the Whisper model once, before serving traffic (takes a second or
    # two from the local cache; the first ever run downloads the model).
    auth.ensure_schema()
    frontdesk.ensure_schema()
    consultations.ensure_schema()
    audit.ensure_schema()
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    app.state.transcriber = await asyncio.to_thread(LiveTranscriber)
    app.state.cds_engine = CDSEngine()
    app.state.rag = RAGService()
    app.state.finalize_tasks = set()  # keep refs so tasks aren't GC'd mid-run
    yield

app = FastAPI(
    title="Consultation AI",
    description=(
        "Research/educational prototype for AI-assisted medical "
        "consultations in Sinhala and English. Not a medical device; "
        "synthetic data only."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_stale_app_code(request, call_next):
    """Pages and /static assets must revalidate on every load. Without
    Cache-Control, browsers cache them heuristically and demo machines
    keep running old JS after a deploy (seen: /live without the patient
    banner until a hard refresh). no-cache still permits ETag 304s."""
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if request.url.path.startswith("/static") or content_type.startswith("text/html"):
        response.headers["cache-control"] = "no-cache"
    return response


# ------------------------------------------------------------ auth & pages

class RegisterBody(BaseModel):
    username: str
    password: str
    display_name: str
    role: str  # doctor | receptionist (first user becomes admin)


class LoginBody(BaseModel):
    username: str
    password: str


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/register")
def register_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "login.html")  # same page, two forms


@app.post("/api/register")
async def register(body: RegisterBody) -> JSONResponse:
    if body.role not in ("doctor", "receptionist"):
        return JSONResponse(status_code=400, content={"error": "role must be doctor or receptionist"})
    if len(body.password) < 8:
        return JSONResponse(status_code=400, content={"error": "password too short (min 8)"})
    try:
        user = await auth.create_user(body.username, body.password, body.display_name, body.role)
    except Exception:
        return JSONResponse(status_code=409, content={"error": "username already taken"})
    await audit.log(user["id"], "user.registered", "user", user["id"], {"role": user["role"]})
    response = JSONResponse(content={"ok": True, "user": user})
    response.set_cookie(COOKIE_NAME, auth.sign_session(user["id"]), httponly=True, samesite="lax")
    return response


@app.post("/api/login")
async def login(body: LoginBody) -> JSONResponse:
    user = await auth.authenticate(body.username, body.password)
    if user is None:
        return JSONResponse(status_code=401, content={"error": "invalid credentials"})
    await audit.log(user["id"], "user.login", "user", user["id"])
    response = JSONResponse(content={"ok": True, "user": user})
    response.set_cookie(COOKIE_NAME, auth.sign_session(user["id"]), httponly=True, samesite="lax")
    return response


@app.post("/api/logout")
async def logout() -> JSONResponse:
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/api/me")
async def me(user: dict = Depends(api_user())) -> dict:
    return user


@app.get("/today")
def today_page(user: dict = Depends(page_user())) -> FileResponse:
    return FileResponse(STATIC_DIR / "today.html")


@app.get("/consultations")
def worklist_page(user: dict = Depends(page_user())) -> FileResponse:
    return FileResponse(STATIC_DIR / "worklist.html")


@app.get("/audit")
def audit_page(user: dict = Depends(page_user("admin"))) -> FileResponse:
    return FileResponse(STATIC_DIR / "audit.html")


@app.get("/api/audit")
async def audit_list(user: dict = Depends(api_user("admin"))) -> list[dict]:
    return await audit.recent()


# -------------------------------------------------------------------- queue

class QueueAddBody(BaseModel):
    name: str
    age: int | None = None
    sex: str | None = None


@app.get("/api/queue")
async def queue_list(user: dict = Depends(api_user())) -> list[dict]:
    return await frontdesk.today_queue()


@app.get("/api/queue/current")
async def queue_current(user: dict = Depends(api_user())) -> JSONResponse:
    """Today's active (in-consultation) entry — the live page's patient
    banner when no entry id is in the URL (e.g. reached via the nav tab)."""
    entry = await frontdesk.current_entry()
    if entry is None:
        return JSONResponse(status_code=404, content={"error": "no patient in consultation"})
    return JSONResponse(content=entry)


@app.get("/api/queue/{entry_id}")
async def queue_entry_detail(
    entry_id: int, user: dict = Depends(api_user())
) -> JSONResponse:
    """Server-side patient identity for one of today's entries. The live
    page's banner reads THIS, never URL text (wrong-patient prevention)."""
    entry = await frontdesk.get_entry(entry_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"error": "no such queue entry today"})
    return JSONResponse(content=entry)


@app.post("/api/queue")
async def queue_add(
    body: QueueAddBody, user: dict = Depends(api_user("receptionist", "admin"))
) -> dict:
    entry = await frontdesk.add_to_queue(body.name.strip(), body.age, body.sex)
    await audit.log(user["id"], "queue.patient_added", "queue_entry",
                    entry["entry_id"], {"patient_id": entry["patient_id"]})
    return entry


@app.post("/api/queue/{entry_id}/move")
async def queue_move(
    entry_id: int, direction: str,
    user: dict = Depends(api_user("receptionist", "admin")),
) -> dict:
    moved = await frontdesk.move_entry(entry_id, direction)
    if moved:
        await audit.log(user["id"], "queue.reordered", "queue_entry", entry_id,
                        {"direction": direction})
    return {"ok": moved}


@app.post("/api/queue/walk-in")
async def queue_walk_in(
    body: QueueAddBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Doctor's walk-in shortcut: register + start in one step. Grants no
    other queue rights — add/move stay receptionist-only."""
    name = body.name.strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})
    entry = await frontdesk.start_walk_in(name, body.age, body.sex)
    if entry is None:  # concurrency guard: another consultation is active
        return JSONResponse(status_code=409, content={
            "error": "another consultation is already in progress",
            "active": await frontdesk.current_entry(),
        })
    await audit.log(user["id"], "queue.walk_in_started", "queue_entry",
                    entry["entry_id"], {"patient_id": entry["patient_id"]})
    return JSONResponse(content=entry)


@app.post("/api/queue/{entry_id}/start")
async def queue_start(
    entry_id: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    started = await frontdesk.start_entry(entry_id)
    if started is None:
        active = await frontdesk.current_entry()
        if active and active["entry_id"] != entry_id:  # concurrency guard
            return JSONResponse(status_code=409, content={
                "error": "another consultation is already in progress",
                "active": active,
            })
        return JSONResponse(status_code=409, content={"error": "entry is not waiting"})
    await audit.log(user["id"], "queue.started", "queue_entry", entry_id,
                    {"patient_id": started["patient_id"]})
    return JSONResponse(content=started)


@app.get("/api/queue/{entry_id}/resume")
async def queue_resume(
    entry_id: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Where to send the doctor for an in-consultation entry: back to the
    live page, or to the review page if a consultation record already
    exists (the session was stopped but the entry outlived it)."""
    entry = await frontdesk.get_entry(entry_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"error": "no such queue entry today"})
    if entry["status"] != "in_consultation":
        return JSONResponse(status_code=409, content={"error": "entry is not in consultation"})
    cid = await consultations.latest_for_patient_today(entry["patient_id"])
    await audit.log(user["id"], "queue.resumed", "queue_entry", entry_id,
                    {"consultation_id": cid})
    if cid is not None:
        return JSONResponse(content={"mode": "review", "consultation_id": cid})
    return JSONResponse(content={"mode": "live", "entry_id": entry_id})


class CloseBody(BaseModel):
    outcome: str = "cancelled"  # cancelled | done


@app.post("/api/queue/{entry_id}/close")
async def queue_close(
    entry_id: int, body: CloseBody, user: dict = Depends(api_user())
) -> JSONResponse:
    """Administrative closure (doctor or receptionist): no recording
    happened — distinct audit event so it can't be mistaken for a
    completed consultation."""
    if body.outcome not in ("done", "cancelled"):
        return JSONResponse(status_code=400, content={"error": "outcome must be done or cancelled"})
    closed = await frontdesk.close_entry(entry_id, body.outcome)
    if closed is None:
        return JSONResponse(status_code=409, content={"error": "entry is not open"})
    await audit.log(user["id"], "queue.cancelled", "queue_entry", entry_id,
                    {"outcome": body.outcome, "from_status": closed["from_status"],
                     "patient_id": closed["patient_id"]})
    return JSONResponse(content={"ok": True, "outcome": body.outcome})


@app.get("/live")
def live_page(user: dict = Depends(page_user(*CLINICAL_ROLES))) -> FileResponse:
    """The live consultation page: mic capture + streaming transcript."""
    return FileResponse(STATIC_DIR / "live.html")


@app.get("/api/consultations")
async def consultation_list(user: dict = Depends(api_user())) -> list[dict]:
    """Worklist: statuses only, no clinical content — all roles may see it."""
    return await consultations.list_consultations()


@app.get("/review/{cid}")
def review_page(cid: int, user: dict = Depends(page_user(*CLINICAL_ROLES))) -> FileResponse:
    """Note review screen: editable draft note + diarised transcript."""
    return FileResponse(STATIC_DIR / "review.html")


async def _not_editable(cid: int) -> JSONResponse | None:
    """Approved consultations are read-only — the signed record is final."""
    consultation = await consultations.get_consultation(cid)
    if consultation and consultation["status"] == "approved":
        return JSONResponse(status_code=409, content={"error": "consultation is approved and read-only"})
    return None


@app.get("/api/consultations/{cid}")
async def consultation_state(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    consultation = await consultations.get_consultation(cid)
    if consultation is None:
        return JSONResponse(status_code=404, content={"error": "not found"})
    turns = await consultations.get_turns(cid)
    note = await consultations.latest_note(cid)
    plain = note_as_plain_text(note["content"]) if note else None
    await audit.log(user["id"], "consultation.viewed", "consultation", cid)
    return JSONResponse(
        content={**consultation, "turns": turns, "note": note, "plain_text": plain}
    )


class ApproveBody(BaseModel):
    text: str


@app.post("/api/consultations/{cid}/approve")
async def approve(
    cid: int, body: ApproveBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    consultation = await consultations.get_consultation(cid)
    if consultation and consultation["urgent_actions"] and not consultation["urgent_ack_at"]:
        return JSONResponse(
            status_code=409,
            content={"error": "Unresolved urgent actions must be acknowledged first."},
        )
    await consultations.approve_note(cid, body.text)
    await audit.log(user["id"], "note.approved", "consultation", cid)
    return JSONResponse(content={"ok": True})


@app.post("/api/consultations/{cid}/acknowledge-urgent")
async def acknowledge_urgent(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> dict:
    acked_at = await consultations.acknowledge_urgent(cid)
    await audit.log(user["id"], "urgent.acknowledged", "consultation", cid,
                    {"acknowledged_at": acked_at})
    return {"ok": True, "acknowledged_at": acked_at}


@app.post("/api/consultations/{cid}/regenerate")
async def regenerate(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Re-draft the note from the (possibly corrected) transcript."""
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    await consultations.set_status(cid, "processing")
    await regenerate_note(cid)
    await consultations.set_status(cid, "awaiting_review")
    await audit.log(user["id"], "note.regenerated", "consultation", cid)
    return JSONResponse(content={"ok": True})


@app.post("/api/consultations/{cid}/swap-roles")
async def swap_roles(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Override for the first-speaker-is-Doctor heuristic."""
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    await consultations.swap_roles(cid)
    await audit.log(user["id"], "roles.swapped", "consultation", cid)
    return JSONResponse(content={"ok": True})


class TurnBody(BaseModel):
    text: str


@app.patch("/api/consultations/{cid}/turns/{idx}")
async def edit_turn(
    cid: int, idx: int, body: TurnBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    await consultations.update_turn_text(cid, idx, body.text)
    await audit.log(user["id"], "turn.edited", "consultation", cid, {"turn": idx})
    return JSONResponse(content={"ok": True})


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket) -> None:
    """Receive 16 kHz 16-bit mono PCM frames; stream transcript JSON back.

    Client → server: binary audio frames, or the text message "stop".
    Server → client: {"type": "final"|"partial"|"done", ...}
    """
    # WebSocket auth: same session cookie, clinical roles only.
    user = await auth.get_user(auth.verify_session(websocket.cookies.get(COOKIE_NAME)) or 0)
    if user is None or user["role"] not in CLINICAL_ROLES:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    session = LiveSession(websocket.app.state.transcriber)
    engine: CDSEngine = websocket.app.state.cds_engine
    patient_id: int | None = None
    queue_entry_id: int | None = None
    logger.info("Live session started by %s", user["username"])

    rag: RAGService = websocket.app.state.rag

    transcript_parts: list[str] = []  # confirmed text, the CDS engine's input
    assessment: dict | None = None
    cds_task: asyncio.Task | None = None
    cds_sent_len = 0
    cds_failures = 0
    gl_task: asyncio.Task | None = None
    gl_conditions: tuple = ()  # conditions the current guideline panel is for
    urgent_first_fired: dict[str, float] = {}  # action text → audio time (s)

    async def maybe_run_cds() -> None:
        """Launch/collect the CDS side task without ever blocking transcription."""
        nonlocal cds_task, assessment, cds_sent_len, cds_failures
        if cds_task is not None and cds_task.done():
            try:
                assessment = cds_task.result()
                cds_failures = 0
                for action in assessment.get("urgent_actions", []):
                    urgent_first_fired.setdefault(
                        action["action"], round(session.audio_seconds, 1)
                    )
                await websocket.send_json({"type": "cds", "assessment": assessment})
            except Exception as exc:  # noqa: BLE001 - degrade, don't crash the stream
                cds_failures += 1
                logger.warning("CDS pass failed (%d): %s", cds_failures, exc)
                if cds_failures >= CDS_MAX_FAILURES:
                    await websocket.send_json(
                        {"type": "cds_unavailable",
                         "detail": "CDS engine unreachable; transcription continues."}
                    )
            cds_task = None
        transcript = "\n".join(transcript_parts)
        if (
            cds_task is None
            and cds_failures < CDS_MAX_FAILURES
            and len(transcript) - cds_sent_len >= CDS_MIN_NEW_CHARS
        ):
            cds_sent_len = len(transcript)
            cds_task = asyncio.create_task(engine.update(transcript, assessment))

    async def maybe_run_guidelines() -> None:
        """Refresh the guideline panel when the leading differentials change.

        Queries are built from the CDS layer's conditions, not raw transcript
        text, and the summary is grounded in retrieved passages only.
        """
        nonlocal gl_task, gl_conditions
        if gl_task is not None and gl_task.done():
            try:
                answer = gl_task.result()
                await websocket.send_json({"type": "guidelines", **answer})
            except Exception as exc:  # noqa: BLE001 - the panel is optional
                logger.warning("Guideline lookup failed: %s", exc)
            gl_task = None
        if assessment is None or gl_task is not None:
            return
        conditions = tuple(
            d["condition"] for d in assessment.get("differentials", [])[:2]
        )
        if conditions and conditions != gl_conditions:
            gl_conditions = conditions
            gl_task = asyncio.create_task(rag.answer_for_conditions(list(conditions)))

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=2.0)
            except asyncio.TimeoutError:
                message = None

            if message is not None:
                if message["type"] == "websocket.disconnect":
                    return
                if message.get("bytes"):
                    session.append_pcm16(message["bytes"])
                elif message.get("text") == "stop":
                    break
                elif (text := message.get("text", "")).startswith("{"):
                    config = json.loads(text)  # {"patient_id": .., "queue_entry_id": ..}
                    patient_id = config.get("patient_id")
                    queue_entry_id = config.get("queue_entry_id")

            if session.new_audio_seconds >= PROCESS_INTERVAL_S:
                committed, partial = await session.process()
                for seg in committed:
                    transcript_parts.append(seg.text)
                    await websocket.send_json(
                        {"type": "final", "text": seg.text, "start": seg.start, "end": seg.end}
                    )
                await websocket.send_json({"type": "partial", "text": partial})

            await maybe_run_cds()
            await maybe_run_guidelines()

        # Client pressed stop: transcribe the tail end and finish cleanly.
        for seg in await session.flush():
            await websocket.send_json(
                {"type": "final", "text": seg.text, "start": seg.start, "end": seg.end}
            )

        # Kick off the finalisation pipeline (Phase 2). The Stop button IS
        # the trigger — no separate generate step.
        cid = await consultations.create_consultation(patient_id, user["id"])
        if queue_entry_id is not None:
            await frontdesk.finish_entry(queue_entry_id)
        await audit.log(user["id"], "consultation.created", "consultation", cid,
                        {"patient_id": patient_id})
        wav_path = str(RECORDINGS_DIR / f"consultation_{cid}.wav")
        duration = session.save_recording(wav_path)
        logger.info("Consultation %d: %.1fs of audio saved", cid, duration)

        # Persist urgent actions still unresolved at session end (the CDS
        # engine clears an action once the transcript shows it arranged, so
        # anything remaining was never seen to be actioned). Shown as an
        # acknowledge-gated banner on review — never merged into the note.
        if assessment and assessment.get("urgent_actions"):
            unresolved = [
                {
                    "action": a["action"],
                    "reason": a["reason"],
                    "first_fired_s": urgent_first_fired.get(a["action"]),
                }
                for a in assessment["urgent_actions"]
            ]
            await consultations.save_urgent_actions(cid, unresolved)
            logger.info(
                "Consultation %d: %d unresolved urgent action(s) recorded",
                cid, len(unresolved),
            )
        task = asyncio.create_task(finalize_consultation(cid, wav_path))
        websocket.app.state.finalize_tasks.add(task)
        task.add_done_callback(websocket.app.state.finalize_tasks.discard)

        await websocket.send_json({"type": "done", "consultation_id": cid})
        await websocket.close()
    except WebSocketDisconnect:
        pass
    finally:
        if cds_task is not None:
            cds_task.cancel()
        if gl_task is not None:
            gl_task.cancel()
        logger.info("Live session ended")


@app.get("/")
def root() -> dict:
    return {
        "app": "Consultation AI",
        "status": "hello, world",
        "phase": 0,
        "warning": "Prototype for research/education only. Not for real patients.",
    }


@app.get("/health")
def health() -> JSONResponse:
    """Readiness check: is the app up AND can it reach the database?"""
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                pg_version = cur.fetchone()[0].split(" on ")[0]
                cur.execute(
                    "SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'"
                )
                pgvector_available = cur.fetchone()[0] > 0
    except psycopg.OperationalError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": f"unreachable: {exc}"},
        )
    return JSONResponse(
        content={
            "status": "ok",
            "database": pg_version,
            "pgvector_available": pgvector_available,
        }
    )
