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
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from fastapi import Depends
from pydantic import BaseModel

from app import (audit, auth, auto_mode, consultations, face, frontdesk, letters,
                 monitor, ratelimit, raw_segments, retention, schema, speech,
                 system_utterances)
from app.auth import COOKIE_NAME, CLINICAL_ROLES, api_user, page_user
from app.cds import CDSEngine, OfficerVerdict, turn_finished
from app.finalize import (expect_declaration, finalize_consultation,
                          regenerate_note, release_declaration)
from app import transcript_quality
from app.live import PROCESS_INTERVAL_S, LiveSession, bytes_to_ms
from app.notes import note_as_plain_text
from app.rag import RAGService
from app.transcription import LiveTranscriber

# Run a CDS pass once this much new confirmed text has accumulated.
CDS_MIN_NEW_CHARS = 150
# Session 5 (owner decision, from the session-4 latency report): the FIRST
# assessment of a session fires as soon as the first committed turn
# exists, instead of waiting for the 150-character gate — the gate was
# 30-45 s of the ~50 s speech-to-questions latency. Subsequent calls keep
# the 150-char cadence unchanged. The urgency officer rides the same
# update it always has, so the alarm can only arrive EARLIER, never
# later. Env-switchable so the owner can restore the old behaviour
# without a deploy.
CDS_FIRST_CALL_ON_FIRST_TURN = (
    os.getenv("CDS_FIRST_CALL_ON_FIRST_TURN", "true").lower() != "false")
# Stop trying after this many consecutive failures (e.g. Ollama not running).
CDS_MAX_FAILURES = 2
# Sentinel for "no patient_affect has been logged for this session yet",
# distinct from every string the log can carry — including "ABSENT".
_AFFECT_UNLOGGED = object()

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")
# Session cookies carry `Secure` (2026-07-31 audit, Finding 6): this app is
# reached over HTTPS (Tailscale Funnel terminates TLS), and a session cookie
# must never travel in clear. Gated only so a plaintext-HTTP development
# host can drop it — and gated with the SECURE DEFAULT, so forgetting the
# variable fails safe rather than silently unprotected. The test suite
# drives the app over http://testserver and sets it false in
# tests/conftest.py; that is the only place it is turned off.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() != "false"
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
    # Phase 7c (PHASE_7C_SPEC.md §9): warm the disk cache with the fixed
    # phrases so an encourager is a cache hit. Off the event loop and never
    # fatal — the method logs and returns whatever happened; a machine
    # without Piper skips in one line. The task handle is kept so it is not
    # collected mid-run and can be cancelled at shutdown.
    app.state.speech_presynth = asyncio.create_task(
        asyncio.to_thread(app.state.speech.presynthesise_phrases))
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
    # Stale-walk-in sweep, beside the retention sweep. An in_consultation entry
    # abandoned before Start holds the single system-wide live slot, so it locks
    # out EVERY doctor until its date rolls over — and once it has, both recovery
    # paths used to refuse it (entry 164). Best-effort: a failure here must not
    # stop the app, but it is logged loudly because the consequence of skipping
    # it is a practice that cannot start a consultation.
    try:
        await frontdesk.sweep_stale_entries()   # audits each closure itself
    except Exception:  # noqa: BLE001 - startup must survive a sweep failure
        logger.exception("Stale-entry sweep failed at startup")
    yield
    app.state.speech_presynth.cancel()
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


# Security headers, on every response (2026-07-31 audit, Finding 5).
#
# THE CSP IS DELIBERATELY INCOMPLETE, and that is the load-bearing comment.
# `default-src 'self'` and `script-src 'self'` are NOT here, because every
# page carries a large inline <script> — roughly 3,300 lines across seven
# pages, live.html alone 1,844. A strict script-src would block all of it
# and the app would serve blank pages. (The audit's own note that the pages
# "use external .js" was incomplete: they load nav.js AND carry an inline
# block.)
#
# What is here costs nothing today — none of it touches inline script, and
# each directive closes a real hole:
#   object-src 'none'       plugin/embed execution
#   base-uri 'self'         an injected <base> re-pointing relative URLs
#   form-action 'self'      a form posting credentials off-origin
#   frame-ancestors 'none'  clickjacking (supersedes X-Frame-Options)
#
# `'unsafe-inline'` is NOT used and MUST NOT be added: it would re-permit
# exactly the injected-script attack the escaping in app/static/nav.js
# closes, while making the header look like protection. The route to the
# full policy is to move the inline blocks out to /static/*.js and then add
# `default-src 'self'; script-src 'self'` — a seven-page refactor that does
# not belong inside a security fix, and is reported rather than smuggled in.
#
# So: the escaping is the XSS defence. This header is not yet a second one.
CSP = ("object-src 'none'; base-uri 'self'; form-action 'self'; "
       "frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request, call_next):
    """CSP + nosniff on every response, including errors and static files."""
    response = await call_next(request)
    response.headers["content-security-policy"] = CSP
    response.headers["x-content-type-options"] = "nosniff"
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
    role: str  # doctor | receptionist


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
    except auth.InvalidUserInput as exc:
        # Refused, never sanitised — and the caller is told which bound it
        # broke, because answering "username already taken" to a rejected
        # display name would be a lie that costs somebody an afternoon.
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception:
        return JSONResponse(status_code=409, content={"error": "username already taken"})
    # Approve-to-activate (public exposure): EVERY registration is pending —
    # no session until the administrator activates the account in the Users
    # view. No exception for an empty table: the first-registrant-becomes-
    # admin bootstrap is gone (owner decision 2026-08-04), the first admin
    # comes from the server shell (scripts/manage_users.py create), and
    # registration must never mint an active account or a session cookie.
    await audit.log(
        user["id"], "user.registered_pending", "user", user["id"],
        {"role": user["role"], "ip": ip},
    )
    return JSONResponse(content={
        "ok": True, "pending": True, "user": user,
        "message": "Account created — awaiting the administrator's approval."
    })


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
    response.set_cookie(COOKIE_NAME, auth.sign_session(user["id"]), httponly=True,
                        samesite="lax", secure=SESSION_COOKIE_SECURE)
    return response


@app.post("/api/logout")
async def logout() -> JSONResponse:
    response = JSONResponse(content={"ok": True})
    # The attributes must match the ones it was set with, or the browser
    # keeps the original cookie and the sign-out does nothing visible.
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax",
                           secure=SESSION_COOKIE_SECURE)
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
    # The capture chain the page REQUESTED for the measuring stream
    # (ec/ns/agc booleans, live.html's CAPTURE_CHAIN — the single source
    # that also builds the getUserMedia constraints). The device-label
    # lesson applied before it bites twice: a level without its
    # processing chain is not a measurement either, and readings across
    # different chains must never pool. Absent on rows from before
    # 2026-07-30, which the calibration report marks incomparable.
    chain: dict[str, bool] | None = None
    # The detector-stream residual (spec Part 10 amendment, 2026-07-30):
    # peak_rms / mean_rms / series (coarse windows across the utterance,
    # the canceller's convergence curve) / window_ms. Machinery data for
    # the barge-in threshold — the doctor-facing result stays raw-only.
    # When absent, residual_unavailable carries WHY: a missing residual
    # must be visible in the row, never a silent zero.
    residual: dict | None = None
    residual_unavailable: str | None = None


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
                     **({"chain": body.chain} if body.chain else {}),
                     # Residual or the reason there is none — never silence.
                     **({"residual": body.residual} if body.residual
                        else {"residual_unavailable":
                              body.residual_unavailable or "not measured"}),
                     **verdict["level"]})
    logger.info("Sound check by %s: %s (ratio %.2f, answer %s, output %s)",
                user["username"], verdict["result"],
                verdict["level"]["ratio"], verdict["answer"], body.device_label)
    # Echoed back so the panel shows the device that was RECORDED, not one the
    # client re-derives — a reading and its audio path must not be able to
    # disagree about which path it was.
    return JSONResponse(content={**verdict, "output_device": body.device_label})


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


def _clock(timestamp: str | None) -> str:
    """HH:MM out of a stored timestamp, for a refusal message."""
    if not timestamp:
        return "an unknown time"
    return timestamp[11:16] if len(timestamp) >= 16 else timestamp


async def _live_slot_refusal(active: dict | None = None) -> JSONResponse:
    """ONE refusal message for the live slot, used by every site that refuses it.

    The guard is NOT weakened here and must not be: one live consultation at a
    time is a safety property, because two would share the faster-whisper model
    and an urgency alarm arriving late under contention is a safety regression.
    This only makes the refusal legible.

    A doctor refused the slot used to learn that "another consultation is already
    in progress" — true, unactionable, and identical whether the blocker is a
    colleague mid-consultation or a walk-in somebody abandoned an hour ago. Now
    it names the patient, the time it was opened, and — because a queue entry is
    something the caller can actually deal with — that it can be closed from
    Today.
    """
    active = active if active is not None else await frontdesk.current_entry()
    if not active:
        # The slot is held by something outside today's queue. Say that rather
        # than falling back to a bare "busy": an unexplained refusal is what
        # this change exists to remove.
        return JSONResponse(status_code=409, content={
            "error": "A live consultation is already in progress, but no entry "
                     "in today's queue is holding it. Reload Today; if this "
                     "persists an administrator can check for a live session.",
            "active": None,
        })
    return JSONResponse(status_code=409, content={
        "error": (f"{active['name']} is already in consultation "
                  f"(opened at {_clock(active.get('added_at'))}). "
                  "Resume it, or close their entry from Today to free the slot."),
        "active": active,
    })


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
        return await _live_slot_refusal()
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
            return await _live_slot_refusal(active)
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


@app.get("/api/consultations/{cid}/raw-transcript")
async def raw_transcript(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """The raw-transcript view (RAW_TRANSCRIPT_VIEW_SPEC.md): pre-merge
    ASR segments, read from STORAGE only — never rebuilt, because
    WhisperX is not deterministic and a rebuilt view would show a
    consultation that never existed (spec §3). Available on approved
    consultations too (D3: an audit trail's value is that it survives
    approval); same scoping as the transcript itself.

    Opening the view is AUDITED (spec §6) — the point is to measure
    whether checking happens, not to be able to say checking was
    possible. Audited also when nothing is stored: an attempt to check
    is the behaviour being measured.

    History is handled honestly: consultations finalised before this
    feature (2026-07-30) have no stored segments, and the payload says
    so plainly rather than falling back to re-running anything.
    """
    consultation = await consultations.get_consultation(cid)
    if consultation is None:
        return JSONResponse(status_code=404, content={"error": "not found"})
    if consultation["voided_at"] and user["role"] != "admin":
        return JSONResponse(status_code=410, content={"error": "consultation voided"})
    if (blocked := _foreign_consultation(consultation, user)) is not None:
        return blocked
    segments = await raw_segments.for_consultation(cid)
    await audit.log(user["id"], "transcript.raw_viewed", "consultation", cid,
                    {"segments": len(segments), "available": bool(segments)})
    return JSONResponse(content={
        "available": bool(segments),
        "segments": segments,
        "reason": None if segments else (
            "No raw segments are stored for this consultation — it was "
            "finalised before raw-segment storage existed (2026-07-30). "
            "The raw view is read from storage and is never rebuilt by "
            "re-running the pipeline.")})


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
    # The Doctor/Patient labels are not a measurement of who spoke — either
    # diarisation returned one cluster, or the doctor declared a count the
    # pipeline did not use (450). Blocked server-side as well as in the UI, the
    # same as the urgency banner: a disabled button can be re-enabled from the
    # console, a refusal cannot.
    if (consultation and consultations.speaker_labels_unverified(consultation)
            and not consultation["single_voice_ack_at"]):
        reason = ("you declared "
                  f"{consultation['declared_speakers']} speaker(s) but speaker "
                  f"identification had already run with "
                  f"{consultation['speakers_used']}"
                  if consultation["declaration_ignored"]
                  else "only one voice was detected in the audio")
        return JSONResponse(
            status_code=409,
            content={"error": f"The speaker roles are unverified — {reason}."
                     " Check the transcript's Doctor/Patient labels and"
                     " acknowledge first."},
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
    # Flag tier (spec §11): a flagged transcript HAS a draft, and signing
    # it is allowed — after the doctor acknowledges the amber banner.
    # Blocked server-side like every acknowledge gate: a disabled button
    # can be re-enabled from the console, a refusal cannot.
    if (consultation and consultation["quality_outcome"] == transcript_quality.OUTCOME_FLAGGED
            and not consultation["quality_ack_at"]):
        return JSONResponse(
            status_code=409,
            content={"error": "The transcript-quality gate flagged this"
                     " transcript (marginal confidence, a long untranscribed"
                     " tail, or a repetition loop). Review the transcript with"
                     " care and acknowledge the notice first."},
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


@app.post("/api/consultations/{cid}/acknowledge-quality")
async def acknowledge_quality(
    cid: int, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """Flag tier (spec §11): the doctor confirms they have reviewed a
    flagged transcript with care. Audited like every acknowledgement."""
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    acked_at = await consultations.acknowledge_quality(cid)
    await audit.log(user["id"], "quality.acknowledged", "consultation", cid,
                    {"acknowledged_at": acked_at})
    return JSONResponse(content={"ok": True, "acknowledged_at": acked_at})


class SpeakersBody(BaseModel):
    count: int | None = None
    skip: bool = False


@app.post("/api/consultations/{cid}/declared-speakers")
async def declare_speakers(
    cid: int, body: SpeakersBody, user: dict = Depends(api_user(*CLINICAL_ROLES))
) -> JSONResponse:
    """The doctor's answer to "who spoke?", asked at Stop.

    Deliberately NOT gated on `_not_editable`: it is asked the moment the
    consultation is completed, and refusing it because finalisation has moved on
    would be a tap that does nothing. Instead the response says whether the
    answer reached diarisation in time, so the caller can tell the doctor the
    truth either way (standing rule: the tap always does something, and what it
    did is reported at the control).

    Skip posts too, rather than staying silent. It carries no count — NULL still
    means defaulted — but it RELEASES the waiting pipeline immediately, which is
    what keeps the offer an offer: skipping must cost nothing, including time.
    """
    if (blocked := await _scoped(cid, user)) is not None:
        return blocked
    if body.skip:
        released = release_declaration(cid)
        await audit.log(user["id"], "speakers.declared", "consultation", cid,
                        {"skipped": True, "released_pipeline": released})
        return JSONResponse(content={"ok": True, "skipped": True,
                                     "applied": True, "used": None})
    if body.count is None:
        return JSONResponse(status_code=400,
                            content={"error": "send a count, or skip: true"})
    try:
        result = await consultations.declare_speakers(cid, body.count)
    except ValueError as err:
        return JSONResponse(status_code=400, content={"error": str(err)})
    released = release_declaration(cid)
    await audit.log(user["id"], "speakers.declared", "consultation", cid,
                    {"count": body.count, "applied": result["applied"],
                     "already_used": result["used"],
                     "released_pipeline": released})
    if not result["applied"]:
        # An answer that did not shape the transcript must leave a trace the
        # doctor will actually meet, not just an audit row and a JSON field.
        # 450: the answer was accepted, discarded, and nothing on any screen
        # said so. `speaker_labels_unverified` (below) is what carries it onto
        # the review page and blocks approval until it is acknowledged.
        logger.warning("Consultation %d: declared %d speaker(s) but diarisation "
                       "had already run with %d", cid, body.count, result["used"])
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

# Phase 7b session 3 — owner decision, 2026-07-28. Auto-on at Disclosure:
# the SPOKEN disclosure switches the face on ("the owner named the
# button" — the 'in my own words' tick does not). The face-off study arm
# must run with this DISABLED, or the arm silently breaks (recorded in
# HANDOVER). A manual face-off is never overridden — the doctor always
# wins.
FACE_AUTO_ON_DISCLOSURE = os.getenv("FACE_AUTO_ON_DISCLOSURE", "true").lower() != "false"
# Auto-chain: when the disclosure plays THROUGH (end_reason complete — a
# cut-off disclosure never chains), the invitation is spoken next, through
# the normal speak path, as its own utterance and audit rows.
AUTO_INVITATION_AFTER_DISCLOSURE = (
    os.getenv("AUTO_INVITATION_AFTER_DISCLOSURE", "true").lower() != "false")
# The silence nudge — THE ONLY AUTONOMOUS UTTERANCE IN 7a/7b, deliberately
# caged (one-shot per consultation, server-enforced; only after the
# invitation has played through; disclosure-gated like every clinical
# phrase; any activity cancels it client-side, biased toward NOT firing).
# Its guard ("do not generalise it into an encourager loop") was retired in
# Phase 7c slice 3, when the behaviour-policy machinery arrived: the
# client's quiet reporter and the controller's encourager loop, dark behind
# AUTO_MODE_ENABLED below. With auto mode off, the cage holds exactly as
# before.
SILENCE_NUDGE_ENABLED = os.getenv("SILENCE_NUDGE_ENABLED", "true").lower() != "false"
SILENCE_NUDGE_S = float(os.getenv("SILENCE_NUDGE_S", "5"))

# --- Phase 7c: supervised auto history-taking (PHASE_7C_SPEC.md §12) -------
#
# THE GATE. Ships false. Everything in 7c builds and tests dark behind it;
# with it false the app's behaviour is exactly what it was before 7c.
# Flipping it is the OWNER'S act, after the frozen gate is met — barge-in
# calibrated (scripts/calibrate_barge_in.py meets D5) and the mock-patient
# round reviewed. Not a code change; 7c must not arrive by drift.
AUTO_MODE_ENABLED = os.getenv("AUTO_MODE_ENABLED", "false").lower() == "true"
# The golden window: encouragers only, zero questions, from the invitation's
# speak_ended (the prereg's metric-3 zero point). Owner decision 2026-08-16:
# 1–2 minutes, superseding the parent spec's 2–3 (PHASE_7C_EVAL_PREREG.md
# amendment A1); recorded per run, scored against the value in force.
AUTO_GOLDEN_MINUTES_S = float(os.getenv("AUTO_GOLDEN_MINUTES_S", "90"))
# The remaining values are UNCALIBRATED GUESSES, stated as such; the
# mock-patient round is the run that informs them (spec §5, §12).
# Quiet this long in GOLDEN earns one encourager (spec's ~1.5–2 s)...
AUTO_ENCOURAGER_QUIET_S = float(os.getenv("AUTO_ENCOURAGER_QUIET_S", "1.75"))
# ...at most one per this many seconds, so encouragers never machine-gun.
AUTO_ENCOURAGER_COOLDOWN_S = float(os.getenv("AUTO_ENCOURAGER_COOLDOWN_S", "8"))
# Quiet this long triggers the end-of-turn officer (app/cds.py).
AUTO_EOT_QUIET_S = float(os.getenv("AUTO_EOT_QUIET_S", "3.0"))
# Officer fail-soft: with the officer unavailable, quiet this long counts as
# a finished thought. Longer than AUTO_EOT_QUIET_S on purpose — err toward
# waiting.
AUTO_EOT_FALLBACK_S = float(os.getenv("AUTO_EOT_FALLBACK_S", "5.0"))
# Pre-synthesise the top agenda question during the patient's turn (slice 4).
AUTO_PRESYNTH = os.getenv("AUTO_PRESYNTH", "true").lower() != "false"
# D2 posture (owner decision 2026-08-16): a CDS pass after every answer,
# questions only from the fresh agenda. Flippable so the mock-patient round
# can compare postures as a recorded per-run threshold (slice 4).
AUTO_STRICT_REVISE = os.getenv("AUTO_STRICT_REVISE", "true").lower() != "false"


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

    # Phase 7b: one consultation-linked audit row with the whole toggle
    # history, so a study arm is one query — the live face.toggled rows
    # carry only the session id, because no consultation row existed yet.
    if entry.get("face_toggles"):
        modes = sorted({t["mode"] for t in entry["face_toggles"] if "mode" in t})
        await audit.log(user["id"], "face.arms", "consultation", cid,
                        {"toggles": entry["face_toggles"],
                         "face_ever_on": any(t["on"] for t in entry["face_toggles"]),
                         "modes": modes})

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
    # Register the waiter BEFORE queueing, so the pipeline cannot reach the
    # count before the doctor's answer could possibly release it. Only the
    # normal Stop path has a client to ask; a grace-period finalisation has
    # nobody at the screen, so it never registers and never waits.
    if not connection_lost:
        expect_declaration(cid)
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


def _auto_needs_disclosure(utterance: auto_mode.Utterance) -> bool:
    """The disclosure lock for the auto path — the same coverage as
    `_needs_disclosure`, on the whitelist types: every agenda question and
    every template question, plus the gated phrases; not the disclosure
    itself and not the encouragers."""
    if isinstance(utterance, auto_mode.PhraseUtterance):
        return utterance.phrase_id in speech.DISCLOSURE_GATED_PHRASES
    return True


def _nudge_refusal(entry: dict) -> str | None:
    """The silence nudge's cage, server-enforced (Phase 7b session 3): one
    shot per consultation, only after the invitation has played through,
    and only while enabled. Returns the refusal reason, or None if the
    nudge may fire. Shared by the tap path and the auto path so the cage
    cannot drift between them."""
    if not SILENCE_NUDGE_ENABLED:
        return "the silence nudge is disabled"
    if not entry["invitation_completed"]:
        return "the silence nudge only follows a completed invitation"
    if entry["nudge_used"]:
        return "the silence nudge has already been used this consultation"
    return None


def _speak_message(utterance: speech.Utterance, msg_type: str) -> dict:
    """The play command for the client: `speak_ready` for a tap, and —
    Phase 7c — `auto_speak` for a server-initiated utterance, built by the
    SAME function so the two can never differ in shape. The client plays
    both through one code path and reports the same lifecycle."""
    ready = {
        "type": msg_type, "utterance_id": utterance.utterance_id,
        "ref_id": utterance.ref_detail.get("id"),
        "duration_ms": utterance.duration_ms,
        # What the server decided to say. The client needs it to log
        # the utterance faithfully rather than by button label — it
        # showed "Disclosure" where the room heard three sentences
        # (2026-07-25 room test). This is the server TELLING the
        # client; it remains impossible for the client to supply text.
        "text": utterance.text,
        "url": f"/api/speech/{utterance.utterance_id}.wav"}
    if speech.BARGE_IN_ENABLED:
        # 7a session 3: the normalised playback envelope rides along so
        # the detector's threshold can follow what is actually being
        # rendered. Only when the flag is up — the shipped (off)
        # protocol is byte-identical to session 2's. A failure here
        # must not stop the system speaking: no envelope simply means
        # absolute-floor detection.
        try:
            ready["envelope"] = speech.playback_envelope(utterance.wav)
            ready["envelope_window_ms"] = speech.ENVELOPE_WINDOW_MS
        except Exception as exc:  # noqa: BLE001 - comfort, not speech
            logger.warning("No playback envelope for %s: %s",
                           utterance.utterance_id, exc)
    return ready


async def issue_auto_speak(state, entry: dict, websocket, utterance: auto_mode.Utterance,
                           *, phase, trigger: dict | None = None,
                           detail: dict | None = None) -> speech.Utterance:
    """Server-initiated speak — Phase 7c slice 2 (PHASE_7C_SPEC.md §3, §4,
    §11). NOTHING CALLS THIS YET: the controller wiring that will (slice
    3) is not built, so the running app's behaviour is unchanged by its
    existence. It is here, tested, so that slice 3 wires an existing path
    rather than inventing one under pressure.

    The auto path reuses the tap pipeline end to end and adds no
    mechanism: the same one-utterance-at-a-time guard, the same
    disclosure lock (hard rule 4), the same nudge cage, the same
    SpeechService (cache, `SPEECH_MAX_UTTERANCE_S` cap), the same
    `pending_utterance` slot — so `speak_started`/`speak_ended` and the
    exclusion window work on an auto utterance exactly as on a tap. The
    client is sent `auto_speak`, built by `_speak_message` — the same
    shape as `speak_ready`.

    What differs from a tap: the input is a WHITELIST TYPE, never a
    message (hard rule 1 by construction — see app/auto_mode.py), and
    refusals RAISE to the caller instead of being answered to a client,
    because the caller is the server. Every refusal is still audited as
    `speech.failed` with via="auto". A synthesis fault or an unavailable
    synthesiser is additionally shown to the client as `speak_refused`,
    exactly as for a tap: a dead speaker must look like a fault, never
    like a system that chose not to speak. Guard refusals (already in
    flight, disclosure not given) are the caller's to handle — requeue,
    or fix the wiring — and are not shown.

    Face auto-on at a spoken disclosure (owner decision 2026-07-28) is
    NOT done here: `handle_face` lives in the connection; the wiring that
    issues an auto disclosure calls it, as `handle_speak` does today.
    """
    session: LiveSession = entry["session"]
    user = entry["user"]
    phase_value = str(getattr(phase, "value", phase))
    trigger = dict(trigger or {})

    async def refuse(reason: str, exc: type[Exception] = speech.SpeechRefused,
                     *, tell_client: bool = False) -> None:
        await audit.log(user["id"], "speech.failed", None, None,
                        {"reason": reason, "via": "auto", "phase": phase_value})
        if tell_client:
            await websocket.send_json({"type": "speak_refused", "detail": reason})
        raise exc(reason)

    if not isinstance(utterance, (auto_mode.PhraseUtterance, auto_mode.TemplateUtterance,
                                  auto_mode.AgendaUtterance)):
        # The type system is the first line; this is the second. A bare
        # string here is the auto path's equivalent of a `speak` carrying
        # text, and it is refused and audited the same way.
        await refuse("the auto path speaks only a whitelist utterance "
                     f"(got {type(utterance).__name__})")
    if session.speaking or entry["pending_utterance"] is not None:
        # One utterance at a time, queue depth zero (7a spec §2.3).
        await refuse("an utterance is already in flight")
    if not entry["disclosed"] and _auto_needs_disclosure(utterance):
        await refuse("the patient has not been told they are talking to a machine — "
                     "play the disclosure, or tick 'disclosure given'")
    if (isinstance(utterance, auto_mode.PhraseUtterance)
            and utterance.phrase_id == "silence_nudge"):
        cage = _nudge_refusal(entry)
        if cage is not None:
            await refuse(cage)
    try:
        prepared = await asyncio.to_thread(
            functools.partial(
                state.speech.prepare_auto, utterance, entry["agenda"],
                phase=phase_value, trigger=trigger, detail=detail, user_id=user["id"],
                # Server-side, from the session's own doctor account.
                doctor=speech.doctor_name_for(entry["user"])))
    except speech.SpeechRefused as exc:
        await refuse(str(exc))
    except speech.SpeechUnavailable as exc:
        await refuse(f"speech unavailable: {exc}", speech.SpeechUnavailable,
                     tell_client=True)
    except speech.SpeechFailed as exc:
        await refuse(f"synthesis failed: {exc}", speech.SpeechFailed, tell_client=True)
    entry["pending_utterance"] = prepared
    if prepared.ref_detail.get("id") == "silence_nudge":
        entry["nudge_used"] = True     # marked used at REQUEST, as for a tap
    await audit.log(user["id"], "speech.requested", None, None,
                    {"utterance_id": prepared.utterance_id,
                     "ref_kind": prepared.ref_kind,
                     "ref_detail": prepared.ref_detail,
                     "stale": prepared.stale,
                     "via": "auto", "phase": phase_value, "trigger": trigger})
    await websocket.send_json(_speak_message(prepared, "auto_speak"))
    return prepared


def _new_auto_state() -> dict:
    """Phase 7c: one session's auto-mode state — the pure controller with an
    injected monotonic clock, and the wiring's bookkeeping around it. Only
    ever built when AUTO_MODE_ENABLED is true."""
    return {
        "controller": auto_mode.AutoModeController(clock=time.monotonic),
        "encourager_index": 0,        # rotation through ENCOURAGER_IDS
        "last_encourager_at": None,   # monotonic seconds of the last one issued
        "last_quiet_s": None,         # to notice a fresh quiet span
        "officer_task": None,         # the in-flight end-of-turn call, if any
        "officer_quiet_s": None,      # the quiet the running officer was asked about
        "officer_last_run_quiet_s": None,   # per span: re-run when quiet grows by EOT
        "officer_verdict": None,      # the last verdict in this span
        "warm_task": None,
        # Slice 4: the question phases (see the wiring's vocabulary note).
        "turn_ended": False,
        "awaiting_answer": False,
        "revision": None,             # None | "requested" | "running"
        "bridge_used": False,
        "queued": None,               # the prepared next utterance (a plan dict)
        "plan_task": None,            # topic call + pre-synthesis in flight
        "opened_topics": set(),       # D3: case-folded topics asked open-form
        "handover": None,             # None | "anything_else" | "final"
        "anything_else_done": False,  # at most once per session
        "last_issued": None,          # the last queued utterance issued, for requeue
        "last_asked_text": None,
    }


def _thresholds_in_force() -> dict:
    """Every auto-mode setting in force, recorded per run on auto.enabled
    (spec §9 / the prereg: thresholds recorded per run, both D2 postures
    visible as a recorded value)."""
    from app import cds as cds_module
    return {
        "golden_s": AUTO_GOLDEN_MINUTES_S,
        "encourager_quiet_s": AUTO_ENCOURAGER_QUIET_S,
        "encourager_cooldown_s": AUTO_ENCOURAGER_COOLDOWN_S,
        "eot_quiet_s": AUTO_EOT_QUIET_S,
        "eot_fallback_s": AUTO_EOT_FALLBACK_S,
        "officer_timeout_s": cds_module.AUTO_OFFICER_TIMEOUT_S,
        "topic_timeout_s": cds_module.AUTO_TOPIC_TIMEOUT_S,
        "presynth": AUTO_PRESYNTH,
        "strict_revise": AUTO_STRICT_REVISE,
        "politeness_floor_rms": speech.BARGE_IN_RMS_THRESHOLD,
    }


def _cancel_playback(entry: dict, reason: str, *,
                     unplayed_reason: str = "failed_to_play") -> dict | None:
    """End any in-flight utterance without a client `speak_ended`.

    Used on reconnect and at session end — and, since Phase 7c slice 5, by
    the server-initiated stop. The window closes at whatever it had
    reached; an utterance that never started leaves no window at all and
    is recorded `unplayed_reason` — `failed_to_play` by default (no window
    means no exclusion, which is correct, because nothing was played into
    the room), or the server's own reason when the server is the one
    cutting it (an urgency pause cancels a not-yet-started utterance
    too, and the row should say why). Returns the row written, or None.
    """
    utterance = entry.get("pending_utterance")
    if utterance is None:
        return None
    session: LiveSession = entry["session"]
    span = session.close_speaking_window(reason) if session.speaking else None
    row = {
        "utterance_id": utterance.utterance_id, "text": utterance.text,
        "ref_kind": utterance.ref_kind, "ref_detail": utterance.ref_detail,
        "cds_rationale": utterance.cds_rationale, "voice": utterance.voice,
        "synth_ms": utterance.synth_ms, "stale": utterance.stale,
        "end_reason": reason if span is not None else unplayed_reason,
        "cut_latency_ms": None,
        "start_byte": span["start_byte"] if span else None,
        "end_byte": span["end_byte"] if span else None,
        "started_offset_ms": bytes_to_ms(span["start_byte"]) if span else None,
        "ended_offset_ms": bytes_to_ms(span["end_byte"]) if span else None,
    }
    entry["utterances"].append(row)
    entry["pending_utterance"] = None
    return row


async def cancel_auto_playback(entry: dict, websocket, reason: str) -> dict | None:
    """The server-initiated stop (Phase 7c slice 5, PHASE_7C_SPEC.md §7).

    Cuts the current utterance NOW: the client is told to stop
    (`auto_stop`, carrying the reason, which it handles through exactly
    its own Esc/Stop path), the exclusion window closes at the cut and the
    row is resolved with the named reason SERVER-SIDE — an utterance not
    yet started records the reason too, with no span — and the queued
    auto utterance and any plan in flight are cleared. The client's echoed
    speak_ended is then recognised by `server_cancelled_id`, not refused.
    Safe with nothing in flight: nothing is sent, nothing breaks. Any
    utterance is cut, tap or auto — an urgency pause is not the moment
    for anyone's question. This slice's caller passes `urgency_pause`;
    the reason travels in the message so later callers can reuse it.
    Returns the row resolved, or None.
    """
    auto = entry.get("auto")
    if auto is not None:
        auto["queued"] = None
        if auto.get("plan_task") is not None and not auto["plan_task"].done():
            auto["plan_task"].cancel()
        auto["plan_task"] = None
    utterance = entry.get("pending_utterance")
    if utterance is None:
        return None
    await websocket.send_json({"type": "auto_stop", "reason": reason,
                               "utterance_id": utterance.utterance_id})
    entry["server_cancelled_id"] = utterance.utterance_id
    row = _cancel_playback(entry, reason, unplayed_reason=reason)
    if entry.get("face") is not None and row is not None and row["start_byte"] is not None:
        entry["face"].on_system_speech_ended()
    if (auto is not None and auto.get("last_issued")
            and auto["last_issued"].get("utterance_id") == utterance.utterance_id):
        auto["last_issued"] = None       # cut, not aborted: never requeued
    if row is not None and row["start_byte"] is not None:
        # It played into the room and was cut: audited as every other end
        # of playback is, marked as the server's cut. An unplayed one is
        # on the row alone — nothing was spoken.
        await audit.log(entry["user"]["id"], "speech.spoken", None, None,
                        {"utterance_id": utterance.utterance_id, "reason": reason,
                         "server_stop": True,
                         "excluded_ms": bytes_to_ms(row["end_byte"] - row["start_byte"])})
    logger.info("Server stop (%s) cut utterance %s", reason, utterance.utterance_id)
    return row


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
            "detail": "This consultation is already streaming from another tab "
                      "or device on your account. Close the other tab, or carry "
                      "on recording there — one live consultation at a time.",
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
            # The blocker here is a live STREAM, not a queue entry, so name the
            # user holding it — and the patient too when the session is linked,
            # since that is what makes it recognisable in the room.
            holder = (active["user"].get("display_name")
                      or active["user"]["username"])
            in_consultation = await frontdesk.current_entry()
            patient = in_consultation["name"] if in_consultation else None
            await websocket.send_json({
                "type": "busy",
                "detail": (f"{holder} is already recording a live consultation"
                           + (f" with {patient}" if patient else "")
                           + ". One live consultation at a time — it must be "
                             "stopped before another can start."),
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
            # Phase 7b: the face driver (created only when toggled on;
            # None = off, and off means NO face_state traffic at all —
            # off is the control arm of a study, not a blanked panel)
            # and the toggle history for study-arm reconstruction.
            "face": None,
            "face_toggles": [],
            # Session 3: a manual face-off is FINAL for the session — the
            # disclosure auto-on never overrides it (the doctor always
            # wins) — and the silence nudge's cage: at most once per
            # consultation, only after the invitation has played through.
            "face_manual_off": False,
            "invitation_completed": False,
            "nudge_used": False,
            # The last patient_affect value LOGGED for this session, so the
            # log line can say whether the verdict changed. Sentinel: no
            # assessment has been logged yet. Lives in the entry so it
            # survives a reconnect, like everything else here.
            "affect_last_logged": _AFFECT_UNLOGGED,
            # Phase 7c: the auto-mode controller and its bookkeeping —
            # constructed ONLY behind the gate. None means 7c does not
            # exist for this session: no controller, no quiet handling, no
            # auto messages; the app behaves exactly as before 7c.
            "auto": _new_auto_state() if AUTO_MODE_ENABLED else None,
            # Phase 7c slice 5: the utterance the SERVER last cut (auto_stop),
            # so the client's echoed speak_ended is recognised, not refused.
            "server_cancelled_id": None,
        }
        sessions[session_id] = entry
        logger.info("Live session %s started by %s", session_id, user["username"])
        if entry["auto"] is not None:
            # Per-session warm (spec §9): the two doctor-named phrases for
            # THIS doctor's name, off the loop, logged and never fatal — the
            # rest of the table was warmed at service start.
            entry["auto"]["warm_task"] = asyncio.create_task(asyncio.to_thread(
                state.speech.presynthesise_phrases, speech.doctor_name_for(user)))

    # Session 3: the client runs the silence-nudge quiet-window detector
    # (it holds the mic analyser and sees the transcript stream), so it is
    # told the server's settings — env lives server-side only. The SERVER
    # still enforces the cage regardless of what the client does.
    #
    # 7a session 3: the barge-in detector is configured the same way. Its
    # loopback level is read from the newest `speech.sound_check` audit
    # row for THIS doctor — measured once in the room, never re-measured
    # here (spec Part 10.5: that reuse is why the rows store raw numbers).
    # No row means no envelope prediction; the client falls back to its
    # absolute floor. The detector is a comfort feature (D5): whatever the
    # client does with this config, exclusion stays structural.
    loopback = None
    if speech.BARGE_IN_ENABLED:
        try:
            loopback = await audit.latest_detail("speech.sound_check", user["id"])
        except Exception as exc:  # noqa: BLE001 - config, not the consultation
            logger.warning("Could not read sound-check rows for barge-in: %s", exc)
    # Part 10 amendment: the threshold scale is the DETECTOR-stream
    # residual when the row carries one; the raw loopback stays as the
    # sanity upper bound. A residual above raw is physically wrong — the
    # value is clamped and the anomaly audited, never silently used.
    scale = speech.barge_in_scale(loopback)
    if scale["anomaly"] is not None:
        await audit.log(user["id"], "speech.barge_in_anomaly", None, None,
                        {"kind": "residual_exceeds_raw_loopback",
                         **scale["anomaly"],
                         "device_label": (loopback or {}).get("device_label")})
        logger.warning("Barge-in scale anomaly for %s: residual %s > raw %s",
                       user["username"], scale["anomaly"]["residual_peak_rms"],
                       scale["anomaly"]["raw_peak_rms"])
    speech_config = {
        "type": "speech_config",
        "silence_nudge_enabled": SILENCE_NUDGE_ENABLED,
        "silence_nudge_s": SILENCE_NUDGE_S,
        "barge_in": {
            "enabled": speech.BARGE_IN_ENABLED,
            "min_ms": speech.BARGE_IN_MIN_MS,
            "margin": speech.BARGE_IN_MARGIN,
            "abs_floor": speech.BARGE_IN_RMS_THRESHOLD,
            "loopback_peak_rms": scale["raw_peak_rms"],
            "residual_peak_rms": scale["residual_peak_rms"],
            "loopback_device": (loopback or {}).get("device_label"),
        },
    }
    if AUTO_MODE_ENABLED:
        # Phase 7c (spec §5): the client's quiet reporter is told the
        # server's thresholds — env lives server-side only. Sent only when
        # the gate is up, so the shipped (off) protocol is byte-identical.
        speech_config["auto"] = {
            "enabled": True,
            "encourager_quiet_s": AUTO_ENCOURAGER_QUIET_S,
            "eot_quiet_s": AUTO_EOT_QUIET_S,
            "eot_fallback_s": AUTO_EOT_FALLBACK_S,
        }
    await websocket.send_json(speech_config)
    if entry["auto"] is not None:
        # Phase 7c: the server's word on auto mode, on connect and on
        # reconnect — the client's reporter and (slice 6) the pill follow
        # it. Never sent when the gate is down.
        _ctl = entry["auto"]["controller"]
        await websocket.send_json({"type": "auto_toggled",
                                   "on": _ctl.phase is not auto_mode.AutoPhase.OFF,
                                   "phase": _ctl.phase.value})

    session: LiveSession = entry["session"]
    engine: CDSEngine = state.cds_engine
    rag: RAGService = state.rag

    # CDS side tasks are per-connection (cancelled on disconnect); their
    # accumulated state lives in the entry and survives reconnects.
    cds_task: asyncio.Task | None = None
    cds_failures = 0
    gl_task: asyncio.Task | None = None
    gl_conditions: tuple = ()  # conditions the current guideline panel is for
    face_task: asyncio.Task | None = None  # Phase 7b tick loop, per-connection
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
                # Phase 7c (D2): the pass auto mode asked for has landed —
                # plan the next ask from THIS version only.
                if entry["auto"] is not None and entry["auto"]["revision"] == "running":
                    await on_fresh_agenda(assessment_version)
                for action in entry["assessment"].get("urgent_actions", []):
                    entry["urgent_first_fired"].setdefault(
                        action["action"], round(session.audio_seconds, 1)
                    )
                await websocket.send_json(
                    {"type": "cds", "assessment": entry["assessment"]}
                )
                # Phase 7b: what the model actually said about the patient,
                # one line per assessment. Consultation 464 could not be
                # explained because this verdict was recorded NOWHERE — not
                # persisted, not audited, not logged.
                #
                # OUTSIDE the face guard on purpose: face-off is a study
                # arm and the affect stream is wanted from it too. EVERY
                # assessment is logged, not only changes — a repeated
                # verdict is evidence. Since c526ffc (2026-08-01) the
                # affect is its own call inside CDSEngine.update, with
                # patient_affect a REQUIRED field of that call's schema
                # and a fail-soft to "neutral" when the call fails — so
                # ABSENT should now be impossible here. It stays in the
                # log's vocabulary as a tripwire, not a state: a sighting
                # of ABSENT in PATIENT_AFFECT would itself be a finding
                # (the merge in app/cds.py not happening), never a
                # judgement about the patient.
                #
                # A DEBUGGING INSTRUMENT, deliberately: no table, no
                # migration, no audit row. The durable version — affect
                # persisted with the assessment, so a past consultation
                # can be replayed through the face — is a separate job
                # (PHASE_7B_FACE_DRIVE_SPEC.md § 6).
                affect_value = entry["assessment"].get("patient_affect")
                affect_field = affect_value if affect_value else "ABSENT"
                previous = entry["affect_last_logged"]
                logger.info(
                    "PATIENT_AFFECT session=%s at=%.1fs value=%s changed=%s",
                    session_id, session.audio_seconds, affect_field,
                    "first" if previous is _AFFECT_UNLOGGED
                    else ("yes" if affect_field != previous else "no"))
                entry["affect_last_logged"] = affect_field
                # The affect verdict arrives merged into the assessment
                # but is its OWN model call since c526ffc — stateless,
                # transcript-only, fail-soft to "neutral" (app/cds.py).
                # Urgency is NOT an input here.
                if entry["face"] is not None:
                    entry["face"].on_affect(
                        entry["assessment"].get("patient_affect"))
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
        # First call of the session: fire on the FIRST committed turn
        # (cds_sent_len == 0 means nothing has ever been handed to the
        # CDS engine — it survives reconnects with the entry). The
        # revision rules already tolerate a thin first list: the prompt
        # says "early, prefer a short list", and the pinned-name rule
        # simply starts from a smaller one (session-4 report).
        first_call_due = (
            CDS_FIRST_CALL_ON_FIRST_TURN
            and entry["cds_sent_len"] == 0
            and len(transcript) > 0
        )
        # Phase 7c (D2 strict-revise): auto mode's post-answer pass runs the
        # moment it is asked for, bypassing CDS_MIN_NEW_CHARS — the whole
        # point is a fresh agenda after every answer.
        auto_due = entry["auto"] is not None and entry["auto"]["revision"] == "requested"
        if (
            cds_task is None
            and cds_failures < CDS_MAX_FAILURES
            and (first_call_due or auto_due
                 or len(transcript) - entry["cds_sent_len"] >= CDS_MIN_NEW_CHARS)
        ):
            entry["cds_sent_len"] = len(transcript)
            if auto_due:
                entry["auto"]["revision"] = "running"
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

    async def handle_speak(payload: dict, via: str = "tap") -> None:
        """Prepare an utterance from a REFERENCE — never from client text.

        PHASE_7A_SPEC.md §2.1. This is where hard rule 1 is enforced in
        code: there is no branch that reads words from the client, so no
        client — buggy, modified or compromised — can make the system
        advise, reassure or diagnose to the patient.

        `via` says what initiated the request — "tap", "auto_invitation"
        (the server chaining the invitation after a completed disclosure),
        or "silence_nudge" (the client's quiet-window detector) — and is
        audited. The nudge is THE ONLY AUTONOMOUS UTTERANCE in 7a/7b and
        its cage is enforced HERE, server-side, not only in the client:
        one shot per consultation, only after the invitation has played
        through, and disclosure-gated like every clinical phrase. Its
        guard against generalisation was retired in Phase 7c slice 3 —
        the controller's encourager loop is that generalisation, behind
        AUTO_MODE_ENABLED; with auto mode off, the cage holds exactly as
        before.
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
        if (payload.get("ref") or {}).get("id") == "silence_nudge":
            # The nudge's cage (see the docstring): server-enforced,
            # because a client-side-only cage is a suggestion.
            cage = _nudge_refusal(entry)
            if cage is not None:
                await refuse_speech(cage)
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
        if utterance.ref_detail.get("id") == "silence_nudge":
            # Marked used at REQUEST, not completion: at most once means
            # once, even if the one firing is cut off.
            entry["nudge_used"] = True
        if via == "tap" and entry["auto"] is not None:
            # Phase 7c: a doctor's tap while auto mode is on is an
            # intervention — audited, and it displaces the queued auto ask.
            await on_doctor_tap(utterance)
        # Auto-on at Disclosure (owner decision 2026-07-28): the SPOKEN
        # disclosure switches the face on — the "in my own words" tick
        # does not (the owner named the button). Never after a manual
        # off, and never when the flag is down (the face-off study arm).
        if (FACE_AUTO_ON_DISCLOSURE
                and utterance.ref_detail.get("id") == "disclosure"
                and entry["face"] is None
                and not entry["face_manual_off"]):
            await handle_face({"on": True}, via="disclosure_auto")
        quiet_s = payload.get("quiet_s")
        await audit.log(user["id"], "speech.requested", None, None,
                        {"utterance_id": utterance.utterance_id,
                         "ref_kind": utterance.ref_kind,
                         "ref_detail": utterance.ref_detail,
                         "stale": utterance.stale,
                         "via": via,
                         # The measured quiet duration, nudges only —
                         # calibration data for SILENCE_NUDGE_S.
                         **({"quiet_s": round(float(quiet_s), 1)}
                            if quiet_s is not None else {})})
        # The play command, built by the same function that builds the
        # auto path's `auto_speak` (Phase 7c) — one shape, one code path
        # on the client.
        await websocket.send_json(_speak_message(utterance, "speak_ready"))

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
        # Phase 7b: the same server-held speak window that drives
        # transcript exclusion also tells the face we started talking.
        if entry["face"] is not None:
            entry["face"].on_system_speech_started()
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
        reason = payload.get("reason") or "complete"
        if (utterance is not None and not session.speaking
                and reason == "politeness_abort"
                and payload.get("utterance_id") == utterance.utterance_id):
            # Phase 7c (PHASE_7C_SPEC.md §5): the client re-checked its own
            # microphone immediately before playback and found speech had
            # resumed, so it declined to play. Nothing entered the room, no
            # window was opened, there is nothing to exclude — the row says
            # so (end_reason politeness_abort, no span) and the slot is
            # released. Requeueing the utterance is the controller's job
            # (slice 3/4); here it is simply not lost from the record.
            record_utterance(utterance, None, "politeness_abort")
            entry["pending_utterance"] = None
            if utterance.ref_detail.get("via") == "auto":
                await on_auto_utterance_ended(utterance, "politeness_abort")
            rms = payload.get("rms")
            await audit.log(user["id"], "speech.politeness_abort", None, None,
                            {"utterance_id": utterance.utterance_id,
                             "via": utterance.ref_detail.get("via", "tap"),
                             "phase": utterance.ref_detail.get("phase"),
                             # The client's reading at the moment it declined
                             # — calibration data for the floor it compared
                             # against, like quiet_s for the nudge.
                             **({"rms": round(float(rms), 5)} if rms is not None else {})})
            return
        if (utterance is None and entry.get("server_cancelled_id") is not None
                and payload.get("utterance_id") == entry["server_cancelled_id"]):
            # Phase 7c slice 5: the client's echo of a server-initiated stop
            # (auto_stop). The server resolved the row when it cut; this is
            # the client confirming, not a stray message — nothing to refuse.
            entry["server_cancelled_id"] = None
            return
        if utterance is None or not session.speaking:
            await refuse_speech("speak_ended with no window open")
            return
        if reason not in system_utterances.END_REASONS:
            reason = "complete"
        span = session.close_speaking_window(reason)
        if entry["face"] is not None:
            entry["face"].on_system_speech_ended()
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
        # The nudge window opens only once the invitation has PLAYED
        # THROUGH — a cut-off invitation opens nothing (session 3).
        if utterance.ref_detail.get("id") == "invitation" and reason == "complete":
            entry["invitation_completed"] = True
            # Phase 7c: GOLDEN starts when the invitation's speak_ended
            # arrives — the prereg's metric-3 zero point — whichever path
            # spoke it (auto, the disclosure chain, or a tap).
            auto = entry["auto"]
            if (auto is not None and auto["controller"].is_legal(
                    auto_mode.AutoEvent.INVITATION_COMPLETED)):
                await auto_transition(auto["controller"].invitation_completed())
        if utterance.ref_detail.get("via") == "auto":
            await on_auto_utterance_ended(utterance, reason)
        # Auto-chain (owner decision 2026-07-28): a disclosure that played
        # THROUGH is followed by the invitation, through the NORMAL speak
        # path — its own utterance, its own audit rows, and behind the
        # same disclosure lock. That lock is the structural safety: a
        # cut-off disclosure never reaches here (reason != complete), and
        # even if this condition regressed, the session would have no
        # disclosure recorded and handle_speak would refuse the
        # invitation anyway. Stop/Esc cuts the chained utterance like any
        # other.
        if utterance.ref_detail.get("id") == "disclosure" and reason == "complete":
            auto = entry["auto"]
            if (auto is not None and auto["controller"].is_legal(
                    auto_mode.AutoEvent.DISCLOSURE_COMPLETED)):
                # Phase 7c (one-tap start, owner decision 2026-08-16): auto
                # mode spoke — or the doctor tapped — the disclosure while
                # the machine waited in DISCLOSURE. It has now been GIVEN
                # (played through; a cut-off one never reaches here), so
                # the machine moves on and the invitation is chained
                # through the AUTO path, its own row and audit, via=auto.
                await auto_transition(auto["controller"].disclosure_completed(),
                                      detail={"disclosure": "spoken"})
                await auto_issue(auto_mode.PhraseUtterance("invitation"),
                                 phase=auto["controller"].phase,
                                 trigger={"via": "auto_chain"})
            elif AUTO_INVITATION_AFTER_DISCLOSURE:
                await handle_speak({"ref": {"kind": "phrase", "id": "invitation"}},
                                   via="auto_invitation")

    async def handle_face(payload: dict, via: str = "manual") -> None:
        """Phase 7b: toggle the face. OFF is a first-class state — the
        control arm of the planned CARE study — so off means the driver is
        gone and the server sends no face_state messages at all, not a
        blanked panel. Every toggle is audited (hard rule 5) with `via`
        ("manual" | "disclosure_auto") and confirmed back to the client,
        which renders the card only on confirmation. A MANUAL off is final
        for the session: the disclosure auto-on checks the flag set here
        and never overrides it — the doctor always wins."""
        nonlocal face_task
        on = bool(payload.get("on"))
        driver: face.FaceDriver | None = None
        if on:
            if entry["face"] is not None and not entry["face"].stopped:
                return  # already on — idempotent, nothing to re-audit
            driver = face.FaceDriver()
            entry["face"] = driver
            driver.on_consultation_started()
            # The tick task starts AFTER the confirmation below, so the
            # client always sees face_toggled before the first face_state.
        else:
            if entry["face"] is None and face_task is None:
                return  # already off
            if via == "manual":
                entry["face_manual_off"] = True
            if entry["face"] is not None:
                entry["face"].stop()
                entry["face"] = None
            if face_task is not None:
                face_task.cancel()
                face_task = None
        # The expression mode rides every on-toggle (an off-toggle has no
        # running mode), so feedback sessions can be correlated with what
        # the face was actually running — full range vs the clinical arm.
        toggle = {"on": on, "at_audio_s": round(session.audio_seconds, 1),
                  "via": via}
        if driver is not None:
            toggle["mode"] = driver.mode
            # ...and the drive version alongside it, so a mock-patient
            # session can always be tied to the drive it ran, not just to
            # the arm. The 463 drive and its replacement are both "full".
            toggle["drive"] = face.FACE_DRIVE_VERSION
        entry["face_toggles"].append(toggle)
        # The consultation row does not exist until Stop, so this row
        # carries the session; _complete_session writes the
        # consultation-linked `face.arms` summary the study reads.
        await audit.log(user["id"], "face.toggled", None, None,
                        {"session_id": session_id,
                         "patient_id": entry["patient_id"], **toggle})
        await websocket.send_json({"type": "face_toggled", "on": on})
        if driver is not None:
            face_task = asyncio.create_task(driver.run(websocket.send_json))

    # ================================ Phase 7c slice 3: auto mode, wired
    # through GOLDEN and dark. Every function below is a no-op unless
    # entry["auto"] exists, and it exists only when AUTO_MODE_ENABLED is
    # true (see _new_auto_state). The controller (app/auto_mode.py) owns
    # the phase; this wiring owns the events and consults controller.phase
    # / is_legal() before firing — the machine's strict legality is
    # deliberate, and a late timer or a second hand-back must never raise
    # out of the receive loop.

    async def auto_transition(transition: auto_mode.Transition,
                              detail: dict | None = None) -> None:
        """Audit auto.phase for every transition (spec §11: from, to,
        trigger), with the session's audio time and whatever the caller
        knows about why (quiet seconds, a hand-back, an officer timing)."""
        await audit.log(user["id"], "auto.phase", None, None,
                        {"session_id": session_id,
                         "from": transition.from_phase.value,
                         "to": transition.to_phase.value,
                         "trigger": transition.trigger.value,
                         "at_audio_s": round(session.audio_seconds, 1),
                         **({"detail": detail} if detail else {})})
        logger.info("Live session %s: auto %s → %s (%s)", session_id,
                    transition.from_phase.value, transition.to_phase.value,
                    transition.trigger.value)

    async def auto_issue(utterance: auto_mode.Utterance, *, phase, trigger: dict,
                         detail: dict | None = None) -> speech.Utterance | None:
        """Speak through the auto path (issue_auto_speak) from inside the
        connection. A guard refusal — already in flight, disclosure not
        given, the nudge cage — is the controller's business, logged and
        swallowed here (the moment has passed; nothing is requeued in this
        slice); a synthesis fault has already been audited and shown to
        the client by issue_auto_speak. A spoken disclosure through this
        path switches the face on exactly as handle_speak does (owner
        decision 2026-07-28), never over a manual off."""
        try:
            prepared = await issue_auto_speak(state, entry, websocket, utterance,
                                              phase=phase, trigger=trigger, detail=detail)
        except speech.SpeechRefused as exc:
            logger.info("Live session %s: auto utterance not issued: %s", session_id, exc)
            return None
        except (speech.SpeechUnavailable, speech.SpeechFailed) as exc:
            logger.warning("Live session %s: auto utterance failed: %s", session_id, exc)
            return None
        if (FACE_AUTO_ON_DISCLOSURE
                and prepared.ref_detail.get("id") == "disclosure"
                and entry["face"] is None
                and not entry["face_manual_off"]):
            await handle_face({"on": True}, via="disclosure_auto")
        return prepared

    async def refuse_auto(reason: str) -> None:
        """A refused auto toggle is answered, never swallowed — the pill
        (slice 6) shows the reason; nothing was done, so nothing is
        audited."""
        logger.info("Live session %s: auto toggle refused: %s", session_id, reason)
        await websocket.send_json({"type": "auto_refused", "detail": reason})

    async def handle_auto(payload: dict, via: str = "manual") -> None:
        """The server-side auto on/off path the slice-6 Auto pill will call.

        ONE TAP starts the auto session (owner decision 2026-08-16, spec
        §10 as amended; replacing slice 3's disabled-until-disclosure
        rule). ON needs no utterance in flight, and then:
        - disclosure NOT yet given: it is spoken through the auto path
          (auto_issue — face auto-on included, exactly as handle_speak),
          the machine waits in DISCLOSURE, and when it plays THROUGH
          handle_speak_ended moves the machine on and chains the
          invitation through the auto path; a cut-off disclosure chains
          nothing, exactly as the tap chain behaves;
        - disclosure already given: the DISCLOSURE step is a pass-through
          (audited as such) and the invitation is spoken through the auto
          path unless it has already played through this session — then
          GOLDEN starts at the toggle and the audit detail says so.
        Either way GOLDEN starts when the invitation's speak_ended arrives
        (handle_speak_ended) — the prereg's metric-3 zero point. If the
        first utterance cannot be issued, enabling fails as a unit and the
        machine is switched back off. Hard rule 4 holds by construction:
        the invitation is disclosure-gated in issue_auto_speak, and the
        chain only runs on a disclosure that played through.

        OFF is legal and immediate from every state (hard rule 3): the
        machine goes to OFF, the officer is cancelled, and nothing more is
        issued. An utterance already playing finishes or is cut by the
        doctor's Stop/Esc as today — there is no server-to-client stop.
        """
        auto = entry["auto"]
        if auto is None:
            await refuse_auto("auto mode is not enabled on this server (AUTO_MODE_ENABLED)")
            return
        if user["id"] != entry["user"]["id"]:
            await refuse_auto("only the doctor running this consultation may toggle auto mode")
            return
        ctl: auto_mode.AutoModeController = auto["controller"]
        on = bool(payload.get("on"))
        if on:
            if ctl.phase is not auto_mode.AutoPhase.OFF:
                await websocket.send_json({"type": "auto_toggled", "on": True,
                                           "phase": ctl.phase.value})
                return   # already on — idempotent, nothing to re-audit
            if session.speaking or entry["pending_utterance"] is not None:
                await refuse_auto("an utterance is in flight — try again when it has finished")
                return
            await audit.log(user["id"], "auto.enabled", None, None,
                            {"session_id": session_id, "via": via,
                             "disclosed": entry["disclosed"],
                             "at_audio_s": round(session.audio_seconds, 1),
                             # The thresholds in force, recorded per run.
                             "thresholds": _thresholds_in_force()})
            await auto_transition(ctl.enable())
            if not entry["disclosed"]:
                prepared = await auto_issue(auto_mode.PhraseUtterance("disclosure"),
                                            phase=ctl.phase, trigger={"via": "auto_enable"})
                if prepared is None:
                    await audit.log(user["id"], "auto.disabled", None, None,
                                    {"session_id": session_id, "via": "enable_failed",
                                     "at_audio_s": round(session.audio_seconds, 1)})
                    await auto_transition(ctl.auto_off(),
                                          detail={"reason": "disclosure_not_issued"})
                    await refuse_auto("auto mode could not speak the disclosure — "
                                      "see the speech error, then try again")
                    return
                await websocket.send_json({"type": "auto_toggled", "on": True,
                                           "phase": ctl.phase.value})
                return
            await auto_transition(ctl.disclosure_completed(),
                                  detail={"disclosure": "already_given"})
            if entry["invitation_completed"]:
                # The invitation played through before auto was switched
                # on (the doctor tapped Disclosure and the chain spoke it):
                # GOLDEN starts NOW, and the record says why the zero point
                # is the toggle rather than the invitation's end.
                await auto_transition(ctl.invitation_completed(),
                                      detail={"invitation": "already_completed"})
            else:
                prepared = await auto_issue(auto_mode.PhraseUtterance("invitation"),
                                            phase=ctl.phase, trigger={"via": "auto_enable"})
                if prepared is None:
                    await audit.log(user["id"], "auto.disabled", None, None,
                                    {"session_id": session_id, "via": "enable_failed",
                                     "at_audio_s": round(session.audio_seconds, 1)})
                    await auto_transition(ctl.auto_off(),
                                          detail={"reason": "invitation_not_issued"})
                    await refuse_auto("auto mode could not speak the invitation — "
                                      "see the speech error, then try again")
                    return
            await websocket.send_json({"type": "auto_toggled", "on": True,
                                       "phase": ctl.phase.value})
        else:
            if ctl.phase is auto_mode.AutoPhase.OFF:
                await websocket.send_json({"type": "auto_toggled", "on": False,
                                           "phase": ctl.phase.value})
                return   # already off
            await audit.log(user["id"], "auto.disabled", None, None,
                            {"session_id": session_id, "via": via,
                             "at_audio_s": round(session.audio_seconds, 1)})
            await auto_transition(ctl.auto_off())
            _cancel_officer(auto)
            auto.update(turn_ended=False, awaiting_answer=False, bridge_used=False,
                        handover=None, last_issued=None)
            await websocket.send_json({"type": "auto_toggled", "on": False,
                                       "phase": ctl.phase.value})

    def _cancel_officer(auto: dict) -> None:
        for key in ("officer_task", "plan_task"):
            task = auto.get(key)
            if task is not None and not task.done():
                task.cancel()
            auto[key] = None
        auto["officer_quiet_s"] = None
        auto["queued"] = None
        auto["revision"] = None

    # ------------------------------------------------------------------
    # Phase 7c slice 4: the question phases (spec §6, D2 and D3). Vocabulary
    # used below, all held in entry["auto"]:
    #   turn_ended       the current quiet span has been judged the end of a
    #                    turn (officer, or its silence fallback); reset by a
    #                    fresh span
    #   awaiting_answer  a question (or the anything-else phrase) has been
    #                    asked and the next turn end is its answer's end
    #   revision         None | "requested" | "running": the D2 strict-revise
    #                    CDS pass that must land before the next ask
    #   queued           the prepared next utterance (a plan dict), waiting
    #                    for a quiet report that permits it
    #   opened_topics    D3: topics already asked open-form, case-folded
    #   handover         None | "anything_else" | "final": where the
    #                    handover sequence stands

    def _request_revision(auto: dict, why: str) -> None:
        """D2: ask for a fresh CDS pass now (maybe_run_cds launches it,
        bypassing CDS_MIN_NEW_CHARS) and ask only from what it returns.
        Non-strict runs plan from the current agenda instead — unless it
        is empty, when the fresh pass is still needed before handover can
        be concluded (agenda-empty counts only on a post-answer revision)."""
        auto["bridge_used"] = False
        if AUTO_STRICT_REVISE or not (entry["agenda"].current and entry["agenda"].current.questions):
            auto["revision"] = "requested"
            logger.info("Live session %s: auto revision requested (%s)", session_id, why)
        else:
            _plan_from_agenda(auto, entry["agenda"].current_version, why=f"{why} (ask-from-current)")

    def _plan_from_agenda(auto: dict, version: int, *, why: str) -> None:
        """Choose the next utterance from agenda version `version` and
        prepare it in the background: the topic call (D1), then
        pre-synthesis (§9, AUTO_PRESYNTH). Empty agenda → the handover
        sequence (§6 as amended). Never plans while a plan is in flight."""
        if auto["plan_task"] is not None and not auto["plan_task"].done():
            return
        snapshot = entry["agenda"].get(version)
        questions = list(snapshot.questions) if snapshot else []
        if not questions:
            _plan_handover(auto, version)
            return
        auto["handover"] = None
        # The top question — but not the same words twice in a row when
        # there is any other to ask (re-asking is allowed and logged, a
        # ping-pong on identical text is bad manners).
        index = 0
        last = auto.get("last_asked_text")
        if last is not None and questions[0] == last and len(questions) > 1:
            index = 1
        auto["plan_task"] = asyncio.create_task(
            _prepare_question(auto, version, index, questions[index], why))

    def _plan_handover(auto: dict, version: int) -> None:
        """§6 as amended: agenda empty on a fresh post-answer revision →
        the anything-else phrase once, take its answer and revise; if the
        agenda refilled the flow returns to the questions; if still empty,
        the examination handover ends the auto run."""
        if not auto["anything_else_done"]:
            auto["handover"] = "anything_else"
            auto["queued"] = {"utterance": auto_mode.PhraseUtterance("anything_else"),
                              "kind": "anything_else", "text": speech.render_phrase("anything_else"),
                              "agenda_version": version, "topic": None, "open_form": None}
        else:
            auto["handover"] = "final"
            auto["queued"] = {"utterance": auto_mode.PhraseUtterance("examination_handover"),
                              "kind": "handover", "agenda_version": version,
                              "text": speech.render_phrase("examination_handover",
                                                           speech.doctor_name_for(entry["user"])),
                              "topic": None, "open_form": None}
        if AUTO_PRESYNTH:
            auto["plan_task"] = asyncio.create_task(_presynth(auto["queued"]["text"]))
        logger.info("Live session %s: auto handover step queued (%s)", session_id, auto["handover"])

    async def _presynth(text: str) -> None:
        try:
            await asyncio.to_thread(state.speech.synthesise, text)
        except Exception as exc:  # noqa: BLE001 - a fault surfaces at issue time as speak_refused
            logger.info("Live session %s: pre-synthesis skipped: %s", session_id, exc)

    async def _prepare_question(auto: dict, version: int, index: int, text: str, why: str) -> None:
        """D3, the topic-scoped cone: a NEW topic is asked open-form through
        the tell_me_more template; a topic already opened this session is
        asked verbatim. The topic call is fail-soft — no usable topic means
        verbatim, audited auto.topic_failed. Then pre-synthesise, so the ask
        is a cache hit when the quiet report permits it."""
        verdict = await engine.topic_for(text)
        topic = verdict.topic
        open_form = False
        if verdict.failed is not None:
            await audit.log(user["id"], "auto.topic_failed", None, None,
                            {"session_id": session_id, "reason": verdict.failed,
                             "agenda_version": version, "index": index,
                             "elapsed_ms": verdict.elapsed_ms})
        elif topic.casefold() not in auto["opened_topics"]:
            open_form = True
        if open_form:
            utterance = auto_mode.TemplateUtterance("tell_me_more", topic)
            spoken = speech.render_template("tell_me_more", topic)
        else:
            utterance = auto_mode.AgendaUtterance(version, index)
            spoken = text
        auto["queued"] = {"utterance": utterance, "kind": "question", "text": spoken,
                          "agenda_version": version, "index": index, "question": text,
                          "topic": topic, "open_form": open_form}
        auto["handover"] = None
        logger.info("Live session %s: auto question planned from v%d[%d] (%s, %s): %r",
                    session_id, version, index, why, "open" if open_form else "verbatim", spoken)
        if AUTO_PRESYNTH:
            await _presynth(spoken)

    async def _issue_queued(auto: dict, quiet_s: float) -> None:
        """A quiet report permits the queued utterance: issue it through the
        auto path with the §11 record — trigger {quiet_s, handed_back} and,
        for a question, topic and open_form. The first verbatim ask moves
        OPEN → CLOSED (narrative_exhausted) before it is spoken; the
        topic-scoped rule keeps working in CLOSED, so a genuinely new topic
        arriving late still gets its one open ask there."""
        ctl: auto_mode.AutoModeController = auto["controller"]
        plan = auto["queued"]
        verdict = auto.get("officer_verdict")
        trigger = {"quiet_s": round(quiet_s, 1),
                   "handed_back": bool(verdict.handed_back) if verdict else False}
        detail = None
        if plan["kind"] == "question":
            detail = {"topic": plan["topic"], "open_form": plan["open_form"]}
            if (not plan["open_form"] and ctl.phase is auto_mode.AutoPhase.OPEN
                    and ctl.is_legal(auto_mode.AutoEvent.NARRATIVE_EXHAUSTED)):
                await auto_transition(ctl.narrative_exhausted(),
                                      detail={"first_verbatim_ask": plan["question"]})
            try:
                ctl.request_question(plan["utterance"])
            except auto_mode.AutoModeError as exc:
                logger.error("Live session %s: question refused by the machine: %s", session_id, exc)
                auto["queued"] = None
                return
        prepared = await auto_issue(plan["utterance"], phase=ctl.phase, trigger=trigger,
                                    detail=detail)
        if prepared is None:
            return                     # in flight or a fault: try again on the next report
        auto["queued"] = None
        auto["last_issued"] = {**plan, "utterance_id": prepared.utterance_id}
        auto["turn_ended"] = False       # the next turn end is the answer's
        if plan["kind"] == "question":
            auto["last_asked_text"] = plan["question"]
            if plan["open_form"]:
                auto["opened_topics"].add(plan["topic"].casefold())
            auto["awaiting_answer"] = True
        elif plan["kind"] == "anything_else":
            auto["anything_else_done"] = True
            auto["awaiting_answer"] = True
        elif plan["kind"] == "handover":
            auto["awaiting_answer"] = False   # nothing follows but the exam

    async def on_fresh_agenda(version: int) -> None:
        """maybe_run_cds landed the pass auto mode asked for (D2): plan the
        next ask from THIS version — the only agenda the strict posture
        asks from — or, if it is empty, the handover sequence."""
        auto = entry["auto"]
        if auto is None or auto["revision"] != "running":
            return
        auto["revision"] = None
        auto["bridge_used"] = False
        if auto["controller"].phase not in auto_mode.QUESTION_PHASES:
            return
        _plan_from_agenda(auto, version, why="post-answer revision")

    async def on_auto_utterance_ended(utterance: speech.Utterance, reason: str) -> None:
        """The lifecycle end of an AUTO utterance, from handle_speak_ended.
        A politeness-aborted QUESTION (or handover phrase) is requeued and
        re-issued at the next permitting quiet — unlike an encourager,
        which is dropped; the examination handover, played through, ends
        the auto run (machine HANDOVER, audit auto.handover)."""
        auto = entry["auto"]
        if auto is None:
            return
        last = auto.get("last_issued")
        if last is None or last.get("utterance_id") != utterance.utterance_id:
            return
        if reason == "politeness_abort":
            auto["queued"] = {k: v for k, v in last.items() if k != "utterance_id"}
            auto["awaiting_answer"] = False
            logger.info("Live session %s: auto %s politeness-aborted, requeued",
                        session_id, last["kind"])
            return
        if last["kind"] == "handover" and reason == "complete":
            ctl: auto_mode.AutoModeController = auto["controller"]
            if ctl.is_legal(auto_mode.AutoEvent.AGENDA_EXHAUSTED):
                await auto_transition(ctl.agenda_exhausted(),
                                      detail={"agenda_version": last["agenda_version"]})
                await audit.log(user["id"], "auto.handover", None, None,
                                {"session_id": session_id,
                                 "agenda_version": last["agenda_version"],
                                 "at_audio_s": round(session.audio_seconds, 1)})
                await websocket.send_json({"type": "auto_toggled", "on": True,
                                           "phase": ctl.phase.value})

    async def on_doctor_tap(utterance: speech.Utterance) -> None:
        """A doctor's tap while auto mode is on (spec §3, hard rule 5): the
        queued auto utterance is cancelled, the tap is audited as an
        intervention naming what it displaced, and the answer that follows
        is treated like any other — its turn end triggers the revision."""
        auto = entry["auto"]
        if auto is None or auto["controller"].phase is auto_mode.AutoPhase.OFF:
            return
        displaced = auto["queued"]
        auto["queued"] = None
        if auto["plan_task"] is not None and not auto["plan_task"].done():
            auto["plan_task"].cancel()
        auto["plan_task"] = None
        await audit.log(user["id"], "auto.doctor_tap", None, None,
                        {"session_id": session_id, "phase": auto["controller"].phase.value,
                         "ref_kind": utterance.ref_kind, "ref_detail": utterance.ref_detail,
                         "utterance_id": utterance.utterance_id,
                         "displaced": ({"kind": displaced["kind"], "text": displaced["text"]}
                                       if displaced else None),
                         "at_audio_s": round(session.audio_seconds, 1)})
        if (utterance.ref_kind == "cds_question"
                and auto["controller"].phase in auto_mode.QUESTION_PHASES):
            auto["awaiting_answer"] = True
            auto["turn_ended"] = False
            auto["last_asked_text"] = utterance.text

    async def handle_quiet(payload: dict) -> None:
        """A quiet report from the client's reporter (spec §5). Measurement
        is the client's; every decision is here.

        In GOLDEN: quiet of AUTO_ENCOURAGER_QUIET_S earns one encourager,
        rotated through the three, at most one per
        AUTO_ENCOURAGER_COOLDOWN_S, through the auto path (a politeness
        abort drops it — the moment has passed). Quiet of AUTO_EOT_QUIET_S
        starts the end-of-turn officer, once per quiet span and again each
        time the quiet has grown by that much, so a "not finished" at 3 s
        is re-asked at 6 s rather than sticking. Its verdict is applied by
        maybe_apply_officer, on the loop's tick.

        In OPEN/CLOSED (slice 4): the officer runs the same way and its
        turn end is what permits an ask; while the D2 revision runs, at
        most one bridging encourager; when the queued utterance is ready
        and the turn has ended, it is issued. Every other phase ignores
        quiet. Ignored entirely when the gate is down.
        """
        auto = entry["auto"]
        if auto is None:
            return
        ctl: auto_mode.AutoModeController = auto["controller"]
        try:
            quiet_s = float(payload.get("quiet_s"))
        except (TypeError, ValueError):
            return
        if quiet_s < 0:
            return
        if auto["last_quiet_s"] is None or quiet_s < auto["last_quiet_s"]:
            # A fresh quiet span: the patient spoke (or we did) in between.
            auto["officer_last_run_quiet_s"] = None
            auto["officer_verdict"] = None
            auto["turn_ended"] = False
        auto["last_quiet_s"] = quiet_s
        in_golden = ctl.phase is auto_mode.AutoPhase.GOLDEN
        in_questions = ctl.phase in auto_mode.QUESTION_PHASES
        if not (in_golden or in_questions):
            return
        now = time.monotonic()
        free = not session.speaking and entry["pending_utterance"] is None
        # 1. The encourager: every pause in GOLDEN; in the question phases
        #    only as the single bridge while the revision runs.
        last = auto["last_encourager_at"]
        wants_encourager = in_golden or (auto["revision"] is not None and not auto["bridge_used"])
        if (wants_encourager and quiet_s >= AUTO_ENCOURAGER_QUIET_S and free
                and (last is None or now - last >= AUTO_ENCOURAGER_COOLDOWN_S)):
            phrase_id = speech.ENCOURAGER_IDS[auto["encourager_index"] % len(speech.ENCOURAGER_IDS)]
            prepared = await auto_issue(auto_mode.PhraseUtterance(phrase_id),
                                        phase=ctl.phase, trigger={"quiet_s": round(quiet_s, 1)})
            if prepared is not None:
                auto["encourager_index"] += 1
                auto["last_encourager_at"] = now
                if in_questions:
                    auto["bridge_used"] = True
                free = False
        # 2. The queued ask, once the turn has ended in this span.
        if in_questions and auto["queued"] is not None and auto["turn_ended"] and free:
            await _issue_queued(auto, quiet_s)
            free = False
        # 3. The officer.
        last_run = auto["officer_last_run_quiet_s"]
        due = (quiet_s >= AUTO_EOT_QUIET_S
               and (last_run is None or quiet_s - last_run >= AUTO_EOT_QUIET_S))
        if due and auto["officer_task"] is None:
            transcript = "\n".join(entry["transcript_parts"]).strip()
            auto["officer_last_run_quiet_s"] = quiet_s
            if not transcript:
                # Nothing committed yet: there is no turn to judge, and a
                # model asked about an empty transcript would be guessing.
                # The silence rule alone applies (a failed-shaped verdict).
                auto["officer_verdict"] = None
                await apply_officer_verdict(
                    OfficerVerdict(False, False, failed="no committed transcript"), quiet_s)
            else:
                auto["officer_quiet_s"] = quiet_s
                auto["officer_task"] = asyncio.create_task(engine.end_of_turn(transcript))
        elif auto["officer_verdict"] is not None and auto["officer_verdict"].failed is not None:
            # A failed officer earlier in this span: the silence rule keeps
            # being consulted as the quiet grows.
            await apply_officer_verdict(auto["officer_verdict"], quiet_s)

    async def apply_officer_verdict(verdict, quiet_s: float) -> None:
        """Turn the officer's word (or its absence) into phase behaviour.

        GOLDEN (spec §6): a hand-back exits to OPEN at once; otherwise OPEN
        only when the golden window has run AND the turn has ended — never
        at a bare timer boundary. Entering OPEN, the D2 revision is asked
        for at once (the golden exit is itself a turn end).

        OPEN/CLOSED: a turn end (finished, or handed back, or the silence
        fallback) marks the span; if it is the answer's turn ending, the
        D2 revision is requested. Anything the machine says is illegal
        from here is simply not fired."""
        auto = entry["auto"]
        ctl: auto_mode.AutoModeController = auto["controller"]
        auto["officer_verdict"] = verdict
        detail = {"quiet_s": round(quiet_s, 1), "handed_back": verdict.handed_back,
                  "officer_ms": verdict.elapsed_ms,
                  **({"officer_failed": verdict.failed} if verdict.failed else {})}
        ended = verdict.handed_back or turn_finished(verdict, quiet_s, AUTO_EOT_FALLBACK_S)
        if ctl.phase is auto_mode.AutoPhase.GOLDEN:
            if verdict.handed_back and ctl.is_legal(auto_mode.AutoEvent.HAND_BACK):
                await auto_transition(ctl.hand_back(), detail=detail)
                auto["turn_ended"] = True
                _request_revision(auto, "golden exit: hand-back")
                return
            elapsed = ctl.seconds_in_phase()
            if (elapsed >= AUTO_GOLDEN_MINUTES_S and ended
                    and ctl.is_legal(auto_mode.AutoEvent.GOLDEN_TIMER_ELAPSED)):
                await auto_transition(ctl.golden_timer_elapsed(),
                                      detail={**detail, "golden_s": round(elapsed, 1)})
                auto["turn_ended"] = True
                _request_revision(auto, "golden exit: window run, turn ended")
            return
        if ctl.phase in auto_mode.QUESTION_PHASES and ended and not auto["turn_ended"]:
            auto["turn_ended"] = True
            if verdict.handed_back:
                logger.info("Live session %s: hand-back detected in %s (quiet %.1fs)",
                            session_id, ctl.phase.value, quiet_s)
            if auto["awaiting_answer"]:
                auto["awaiting_answer"] = False
                _request_revision(auto, "answer's turn ended")

    async def maybe_apply_officer() -> None:
        """Called on the loop's tick, like maybe_run_cds: when the officer
        has answered, audit a failure (auto.officer_failed — fail-soft
        visibility, spec §11) and apply the verdict."""
        auto = entry["auto"]
        if auto is None or auto["officer_task"] is None or not auto["officer_task"].done():
            return
        task, quiet_s = auto["officer_task"], auto["officer_quiet_s"]
        auto["officer_task"] = None
        auto["officer_quiet_s"] = None
        try:
            verdict = task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001 - end_of_turn never raises; belt and braces
            logger.warning("Live session %s: officer task failed unexpectedly: %s", session_id, exc)
            return
        if verdict.failed is not None:
            await audit.log(user["id"], "auto.officer_failed", None, None,
                            {"session_id": session_id, "reason": verdict.failed,
                             "quiet_s": round(quiet_s or 0.0, 1),
                             "elapsed_ms": verdict.elapsed_ms,
                             "fallback_s": AUTO_EOT_FALLBACK_S})
        await apply_officer_verdict(verdict, quiet_s or 0.0)

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
                        # Phase 7b (rewritten 2026-08-01): attention while
                        # the room is audible. The frame's RMS is the test —
                        # "a frame arrived" only meant the microphone was
                        # on, which was the 463 metronome. Every speaker
                        # counts, including our own voice (owner decision
                        # 2026-08-01): the face is a listening presence, and
                        # it is at least as relevant while the doctor — or
                        # Alba — is the one talking.
                        if entry["face"] is not None and face.frame_is_active(data[4:]):
                            entry["face"].on_speech_activity()
                elif (text_message := message.get("text")) == "stop":
                    entry["stopped"] = True
                    break
                elif text_message and text_message.startswith("{"):
                    payload = json.loads(text_message)
                    kind = payload.get("type")
                    if kind == "speak":
                        # The client may declare via="silence_nudge" (its
                        # quiet-window detector); anything else is a tap.
                        # The nudge CAGE keys on the phrase reference, not
                        # on this label — via is audit vocabulary only.
                        await handle_speak(
                            payload,
                            via=("silence_nudge"
                                 if payload.get("via") == "silence_nudge"
                                 else "tap"))
                    elif kind == "speak_started":
                        await handle_speak_started(payload)
                    elif kind == "speak_ended":
                        await handle_speak_ended(payload)
                    elif kind == "face":
                        await handle_face(payload)
                    elif kind == "auto":
                        await handle_auto(payload)      # Phase 7c; refused when the gate is down
                    elif kind == "quiet":
                        await handle_quiet(payload)     # Phase 7c; ignored when the gate is down
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

            # Phase 7c: an officer verdict that has arrived is applied
            # BEFORE this iteration's ack, so a client (or a test) that has
            # seen the ack has seen the phase it implies.
            await maybe_apply_officer()

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
        # The tick loop is per-connection, like the CDS task. The driver
        # itself is stopped too: chemistry does not survive a drop, and a
        # reconnecting client re-sends its toggle if the face was on.
        if face_task is not None:
            face_task.cancel()
        if entry["face"] is not None:
            entry["face"].stop()
            entry["face"] = None
        if entry["auto"] is not None:
            _cancel_officer(entry["auto"])   # per-connection, like the CDS task
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
