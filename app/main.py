"""Consultation AI — application entry point.

Phase 0: a minimal FastAPI app proving the environment works.
Later phases add the audio gateway, live transcription, and the
patient/consultation views described in PROJECT_PLAN.md.
"""

import asyncio
import contextlib
import functools
import json
import logging
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from fastapi import Depends
from pydantic import BaseModel

from app import (audit, auth, consultations, frontdesk, letters, monitor, ratelimit,
                 retention, schema, speech, system_utterances)
from app.auth import COOKIE_NAME, CLINICAL_ROLES, api_user, page_user
from app.cds import CDSEngine
from app.finalize import finalize_consultation, regenerate_note
from app import transcript_quality
from app.live import PROCESS_INTERVAL_S, LiveSession, bytes_to_ms
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
    # One entry point for the whole schema, in one order (app/schema.py).
    # Applied, never gated on: the app is what applies the schema, so a
    # refuse-to-start check would turn a self-healing restart into an outage.
    schema.ensure_all()
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    app.state.transcriber = await asyncio.to_thread(LiveTranscriber)
    # Speech is constructed unconditionally; the Piper voice loads lazily
    # on first synthesis, so a machine without piper-tts starts normally
    # and simply cannot speak.
    app.state.speech = speech.SpeechService()
    app.state.cds_engine = CDSEngine()
    app.state.rag = RAGService()
    # Finalisation is serialised through a single-consumer queue: exactly
    # one pipeline touches the GPU at a time (finalize.py's VRAM
    # sequencing assumes sole ownership of the 24 GB). Consultations wait
    # as status 'queued'. Crash recovery: anything left 'queued' with
    # audio on disk is re-enqueued at startup.
    app.state.finalize_queue = asyncio.Queue()
    app.state.finalize_worker = asyncio.create_task(finalize_worker(app))
    for cid, wav_path in await consultations.queued_finalisations():
        app.state.finalize_queue.put_nowait((cid, wav_path))
        logger.info("Re-enqueued consultation %d for finalisation", cid)
    # Live-session registry (connection resilience): sessions survive
    # their WebSocket, keyed by client session id. Also enforces one
    # live consultation at a time at the WS layer (the queue's
    # one-active-entry guard is UI-level; this is the wall).
    app.state.live_sessions = {}
    app.state.retention_task = asyncio.create_task(retention.retention_loop())
    yield
    app.state.retention_task.cancel()
    app.state.finalize_worker.cancel()

async def finalize_worker(app: FastAPI) -> None:
    """Single consumer for the finalisation queue. Never dies: a failed
    pipeline marks its own consultation failed (finalize_consultation
    catches internally); anything unexpected is logged and skipped."""
    while True:
        cid, wav_path = await app.state.finalize_queue.get()
        try:
            await finalize_consultation(cid, wav_path)
        except Exception:  # noqa: BLE001 - the worker must survive any job
            logger.exception("Finalisation worker error for consultation %d", cid)
        finally:
            app.state.finalize_queue.task_done()


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


@app.middleware("http")
async def count_errors(request, call_next):
    """Feed the pulse's errors_last_hour: unhandled exceptions and 5xx
    responses only — 4xx refusals (RBAC probes, guards) are not errors."""
    try:
        response = await call_next(request)
    except Exception:
        monitor.record_error()
        raise
    if response.status_code >= 500:
        monitor.record_error()
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
async def register(body: RegisterBody, request: Request) -> JSONResponse:
    ip = ratelimit.client_ip(request)
    retry = ratelimit.register_limiter.retry_after(ip)
    if retry is not None:
        return JSONResponse(
            status_code=429, headers={"Retry-After": str(retry)},
            content={"error": f"too many registration attempts from your address"
                              f" — try again in {retry} seconds"})
    if body.role not in ("doctor", "receptionist"):
        return JSONResponse(status_code=400, content={"error": "role must be doctor or receptionist"})
    if len(body.password) < 8:
        return JSONResponse(status_code=400, content={"error": "password too short (min 8)"})
    try:
        user = await auth.create_user(
            body.username, body.password, body.display_name, body.role, pending=True
        )
    except Exception:
        return JSONResponse(status_code=409, content={"error": "username already taken"})
    if user["pending_approval"]:
        # Approve-to-activate (public exposure): no session until the
        # administrator activates the account in the Users view.
        await audit.log(
            user["id"], "user.registered_pending", "user", user["id"],
            {"role": user["role"], "ip": ip},
        )
        return JSONResponse(content={
            "ok": True, "pending": True, "user": user,
            "message": "Account created — awaiting the administrator's approval."
        })
    # First-account bootstrap only: active immediately, session as before.
    await audit.log(
        user["id"], "user.registered", "user", user["id"],
        {"role": user["role"], "ip": ip},
    )
    response = JSONResponse(content={"ok": True, "pending": False, "user": user})
    response.set_cookie(COOKIE_NAME, auth.sign_session(user["id"]), httponly=True, samesite="lax")
    return response


@app.post("/api/login")
async def login(body: LoginBody, request: Request) -> JSONResponse:
    ip = ratelimit.client_ip(request)
    retry = ratelimit.login_limiter.retry_after(ip)
    if retry is not None:
        return JSONResponse(
            status_code=429, headers={"Retry-After": str(retry)},
            content={"error": f"too many login attempts from your address"
                              f" — try again in {retry} seconds"})
    user, reason = await auth.authenticate(body.username, body.password)
    if user is None:
        # Failures are audited with their source for forensics; the
        # username is whatever the caller typed, truncated, never echoed.
        await audit.log(
            None, "user.login_failed", None, None,
            {"username": body.username[:200], "ip": ip, "reason": reason},
        )
        if reason == "awaiting_approval":
            return JSONResponse(status_code=403, content={
                "error": "account awaiting administrator approval — "
                         "you will be able to sign in once it is activated"})
        return JSONResponse(status_code=401, content={"error": "invalid credentials"})
    await audit.log(user["id"], "user.login", "user", user["id"], {"ip": ip})
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


@app.get("/api/speech/{utterance_id}.wav")
async def speech_audio(utterance_id: str, user: dict = Depends(api_user(*CLINICAL_ROLES))):
    """The audio for one prepared utterance (PHASE_7A_SPEC.md §2.2 step 2).

    Bound to the doctor who requested it: an utterance is not fetchable by
    anyone who guesses an id. Unknown and foreign ids answer the same 404,
    so the endpoint does not confirm that an id exists.
    """
    utterance = app.state.speech.get(utterance_id)
    if utterance is None or (
        utterance.user_id is not None and utterance.user_id != user["id"]
    ):
        return JSONResponse(status_code=404, content={"error": "unknown utterance"})
    return Response(content=utterance.wav, media_type="audio/wav",
                    headers={"Cache-Control": "no-store"})


class SoundCheckResultBody(BaseModel):
    noise_floor_rms: float
    peak_rms: float
    mean_rms: float | None = None
    answer: str | None = None          # 'yes' | 'no' | anything else = skipped
    device_label: str | None = None    # output device, when the browser exposes it


def _user_is_recording(user_id: int) -> bool:
    """True when this doctor has a live session attached right now.

    The sound check is refused during recording (spec §10.3): a test
    phrase inside a live consultation would be a system utterance and
    would have to go through the whole exclusion machinery for no clinical
    benefit. The UI disables the button; this is the server saying the
    same thing, because a disabled button is a courtesy and a refusal is
    a rule.
    """
    sessions = getattr(app.state, "live_sessions", None) or {}
    return any(entry.get("attached") and entry["user"]["id"] == user_id
               for entry in sessions.values())


@app.post("/api/speech/sound-check")
async def sound_check_start(user: dict = Depends(api_user(*CLINICAL_ROLES))) -> JSONResponse:
    """Prepare the sound-check utterance (spec Part 10).

    Deliberately NOT over the `/ws/transcribe` speak protocol: that
    protocol belongs to a live consultation, and this runs before one
    starts. It uses the same audio OUTPUT path a spoken question uses —
    synthesis, cache, and `/api/speech/{id}.wav`.
    """
    if _user_is_recording(user["id"]):
        return JSONResponse(status_code=409, content={
            "error": "a sound check cannot run during a consultation — "
                     "it would be a system utterance in the transcript"})
    try:
        utterance = await asyncio.to_thread(
            functools.partial(app.state.speech.prepare,
                              {"kind": "phrase", "id": "sound_check"},
                              None, user_id=user["id"]))
    except (speech.SpeechUnavailable, speech.SpeechFailed) as exc:
        await audit.log(user["id"], "speech.failed", None, None,
                        {"reason": str(exc), "via": "sound_check"})
        return JSONResponse(status_code=503, content={"error": str(exc)})
    return JSONResponse(content={
        "utterance_id": utterance.utterance_id,
        "duration_ms": utterance.duration_ms,
        "url": f"/api/speech/{utterance.utterance_id}.wav",
        "text": utterance.text})


@app.post("/api/speech/sound-check/result")
async def sound_check_result(
    body: SoundCheckResultBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Classify the loopback measurement against the doctor's answer.

    Classification is server-side and pure (`speech.classify_sound_check`)
    so the four result classes are testable without a browser, a speaker
    or a room. The raw RMS numbers are audited exactly as measured —
    `scripts/calibrate_barge_in.py` (build order item 5) is meant to read
    these rather than re-measure from scratch, since the loopback level is
    precisely the input its envelope-proportional threshold needs.
    """
    verdict = speech.classify_sound_check(
        noise_floor_rms=body.noise_floor_rms, peak_rms=body.peak_rms,
        mean_rms=body.mean_rms, answer=body.answer)
    await audit.log(user["id"], "speech.sound_check", None, None,
                    {"result": verdict["result"], "answer": verdict["answer"],
                     "discrepancy": verdict["discrepancy"],
                     "device_label": body.device_label,
                     **verdict["level"]})
    logger.info("Sound check by %s: %s (ratio %.2f, answer %s)",
                user["username"], verdict["result"],
                verdict["level"]["ratio"], verdict["answer"])
    return JSONResponse(content=verdict)


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/change-password")
async def change_password(
    body: ChangePasswordBody, user: dict = Depends(api_user())
) -> JSONResponse:
    """Self-service, any logged-in role; the current password gates it."""
    if len(body.new_password) < 8:
        return JSONResponse(status_code=400, content={"error": "password too short (min 8)"})
    if not await auth.change_password(user["id"], body.current_password, body.new_password):
        return JSONResponse(status_code=403, content={"error": "current password is incorrect"})
    await audit.log(user["id"], "user.password_changed", "user", user["id"])
    return JSONResponse(content={"ok": True})


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


# -------------------------------------------------- admin: users, void, purge

@app.get("/users")
def users_page(user: dict = Depends(page_user("admin"))) -> FileResponse:
    return FileResponse(STATIC_DIR / "users.html")


@app.get("/api/admin/users")
async def admin_users(user: dict = Depends(api_user("admin"))) -> list[dict]:
    return await auth.list_users()


@app.post("/api/admin/users/{uid}/deactivate")
async def admin_deactivate_user(
    uid: int, user: dict = Depends(api_user("admin"))
) -> JSONResponse:
    """Governance, not deletion: the account can no longer log in and its
    sessions stop resolving, but the row (and every audit/consultation
    reference to it) is preserved."""
    if uid == user["id"]:
        return JSONResponse(status_code=409, content={"error": "you cannot deactivate your own account"})
    if not await auth.set_user_active(uid, False):
        return JSONResponse(
            status_code=409,
            content={"error": "cannot deactivate: user not found or last active admin"},
        )
    await audit.log(user["id"], "user.deactivated", "user", uid)
    return JSONResponse(content={"ok": True})


@app.post("/api/admin/users/{uid}/reactivate")
async def admin_reactivate_user(
    uid: int, user: dict = Depends(api_user("admin"))
) -> JSONResponse:
    was_pending = await auth.is_pending_approval(uid)
    if not await auth.set_user_active(uid, True):
        return JSONResponse(status_code=404, content={"error": "no such user"})
    # First approval of a public registration vs reactivating a
    # governance-deactivated account — different events for the record.
    action = "user.activated" if was_pending else "user.reactivated"
    await audit.log(user["id"], action, "user", uid)
    return JSONResponse(content={"ok": True})


@app.get("/api/admin/consultations")
async def admin_consultations(user: dict = Depends(api_user("admin"))) -> list[dict]:
    """All consultations, any status or doctor, voided included — plus
    per-recording disk usage for the retention view."""
    rows = await consultations.list_consultations(include_voided=True)
    for row in rows:
        size = None
        if row["audio_path"]:
            with contextlib.suppress(OSError):
                size = os.path.getsize(row["audio_path"])
        row["audio_bytes"] = size
        del row["audio_path"]  # server filesystem detail, size is the point
    return rows


class KeepBody(BaseModel):
    value: bool


@app.post("/api/admin/consultations/{cid}/keep-for-research")
async def admin_keep_for_research(
    cid: int, body: KeepBody, user: dict = Depends(api_user("admin"))
) -> JSONResponse:
    """Exempts (or re-includes) a recording from the retention sweep.
    Audio-governance flag only — clinical content is unaffected."""
    if not await consultations.set_keep_for_research(cid, body.value):
        return JSONResponse(status_code=404, content={"error": "not found"})
    await audit.log(user["id"], "consultation.keep_for_research",
                    "consultation", cid, {"value": body.value})
    return JSONResponse(content={"ok": True})


class VoidBody(BaseModel):
    reason: str
    # Defaults to test_data, the common case. clinical_safety marks a void
    # that must never be reversed over HTTP (see the unvoid guard below).
    reason_class: str = consultations.VOID_CLASS_TEST_DATA


class UnvoidBody(BaseModel):
    # Unvoid gained its own mandatory typed reason on 2026-07-25: #70 was
    # unvoided twice because nothing made the person state why, or read
    # why it had been voided. See HANDOVER docket 5.
    reason: str


@app.post("/api/admin/consultations/{cid}/void")
async def admin_void_consultation(
    cid: int, body: VoidBody, user: dict = Depends(api_user("admin"))
) -> JSONResponse:
    """Error correction on any status, including approved. The reason is
    mandatory; content stays in the database until an explicit purge."""
    reason = body.reason.strip()
    if not reason:
        return JSONResponse(status_code=400, content={"error": "a reason is required to void"})
    reason_class = body.reason_class.strip()
    if reason_class not in consultations.VOID_CLASSES:
        return JSONResponse(status_code=400, content={
            "error": "reason_class must be one of "
                     + ", ".join(consultations.VOID_CLASSES)})
    voided = await consultations.void_consultation(cid, user["id"], reason,
                                                  reason_class)
    if voided is None:
        return JSONResponse(status_code=409, content={"error": "not found or already voided"})
    # Free any open queue entry for this patient today so a voided live
    # session can't hold the one-active-consultation guard.
    if voided["patient_id"]:
        for entry in await frontdesk.today_queue():
            if (entry["patient_id"] == voided["patient_id"]
                    and entry["status"] in ("waiting", "in_consultation")):
                await frontdesk.close_entry(entry["entry_id"], "cancelled")
                await audit.log(user["id"], "queue.cancelled", "queue_entry",
                                entry["entry_id"], {"via": "consultation.voided"})
    await audit.log(user["id"], "consultation.voided", "consultation", cid,
                    {"reason": reason, "reason_class": reason_class,
                     "from_status": voided["from_status"]})
    return JSONResponse(content={"ok": True})


@app.post("/api/admin/consultations/{cid}/unvoid")
async def admin_unvoid_consultation(
    cid: int, body: UnvoidBody, user: dict = Depends(api_user("admin"))
) -> JSONResponse:
    """Reverse a mistaken void; the consultation returns to working views
    in its prior state. The audit trail keeps both the void and this.

    A `clinical_safety` void is refused here unconditionally — there is no
    override parameter, so no HTTP caller can reach the reversal at all.
    Break-glass reversal is `scripts/manage_consultations.py`, server
    shell only. The refusal is audited: `consultation.unvoid_refused` is
    the event that shows whether this guard earned its place.
    """
    reason = body.reason.strip()
    if not reason:
        return JSONResponse(status_code=400, content={
            "error": "a reason is required to unvoid"})

    state = await consultations.void_state(cid)
    if state is not None and state["voided"] and \
            state["reason_class"] == consultations.VOID_CLASS_CLINICAL_SAFETY:
        await audit.log(user["id"], "consultation.unvoid_refused",
                        "consultation", cid,
                        {"reason_class": state["reason_class"],
                         "attempted_reason": reason})
        return JSONResponse(status_code=409, content={
            "error": "this consultation was voided as clinical_safety and "
                     "cannot be unvoided here. Reversal is break-glass only: "
                     "scripts/manage_consultations.py on the server shell.",
            "reason_class": state["reason_class"]})

    reverted = await consultations.unvoid_consultation(cid)
    if reverted is None:
        return JSONResponse(status_code=409, content={"error": "not found or not voided"})
    await audit.log(user["id"], "consultation.unvoided", "consultation", cid,
                    {"reverted_reason": reverted["reverted_reason"],
                     "reverted_class": reverted["reverted_class"],
                     "reason": reason,
                     "status": reverted["status"]})
    return JSONResponse(content={"ok": True})


@app.post("/api/admin/purge-voided")
async def admin_purge_voided(user: dict = Depends(api_user("admin"))) -> dict:
    """The second deliberate step after voiding: hard-delete voided
    consultations and their orphaned synthetic patients. UI double-confirms.

    Clinical-safety voids are skipped and reported — see purge_voided."""
    purged = await consultations.purge_voided()
    removed_files = 0
    for path in purged["audio_paths"]:
        with contextlib.suppress(OSError):
            os.unlink(path)
            removed_files += 1
    await audit.log(user["id"], "data.purged", "consultation", None,
                    {"consultations": purged["consultations"],
                     "consultation_ids": purged["consultation_ids"],
                     "patients": purged["patients"],
                     "audio_files": removed_files,
                     "protected": purged["protected"],
                     "protected_ids": purged["protected_ids"]})
    return {"ok": True, "consultations": purged["consultations"],
            "patients": purged["patients"], "audio_files": removed_files,
            "protected": purged["protected"],
            "protected_ids": purged["protected_ids"]}


@app.get("/api/admin/purge-preview")
async def admin_purge_preview(user: dict = Depends(api_user("admin"))) -> dict:
    """Counts for the purge confirmation, so it can name what it will and
    will not destroy rather than asking for a blind yes."""
    return await consultations.purge_preview()


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
        await audit.log(user["id"], "live.slot_rejected", None, None,
                        {"via": "walk_in"})
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
            await audit.log(user["id"], "live.slot_rejected", "queue_entry",
                            entry_id, {"via": "queue_start"})
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
    """Worklist: statuses only, no clinical content — all roles may see it.
    Strict scoping (owner decision 2026-07-24): a doctor sees only their
    own consultations (plus unowned legacy rows); admin and receptionist
    behaviour unchanged (receptionist rows are status-only anyway)."""
    doctor_id = user["id"] if user["role"] == "doctor" else None
    rows = await consultations.list_consultations(doctor_id=doctor_id)
    for row in rows:  # retention/audio fields are the admin view's concern
        del row["audio_path"], row["keep_for_research"], row["audio_deleted_at"]
    return rows


@app.get("/review/{cid}")
def review_page(cid: int, user: dict = Depends(page_user(*CLINICAL_ROLES))) -> FileResponse:
    """Note review screen: editable draft note + diarised transcript."""
    return FileResponse(STATIC_DIR / "review.html")


def _foreign_consultation(consultation: dict, user: dict) -> JSONResponse | None:
    """Strict own-consultations scoping (owner decision 2026-07-24, over
    continuity-of-care sharing — revisit only as an owner decision): a
    doctor may open or act on only their own consultations. Unowned rows
    (doctor_id IS NULL: legacy/test data) stay open to clinical roles —
    real consultations always record their doctor. Admin sees all. 403
    matches the receptionist-probe pattern; voided stays 410."""
    if (user["role"] == "doctor" and consultation["doctor_id"] is not None
            and consultation["doctor_id"] != user["id"]):
        return JSONResponse(status_code=403,
                            content={"error": "not your consultation"})
    return None


async def _scoped(cid: int, user: dict) -> JSONResponse | None:
    """404 for a missing consultation, 403 for another doctor's."""
    consultation = await consultations.get_consultation(cid)
    if consultation is None:
        return JSONResponse(status_code=404, content={"error": "not found"})
    return _foreign_consultation(consultation, user)


async def _not_editable(cid: int) -> JSONResponse | None:
    """Approved consultations are read-only — the signed record is final.
    Voided ones are frozen too: content is preserved for audit, not work."""
    consultation = await consultations.get_consultation(cid)
    if consultation and consultation["voided_at"]:
        return JSONResponse(status_code=409, content={"error": "consultation is voided"})
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
    if consultation["voided_at"] and user["role"] != "admin":
        # Voided consultations exist only in the admin view.
        return JSONResponse(status_code=410, content={"error": "consultation voided"})
    if (blocked := _foreign_consultation(consultation, user)) is not None:
        return blocked
    turns = await consultations.get_turns(cid)
    note = await consultations.latest_note(cid)
    plain = note_as_plain_text(note["content"]) if note else None
    letter_rows = await letters.list_letters(cid)
    # Phase 7a: what the machine said, for the review page's grey channel.
    # A SEPARATE key from `turns`, matching the separate table — the note
    # and its citations read `turns` and can never reach these.
    spoken = await system_utterances.for_consultation(cid)
    # Whether the drafted note predates a role change. Queried from the same
    # function the approve guard uses, so the banner and the button cannot
    # disagree about it.
    labels = await consultations.labels_state(cid)
    await audit.log(user["id"], "consultation.viewed", "consultation", cid)
    return JSONResponse(
        content={**consultation, "turns": turns, "note": note, "plain_text": plain,
                 "letters": letter_rows, "system_utterances": spoken,
                 "labels": labels}
    )


class ApproveBody(BaseModel):
    text: str


@app.post("/api/consultations/{cid}/approve")
async def approve(
    cid: int, body: ApproveBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    consultation = await consultations.get_consultation(cid)
    if consultation and consultation["urgent_actions"] and not consultation["urgent_ack_at"]:
        return JSONResponse(
            status_code=409,
            content={"error": "Unresolved urgent actions must be acknowledged first."},
        )
    # Diarisation found one voice, so the Doctor/Patient labels are a default
    # rather than a measurement (2026-07-28). Blocked server-side as well as
    # in the UI, the same as the urgency banner: a disabled button can be
    # re-enabled from the console, a refusal cannot.
    if (consultation and consultation["single_voice_detected"]
            and not consultation["single_voice_ack_at"]):
        return JSONResponse(
            status_code=409,
            content={"error": "Only one voice was detected in the audio, so the"
                     " speaker roles could not be determined from it. Check the"
                     " transcript's Doctor/Patient labels and acknowledge first."},
        )
    # A role change after the note was drafted leaves the note's claims
    # citing turns that now say something different. Acknowledge or
    # regenerate — never a silent regeneration, the note is the doctor's.
    labels = await consultations.labels_state(cid)
    if labels["stale"] and not labels["acknowledged"]:
        return JSONResponse(
            status_code=409,
            content={"error": "The speaker labels changed after this note was"
                     " drafted. Regenerate the note, or acknowledge that you have"
                     " checked it against the corrected labels."},
        )
    # Transcript-quality gate refusal: there is no draft to approve, and
    # there must not be one — the transcript is not trustworthy. Guarded
    # on status as well as on the missing note, so a later regenerate
    # cannot open a path to approving a refused transcript.
    if consultation and consultation["status"] == transcript_quality.STATUS_UNRELIABLE:
        return JSONResponse(
            status_code=409,
            content={"error": "This transcript was refused by the quality gate and"
                     " cannot be approved. No note was drafted from it."},
        )
    note = await consultations.latest_note(cid)
    if note is None or note["content"].get("refusal"):
        return JSONResponse(
            status_code=409,
            content={"error": "No approvable draft: the transcript had insufficient"
                     " clinical content. Correct the transcript and regenerate."},
        )
    await consultations.approve_note(cid, body.text)
    await audit.log(user["id"], "note.approved", "consultation", cid)
    # Retention step 1 (plan §8): the signed consultation's WAV becomes a
    # lossless FLAC. Best-effort — approval never fails on compression.
    await retention.compress_on_approval(cid, consultation["audio_path"])
    return JSONResponse(content={"ok": True})


@app.post("/api/consultations/{cid}/acknowledge-urgent")
async def acknowledge_urgent(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    acked_at = await consultations.acknowledge_urgent(cid)
    await audit.log(user["id"], "urgent.acknowledged", "consultation", cid,
                    {"acknowledged_at": acked_at})
    return JSONResponse(content={"ok": True, "acknowledged_at": acked_at})


class SpeakersBody(BaseModel):
    count: int


@app.post("/api/consultations/{cid}/declared-speakers")
async def declare_speakers(
    cid: int, body: SpeakersBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """The doctor's answer to "how many people spoke?", asked at Stop.

    Deliberately NOT gated on `_not_editable`: it is asked the moment the
    consultation is completed, and refusing it because finalisation has moved on
    would be a tap that does nothing. Instead the response says whether the
    answer reached diarisation in time, so the caller can tell the doctor the
    truth either way (standing rule: the tap always does something, and what it
    did is reported at the control).
    """
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    try:
        result = await consultations.declare_speakers(cid, body.count)
    except ValueError as err:
        return JSONResponse(status_code=400, content={"error": str(err)})
    await audit.log(user["id"], "speakers.declared", "consultation", cid,
                    {"count": body.count, "applied": result["applied"],
                     "already_used": result["used"]})
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/consultations/{cid}/acknowledge-single-voice")
async def acknowledge_single_voice(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """The doctor confirms they have checked the speaker labels on a
    consultation where only one voice was detected."""
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    acked_at = await consultations.acknowledge_single_voice(cid)
    await audit.log(user["id"], "single_voice.acknowledged", "consultation", cid,
                    {"acknowledged_at": acked_at})
    return JSONResponse(content={"ok": True, "acknowledged_at": acked_at})


@app.post("/api/consultations/{cid}/acknowledge-labels")
async def acknowledge_labels(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """The doctor confirms they have re-read a note drafted against the
    speaker labels as they were BEFORE a role correction."""
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    acked_at = await consultations.acknowledge_labels(cid)
    await audit.log(user["id"], "labels.acknowledged", "consultation", cid,
                    {"acknowledged_at": acked_at})
    return JSONResponse(content={"ok": True, "acknowledged_at": acked_at})


@app.post("/api/consultations/{cid}/regenerate")
async def regenerate(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Re-draft the note from the (possibly corrected) transcript."""
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
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
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    await consultations.swap_roles(cid)
    await audit.log(user["id"], "roles.swapped", "consultation", cid)
    return JSONResponse(content={"ok": True})


# ---------------------------------------------------------- referral letters

async def _letter_gate(cid: int, user: dict):
    """Letters exist ONLY on approved, non-voided consultations (a letter
    must not cite content the doctor hasn't signed), scoped like every
    other clinical object. Returns (error_response, consultation, note)."""
    consultation = await consultations.get_consultation(cid)
    if consultation is None:
        return JSONResponse(status_code=404, content={"error": "not found"}), None, None
    if consultation["voided_at"]:
        return JSONResponse(status_code=409, content={"error": "consultation is voided"}), None, None
    if (blocked := _foreign_consultation(consultation, user)) is not None:
        return blocked, None, None
    if consultation["status"] != "approved":
        return JSONResponse(
            status_code=409,
            content={"error": "letters can only be created for an approved consultation"},
        ), None, None
    note = await consultations.latest_note(cid)
    if note is None or not note.get("approved_text"):
        return JSONResponse(
            status_code=409, content={"error": "no approved note text found"}
        ), None, None
    return None, consultation, note


@app.post("/api/consultations/{cid}/letters/suggest")
async def letters_suggest(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Model-inferred indicated referrals, from the approved note only.
    Cached per note version; an empty list is a valid and common answer."""
    blocked, consultation, note = await _letter_gate(cid, user)
    if blocked is not None:
        return blocked
    suggestions = await letters.cached_suggestions(cid, note["version"])
    if suggestions is None:
        suggestions = await letters.suggest_referrals(note["approved_text"])
        await letters.save_suggestions(cid, note["version"], suggestions)
        await audit.log(user["id"], "letter.suggested", "consultation", cid,
                        {"note_version": note["version"], "suggestions": suggestions})
    return JSONResponse(content={"suggestions": suggestions})


class LetterCreateBody(BaseModel):
    specialty: str
    reason: str | None = None


@app.post("/api/consultations/{cid}/letters")
async def letter_create(
    cid: int, body: LetterCreateBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    blocked, consultation, note = await _letter_gate(cid, user)
    if blocked is not None:
        return blocked
    specialty = body.specialty.strip()
    if not specialty:
        return JSONResponse(status_code=400, content={"error": "specialty is required"})
    patient = (await frontdesk.get_patient(consultation["patient_id"])
               if consultation["patient_id"] else None) or {"name": consultation["patient_name"]}
    # The letter signs off as the consultation's doctor (fall back to the
    # acting user, e.g. an admin drafting on an unowned legacy row).
    doctor = None
    if consultation["doctor_id"]:
        doctor = await auth.get_user(consultation["doctor_id"])
    doctor_name = (doctor or user)["display_name"]
    drafted = await letters.draft_letter(
        note["approved_text"], specialty, patient, doctor_name
    )
    lid = await letters.create_letter(
        cid, specialty, body.reason, drafted["body"], drafted["grounding"], user["id"]
    )
    await audit.log(user["id"], "letter.created", "letter", lid,
                    {"consultation_id": cid, "specialty": specialty,
                     "grounding": drafted["grounding"]})
    return JSONResponse(content={"ok": True, "letter_id": lid})


class LetterEditBody(BaseModel):
    body: str


@app.put("/api/consultations/{cid}/letters/{lid}")
async def letter_edit(
    cid: int, lid: int, body: LetterEditBody,
    user: dict = Depends(api_user(*CLINICAL_ROLES)),
) -> JSONResponse:
    blocked, _, _ = await _letter_gate(cid, user)
    if blocked is not None:
        return blocked
    if not await letters.update_letter_body(cid, lid, body.body):
        return JSONResponse(status_code=409,
                            content={"error": "letter not found or already approved"})
    await audit.log(user["id"], "letter.edited", "letter", lid,
                    {"consultation_id": cid})
    return JSONResponse(content={"ok": True})


@app.post("/api/consultations/{cid}/letters/{lid}/approve")
async def letter_approve(
    cid: int, lid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    blocked, _, _ = await _letter_gate(cid, user)
    if blocked is not None:
        return blocked
    if not await letters.approve_letter(cid, lid, user["id"]):
        return JSONResponse(status_code=409,
                            content={"error": "letter not found or already approved"})
    await audit.log(user["id"], "letter.approved", "letter", lid,
                    {"consultation_id": cid})
    return JSONResponse(content={"ok": True})


class TurnBody(BaseModel):
    # Both optional: a correction may be to the words, to the speaker label,
    # or to both. Text stays a separate concern from role — correcting the
    # words sets confidence to 1.0, and relabelling a speaker must not.
    text: str | None = None
    role: str | None = None


@app.patch("/api/consultations/{cid}/turns/{idx}")
async def edit_turn(
    cid: int, idx: int, body: TurnBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Correct a turn's words and/or its speaker label.

    Per-turn role correction (2026-07-28) is the answer to a SPLIT speaker
    cluster, which Swap Doctor/Patient cannot fix: swapping a split makes it
    worse, because some of the labels were already right (consultation 448 —
    a swap would correct two turns and break the third).
    """
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    if (blocked := await _not_editable(cid)) is not None:
        return blocked
    if body.text is None and body.role is None:
        return JSONResponse(status_code=400,
                            content={"error": "nothing to change: send text, role, or both"})
    if body.role is not None and body.role not in consultations.ROLES:
        return JSONResponse(
            status_code=400,
            content={"error": f"role must be one of {', '.join(consultations.ROLES)}"})
    if body.text is not None:
        await consultations.update_turn_text(cid, idx, body.text)
        await audit.log(user["id"], "turn.edited", "consultation", cid, {"turn": idx})
    if body.role is not None:
        was = await consultations.update_turn_role(cid, idx, body.role)
        if was is None:
            return JSONResponse(status_code=404, content={"error": "no such turn"})
        # Old AND new role in the row: a speaker relabel changes who the
        # record says said something, and that must be reconstructible.
        await audit.log(user["id"], "turn.role_changed", "consultation", cid,
                        {"turn": idx, "from": was, "to": body.role})
    return JSONResponse(content={"ok": True})


# Abrupt-disconnect grace: how long a detached live session waits for a
# reconnect before its received audio is finalised anyway (owner lost a
# full remote consultation to a drop near the end — audio must never be
# abandoned).
LIVE_RECONNECT_GRACE_S = float(os.getenv("LIVE_RECONNECT_GRACE_S", "120"))


async def _complete_session(app_state, entry: dict, *, connection_lost: bool) -> int:
    """Turn a live session's received audio into a queued consultation.
    Shared by the normal Stop path and grace-period finalisation — the
    only difference is the connection_lost flag (review shows a warning
    banner: the tail may be missing)."""
    session: LiveSession = entry["session"]
    user = entry["user"]
    # Close any window still open — an utterance interrupted by a hard
    # disconnect must still exclude the audio it was speaking over.
    _cancel_playback(entry, "cancelled")
    cid = await consultations.create_consultation(entry["patient_id"], user["id"])
    if entry["queue_entry_id"] is not None:
        await frontdesk.finish_entry(entry["queue_entry_id"])
    await audit.log(user["id"], "consultation.created", "consultation", cid,
                    {"patient_id": entry["patient_id"],
                     **({"connection_lost": True} if connection_lost else {})})
    wav_path = str(RECORDINGS_DIR / f"consultation_{cid}.wav")
    duration = session.save_recording(wav_path)
    logger.info("Consultation %d: %.1fs of audio saved%s", cid, duration,
                " (connection lost — tail may be missing)" if connection_lost else "")

    # System utterances and their exclusion spans, persisted BEFORE the
    # recording is enqueued for finalisation: from here on the spans live
    # in the database, not in this session object, which is how a
    # connection_lost or post-restart finalisation still excludes our
    # voice from the final transcript (spec §2.3).
    if entry.get("utterances"):
        await system_utterances.save(cid, entry["utterances"])
        logger.info("Consultation %d: %d system utterance(s) recorded",
                    cid, len(entry["utterances"]))

    # Persist urgent actions still unresolved at session end (the CDS
    # engine clears an action once the transcript shows it arranged, so
    # anything remaining was never seen to be actioned). Shown as an
    # acknowledge-gated banner on review — never merged into the note.
    assessment = entry["assessment"]
    if assessment and assessment.get("urgent_actions"):
        unresolved = [
            {
                "action": a["action"],
                "reason": a["reason"],
                "first_fired_s": entry["urgent_first_fired"].get(a["action"]),
            }
            for a in assessment["urgent_actions"]
        ]
        await consultations.save_urgent_actions(cid, unresolved)
        logger.info("Consultation %d: %d unresolved urgent action(s) recorded",
                    cid, len(unresolved))
    if connection_lost:
        await consultations.set_connection_lost(cid)
    # Hand the recording to the serialised finalisation worker: with one
    # GPU, pipelines run one at a time; the consultation waits as
    # 'queued' (worklist shows "processing (queued)").
    await consultations.set_status(cid, "queued", audio_path=wav_path)
    app_state.finalize_queue.put_nowait((cid, wav_path))
    return cid


async def _grace_finalise(app_state, session_id: str) -> None:
    """No reconnect within the grace window: finalise what was received
    rather than abandoning it. Cancelled by a successful reconnect."""
    try:
        await asyncio.sleep(LIVE_RECONNECT_GRACE_S)
    except asyncio.CancelledError:
        return
    entry = app_state.live_sessions.pop(session_id, None)
    if entry is None or entry["attached"]:
        return
    logger.warning("Live session %s: no reconnect within %.0fs — finalising "
                   "received audio", session_id, LIVE_RECONNECT_GRACE_S)
    await _complete_session(app_state, entry, connection_lost=True)


def _needs_disclosure(ref: dict) -> bool:
    """Which utterances the disclosure lock covers (hard rule 4).

    Every CDS question, plus the clinical phrases. NOT the disclosure
    itself — it cannot require itself — and not the encouragers: "mm-hm"
    is not a clinical interaction, and gating it would make the lock feel
    like a nuisance rather than a rule.
    """
    if ref.get("kind") == "cds_question":
        return True
    if ref.get("kind") == "phrase":
        return ref.get("id") in speech.DISCLOSURE_GATED_PHRASES
    return False


def _cancel_playback(entry: dict, reason: str) -> None:
    """End any in-flight utterance without a client `speak_ended`.

    Used on reconnect and at session end. The window closes at whatever it
    had reached; an utterance that never started leaves no window at all
    and is recorded `failed_to_play` — no window means no exclusion, which
    is correct, because nothing was played into the room.
    """
    utterance = entry.get("pending_utterance")
    if utterance is None:
        return
    session: LiveSession = entry["session"]
    span = session.close_speaking_window(reason) if session.speaking else None
    entry["utterances"].append({
        "utterance_id": utterance.utterance_id, "text": utterance.text,
        "ref_kind": utterance.ref_kind, "ref_detail": utterance.ref_detail,
        "cds_rationale": utterance.cds_rationale, "voice": utterance.voice,
        "synth_ms": utterance.synth_ms, "stale": utterance.stale,
        "end_reason": reason if span is not None else "failed_to_play",
        "cut_latency_ms": None,
        "start_byte": span["start_byte"] if span else None,
        "end_byte": span["end_byte"] if span else None,
        "started_offset_ms": bytes_to_ms(span["start_byte"]) if span else None,
        "ended_offset_ms": bytes_to_ms(span["end_byte"]) if span else None,
    })
    entry["pending_utterance"] = None


def _detach_for_grace(app_state, session_id: str, entry: dict) -> None:
    entry["attached"] = False
    entry["grace_task"] = asyncio.create_task(_grace_finalise(app_state, session_id))
    logger.warning("Live session %s: connection lost mid-recording — holding "
                   "for reconnect (%.0fs grace)", session_id, LIVE_RECONNECT_GRACE_S)


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket) -> None:
    """Receive 16 kHz 16-bit mono PCM frames; stream transcript JSON back.

    Protocol (connection-resilient since 2026-07-24):
    - Client's FIRST message is JSON config: {"session_id", "patient_id",
      "queue_entry_id", "resume": bool}.
    - Binary frames carry a 4-byte big-endian sequence number, then PCM.
      The server acks progress ({"type": "ack", "seq": N}); the client
      keeps unacked chunks and resends them after a reconnect.
    - On abrupt disconnect the session detaches and waits
      LIVE_RECONNECT_GRACE_S for a resume; then the received audio is
      finalised with a connection-lost flag instead of being abandoned.
    - Text "stop" ends the session normally.
    """
    # WebSocket auth: same session cookie, clinical roles only.
    user = await auth.get_user(auth.verify_session(websocket.cookies.get(COOKIE_NAME)) or 0)
    if user is None or user["role"] not in CLINICAL_ROLES:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    state = websocket.app.state
    if getattr(state, "live_sessions", None) is None:
        state.live_sessions = {}
    sessions: dict[str, dict] = state.live_sessions

    # ---- handshake: the first message must be the JSON config
    try:
        first = await asyncio.wait_for(websocket.receive(), timeout=15.0)
    except asyncio.TimeoutError:
        await websocket.close(code=4400)
        return
    if first["type"] == "websocket.disconnect":
        return
    text = first.get("text") or ""
    if not text.startswith("{"):
        await websocket.close(code=4400)
        return
    config = json.loads(text)
    session_id = str(config.get("session_id") or os.urandom(8).hex())

    entry = sessions.get(session_id)
    if config.get("resume") and entry is None:
        # Grace expired: the audio was finalised server-side already.
        await websocket.send_json({
            "type": "resume_failed",
            "detail": "This session was already finalised on the server — "
                      "check the Consultations tab for the result.",
        })
        await websocket.close(code=4404)
        return
    if entry is not None and not entry["attached"]:
        # Reconnect: cancel the grace timer, resume where we left off.
        if entry["grace_task"] is not None:
            with contextlib.suppress(RuntimeError):  # timer loop may be gone
                entry["grace_task"].cancel()
            entry["grace_task"] = None
        entry["attached"] = True
        # Playback is never resumed across a reconnect (spec §2.3): the
        # client has stopped, so the window must close at whatever it
        # reached rather than keep excluding live patient audio.
        _cancel_playback(entry, "cancelled")
        await websocket.send_json({"type": "resume", "last_seq": entry["last_seq"]})
        logger.info("Live session %s: reconnected at seq %d", session_id,
                    entry["last_seq"])
    elif entry is not None:  # attached elsewhere — duplicate tab/device
        await audit.log(user["id"], "live.slot_rejected", None, None,
                        {"via": "ws_duplicate"})
        await websocket.send_json({
            "type": "busy",
            "detail": "This consultation is already streaming from another "
                      "tab or device. One live consultation at a time.",
        })
        await websocket.close(code=4409)
        return
    else:
        # New session. One live consultation at a time, globally: a second
        # stream would share the one faster-whisper model (commit latency
        # blows past the 2-5 s target) and race the finalisation GPU
        # hand-off. The Today-queue guard makes this unreachable through
        # the UI; this is the server-side wall.
        if any(e["attached"] for e in sessions.values()):
            active = next(e for e in sessions.values() if e["attached"])
            await audit.log(user["id"], "live.slot_rejected", None, None,
                            {"via": "ws"})
            await websocket.send_json({
                "type": "busy",
                "detail": "Another live consultation is already in progress "
                          f"(started by {active['user']['username']}). "
                          "One live consultation at a time.",
            })
            await websocket.close(code=4409)
            return
        # A detached session still in grace means its owner is gone and
        # someone is starting fresh (e.g. page reload = new session id):
        # finalise its audio NOW — never lost — and free the slot.
        for stale_id in [sid for sid, e in sessions.items() if not e["attached"]]:
            stale = sessions.pop(stale_id)
            if stale["grace_task"] is not None:
                with contextlib.suppress(RuntimeError):
                    stale["grace_task"].cancel()
            await _complete_session(state, stale, connection_lost=True)
        entry = {
            "session": LiveSession(state.transcriber),
            "user": user,
            "patient_id": config.get("patient_id"),
            "queue_entry_id": config.get("queue_entry_id"),
            "transcript_parts": [],   # confirmed text, the CDS engine's input
            "assessment": None,
            "cds_sent_len": 0,
            "urgent_first_fired": {},  # action text → audio time (s)
            "last_seq": 0,
            "attached": True,
            "grace_task": None,
            "stopped": False,
            # Phase 7a: the server's own copy of the question agenda, and
            # every utterance it has been asked to speak this session.
            "agenda": speech.AgendaLog(),
            "utterances": [],          # dicts, persisted at session end
            "pending_utterance": None,  # prepared, not yet started
            # Hard rule 4: the patient must be told they are talking to a
            # machine. Held server-side because the rule is code-enforced,
            # not a UI courtesy — a disabled button can be re-enabled from
            # the console, a server refusal cannot.
            "disclosed": False,
        }
        sessions[session_id] = entry
        logger.info("Live session %s started by %s", session_id, user["username"])

    session: LiveSession = entry["session"]
    engine: CDSEngine = state.cds_engine
    rag: RAGService = state.rag

    # CDS side tasks are per-connection (cancelled on disconnect); their
    # accumulated state lives in the entry and survives reconnects.
    cds_task: asyncio.Task | None = None
    cds_failures = 0
    gl_task: asyncio.Task | None = None
    gl_conditions: tuple = ()  # conditions the current guideline panel is for
    last_acked = -1

    async def maybe_run_cds() -> None:
        """Launch/collect the CDS side task without ever blocking transcription."""
        nonlocal cds_task, cds_failures
        if cds_task is not None and cds_task.done():
            try:
                entry["assessment"] = cds_task.result()
                cds_failures = 0
                # Version the agenda before sending it, so the version the
                # client tap refers to is one the server can resolve.
                assessment_version = entry["agenda"].record(entry["assessment"])
                entry["assessment"]["assessment_version"] = assessment_version
                for action in entry["assessment"].get("urgent_actions", []):
                    entry["urgent_first_fired"].setdefault(
                        action["action"], round(session.audio_seconds, 1)
                    )
                await websocket.send_json(
                    {"type": "cds", "assessment": entry["assessment"]}
                )
            except Exception as exc:  # noqa: BLE001 - degrade, don't crash the stream
                cds_failures += 1
                logger.warning("CDS pass failed (%d): %s", cds_failures, exc)
                if cds_failures >= CDS_MAX_FAILURES:
                    await websocket.send_json(
                        {"type": "cds_unavailable",
                         "detail": "CDS engine unreachable; transcription continues."}
                    )
            cds_task = None
        transcript = "\n".join(entry["transcript_parts"])
        if (
            cds_task is None
            and cds_failures < CDS_MAX_FAILURES
            and len(transcript) - entry["cds_sent_len"] >= CDS_MIN_NEW_CHARS
        ):
            entry["cds_sent_len"] = len(transcript)
            cds_task = asyncio.create_task(
                engine.update(transcript, entry["assessment"])
            )

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
        if entry["assessment"] is None or gl_task is not None:
            return
        conditions = tuple(
            d["condition"] for d in entry["assessment"].get("differentials", [])[:2]
        )
        if conditions and conditions != gl_conditions:
            gl_conditions = conditions
            gl_task = asyncio.create_task(rag.answer_for_conditions(list(conditions)))

    async def refuse_speech(reason: str, detail: dict | None = None) -> None:
        """Every refusal is loud and audited. A rejected message is a bug
        report; a quietly sanitised one is a silent hole."""
        await audit.log(user["id"], "speech.failed", None, None,
                        {"reason": reason, **(detail or {})})
        await websocket.send_json({"type": "speak_refused", "detail": reason})

    async def handle_speak(payload: dict) -> None:
        """Prepare an utterance from a REFERENCE — never from client text.

        PHASE_7A_SPEC.md §2.1. This is where hard rule 1 is enforced in
        code: there is no branch that reads words from the client, so no
        client — buggy, modified or compromised — can make the system
        advise, reassure or diagnose to the patient.
        """
        if "text" in payload or "text" in (payload.get("ref") or {}):
            # Rejected outright rather than stripped. Sanitising would make
            # this a filter; refusing keeps it a closed channel.
            await refuse_speech("speak may not carry text; send a ref",
                                {"ref_kind": (payload.get("ref") or {}).get("kind")})
            return
        if user["id"] != entry["user"]["id"]:
            await refuse_speech("only the doctor running this consultation may speak")
            return
        if session.speaking or entry["pending_utterance"] is not None:
            # One utterance at a time, queue depth zero (spec §2.3): two
            # overlapping windows would make the exclusion span ambiguous.
            await refuse_speech("an utterance is already in flight")
            return
        if not entry["disclosed"] and _needs_disclosure(payload.get("ref") or {}):
            # Hard rule 4, enforced here rather than only in the UI: the
            # patient is told they are talking to a machine BEFORE the
            # machine starts asking them things.
            await refuse_speech(
                "the patient has not been told they are talking to a machine — "
                "play the disclosure, or tick 'disclosure given'")
            return
        try:
            utterance = await asyncio.to_thread(
                functools.partial(
                    state.speech.prepare, payload.get("ref") or {}, entry["agenda"],
                    user_id=user["id"],
                    # Server-side, from the session's own doctor account —
                    # the client cannot choose whose name the machine says.
                    doctor=speech.doctor_name_for(entry["user"])))
        except speech.SpeechRefused as exc:
            await refuse_speech(str(exc))
            return
        except speech.SpeechUnavailable as exc:
            await refuse_speech(f"speech unavailable: {exc}")
            return
        except speech.SpeechFailed as exc:
            # A fault, not a configuration state: it must show as an error
            # rather than as a system that chose not to speak.
            await refuse_speech(f"synthesis failed: {exc}")
            return
        entry["pending_utterance"] = utterance
        await audit.log(user["id"], "speech.requested", None, None,
                        {"utterance_id": utterance.utterance_id,
                         "ref_kind": utterance.ref_kind,
                         "ref_detail": utterance.ref_detail,
                         "stale": utterance.stale})
        await websocket.send_json({
            "type": "speak_ready", "utterance_id": utterance.utterance_id,
            "duration_ms": utterance.duration_ms,
            # What the server decided to say. The client needs it to log
            # the utterance faithfully rather than by button label — it
            # showed "Disclosure" where the room heard three sentences
            # (2026-07-25 room test). This is the server TELLING the
            # client; it remains impossible for the client to supply text.
            "text": utterance.text,
            "url": f"/api/speech/{utterance.utterance_id}.wav"})

    def record_utterance(utterance, span: dict | None, end_reason: str,
                         cut_latency_ms: int | None = None) -> None:
        row = {
            "utterance_id": utterance.utterance_id, "text": utterance.text,
            "ref_kind": utterance.ref_kind, "ref_detail": utterance.ref_detail,
            "cds_rationale": utterance.cds_rationale, "voice": utterance.voice,
            "synth_ms": utterance.synth_ms, "stale": utterance.stale,
            "end_reason": end_reason, "cut_latency_ms": cut_latency_ms,
            "start_byte": None, "end_byte": None,
            "started_offset_ms": None, "ended_offset_ms": None,
        }
        if span is not None:
            row.update(
                start_byte=span["start_byte"], end_byte=span["end_byte"],
                started_offset_ms=bytes_to_ms(span["start_byte"]),
                ended_offset_ms=bytes_to_ms(span["end_byte"]))
        entry["utterances"].append(row)

    async def mark_disclosed(how: str) -> None:
        """Record that the patient has been told. Audited with user and
        timestamp (the audit row carries `at` and `user_id`)."""
        entry["disclosed"] = True
        await audit.log(user["id"], "speech.disclosure_given", None, None,
                        {"how": how})
        await websocket.send_json({"type": "disclosure", "given": True, "how": how})
        logger.info("Live session %s: disclosure recorded (%s) by %s",
                    session_id, how, user["username"])

    async def handle_speak_started(payload: dict) -> None:
        """Open the exclusion window at actual playback start (§2.2 step 2)."""
        utterance = entry["pending_utterance"]
        if utterance is None or payload.get("utterance_id") != utterance.utterance_id:
            await refuse_speech("speak_started for an unknown utterance",
                                {"utterance_id": payload.get("utterance_id")})
            return
        start = session.open_speaking_window(
            utterance.utterance_id, utterance.duration_ms,
            speech.SPEECH_EXCLUSION_TAIL_MS)
        # The client's declared seq is a cross-check only. The server's own
        # byte count is what says where in the file playback began, and
        # trusting the client here would put the guarantee in its hands.
        declared = payload.get("seq")
        if declared is not None and int(declared) != entry["last_seq"] + 1:
            logger.warning(
                "Live session %s: speak_started declared seq %s, server expected %d "
                "— using the server's byte offset (%d)",
                session_id, declared, entry["last_seq"] + 1, start)

    async def handle_speak_ended(payload: dict) -> None:
        utterance = entry["pending_utterance"]
        if utterance is None or not session.speaking:
            await refuse_speech("speak_ended with no window open")
            return
        reason = payload.get("reason") or "complete"
        if reason not in system_utterances.END_REASONS:
            reason = "complete"
        span = session.close_speaking_window(reason)
        cut_latency = payload.get("cut_latency_ms")
        record_utterance(utterance, span, reason,
                         int(cut_latency) if cut_latency is not None else None)
        # The disclosure counts once the patient has actually heard it —
        # a cut-off disclosure has not been given.
        if (utterance.ref_detail.get("id") == "disclosure"
                and reason == "complete" and not entry["disclosed"]):
            await mark_disclosed("spoken")
        entry["pending_utterance"] = None
        await audit.log(
            user["id"], "speech.barge_in" if reason == "barge_in" else "speech.spoken",
            None, None,
            {"utterance_id": utterance.utterance_id, "reason": reason,
             "excluded_ms": bytes_to_ms(
                 span["end_byte"] - span["start_byte"]),
             **({"cut_latency_ms": int(cut_latency)} if cut_latency is not None else {})})

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=2.0)
            except asyncio.TimeoutError:
                message = None

            if message is not None:
                if message["type"] == "websocket.disconnect":
                    return  # finally: detach + grace (audio is never dropped)
                if data := message.get("bytes"):
                    # 4-byte big-endian seq + PCM. Duplicates (a resend
                    # overlapping what already arrived) are skipped by seq.
                    seq = int.from_bytes(data[:4], "big")
                    if seq > entry["last_seq"]:
                        if seq != entry["last_seq"] + 1:
                            logger.warning("Live session %s: seq gap %d → %d",
                                           session_id, entry["last_seq"], seq)
                        session.append_pcm16(data[4:])
                        entry["last_seq"] = seq
                elif (text_message := message.get("text")) == "stop":
                    entry["stopped"] = True
                    break
                elif text_message and text_message.startswith("{"):
                    payload = json.loads(text_message)
                    kind = payload.get("type")
                    if kind == "speak":
                        await handle_speak(payload)
                    elif kind == "speak_started":
                        await handle_speak_started(payload)
                    elif kind == "speak_ended":
                        await handle_speak_ended(payload)
                    elif kind == "disclosure_given":
                        # The doctor's own words instead of ours. Only the
                        # doctor running the consultation may attest it.
                        if user["id"] != entry["user"]["id"]:
                            await refuse_speech(
                                "only the doctor running this consultation "
                                "may record the disclosure")
                        elif not entry["disclosed"]:
                            await mark_disclosed("doctor_attested")

            if session.new_audio_seconds >= PROCESS_INTERVAL_S:
                committed, partial = await session.process()
                for seg in committed:
                    entry["transcript_parts"].append(seg.text)
                    await websocket.send_json(
                        {"type": "final", "text": seg.text, "start": seg.start, "end": seg.end}
                    )
                await websocket.send_json({"type": "partial", "text": partial})

            # Ack received audio so the client can prune its resend buffer.
            if entry["last_seq"] != last_acked:
                last_acked = entry["last_seq"]
                await websocket.send_json({"type": "ack", "seq": last_acked})

            await maybe_run_cds()
            await maybe_run_guidelines()

        # Client pressed stop: transcribe the tail end and finish cleanly.
        for seg in await session.flush():
            entry["transcript_parts"].append(seg.text)
            await websocket.send_json(
                {"type": "final", "text": seg.text, "start": seg.start, "end": seg.end}
            )

        # The Stop button IS the finalisation trigger — no separate step.
        sessions.pop(session_id, None)
        cid = await _complete_session(state, entry, connection_lost=False)
        await websocket.send_json({"type": "done", "consultation_id": cid})
        await websocket.close()
    except WebSocketDisconnect:
        pass
    finally:
        if cds_task is not None:
            cds_task.cancel()
        if gl_task is not None:
            gl_task.cancel()
        still_mine = sessions.get(session_id) is entry
        if still_mine and not entry["stopped"]:
            if entry["last_seq"] > 0:
                # Abrupt disconnect with audio on the server: hold the
                # session for a reconnect; grace expiry finalises it.
                _detach_for_grace(state, session_id, entry)
            else:
                sessions.pop(session_id, None)  # nothing received — discard
        logger.info("Live connection closed (session %s%s)", session_id,
                    ", held for reconnect" if still_mine and not entry["stopped"]
                    and entry["last_seq"] > 0 else "")


@app.get("/")
def root(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> RedirectResponse:
    """Land on Today when a session cookie is valid, else the login page."""
    destination = "/today" if auth.verify_session(session) else "/login"
    return RedirectResponse(destination, status_code=307)


@app.get("/api/monitor/pulse")
async def monitor_pulse() -> JSONResponse:
    """Public monitoring pulse — deliberately unauthenticated, for
    external-demo observation. Aggregate counts ONLY: never a username,
    patient name, or clinical content (tested in test_rbac.py). The
    database/disk aggregates are cached ~10 s (app/monitor.py) so
    polling cannot load the database."""
    sessions = getattr(app.state, "live_sessions", None) or {}
    live = any(entry["attached"] for entry in sessions.values())
    return JSONResponse(content=await monitor.pulse(live, RECORDINGS_DIR))


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
