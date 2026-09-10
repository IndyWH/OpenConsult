"""OpenConsult — application entry point.

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
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from fastapi import Depends
from pydantic import BaseModel

from app import (agenda_queue, assessment_snapshots, audit, auth, auto_mode, consultations,
                 face, frontdesk, letters, monitor, ratelimit, raw_segments, retention,
                 schema, speech, system_utterances)
from app.auth import COOKIE_NAME, CLINICAL_ROLES, api_user, page_user
from app import cds
from app.cds import CDSEngine, OfficerVerdict, turn_finished
from app.finalize import (AUTO_SPEAKER_DECLARATION_WAIT_S, declaration_bound,
                          declaration_pending, expect_declaration,
                          finalize_consultation, hold_declaration_for,
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
    title="OpenConsult",
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
    # The microphone's label at the time of the check (owner decision
    # 2026-09-09, pilot G10): the record knew the output device and not the
    # input; the input track's label was on the page all along.
    input_label: str | None = None
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
                     "input_label": body.input_label,
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
    # Phase 7c slice 5: the live acknowledgements of urgency pauses, read
    # from the audit trail — who, when, which action texts. Display only;
    # the acknowledge-gated banner and its gate are exactly as they were.
    live_acks = [ack for row in await audit.for_subject("consultation", cid,
                                                        "auto.acknowledgements")
                 for ack in (row["detail"] or {}).get("acknowledgements", [])]
    await audit.log(user["id"], "consultation.viewed", "consultation", cid)
    return JSONResponse(
        content={**consultation, "turns": turns, "note": note, "plain_text": plain,
                 "live_acknowledgements": live_acks,
                 "letters": letter_rows, "system_utterances": spoken,
                 "labels": labels,
                 # The pipeline is holding for the doctor's "Who spoke?" answer
                 # (the bound in force, seconds), or null. In-process state,
                 # read live: the review page says it is waiting rather than
                 # "finalising" (owner decision 2026-09-01, pilot D6).
                 "awaiting_declaration": declaration_pending(cid)}
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
# (AUTO_ENCOURAGER_QUIET_S — the bridge "go on" in the question phases —
# was retired 2026-09-09: the thinking phrase below replaces the bridge
# entirely, gated by the turn end rather than a quiet length.)
# Golden window encouragers (owner decision 2026-09-09, after consultations
# 487–490; reversing the 1 Sept one-per-window rule). In GOLDEN, before the
# window has run, an encourager may be spoken every time the patient has
# been quiet for this long — the quiet counted from the later of the
# patient's last speech and the end of Alba's own last phrase (the client's
# span restarts at both), at most one per quiet span. Two phrasings
# alternate: go_on ("Go on.") and tell_me_more_short ("Please, tell me
# more."). After AUTO_ENCOURAGER_MAX_UNANSWERED encouragers with no patient
# speech between them, the NEXT qualifying silence sets golden_window_ran
# early (audited auto.golden_window_ran, reason unanswered_encouragers) so
# the questions begin exactly as when the window elapses; none once the
# window has run. The 1 Sept rule replaced a rotation through three phrases
# on an 8 s cooldown that was the livelock's engine in 482 and 483; this
# rule keeps its brakes — the minimum quiet, none after the window — and
# adds the unanswered count as the loop's end.
AUTO_ENCOURAGER_MIN_QUIET_S = float(os.getenv("AUTO_ENCOURAGER_MIN_QUIET_S", "4.0"))
AUTO_ENCOURAGER_MAX_UNANSWERED = int(os.getenv("AUTO_ENCOURAGER_MAX_UNANSWERED", "2"))
# "Let me think for a moment." (owner decision 2026-09-09; replaces the
# bridge "go on" in the question phases entirely). Spoken at most once per
# wait, only when the patient's turn has ended and no question is ready:
# the queue is empty and a pass is in flight (or has just been requested),
# or the planned question's preparation has already run this long since
# the turn end with nothing ready. Not a question: it does not count as
# asked, does not touch the queue and never resets the quiet clock (the
# client keeps its span across it; the judged turn end stands). Audited
# auto.thinking with the reason. In 489/490 the bridge "Go on." was spoken
# into finished answers three times while the queue had run dry (G13).
AUTO_THINK_THRESHOLD_S = float(os.getenv("AUTO_THINK_THRESHOLD_S", "3.0"))
# Quiet this long triggers the end-of-turn officer (app/cds.py). 3.0 → 2.0
# (owner decision 2026-09-09, pilot 489/490 G6; the officer's half of the
# turn-end rule, moved with the fallback below).
AUTO_EOT_QUIET_S = float(os.getenv("AUTO_EOT_QUIET_S", "2.0"))
# The turn-end quiet rule: quiet this long ends the patient's turn on the
# report itself, whatever the officer said (E1), and is the officer's
# fail-soft. Longer than AUTO_EOT_QUIET_S on purpose — err toward waiting.
# 5.0 → 3.5 (owner decision 2026-09-09, pilot 489/490 G6): over nine clean
# answers the patient waited a mean 11.6 s from the last word to Alba's
# voice, of which the 5 s rule was 5; the diagnostic's simulation of these
# turns put 3.5 s at one answer of nine cut on the pessimistic (transcript)
# reading and none on the optimistic (RMS) reading, 2.5 s at two. The
# ≈ 3 s of untranscribed trailing energy above the floor after every answer
# is unrecorded, so the quiet reports and an RMS trace at each turn end are
# now audited (AUTO_TRACE_S, AUTO_QUIET_REPORT_AUDIT_S) for the next run to
# say what it is.
AUTO_EOT_FALLBACK_S = float(os.getenv("AUTO_EOT_FALLBACK_S", "3.5"))
# The client keeps a ring of its ~10 fps RMS readings this many seconds long
# and sends it with every quiet report; every auto.turn_ended row carries the
# latest one, so the trailing energy before each turn end is on the record.
AUTO_TRACE_S = float(os.getenv("AUTO_TRACE_S", "8.0"))
# The client's quiet reports are audited (auto.quiet_report: quiet_s, span,
# since, rms, floor) at a bounded rate — the first report of every span
# always, then at most one per this many seconds.
AUTO_QUIET_REPORT_AUDIT_S = float(os.getenv("AUTO_QUIET_REPORT_AUDIT_S", "1.0"))
# Pre-synthesise the top agenda question during the patient's turn (slice 4).
AUTO_PRESYNTH = os.getenv("AUTO_PRESYNTH", "true").lower() != "false"
# No plan is issued before its pre-synthesis has finished (owner decision
# 2026-09-09, pilot 489/490 G7): when the quiet report that permits the ask
# arrives while the plan's synthesis is still running, the issue waits for
# it — at most this long — rather than synthesising the same text a second
# time at issue (489/490: the same question synthesised twice, 0.9–1.4 s
# on issue_to_speech_ms against 24 ms on a cache hit). Past the bound the
# issue proceeds and synthesises at issue, audited auto.presynth_fallback.
# An UNCALIBRATED GUESS; synthesis of a question takes ≈ 1 s on this machine.
AUTO_PRESYNTH_WAIT_S = float(os.getenv("AUTO_PRESYNTH_WAIT_S", "2.0"))
# D2 posture (owner decision 2026-08-16), re-meant by the standing question
# queue (AGENDA_QUEUE_SPEC.md §4, D-C option a, 2026-09-07): true = a full
# CDS pass is REQUESTED on every answer, so the urgency check runs as often
# as before; asking never waits for it — the next question comes from the
# queue's head as soon as the turn ends. false = no pass on every answer;
# a pass is still requested when the queue has nothing pending. Flippable
# so the mock-patient round can compare postures as a recorded per-run
# threshold.
AUTO_STRICT_REVISE = os.getenv("AUTO_STRICT_REVISE", "true").lower() != "false"
# The ratchet matches actions by meaning, not wording (owner decision
# 2026-09-07, pilot 485 E3): a re-fired action is the same pending action
# when its normalised token-set similarity to an already-pending or
# already-acknowledged action reaches this (app/auto_mode.py,
# match_action). Recorded per run with the other thresholds.
AUTO_ACTION_MATCH_THRESHOLD = float(os.getenv("AUTO_ACTION_MATCH_THRESHOLD", "0.6"))
# A turn must start before it can end (owner decision 2026-09-07, pilot 486
# F5): after an auto question, quiet counts toward a turn end only once
# the client has reported patient speech since it. With no speech inside
# this grace the question is re-asked once; past a second grace the
# ordinary turn-end path proceeds, so silence can never trap the run.
AUTO_NO_ANSWER_GRACE_S = float(os.getenv("AUTO_NO_ANSWER_GRACE_S", "12.0"))
# The D3 cone's topic identity (owner decision 2026-09-07, pilot 486 F4):
# two topic strings are one topic when their normalised token-set
# similarity (the E3 normaliser) reaches this — "this chest pain" and
# "the pain" opened the chest pain twice in 486.
AUTO_TOPIC_MATCH_THRESHOLD = float(os.getenv("AUTO_TOPIC_MATCH_THRESHOLD", "0.6"))
# The standing question queue (AGENDA_QUEUE_SPEC.md, owner-approved
# 2026-09-07). Slice 1 landed the pure module (app/agenda_queue.py); slice
# 2 wires it: one AgendaQueue per auto session, built from the two numbers
# below (the topic threshold is AUTO_TOPIC_MATCH_THRESHOLD above), and
# every CDS pass that lands while auto mode is on merges into it. The
# module's own defaults are the same numbers.
# D-D: at most this many PENDING questions; the lowest-ranked excess is
# dropped and audited auto.queue_capped.
AUTO_QUEUE_MAX = int(os.getenv("AUTO_QUEUE_MAX", "8"))
# D-A: a pending question absent from this many CONSECUTIVE passes is
# dropped (audited auto.queue_dropped_absent); absence from one pass is kept.
AUTO_QUEUE_ABSENT_PASSES = int(os.getenv("AUTO_QUEUE_ABSENT_PASSES", "3"))
# §3, D-B: the re-ranker (slice 3) sees the last this-many committed
# transcript turns since the last full pass landed, capped by characters
# (cut from the front, so the most recent words survive — cds.rerank_excerpt).
# Its timeout and output cap live with the call in app/cds.py
# (AUTO_RERANK_TIMEOUT_S, AUTO_RERANK_MAX_TOKENS).
AUTO_RERANK_CONTEXT_TURNS = int(os.getenv("AUTO_RERANK_CONTEXT_TURNS", "6"))
AUTO_RERANK_MAX_CHARS = int(os.getenv("AUTO_RERANK_MAX_CHARS", "1500"))
# The re-ranker re-orders only, never drops (owner decision 2026-09-10, after
# consultation 491: 0 for 7 wrong drops on the record across 489-491, every
# dropped question re-proposed by the very next pass). The verdict's drops
# are still received and recorded on auto.queue_reranked as drops_advised,
# with the reason text, but none is applied and nothing changes status.
# This flag guards the old behaviour so the drop path is not deleted; it
# may be turned on only after the re-ranker has been through evals/.
AUTO_RERANK_DROPS_ENABLED = os.getenv("AUTO_RERANK_DROPS_ENABLED", "false").lower() == "true"
# A cut-off enable disclosure is retried, then the machine switches itself
# off (owner decision 2026-09-09, pilot 488 G1). In 488 the enable's
# disclosure was politeness-aborted 105 ms after issue (0.031 RMS against
# the 0.02 floor, a cafe) and nothing ever re-issued it: the machine sat in
# DISCLOSURE, on and silent, for 41 s. Now the enable's disclosure (or the
# chained invitation) is re-issued on the next quiet report, at most
# AUTO_ENABLE_RETRIES attempts in all (the enable's own issue counts as the
# first) inside AUTO_ENABLE_RETRY_WINDOW_S of the first issue; each re-issue
# is audited auto.enable_retry with the attempt number and the abort's RMS.
# With the tries spent the machine switches itself off — auto.disabled with
# reason too_loud_to_start, the measured RMS and the floor — and the Auto
# pill is told in plain words. The enable never reports success while the
# disclosure has not played through: the pill shows "starting" until then.
AUTO_ENABLE_RETRIES = int(os.getenv("AUTO_ENABLE_RETRIES", "3"))
AUTO_ENABLE_RETRY_WINDOW_S = float(os.getenv("AUTO_ENABLE_RETRY_WINDOW_S", "30"))
# Short calls before the pass (owner decision 2026-09-09, pilot 489/490 G4
# and G5; AGENDA_QUEUE_SPEC.md §3, §7a). Ollama serves one request at a
# time, and the topic call issued at a turn end in the same tick as the
# full pass lost the slot to it on 9 of 10 questions (timeout, always
# verbatim, 2 s on every question's latency). Now, at a turn end, the
# re-ranker and then the topic call run FIRST and the requested full pass
# is launched only when they have returned — the hold bounded by this many
# seconds from the turn end, after which the pass launches anyway. The hold
# is on the record: auto.pass_held with its length, and queued_ms on the
# pass's model.call row.
AUTO_SHORT_CALLS_HOLD_S = float(os.getenv("AUTO_SHORT_CALLS_HOLD_S", "4.0"))


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
    # Phase 7c (owner decision 2026-09-01, pilot D6): a consultation in
    # which auto mode was enabled — an auto.enabled row exists for the
    # session, i.e. the machine's history has an ENABLE transition — waits
    # longer for the speaker count (see below). Said on the created row so
    # the consultation carries the fact the session-keyed rows hold.
    auto_ran = bool(entry.get("auto")) and any(
        t.trigger is auto_mode.AutoEvent.ENABLE for t in entry["auto"]["controller"].history)
    await audit.log(user["id"], "consultation.created", "consultation", cid,
                    {"patient_id": entry["patient_id"],
                     **({"connection_lost": True} if connection_lost else {}),
                     **({"auto_run": True,
                         "speaker_wait_s": AUTO_SPEAKER_DECLARATION_WAIT_S}
                        if auto_ran and not connection_lost else {})})
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
    # Phase 7c slice 5: the per-revision assessment snapshots, persisted the
    # same way and for the same reason — from here they live in the
    # database, not the session object.
    if entry.get("assessment_snapshots"):
        await assessment_snapshots.save(cid, entry["assessment_snapshots"])
        logger.info("Consultation %d: %d assessment snapshot(s) recorded",
                    cid, len(entry["assessment_snapshots"]))
    # Phase 7c slice 5: the live acknowledgements, as one consultation-linked
    # audit row (the face.arms pattern) — the live auto.acknowledged rows
    # carry only the session id, because no consultation row existed yet.
    # The review page reads this to SHOW who acknowledged what, when; it
    # gates nothing.
    if entry.get("auto") and entry["auto"].get("acks"):
        await audit.log(user["id"], "auto.acknowledgements", "consultation", cid,
                        {"acknowledgements": entry["auto"]["acks"]})

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
        if auto_ran:
            # The doctor supervising an auto run is not at the keyboard when
            # Stop lands (41 s and 127 s late in 482 and 483): the pipeline
            # waits AUTO_SPEAKER_DECLARATION_WAIT_S for them, not the 25 s.
            # On expiry the ignored-declaration path applies unchanged.
            hold_declaration_for(cid, AUTO_SPEAKER_DECLARATION_WAIT_S)
        entry["speaker_wait_s"] = declaration_bound(cid)
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
                                  auto_mode.AgendaUtterance, auto_mode.LayUtterance)):
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
    _own_voice_requested(entry, prepared.utterance_id)   # H1: our window opens at the request
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
        # The standing question queue (AGENDA_QUEUE_SPEC.md, slice 2): one
        # per session, alive as long as the entry is. Every pass that lands
        # while auto mode is on merges into it (maybe_run_cds); it is the
        # session's asked-memory too, so it survives a toggle off and on —
        # a question asked in an earlier run of this session is still asked.
        "queue": agenda_queue.AgendaQueue(max_pending=AUTO_QUEUE_MAX,
                                          absent_passes=AUTO_QUEUE_ABSENT_PASSES,
                                          topic_threshold=AUTO_TOPIC_MATCH_THRESHOLD),
        # Golden window encouragers (owner decision 2026-09-09): how many
        # this window has spoken (the phrasing alternates on it), how many
        # since the patient last spoke (the early end's count), the quiet
        # span the last one was issued in (one per span), and a counter of
        # every fresh quiet span whatever began it.
        "golden_encourager_count": 0,
        "golden_unanswered": 0,
        "golden_encourager_span": None,
        "quiet_span_seq": 0,
        "golden_tapped": [],          # queue items the doctor tapped in GOLDEN (G9): answered at the exit
        "last_quiet_s": None,         # the last report's quiet (the fallback fresh-span test)
        "last_span": None,            # the client's span number on the last report (G3: the fresh-span test)
        "officer_task": None,         # the in-flight end-of-turn call, if any
        "officer_quiet_s": None,      # the quiet the running officer was asked about
        "officer_deferred": None,     # the CDS pass version the running officer waits behind (E4)
        "officer_span": 0,            # the patient span the running officer was asked in
        "span_seq": 0,                # bumps on every fresh span the PATIENT began
        "officer_last_run_quiet_s": None,   # per span: re-run when quiet grows by EOT
        "officer_verdict": None,      # the last verdict in this span
        "warm_task": None,
        # Slice 4: the question phases (see the wiring's vocabulary note).
        "turn_ended": False,
        "awaiting_answer": False,
        "revision": None,             # None | "requested" | "running"
        "think_used": False,          # "Let me think" spoken in this wait (once per wait)
        # G6 instrumentation (owner decision 2026-09-09): the latest RMS
        # trace the client sent with a quiet report (for the turn_ended
        # row) and when a quiet report was last audited (the rate bound).
        "last_trace": None,
        "quiet_audit_at": None,
        "queued": None,               # the prepared next utterance (a plan dict)
        "plan_task": None,            # topic call + pre-synthesis in flight
        "planning_item_id": None,     # the queue item plan_task is preparing (the re-rank race guard)
        # The re-ranker (AGENDA_QUEUE_SPEC.md §3, slice 3): the call in
        # flight after an answered turn end, and the plan that follows it.
        "rerank_task": None,
        "opened_topics": set(),       # D3: case-folded topics asked open-form (matched by meaning, F4)
        # No question is asked twice (pilot 486 F4): the asked-memory IS the
        # queue's asked/answered status (owner decision 2026-09-07, the
        # standing question queue). This is the queue item whose answer the
        # machine is waiting for — marked answered at its turn end.
        "asked_item_id": None,
        "handover": None,             # None | "anything_else" | "final"
        "anything_else_done": False,  # at most once per session
        "last_issued": None,          # the last queued utterance issued, for requeue
        # The number to beat (AGENDA_QUEUE_SPEC.md §7): the monotonic time of
        # the turn end that permitted the next ask, so every auto question
        # carries turn_end_to_issue_ms and, at the client's speak_started,
        # turn_end_to_speech_ms (auto.question_latency).
        "turn_ended_at": None,
        "last_asked_text": None,
        "plan_state": ("idle", None), # what the client was last told (auto_plan): the thinking state
        # Slice 5: golden seconds spent BEFORE a pause, so the window is not
        # restarted by a resume (seconds_in_phase resets on every transition).
        "golden_spent": 0.0,
        # Owner decision 2026-09-01 (pilot D1/D3): the window has run. Set
        # the first time elapsed >= AUTO_GOLDEN_MINUTES_S is observed on any
        # quiet report or verdict in GOLDEN, audited once; from then on no
        # encourager is issued and the exit waits only for a turn end or
        # AUTO_EOT_FALLBACK_S of quiet. Reset with golden_spent.
        "golden_window_ran": False,
        "pause_versions": [],         # assessment_snapshot versions of the alarms in the live pause
        "acks": [],                   # live acknowledgements, for the consultation-linked audit row
        "standing_sent": None,        # the acknowledged-but-open actions last pushed (auto_standing, F1)
        "action_aliases": set(),      # re-wordings matched to an acknowledged action (F1: the chain holds)
        # A turn must start before it can end (pilot 486 F5): after an auto
        # question, no turn end until the client reports patient speech;
        # one re-ask at AUTO_NO_ANSWER_GRACE_S, then the ordinary path.
        "awaiting_speech": False,
        "reasked": False,
        "handover_by_doctor": False,  # slice 6: the doctor's Handover tap started the sequence
        # Owner decision 2026-09-01 (pilot D4): from RESUME AUTO until the
        # first turn end that follows it, a CDS pass that lands may not
        # re-pause on an already-acknowledged action — the one answer's
        # chance made real. Cleared by that turn end; see maybe_run_cds.
        "repause_block": False,
        # A cut-off enable disclosure is retried (owner decision 2026-09-09,
        # pilot 488 G1): the utterance the enable is waiting on — the
        # disclosure, then the chained invitation — with its attempt count,
        # the time of its first issue and, after a politeness abort, the
        # RMS the client read. None once the invitation has played through
        # (or the machine is off).
        "enable_chain": None,
        # The floor comes from the room (owner decision 2026-09-09, pilot 488
        # G2): the session's politeness-abort and quiet-reporter floor,
        # derived from the doctor's newest sound check at session start
        # (ws_transcribe) — this default is the no-sound-check fallback.
        "floor": speech.auto_floor(None),
        # Short calls before the pass (owner decision 2026-09-09, G4/G5):
        # whether a topic call is out (set when a plan is made, cleared
        # when the call returns), when the short calls at this turn end
        # began (the hold's zero), and when a due pass was first held.
        "topic_pending": False,
        "short_calls_since": None,
        "pass_hold_since": None,
    }


def _reset_golden(auto: dict) -> None:
    """A fresh golden window: at the invitation's end (either path) and at
    auto off. The window's bookkeeping — seconds spent before a pause and
    the has-run flag — belongs to one run of the golden minutes."""
    auto["golden_spent"] = 0.0
    auto["golden_window_ran"] = False
    auto["golden_encourager_count"] = 0
    auto["golden_unanswered"] = 0
    auto["golden_encourager_span"] = None
    auto["golden_tapped"] = []


def _auto_on(ctl: auto_mode.AutoModeController) -> bool:
    """What the client's `auto_toggled.on` means: the machine is in a live
    run — not OFF, and not past its end (HANDOVER, TAKEN_OVER)."""
    return ctl.phase not in (auto_mode.AutoPhase.OFF, auto_mode.AutoPhase.HANDOVER,
                             auto_mode.AutoPhase.TAKEN_OVER)


def _thresholds_in_force(floor: float | None = None) -> dict:
    """Every auto-mode setting in force, recorded per run on auto.enabled
    (spec §9 / the prereg: thresholds recorded per run, both D2 postures
    visible as a recorded value). `floor` is the session's own politeness
    floor (G2); without one the module default is recorded."""
    from app import cds as cds_module
    return {
        "golden_s": AUTO_GOLDEN_MINUTES_S,
        "encourager_min_quiet_s": AUTO_ENCOURAGER_MIN_QUIET_S,
        "encourager_max_unanswered": AUTO_ENCOURAGER_MAX_UNANSWERED,
        "think_threshold_s": AUTO_THINK_THRESHOLD_S,
        "trace_s": AUTO_TRACE_S,
        "quiet_report_audit_s": AUTO_QUIET_REPORT_AUDIT_S,
        "eot_quiet_s": AUTO_EOT_QUIET_S,
        "eot_fallback_s": AUTO_EOT_FALLBACK_S,
        "officer_timeout_s": cds_module.AUTO_OFFICER_TIMEOUT_S,
        "officer_max_wait_s": cds_module.AUTO_OFFICER_MAX_WAIT_S,
        "topic_timeout_s": cds_module.AUTO_TOPIC_TIMEOUT_S,
        "presynth": AUTO_PRESYNTH,
        "presynth_wait_s": AUTO_PRESYNTH_WAIT_S,
        "strict_revise": AUTO_STRICT_REVISE,
        "action_match_threshold": AUTO_ACTION_MATCH_THRESHOLD,
        "no_answer_grace_s": AUTO_NO_ANSWER_GRACE_S,
        "topic_match_threshold": AUTO_TOPIC_MATCH_THRESHOLD,
        "queue_max": AUTO_QUEUE_MAX,
        "queue_absent_passes": AUTO_QUEUE_ABSENT_PASSES,
        "rerank_timeout_s": cds_module.AUTO_RERANK_TIMEOUT_S,
        "rerank_max_tokens": cds_module.AUTO_RERANK_MAX_TOKENS,
        "rerank_context_turns": AUTO_RERANK_CONTEXT_TURNS,
        "rerank_drops_enabled": AUTO_RERANK_DROPS_ENABLED,
        "rerank_max_chars": AUTO_RERANK_MAX_CHARS,
        "politeness_floor_rms": speech.AUTO_FLOOR_MIN if floor is None else floor,
        "floor_margin": speech.AUTO_FLOOR_MARGIN,
        "floor_min": speech.AUTO_FLOOR_MIN,
        "floor_max": speech.AUTO_FLOOR_MAX,
        "enable_retries": AUTO_ENABLE_RETRIES,
        "enable_retry_window_s": AUTO_ENABLE_RETRY_WINDOW_S,
        "short_calls_hold_s": AUTO_SHORT_CALLS_HOLD_S,
        "lay_min_similarity": speech.AUTO_LAY_MIN_SIMILARITY,
    }


def _auto_toggled(ctl: auto_mode.AutoModeController, **extra) -> dict:
    """The auto_toggled echo — the server's word on whether the machine is
    on, which the pill and the client's quiet reporter follow. While the
    machine is in DISCLOSURE the enable has not succeeded yet (owner
    decision 2026-09-09, pilot 488 G1: the enable must never report
    success while the disclosure has not played through), so the echo
    says `starting`: the reporter is armed — its reports are what a
    retried disclosure rides on — and the pill says "starting", not on."""
    message = {"type": "auto_toggled", "on": _auto_on(ctl), "phase": ctl.phase.value}
    if ctl.phase is auto_mode.AutoPhase.DISCLOSURE:
        message["starting"] = True
    message.update(extra)
    return message


# H1 (owner decision 2026-09-10, pilot 491): the machine must not hear its
# own voice as the patient. In 491 "Let me think for a moment." re-armed
# itself ten times: the phrase, heard by the microphone at 0.05-0.23 RMS,
# restarted the client's quiet span as "speech", the server cleared the
# judged turn end, the 3.5 s fallback ended a turn with nothing asked and
# reset the once-per-wait guard. The client now keeps its meter off our own
# playback (live.html, OWN_VOICE_TAIL_MS); the server keeps every utterance's
# window — speech.requested to speech.spoken, plus this tail — and a fresh
# span stamped "speech" whose start falls inside one is read as playback:
# the turn end stands, and the report says own_voice on the record.
AUTO_OWN_VOICE_TAIL_S = 0.3
_OWN_VOICE_WINDOWS_KEPT = 8


def _own_voice_requested(entry: dict, utterance_id: str) -> None:
    """An utterance of ours was requested: its window opens now (the
    request precedes the audio, and the meter cannot tell them apart)."""
    windows = entry.setdefault("own_voice", [])
    windows.append({"utterance_id": utterance_id,
                    "requested_at": time.monotonic(), "ended_at": None})
    del windows[:-_OWN_VOICE_WINDOWS_KEPT]


def _own_voice_ended(entry: dict, utterance_id: str) -> None:
    """The utterance's playback ended (played through, cut, aborted, or
    cancelled by the server): its window closes now, plus the tail."""
    for window in reversed(entry.get("own_voice") or ()):
        if window["utterance_id"] == utterance_id and window["ended_at"] is None:
            window["ended_at"] = time.monotonic()
            return


def _own_voice_at(entry: dict, at: float) -> str | None:
    """The utterance of ours whose window the monotonic instant `at` falls
    in — requested_at to ended_at + AUTO_OWN_VOICE_TAIL_S — or None. A
    window still open counts only while its utterance is the pending one;
    a window that never saw its end (a lost speak_ended) cannot swallow
    every later span."""
    pending = entry.get("pending_utterance")
    pending_id = pending.utterance_id if pending is not None else None
    for window in reversed(entry.get("own_voice") or ()):
        if at < window["requested_at"]:
            continue
        end = window["ended_at"]
        if end is None:
            if window["utterance_id"] == pending_id:
                return window["utterance_id"]
            continue
        if at <= end + AUTO_OWN_VOICE_TAIL_S:
            return window["utterance_id"]
    return None


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
    _own_voice_ended(entry, utterance.utterance_id)
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
        auto["topic_pending"] = False
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
            "cds_landed_parts": 0,    # how many transcript_parts the last LANDED pass saw (the re-ranker's excerpt starts after them)
            "urgent_first_fired": {},  # action text → audio time (s)
            "last_seq": 0,
            "attached": True,
            "grace_task": None,
            "stopped": False,
            # Phase 7a: the server's own copy of the question agenda, and
            # every utterance it has been asked to speak this session.
            "agenda": speech.AgendaLog(),
            "utterances": [],          # dicts, persisted at session end
            # Phase 7c slice 5: one row per CDS revision, persisted at
            # session end beside the utterances (app/assessment_snapshots.py).
            "assessment_snapshots": [],
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
            # H1 (owner decision 2026-09-10, pilot 491): the windows of our
            # own recent utterances (requested to ended), so a fresh quiet
            # span that began inside one is read as our voice, not the
            # patient's (_own_voice_at).
            "own_voice": [],
        }
        sessions[session_id] = entry
        logger.info("Live session %s started by %s", session_id, user["username"])
        if entry["auto"] is not None:
            # Per-session warm (spec §9): the two doctor-named phrases for
            # THIS doctor's name, off the loop, logged and never fatal — the
            # rest of the table was warmed at service start.
            entry["auto"]["warm_task"] = asyncio.create_task(asyncio.to_thread(
                state.speech.presynthesise_phrases, speech.doctor_name_for(user)))
            # The floor comes from the room (owner decision 2026-09-09, pilot
            # 488 G2): this doctor's newest sound check — the calibration
            # surface that already exists — gives the quiet room's
            # noise_floor_rms; the session's floor for the politeness abort
            # and the quiet reporter is derived from it (speech.auto_floor)
            # and lives with the session, across a reconnect. No sound
            # check: AUTO_FLOOR_MIN, and the record says so. The check's age
            # travels with it — nothing here bounds it (the owner's call).
            sound_check = None
            try:
                sound_check = await audit.latest_row("speech.sound_check", user["id"])
            except Exception as exc:  # noqa: BLE001 - config, not the consultation
                logger.warning("Could not read sound-check rows for the auto floor: %s", exc)
            check_detail = (sound_check or {}).get("detail") or {}
            floor = speech.auto_floor(check_detail.get("noise_floor_rms"))
            if sound_check is not None:
                age = (datetime.now(timezone.utc) - sound_check["at"]).total_seconds()
                floor["sound_check_age_s"] = round(max(age, 0.0), 1)
                floor["sound_check_output_label"] = check_detail.get("device_label")
                floor["sound_check_input_label"] = check_detail.get("input_label")
            entry["auto"]["floor"] = floor
            logger.info("Live session %s: auto floor %.5f (%s%s)", session_id, floor["floor"],
                        floor["source"],
                        f", noise {floor['noise_floor_rms']} x {floor['margin']}"
                        + (f", clamped at {floor['clamped']}" if floor["clamped"] else "")
                        if floor["source"] == "sound_check" else "")

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
    # sanity upper bound and the value is always clamped to it. A residual
    # above raw within the window-length bound is the expected effect of
    # the two streams' different analyser windows and AGC (2026-08-18) and
    # is logged; beyond that bound it is an anomaly and audited — never
    # silently used either way.
    scale = speech.barge_in_scale(loopback)
    if scale["anomaly"] is not None:
        await audit.log(user["id"], "speech.barge_in_anomaly", None, None,
                        {"kind": "residual_exceeds_raw_loopback",
                         **scale["anomaly"],
                         "device_label": (loopback or {}).get("device_label")})
        logger.warning("Barge-in scale anomaly for %s: residual %s > raw %s "
                       "(x%s — beyond the window-length bound)",
                       user["username"], scale["anomaly"]["residual_peak_rms"],
                       scale["anomaly"]["raw_peak_rms"], scale["anomaly"]["ratio"])
    elif scale.get("clamped") is not None:
        # The expected case (2026-08-18): the shorter-window, un-AGC'd
        # detector stream peaks above the main stream's peak. Clamped to
        # raw, logged, not an anomaly.
        logger.info("Barge-in scale: residual %s > raw %s (x%s) for %s — the "
                    "window-length/AGC effect; clamped to raw",
                    scale["clamped"]["residual_peak_rms"],
                    scale["clamped"]["raw_peak_rms"], scale["clamped"]["ratio"],
                    user["username"])
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
            "golden_s": AUTO_GOLDEN_MINUTES_S,
            "encourager_min_quiet_s": AUTO_ENCOURAGER_MIN_QUIET_S,
            "eot_quiet_s": AUTO_EOT_QUIET_S,
            "eot_fallback_s": AUTO_EOT_FALLBACK_S,
            # The RMS trace the client keeps and sends with each report
            # (owner decision 2026-09-09, G6): its length; the step is the
            # meter loop's own 100 ms.
            "trace_s": AUTO_TRACE_S,
            "trace_step_ms": 100,
            # The floor comes from the room (owner decision 2026-09-09, G2):
            # the session's own floor for the politeness abort and the
            # quiet reporter, replacing the absolute BARGE_IN_RMS_THRESHOLD
            # for both; the client holds no number of its own.
            "floor": entry["auto"]["floor"]["floor"],
            "floor_source": entry["auto"]["floor"]["source"],
        }
    await websocket.send_json(speech_config)
    if entry["auto"] is not None:
        # Phase 7c: the server's word on auto mode, on connect and on
        # reconnect — the client's reporter and (slice 6) the pill follow
        # it. Never sent when the gate is down.
        _ctl = entry["auto"]["controller"]
        await websocket.send_json(_auto_toggled(
            _ctl, **({"pending": sorted(_ctl.pending_actions)}
                     if _ctl.phase is auto_mode.AutoPhase.PAUSED_URGENT else {})))

    session: LiveSession = entry["session"]
    engine: CDSEngine = state.cds_engine
    rag: RAGService = state.rag

    # CDS side tasks are per-connection (cancelled on disconnect); their
    # accumulated state lives in the entry and survives reconnects.
    cds_task: asyncio.Task | None = None
    cds_task_parts = 0        # len(transcript_parts) when the pass in flight was launched
    cds_task_launched_at = 0.0   # monotonic, for the pass's model.call row (elapsed_ms)
    cds_task_queued_ms = 0       # how long the short calls held it back (owner decision 2026-09-09, G4)
    cds_failures = 0
    # Phase 7c (owner decision 2026-09-01, pilot D4): whether the CDS pass
    # in flight was launched before the first post-resume turn end — or was
    # already in flight when RESUME AUTO was acknowledged. Such a pass may
    # not re-pause on an already-acknowledged action when it lands.
    cds_pre_answer = False
    gl_task: asyncio.Task | None = None
    gl_conditions: tuple = ()  # conditions the current guideline panel is for
    face_task: asyncio.Task | None = None  # Phase 7b tick loop, per-connection
    last_acked = -1

    async def _audit_pass_call(outcome: str, *, failed: str | None = None,
                               version: int | None = None) -> None:
        """The full pass on the model.call record (AGENDA_QUEUE_SPEC.md §7a):
        one row for the pass's three calls (assessment, urgency, affect —
        their own tokens and run_ms wait for slice 6 of the queue), with
        queued_ms = how long the short calls held it back at the turn end
        (owner decision 2026-09-09, G4) and elapsed_ms launch → landing."""
        await audit.log(user["id"], "model.call", None, None,
                        {"session_id": session_id, "kind": "pass",
                         "model": getattr(engine, "model", None),
                         "queued_ms": int(cds_task_queued_ms),
                         "run_ms": None,
                         "elapsed_ms": int(round((time.monotonic() - cds_task_launched_at) * 1000)),
                         "tokens": None, "outcome": outcome,
                         **({"failed": failed} if failed else {}),
                         "pass_in_flight": False,
                         **({"version": version} if version is not None else {}),
                         "at_audio_s": round(session.audio_seconds, 1)})

    def _short_calls_out(auto: dict) -> bool:
        """A re-ranker call or a topic call is out right now."""
        return ((auto["rerank_task"] is not None and not auto["rerank_task"].done())
                or bool(auto["topic_pending"]))

    def _pass_held() -> bool:
        """Short calls before the pass (owner decision 2026-09-09, pilot
        489/490 G4; AGENDA_QUEUE_SPEC.md §3, §7a). While the re-ranker or
        the topic call is out, a due full pass is not launched — on Ollama's
        single slot it would win the slot from them and the topic call
        would time out, as it did on 9 of 10 questions — for at most
        AUTO_SHORT_CALLS_HOLD_S from the moment the short calls began; past
        the bound the pass launches anyway. Clears the hold's zero once the
        short calls are back."""
        auto = entry["auto"]
        if auto is None:
            return False
        if not _short_calls_out(auto):
            auto["short_calls_since"] = None
            return False
        if auto["short_calls_since"] is None:
            auto["short_calls_since"] = time.monotonic()
        return time.monotonic() - auto["short_calls_since"] < AUTO_SHORT_CALLS_HOLD_S

    async def maybe_run_cds() -> None:
        """Launch/collect the CDS side task without ever blocking transcription."""
        nonlocal cds_task, cds_task_parts, cds_task_launched_at, cds_task_queued_ms
        nonlocal cds_failures, cds_pre_answer
        if cds_task is not None and cds_task.done():
            try:
                entry["assessment"] = cds_task.result()
                cds_failures = 0
                entry["cds_landed_parts"] = cds_task_parts   # the re-ranker's excerpt begins after these
                # Version the agenda before sending it, so the version the
                # client tap refers to is one the server can resolve.
                assessment_version = entry["agenda"].record(entry["assessment"])
                entry["assessment"]["assessment_version"] = assessment_version
                # Phase 7c slice 5: the revision's snapshot — every pass,
                # auto mode on or off (metric 7 and replay both want it).
                entry["assessment_snapshots"].append(assessment_snapshots.snapshot_of(
                    entry["assessment"], assessment_version,
                    datetime.now(timezone.utc), session.audio_seconds))
                # The standing question queue (AGENDA_QUEUE_SPEC.md §2, §5):
                # every pass that lands while auto mode is on merges its
                # questions into the session's queue — whether or not auto
                # mode asked for the pass — before anything else reads it,
                # so an alarm-bearing pass has merged by the time RESUME
                # AUTO asks from the head. The merge itself is synchronous;
                # its audit rows are written after the alarm handling below
                # so the pause is never delayed by the record.
                queue_events = (_merge_pass(assessment_version, entry["assessment"])
                                if entry["auto"] is not None else ())
                # Phase 7c slice 5 (spec §7, hard rule 2): a non-empty
                # urgent_actions while auto mode is listening pauses it.
                # Nothing here touches the face (the alarm is deliberately
                # kept off it, app/face.py); with the gate down or auto
                # off this is a no-op and today's behaviour stands.
                if entry["auto"] is not None and entry["assessment"].get("urgent_actions"):
                    if not await _repause_suppressed(entry["assessment"]["urgent_actions"],
                                                     assessment_version, cds_pre_answer):
                        await on_urgent_alarm(entry["assessment"]["urgent_actions"],
                                              assessment_version)
                if entry["auto"] is not None:
                    await _push_standing(assessment_version)
                if queue_events:
                    await _audit_queue_events(queue_events)
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
                if entry["auto"] is not None:
                    await _audit_pass_call("ok", version=assessment_version)
            except cds.CDSRunaway as exc:
                # Cap runaway generation (owner decision 2026-09-07, pilot
                # 486 F3): the pass failed at its cap or its timeout. On the
                # record with tokens and elapsed; the previous assessment is
                # kept; the urgency check ran on its own call and its alarm
                # still counts; a revision auto mode was waiting for is
                # answered from the agenda it already has, so the flow is
                # never held by a pass that cannot land. Deferred officer
                # calls fall to their E4 bound as designed.
                cds_failures += 1
                await audit.log(user["id"], "cds.runaway", None, None,
                                {"session_id": session_id, "call": exc.call, "reason": exc.reason,
                                 "tokens": exc.tokens, "elapsed_ms": exc.elapsed_ms,
                                 "cap": exc.cap, "timeout_s": exc.timeout_s,
                                 "failures": cds_failures,
                                 "kept_assessment_version": entry["agenda"].current_version,
                                 "at_audio_s": round(session.audio_seconds, 1)})
                logger.warning("CDS pass failed (%d): runaway — %s", cds_failures, exc)
                if exc.urgency is not None:
                    if entry["assessment"] is None:
                        # A runaway on the very first pass: nothing to keep,
                        # but the alarm still counts — a minimal assessment
                        # carries the urgency check's own result.
                        entry["assessment"] = {"reasoning": "", "differentials": [],
                                               "questions_to_ask": [], "signs_to_check": [],
                                               "patient_affect": "neutral"}
                    entry["assessment"]["urgency_check"] = exc.urgency["urgency_check"]
                    entry["assessment"]["urgent_actions"] = exc.urgency["urgent_actions"]
                    await websocket.send_json({"type": "cds", "assessment": entry["assessment"]})
                    if entry["auto"] is not None and exc.urgency["urgent_actions"]:
                        if not await _repause_suppressed(exc.urgency["urgent_actions"],
                                                         entry["agenda"].current_version,
                                                         cds_pre_answer):
                            await on_urgent_alarm(exc.urgency["urgent_actions"],
                                                  entry["agenda"].current_version)
                    if entry["auto"] is not None:
                        await _push_standing(entry["agenda"].current_version)
                if entry["auto"] is not None and entry["auto"]["revision"] == "running":
                    auto = entry["auto"]
                    auto["revision"] = None
                    if auto["controller"].phase in auto_mode.QUESTION_PHASES:
                        _ask_after_pass(auto, entry["agenda"].current_version,
                                        "revision failed (runaway), asking from the queue in hand")
                if entry["auto"] is not None:
                    await _audit_pass_call(exc.reason, failed=str(exc),
                                           version=entry["agenda"].current_version)
                if cds_failures >= CDS_MAX_FAILURES:
                    await websocket.send_json(
                        {"type": "cds_unavailable",
                         "detail": "CDS engine unreachable; transcription continues."}
                    )
            except Exception as exc:  # noqa: BLE001 - degrade, don't crash the stream
                cds_failures += 1
                logger.warning("CDS pass failed (%d): %s: %s", cds_failures, type(exc).__name__, exc)
                if entry["auto"] is not None:
                    await _audit_pass_call("error", failed=f"{type(exc).__name__}: {exc}")
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
        due = (cds_task is None and cds_failures < CDS_MAX_FAILURES
               and (first_call_due or auto_due
                    or len(transcript) - entry["cds_sent_len"] >= CDS_MIN_NEW_CHARS))
        if due and _pass_held():
            # Short calls before the pass (owner decision 2026-09-09, G4):
            # the re-ranker and the topic call are out; the pass waits for
            # them (bounded) rather than taking the slot from them.
            auto = entry["auto"]
            if auto["pass_hold_since"] is None:
                auto["pass_hold_since"] = time.monotonic()
            return
        if due:
            held_since = entry["auto"]["pass_hold_since"] if entry["auto"] is not None else None
            cds_task_queued_ms = 0
            if held_since is not None:
                auto = entry["auto"]
                auto["pass_hold_since"] = None
                cds_task_queued_ms = int(round((time.monotonic() - held_since) * 1000))
                released = "bound" if _short_calls_out(auto) else "short_calls_done"
                logger.info("Live session %s: pass held %d ms for the short calls (%s)",
                            session_id, cds_task_queued_ms, released)
                await audit.log(user["id"], "auto.pass_held", None, None,
                                {"session_id": session_id, "hold_ms": cds_task_queued_ms,
                                 "released": released, "bound_s": AUTO_SHORT_CALLS_HOLD_S,
                                 "pass_version": entry["agenda"].current_version + 1,
                                 "at_audio_s": round(session.audio_seconds, 1)})
            entry["cds_sent_len"] = len(transcript)
            if auto_due:
                entry["auto"]["revision"] = "running"
            cds_pre_answer = bool(entry["auto"] is not None and entry["auto"]["repause_block"])
            cds_task_parts = len(entry["transcript_parts"])
            cds_task_launched_at = time.monotonic()
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
        confirmed = bool(payload.get("confirm_displace"))
        if via == "tap" and entry["auto"] is not None and not confirmed:
            # The guarded tap (owner decision 2026-09-07, pilot 485, item 5):
            # a doctor's tap while the machine has a question planned or
            # queued does not displace it silently. In 485 the doctor tapped
            # 0.9 s after the machine had queued its own open question and
            # never knew. The tap is answered with speak_confirm — the
            # queued text shown, "ask yours instead" (the same tap with
            # confirm_displace) or "let Alba ask" — and the queue is left
            # untouched. A tapped examination handover is exempt: it ends
            # the run, and there is nothing for the machine to ask after
            # it. Taps with nothing planned are unchanged.
            auto = entry["auto"]
            # "Planned" is everything the indicator shows as preparing: the
            # revision the ask will come from, the topic call and synthesis,
            # or the question itself sitting queued.
            planned = (auto["queued"] is not None
                       or (auto["plan_task"] is not None and not auto["plan_task"].done())
                       or (auto["rerank_task"] is not None and not auto["rerank_task"].done())
                       or (auto["revision"] is not None
                           and auto["controller"].phase in auto_mode.QUESTION_PHASES))
            ref = payload.get("ref") or {}
            if (planned and auto["controller"].phase is not auto_mode.AutoPhase.OFF
                    and not (ref.get("kind") == "phrase" and ref.get("id") == "examination_handover")):
                queued = auto["queued"]
                await websocket.send_json({
                    "type": "speak_confirm", "ref": ref,
                    "queued": ({"kind": queued["kind"], "text": queued["text"]}
                               if queued is not None else None),
                    "detail": ("the machine is about to ask: " + queued["text"]
                               if queued is not None else "the machine is preparing a question")})
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
            await on_doctor_tap(utterance, confirmed=confirmed)
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
        _own_voice_requested(entry, utterance.utterance_id)   # H1: our window opens at the request
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
        await _note_question_latency(utterance)
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
            _own_voice_ended(entry, utterance.utterance_id)   # H1: nothing played; the window closes
            entry["pending_utterance"] = None
            rms = payload.get("rms")
            if utterance.ref_detail.get("via") == "auto":
                await on_auto_utterance_ended(
                    utterance, "politeness_abort",
                    rms=round(float(rms), 5) if rms is not None else None)
            await audit.log(user["id"], "speech.politeness_abort", None, None,
                            {"utterance_id": utterance.utterance_id,
                             "via": utterance.ref_detail.get("via", "tap"),
                             "phase": utterance.ref_detail.get("phase"),
                             # The floor the client compared against — the
                             # session's own, from the room (G2) — beside
                             # the reading, so the row can be read alone.
                             **({"floor": entry["auto"]["floor"]["floor"]}
                                if entry["auto"] is not None else {}),
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
        _own_voice_ended(entry, utterance.utterance_id)   # H1: the tail runs from here
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
                _reset_golden(auto)
                auto["enable_chain"] = None      # the enable's chain is complete (G1)
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
                chained = await auto_issue(auto_mode.PhraseUtterance("invitation"),
                                           phase=auto["controller"].phase,
                                           trigger={"via": "auto_chain"})
                if chained is not None:
                    # The chained invitation is the enable chain's next
                    # step: a politeness abort of it is retried the same
                    # way (owner decision 2026-09-09, G1).
                    _begin_enable_chain(auto, "invitation", chained)
                else:
                    auto["enable_chain"] = None
                # The disclosure has played through: NOW the enable has
                # succeeded, and the pill is told on (it said "starting").
                await websocket.send_json(_auto_toggled(auto["controller"]))
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
        # Slice 6: the phase indicator on the live page follows a live push
        # of every transition (the auto_toggled echo carries the phase only
        # at toggles and reconnects).
        await websocket.send_json({"type": "auto_phase",
                                   "phase": transition.to_phase.value,
                                   "from": transition.from_phase.value,
                                   "trigger": transition.trigger.value,
                                   # Owner decision 2026-09-01 (pilot D7): the
                                   # golden seconds already spent, so the
                                   # indicator can count the window down
                                   # from the same arithmetic the server
                                   # uses (a pause push carries the sum
                                   # including the stretch just paused).
                                   "golden_spent": round(entry["auto"]["golden_spent"], 1)})

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
            if ctl.phase in (auto_mode.AutoPhase.HANDOVER, auto_mode.AutoPhase.TAKEN_OVER):
                # The previous auto run has ended; a fresh tap starts a
                # fresh run — the machine goes through OFF first (auto off
                # is legal from every state), audited as a restart.
                await audit.log(user["id"], "auto.disabled", None, None,
                                {"session_id": session_id, "via": "restart",
                                 "at_audio_s": round(session.audio_seconds, 1)})
                await auto_transition(ctl.auto_off(), detail={"reason": "restart"})
                _cancel_officer(auto)
            if ctl.phase is not auto_mode.AutoPhase.OFF:
                await websocket.send_json(_auto_toggled(ctl))
                return   # already on — idempotent, nothing to re-audit
            if session.speaking or entry["pending_utterance"] is not None:
                await refuse_auto("an utterance is in flight — try again when it has finished")
                return
            floor = auto["floor"]
            # The machine, browser and microphone on the record (owner
            # decision 2026-09-09, pilot G10): the user agent from the
            # socket's own headers, the platform and the current input
            # label from the client's toggle, and the labels the sound
            # check recorded — 487–490 knew only "MacBook Air Speakers".
            raw_client = payload.get("client") if isinstance(payload.get("client"), dict) else {}
            def _text(value, limit=300):
                return str(value)[:limit] if isinstance(value, (str, int, float)) and str(value) else None
            client_record = {
                "user_agent": _text(websocket.headers.get("user-agent"), 500),
                "platform": _text(raw_client.get("platform")),
                "input_label": _text(raw_client.get("input_label")),
                "output_label": floor.get("sound_check_output_label"),
                "sound_check_input_label": floor.get("sound_check_input_label"),
            }
            await audit.log(user["id"], "auto.enabled", None, None,
                            {"session_id": session_id, "via": via,
                             "disclosed": entry["disclosed"],
                             "at_audio_s": round(session.audio_seconds, 1),
                             "client": client_record,
                             # The floor from the room (G2): the value, the
                             # measurement it came from and the margin — or
                             # that there was no sound check and the minimum
                             # was used.
                             "floor": floor["floor"],
                             "noise_floor_rms": floor["noise_floor_rms"],
                             "margin": floor["margin"],
                             "floor_source": floor["source"],
                             "floor_clamped": floor["clamped"],
                             **({"sound_check_age_s": floor["sound_check_age_s"]}
                                if "sound_check_age_s" in floor else {}),
                             # The thresholds in force, recorded per run.
                             "thresholds": _thresholds_in_force(floor["floor"])})
            await auto_transition(ctl.enable())
            # Owner decision 2026-09-08: the questions the CDS has already
            # proposed are in the queue from the toggle, so the first ask
            # does not wait for a fresh pass (a no-op on an empty agenda).
            await _seed_queue()
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
                _begin_enable_chain(auto, "disclosure", prepared)
                # Not success yet (G1): the disclosure has not played
                # through. The echo says `starting`; the on-echo follows the
                # disclosure's completion (handle_speak_ended).
                await websocket.send_json(_auto_toggled(ctl))
                return
            await auto_transition(ctl.disclosure_completed(),
                                  detail={"disclosure": "already_given"})
            if entry["invitation_completed"]:
                # The invitation played through before auto was switched
                # on (the doctor tapped Disclosure and the chain spoke it):
                # GOLDEN starts NOW, and the record says why the zero point
                # is the toggle rather than the invitation's end.
                _reset_golden(auto)
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
                _begin_enable_chain(auto, "invitation", prepared)
            await websocket.send_json(_auto_toggled(ctl))
        else:
            if ctl.phase is auto_mode.AutoPhase.OFF:
                await websocket.send_json({"type": "auto_toggled", "on": False,
                                           "phase": ctl.phase.value})
                return   # already off
            await _switch_auto_off(auto, via=via)

    async def _switch_auto_off(auto: dict, *, via: str, reason: str | None = None,
                               detail: dict | None = None, tell: str | None = None) -> None:
        """Auto off, from any state: audited auto.disabled (with `via`, and
        the machine's own `reason` and detail when it switched itself off),
        the machine to OFF, the officer, any plan and the enable chain
        stood down, the golden bookkeeping reset, and the client told
        (auto_toggled off — with `reason` in plain words when the machine
        decided, so the pill can say why)."""
        ctl: auto_mode.AutoModeController = auto["controller"]
        await audit.log(user["id"], "auto.disabled", None, None,
                        {"session_id": session_id, "via": via,
                         **({"reason": reason} if reason else {}),
                         **(detail or {}),
                         "at_audio_s": round(session.audio_seconds, 1)})
        await auto_transition(ctl.auto_off(), detail={"reason": reason} if reason else None)
        _cancel_officer(auto)
        auto.update(turn_ended=False, awaiting_answer=False, think_used=False,
                    handover=None, last_issued=None, handover_by_doctor=False,
                    repause_block=False, enable_chain=None)
        _reset_golden(auto)
        await websocket.send_json({"type": "auto_toggled", "on": False,
                                   "phase": ctl.phase.value,
                                   **({"reason": tell} if tell else {})})

    def _begin_enable_chain(auto: dict, phrase_id: str, prepared: speech.Utterance) -> None:
        """The enable is now waiting on this utterance (the disclosure, or
        the invitation) to play through — attempt 1 of AUTO_ENABLE_RETRIES,
        the retry window open from now (owner decision 2026-09-09, G1)."""
        auto["enable_chain"] = {"phrase": phrase_id, "attempt": 1,
                                "first_issued_at": time.monotonic(),
                                "utterance_id": prepared.utterance_id,
                                "aborted": False, "abort_rms": None}

    def _politeness_floor() -> float:
        """The floor the client's politeness abort compares against: the
        session's own, from the room (owner decision 2026-09-09, G2)."""
        return float(entry["auto"]["floor"]["floor"])

    async def _too_loud_to_start(auto: dict) -> None:
        """The tries are spent (owner decision 2026-09-09, G1): the machine
        switches itself off with the reason on the record — the last
        abort's RMS against the floor, the attempts made — and on the pill
        in plain words ("Too loud to start: 0.031 against 0.020")."""
        chain = auto["enable_chain"] or {}
        rms, floor = chain.get("abort_rms"), _politeness_floor()
        words = (f"Too loud to start: {rms:.3f} against {floor:.3f}" if rms is not None
                 else f"Too loud to start (floor {floor:.3f})")
        logger.info("Live session %s: auto off — %s after %d attempt(s) at the %s",
                    session_id, words, chain.get("attempt", 0), chain.get("phrase"))
        await _switch_auto_off(auto, via="too_loud_to_start", reason="too_loud_to_start",
                               detail={"rms": rms, "floor": floor,
                                       "attempts": chain.get("attempt"),
                                       "phrase": chain.get("phrase"),
                                       "retries": AUTO_ENABLE_RETRIES,
                                       "window_s": AUTO_ENABLE_RETRY_WINDOW_S},
                               tell=words)

    async def _on_enable_chain_aborted(auto: dict, utterance: speech.Utterance,
                                       rms: float | None) -> None:
        """The enable's disclosure (or the chained invitation) was
        politeness-aborted: remember the reading; with the tries already
        spent, switch off now — otherwise the next quiet report retries
        (_retry_enable_chain)."""
        chain = auto["enable_chain"]
        chain["aborted"] = True
        chain["abort_rms"] = rms
        logger.info("Live session %s: the enable's %s was politeness-aborted (rms %s) on attempt "
                    "%d of %d", session_id, chain["phrase"], rms, chain["attempt"],
                    AUTO_ENABLE_RETRIES)
        if chain["attempt"] >= AUTO_ENABLE_RETRIES:
            await _too_loud_to_start(auto)

    async def _retry_enable_chain(auto: dict, quiet_s: float) -> None:
        """A quiet report while the enable's utterance stands aborted: re-issue
        it (attempt n+1, audited auto.enable_retry with the abort's RMS)
        while attempts and the window allow; otherwise the machine switches
        itself off (too_loud_to_start). A slot not free waits for the next
        report."""
        chain = auto["enable_chain"]
        ctl: auto_mode.AutoModeController = auto["controller"]
        if session.speaking or entry["pending_utterance"] is not None:
            return
        if (chain["attempt"] >= AUTO_ENABLE_RETRIES
                or time.monotonic() - chain["first_issued_at"] > AUTO_ENABLE_RETRY_WINDOW_S):
            await _too_loud_to_start(auto)
            return
        attempt = chain["attempt"] + 1
        prepared = await auto_issue(auto_mode.PhraseUtterance(chain["phrase"]), phase=ctl.phase,
                                    trigger={"via": "auto_enable_retry", "attempt": attempt,
                                             "quiet_s": round(quiet_s, 1)})
        if prepared is None:
            return                          # a guard refusal: the next report tries again
        chain.update(attempt=attempt, aborted=False, utterance_id=prepared.utterance_id)
        await audit.log(user["id"], "auto.enable_retry", None, None,
                        {"session_id": session_id, "phrase": chain["phrase"], "attempt": attempt,
                         "abort_rms": chain["abort_rms"], "floor": _politeness_floor(),
                         "quiet_s": round(quiet_s, 1), "retries": AUTO_ENABLE_RETRIES,
                         "window_s": AUTO_ENABLE_RETRY_WINDOW_S,
                         "utterance_id": prepared.utterance_id,
                         "at_audio_s": round(session.audio_seconds, 1)})
        logger.info("Live session %s: the enable's %s re-issued (attempt %d of %d) on quiet %.1f s",
                    session_id, chain["phrase"], attempt, AUTO_ENABLE_RETRIES, quiet_s)

    async def handle_auto_ack(payload: dict) -> None:
        """RESUME AUTO / TAKE OVER on the pause banner (spec §7, §10).

        Only while PAUSED_URGENT, only by the doctor running the session.
        Both first audit auto.acknowledged with EVERY pending action text
        the acknowledgement covers and the assessment_snapshot versions of
        the alarms that fired in this pause — the doctor saw all of them
        on the banner (the slice-2 hard requirement); an acknowledgement
        never covers what was not shown. Then:
        - resume: controller.acknowledge_and_resume returns to the exact
          prior phase, audited auto.resumed; in a question phase the next
          ask is planned from the alarm-bearing pass's agenda — no
          revision is requested first (owner decision 2026-08-17): that
          agenda already carries the alarm's clarifying questions, and
          urgency re-evaluates at the next post-answer revision. The
          ratchet is the machine's: the same action re-firing pauses
          again and needs a fresh acknowledgement.
        - take_over: controller.acknowledge_and_take_over — TAKEN_OVER,
          terminal for the auto run — audited auto.takeover; the session
          continues in standard mode with all of today's behaviour.
        A refusal is answered (auto_refused), never swallowed.
        """
        nonlocal cds_pre_answer
        auto = entry["auto"]
        if auto is None:
            await refuse_auto("auto mode is not enabled on this server (AUTO_MODE_ENABLED)")
            return
        if user["id"] != entry["user"]["id"]:
            await refuse_auto("only the doctor running this consultation may acknowledge")
            return
        ctl: auto_mode.AutoModeController = auto["controller"]
        resolution = payload.get("resolution")
        if resolution not in ("resume", "take_over"):
            await refuse_auto("acknowledge with resolution 'resume' or 'take_over'")
            return
        if ctl.phase is not auto_mode.AutoPhase.PAUSED_URGENT:
            await refuse_auto("nothing to acknowledge — auto mode is not paused")
            return
        covered = sorted(ctl.pending_actions)
        versions = list(auto["pause_versions"])
        paused_from = ctl.paused_from.value if ctl.paused_from else None
        ack_detail = {"session_id": session_id, "resolution": resolution,
                      "actions": covered, "assessment_versions": versions,
                      "paused_from": paused_from,
                      "at_audio_s": round(session.audio_seconds, 1)}
        await audit.log(user["id"], "auto.acknowledged", None, None, ack_detail)
        auto["acks"].append({**ack_detail, "at": datetime.now(timezone.utc).isoformat(),
                             "user_id": user["id"], "username": user["username"],
                             "display_name": user.get("display_name")})
        auto["pause_versions"] = []
        if resolution == "resume":
            transition = ctl.acknowledge_and_resume()
            await auto_transition(transition, detail={"actions": covered})
            await audit.log(user["id"], "auto.resumed", None, None,
                            {"session_id": session_id, "phase": ctl.phase.value,
                             "actions": covered, "at_audio_s": round(session.audio_seconds, 1)})
            auto.update(turn_ended=False, awaiting_answer=False, think_used=False)
            # Owner decision 2026-09-01 (pilot D4, the 482 stutter): the
            # ratchet may only re-pause on a pass started after at least
            # one answer following this resume. A pass already in flight
            # now predates it; so does any pass launched before the next
            # turn end. maybe_run_cds consults both when a pass lands.
            auto["repause_block"] = True
            if cds_task is not None and not cds_task.done():
                cds_pre_answer = True
            if ctl.phase in auto_mode.QUESTION_PHASES:
                # Owner decision 2026-08-17 (spec §7 as amended): NO immediate
                # revision. The alarm-bearing pass's agenda is the freshest
                # there is and already carries the alarm's clarifying
                # questions, so clarification gets exactly one answer's
                # chance; urgency re-evaluates at the next post-answer
                # revision as D2 always does — clearing the alarm, or
                # re-pausing under the ratchet. Replaces slice 5's
                # immediate re-revision, which re-paused before any answer
                # could be given. The alarm-bearing pass has merged into the
                # standing queue (maybe_run_cds), so the ask is its head;
                # a queue with nothing pending after that pass is spent and
                # the handover sequence follows, as before the queue.
                if not _plan_from_queue(auto, why="resumed after pause"):
                    _plan_handover(auto, entry["agenda"].current_version)
            await _push_standing(entry["agenda"].current_version)
        else:
            transition = ctl.acknowledge_and_take_over()
            await auto_transition(transition, detail={"actions": covered})
            await audit.log(user["id"], "auto.takeover", None, None,
                            {"session_id": session_id, "actions": covered,
                             "at_audio_s": round(session.audio_seconds, 1)})
            _cancel_officer(auto)
        await websocket.send_json({"type": "auto_acknowledged", "resolution": resolution,
                                   "actions": covered, "phase": ctl.phase.value})
        await websocket.send_json({"type": "auto_toggled", "on": _auto_on(ctl),
                                   "phase": ctl.phase.value})

    async def handle_auto_handover(payload: dict) -> None:
        """The doctor's Handover control (Phase 7c slice 6, spec §6, §10).

        Available only while auto mode is listening (GOLDEN, OPEN, CLOSED)
        and only to the doctor running the session; audited as a doctor
        intervention (auto.doctor_handover). It starts the wired handover
        sequence: the anything-else follow-up once, its answer, then the
        examination handover, and the auto run ends.

        In OPEN or CLOSED the sequence runs exactly as the agenda-empty
        path does — including the agenda-refill return: if the anything-
        else answer's revision refills the agenda, the flow returns to the
        questions and the handover waits — and when the examination
        handover plays through the machine fires handover_requested (the
        doctor asked) rather than agenda_exhausted.

        In GOLDEN there are no question phases to return to and no
        questions may be asked, so the machine's own edge fires at once
        (GOLDEN → HANDOVER: the doctor has ended the golden minutes and
        the history), and the two phrases are spoken from HANDOVER as a
        fixed sequence — anything-else, its answer, the examination
        handover — with no refill path: the machine is past its question
        phases (HANDOVER has no edge back to OPEN). Stated in HANDOVER as
        the one asymmetry the design left open.
        """
        auto = entry["auto"]
        if auto is None:
            await refuse_auto("auto mode is not enabled on this server (AUTO_MODE_ENABLED)")
            return
        if user["id"] != entry["user"]["id"]:
            await refuse_auto("only the doctor running this consultation may hand over")
            return
        ctl: auto_mode.AutoModeController = auto["controller"]
        if ctl.phase not in auto_mode.LISTENING_PHASES:
            await refuse_auto("handover is available while auto mode is listening — "
                              f"it is {ctl.phase.value.replace('_', ' ')} now")
            return
        if auto["handover"] is not None:
            await refuse_auto("the handover sequence is already under way")
            return
        await audit.log(user["id"], "auto.doctor_handover", None, None,
                        {"session_id": session_id, "phase": ctl.phase.value,
                         "via": "control", "at_audio_s": round(session.audio_seconds, 1)})
        auto["handover_by_doctor"] = True
        # Whatever was queued or planned yields to the doctor's decision.
        auto["queued"] = None
        if auto["plan_task"] is not None and not auto["plan_task"].done():
            auto["plan_task"].cancel()
        auto["plan_task"] = None
        auto.update(awaiting_answer=False, revision=None, think_used=False, topic_pending=False)
        if ctl.phase is auto_mode.AutoPhase.GOLDEN:
            await auto_transition(ctl.handover_requested(), detail={"by": "doctor"})
        _plan_handover(auto, entry["agenda"].current_version)
        await websocket.send_json({"type": "auto_handover_started", "phase": ctl.phase.value})

    def _cancel_officer(auto: dict) -> None:
        for key in ("officer_task", "plan_task", "rerank_task"):
            task = auto.get(key)
            if task is not None and not task.done():
                task.cancel()
            auto[key] = None
        auto["officer_quiet_s"] = None
        auto["officer_deferred"] = None
        auto["queued"] = None
        auto["revision"] = None
        auto["topic_pending"] = False
        auto["awaiting_speech"] = False
        # A question cut by a pause, auto off or a handover keeps its ASKED
        # status in the queue — never asked again — but no answer is
        # awaited for it.
        auto["asked_item_id"] = None

    # ------------------------------------------------------------------
    # Phase 7c slice 4: the question phases (spec §6, D2 and D3). Vocabulary
    # used below, all held in entry["auto"]:
    #   turn_ended       the current quiet span has been judged the end of a
    #                    turn (officer, or its silence fallback); cleared when
    #                    a question is issued or the PATIENT begins a fresh
    #                    span — never by our own playback (pilot 485 E2)
    #   awaiting_answer  a question (or the anything-else phrase) has been
    #                    asked and the next turn end is its answer's end
    #   revision         None | "requested" | "running": the D2 post-answer
    #                    CDS pass in flight
    #   queue            the standing question queue (AGENDA_QUEUE_SPEC.md):
    #                    what Alba asks from, and the asked-memory
    #   asked_item_id    the queue item whose answer is awaited
    #   queued           the prepared next utterance (a plan dict), waiting
    #                    for a quiet report that permits it
    #   opened_topics    D3: topics already asked open-form, case-folded
    #   handover         None | "anything_else" | "final": where the
    #                    handover sequence stands

    def _request_revision(auto: dict, why: str, *, rerank: bool = False) -> None:
        """A turn has ended and the machine's next ask is due (an answer's
        end, the golden exit, a hand-back). Spec §5 — asking does not wait
        for the pass:

        - Under AUTO_STRICT_REVISE (D-C option a, the recommended
          cadence) a full CDS pass is requested on every answer, so the
          urgency check runs exactly as often as before the queue;
          maybe_run_cds launches it at once, bypassing CDS_MIN_NEW_CHARS.
          The flag now says only whether that pass is requested — never
          whether the ask waits for it.
        - If the queue has a pending item, the next ask is planned NOW
          from its head (topic call, pre-synthesis, issue at the next
          permitting quiet); a running pass never blocks it, and its
          merge may change the head before the ask after this one, which
          is fine.
        - Empty rules (as the owner restated them 2026-09-09): nothing
          pending → "Let me think for a moment." once (handle_quiet) and
          wait for the pass in flight, or request one; its merge adds
          pending items → ask from the head; adds nothing → the
          anything-else phrase once, then the examination handover
          (_ask_after_pass).
        - With `rerank` (an ANSWER's turn end, spec §3): if anything is
          pending, the re-ranker runs first — whether or not a full pass
          is in flight, and with a single pending item too (owner
          decision 2026-09-09, G5: D-F switched it off exactly when it
          was needed, and a lone stale head was never checked) — and the
          plan follows its verdict (or its failure, bounded by
          AUTO_RERANK_TIMEOUT_S): the head Alba asks next is chosen after
          what the patient just said. The pass requested here is held
          until the re-ranker and the topic call have returned (bounded by
          AUTO_SHORT_CALLS_HOLD_S; maybe_run_cds), so on Ollama's single
          slot the short calls come first (owner decision 2026-09-09, G4)."""
        if AUTO_STRICT_REVISE:
            auto["revision"] = "requested"
            logger.info("Live session %s: auto revision requested (%s)", session_id, why)
        if rerank and _start_rerank(auto, why):
            return
        if _plan_from_queue(auto, why=why):
            return
        if auto["revision"] is None:
            auto["revision"] = "requested"
            logger.info("Live session %s: auto revision requested — nothing pending (%s)",
                        session_id, why)

    def _pass_in_flight() -> bool:
        return cds_task is not None and not cds_task.done()

    def _planned_item_id(auto: dict) -> str | None:
        """The queue item a plan already covers — queued, or being prepared
        by a live plan_task — which a re-rank verdict must leave alone."""
        queued = auto["queued"]
        if queued is not None and queued.get("kind") == "question":
            return queued.get("item_id")
        if auto["plan_task"] is not None and not auto["plan_task"].done():
            return auto.get("planning_item_id")
        return None

    def _start_rerank(auto: dict, why: str) -> bool:
        """The re-ranker at an answered turn end (AGENDA_QUEUE_SPEC.md §3,
        D-B). Returns True when a re-rank is under way and the plan will
        follow it; False when the caller should plan now.

        - Nothing pending: nothing to judge, no call, no row.
        - A full pass in flight is NOT a skip (owner decision 2026-09-09,
          pilot 490 G5, reversing D-F): under cadence (a) a pass is in
          flight at most answered turn ends, so the skip switched the
          re-ranker off exactly when it was needed — 490 asked "Do you
          smoke?" to a patient who had just said so, the pass that knew
          in flight. The slice-3 race logic protects a planned item and
          applies a late verdict to the post-merge queue; the pass
          requested at this turn end is held behind the short calls
          (maybe_run_cds), so the re-ranker is not queued behind it.
        - One pending item IS consulted (same decision): a lone stale
          head can be dropped by a verdict, and the empty rules follow.
        - No committed turn since the last pass landed: nothing for the
          re-ranker to judge, skipped (reason no_new_turns).
        - Otherwise the call runs on the pending (id, text) pairs and the
          D-B excerpt — the turns since the last landed pass, at most
          AUTO_RERANK_CONTEXT_TURNS, cut to AUTO_RERANK_MAX_CHARS from the
          front — and _rerank_then_plan applies what comes back."""
        queue: agenda_queue.AgendaQueue = auto["queue"]
        pending = queue.pending
        if not pending:
            return False
        if auto["rerank_task"] is not None and not auto["rerank_task"].done():
            return True
        turns = entry["transcript_parts"][entry["cds_landed_parts"]:]
        excerpt = cds.rerank_excerpt(turns, max_turns=AUTO_RERANK_CONTEXT_TURNS,
                                     max_chars=AUTO_RERANK_MAX_CHARS)
        if not excerpt:
            logger.info("Live session %s: re-rank skipped (no_new_turns), %d pending", session_id,
                        len(pending))
            asyncio.create_task(audit.log(user["id"], "auto.rerank_skipped", None, None,
                                          {"session_id": session_id, "reason": "no_new_turns",
                                           "pending": len(pending),
                                           "pass_in_flight": _pass_in_flight(),
                                           "at_audio_s": round(session.audio_seconds, 1)}))
            return False
        pairs = [(i.id, i.text) for i in pending]
        if auto["short_calls_since"] is None:
            auto["short_calls_since"] = time.monotonic()   # the pass hold's zero (G4)
        auto["rerank_task"] = asyncio.create_task(
            _rerank_then_plan(auto, pairs, excerpt, len(turns), why))
        return True

    async def _audit_model_call(kind: str, verdict, *, queued_ms: int, pass_in_flight: bool) -> None:
        """Every model call on the record (AGENDA_QUEUE_SPEC.md §7a): the
        re-ranker first, in the shape slice 6 extends to the other calls —
        kind; queued_ms (from the decision to call to the request leaving;
        0 until slice 6's scheduler holds calls back); run_ms (the server's
        own total for the call when it reported one — Ollama's
        total_duration — else the HTTP round trip); elapsed_ms (the round
        trip); tokens {prompt, output} when reported; outcome (ok |
        timeout | cap | malformed | error) with the failure text when not
        ok; the model; and whether a full pass held the slot when the call
        was issued (false for the re-ranker by construction)."""
        await audit.log(user["id"], "model.call", None, None,
                        {"session_id": session_id, "kind": kind,
                         "model": getattr(engine, "model", None),
                         "queued_ms": int(queued_ms),
                         "run_ms": verdict.run_ms if verdict.run_ms is not None else verdict.elapsed_ms,
                         "elapsed_ms": verdict.elapsed_ms,
                         "tokens": dict(verdict.tokens) if verdict.tokens else None,
                         "outcome": verdict.outcome,
                         **({"failed": verdict.failed} if verdict.failed else {}),
                         "pass_in_flight": pass_in_flight,
                         "at_audio_s": round(session.audio_seconds, 1)})

    async def _rerank_then_plan(auto: dict, pairs: list, excerpt: str, excerpt_turns: int,
                                why: str) -> None:
        """Run the re-ranker, apply its verdict, plan the next ask, then
        write the record.

        Fail-soft (spec §3): a failed or timed-out call leaves the order
        standing, audited auto.rerank_failed with the reason and elapsed_ms
        (a cap hit is also cds.runaway, like the topic call's). A verdict
        goes through queue.apply_rerank — pending items only; any id that
        is not a known pending item is ignored and listed in the row (the
        no-invention guard is the module's) — audited auto.queue_reranked
        with order, drops with reasons, ignored ids and ms.

        Re-order only, never drop (owner decision 2026-09-10, pilot 491:
        0 for 7 wrong drops on the record): the verdict's drops are
        received by the module and written on the row as drops_advised
        (id, text, the reason text), but with AUTO_RERANK_DROPS_ENABLED
        false — the default — none is applied: the items keep their
        pending status; one the order does not name follows the named
        ones (the protected item is popped before either way). With the
        flag on (the old behaviour, kept for evals/, never deleted) a drop
        marks the item dropped with the re-ranker's one-word reason; a
        dropped item is a fresh proposal if a later pass raises it again
        (slice-1 decision).

        The verdict is applied and the plan made in the same step the
        call returns, BEFORE any audit write: an await between the two is
        a window in which the pass requested at the same turn end can
        land, merge and plan the un-re-ranked head (it did, under a slow
        database). The race that remains: something planned a question
        while the call was out — that pass landing first (the merge
        supersedes the verdict, D-F, and _ask_after_pass plans from the
        merged head at once), a doctor's tap that consumed an item, RESUME
        planning from the head. Then the planned item is protected:
        removed from the drops and put first in the order, so the verdict
        shapes the rest of the queue and never displaces a question whose
        words may already be audio. If nothing is planned or queued, the
        new head is planned; nothing pending falls to the empty rules.
        Every model call is audited model.call (kind=rerank)."""
        queue: agenda_queue.AgendaQueue = auto["queue"]
        decided = time.monotonic()
        in_flight = _pass_in_flight()
        started = time.monotonic()
        try:
            verdict = await engine.rerank(pairs, excerpt)
        finally:
            auto["rerank_task"] = None
        # -- apply and plan, synchronously ---------------------------------
        event = protected = None
        protected_dropped = False
        if verdict.failed is None:
            protected = _planned_item_id(auto)
            order = list(verdict.order_ids)
            drops = dict(verdict.drop_ids)
            protected_dropped = protected is not None and protected in drops
            if protected is not None:
                drops.pop(protected, None)
                order = [protected] + [i for i in order if i != protected]
            # The module still receives the drops (its no-invention guard
            # lists the unknown ids); whether it applies them is the flag's
            # — off, re-order only (owner decision 2026-09-10).
            event = queue.apply_rerank(order, drops, ms=verdict.elapsed_ms,
                                       apply_drops=AUTO_RERANK_DROPS_ENABLED)
            logger.info("Live session %s: queue re-ranked in %d ms — order %s, dropped %s "
                        "(advised %s), ignored %s%s", session_id, verdict.elapsed_ms,
                        event["order"], [d["id"] for d in event["drops"]],
                        [d["id"] for d in event["drops_advised"]], event["ignored"],
                        f", protected {protected}" if protected else "")
        else:
            logger.info("Live session %s: re-rank failed (%s) after %d ms — the order stands",
                        session_id, verdict.failed, verdict.elapsed_ms)
        ctl: auto_mode.AutoModeController = auto["controller"]
        if ctl.phase in auto_mode.QUESTION_PHASES and auto["handover"] is None:
            if not _plan_from_queue(auto, why=f"{why}; after re-rank") and auto["revision"] is None:
                # Nothing pending after the verdict and no pass running:
                # the empty rule — request one (spec §5).
                auto["revision"] = "requested"
                logger.info("Live session %s: auto revision requested — nothing pending after "
                            "re-rank (%s)", session_id, why)
        # -- the record ----------------------------------------------------
        await _audit_model_call("rerank", verdict, queued_ms=round((started - decided) * 1000),
                                pass_in_flight=in_flight)
        if verdict.failed is not None:
            if verdict.outcome == "cap":
                await audit.log(user["id"], "cds.runaway", None, None,
                                {"session_id": session_id, "call": "rerank", "reason": "cap",
                                 "detail": verdict.failed, "elapsed_ms": verdict.elapsed_ms,
                                 "cap": cds.AUTO_RERANK_MAX_TOKENS,
                                 "at_audio_s": round(session.audio_seconds, 1)})
            await audit.log(user["id"], "auto.rerank_failed", None, None,
                            {"session_id": session_id, "reason": verdict.failed,
                             "outcome": verdict.outcome, "elapsed_ms": verdict.elapsed_ms,
                             "timeout_s": cds.AUTO_RERANK_TIMEOUT_S, "pending": len(pairs),
                             "at_audio_s": round(session.audio_seconds, 1)})
        else:
            await _audit_queue_events((event,), {
                "excerpt_turns": excerpt_turns, "excerpt_chars": len(excerpt),
                "protected": protected, "protected_dropped_by_verdict": protected_dropped,
                "drops_enabled": AUTO_RERANK_DROPS_ENABLED})

    def _ask_after_pass(auto: dict, version: int, why: str) -> None:
        """The pass auto mode asked for has landed (and merged) or failed.
        A plan already under way, or a question already queued, is left
        alone. Nothing pending after a post-answer revision → the handover
        sequence (§6 as amended; it issues at the next turn end if the
        patient is speaking). Something pending and the turn already
        ended → the ask was waiting for this pass: plan it now. Something
        pending and the patient mid-turn → nothing here; that turn's end
        plans from the head (spec §5), after the re-rank. A pass that
        lands while a re-rank is still in flight plans from the merged
        head at once — the merge supersedes the verdict (D-F), and when
        the late verdict arrives it leaves the planned item alone
        (_rerank_then_plan)."""
        if auto["queued"] is not None:
            return
        if auto["plan_task"] is not None and not auto["plan_task"].done():
            return
        if not auto["queue"].has_pending:
            _plan_handover(auto, version)
        elif auto["turn_ended"]:
            _plan_from_queue(auto, why=why)

    def _agenda_ref(item) -> tuple[int, int] | None:
        """Where the whitelist finds a queue item's words: the (assessment
        version, index) of its text in the versioned AgendaLog — the pass
        that last listed it first (exactly, else the pass's own wording of
        it, which is equal after normalisation), then the pass that first
        proposed it. None only if both have aged out of the log's history,
        which D-A (three absent passes drop) should make impossible."""
        log = entry["agenda"]
        for version in dict.fromkeys((item.last_seen_version, item.first_version)):
            snapshot = log.get(version)
            if snapshot is None:
                continue
            for i, q in enumerate(snapshot.questions):
                if q.strip() == item.text:
                    return version, i
            for i, q in enumerate(snapshot.questions):
                if agenda_queue.question_key(q) == item.key:
                    return version, i
        return None

    def _plan_from_queue(auto: dict, *, why: str) -> bool:
        """Choose the next question from the standing queue's head and
        prepare it in the background: the topic call (D1), then
        pre-synthesis (§9, AUTO_PRESYNTH). Returns True when a plan is
        under way (new, or already in flight); False when the queue has
        nothing pending — the caller applies the empty rules (spec §5).

        No question is asked twice (owner decision 2026-09-07, pilot 486
        F4, and the standing question queue): the guarantee lives in the
        queue — an asked or answered question is DISCARDED at the merge
        and is never pending again — so there is nothing to skip here.
        The deliberate re-ask for want of an answer (F5) does not come
        this way and is exempt. One manner rule stays: not the same words
        twice in a row when there is any other to ask — a question asked
        but not heard (politeness-aborted, requeued at its rank) is not
        planned again straight after itself."""
        if auto["plan_task"] is not None and not auto["plan_task"].done():
            return True
        if auto["queued"] is not None and auto["queued"]["kind"] == "question":
            return True                      # already prepared, waiting for its quiet
        queue: agenda_queue.AgendaQueue = auto["queue"]
        while True:
            pending = queue.pending
            if not pending:
                return False
            item = pending[0]
            last = auto.get("last_asked_text")
            if last is not None and item.text == last and len(pending) > 1:
                item = pending[1]
            ref = _agenda_ref(item)
            if ref is not None:
                break
            logger.error("Live session %s: queue item %s (%r, v%d) resolves to no agenda "
                         "version — dropped", session_id, item.id, item.text, item.first_version)
            asyncio.create_task(_audit_queue_events((queue.drop(item.id, "unresolvable"),)))
        auto["handover"] = None
        auto["handover_by_doctor"] = False   # a refill returned the flow to the questions
        auto["planning_item_id"] = item.id   # a re-rank verdict landing now leaves this item alone
        auto["topic_pending"] = True         # a short call is out: the pass waits for it (G4)
        if auto["short_calls_since"] is None:
            auto["short_calls_since"] = time.monotonic()
        auto["plan_task"] = asyncio.create_task(_prepare_question(auto, item, ref, why))
        return True

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

    async def _prepare_question(auto: dict, item, ref: tuple[int, int], why: str) -> None:
        """D3, the topic-scoped cone: a NEW topic is asked open-form through
        the tell_me_more template; a topic already opened this session is
        asked verbatim. The topic call is fail-soft — no usable topic means
        verbatim, audited auto.topic_failed. Then pre-synthesise, so the ask
        is a cache hit when the quiet report permits it. The plan remembers
        the queue item's id: THAT item is consumed at issue, whatever the
        head is by then, because the prepared audio is for its words."""
        version, index = ref
        text = item.text
        queue: agenda_queue.AgendaQueue = auto["queue"]
        try:
            verdict = await engine.topic_for(text)
        finally:
            auto["topic_pending"] = False    # the short call is back: the pass may launch (G4)
        current = queue.get(item.id)
        if current is None or not current.pending:
            # Consumed by a doctor's tap, or dropped by a merge, while the
            # topic call ran: nothing to queue for it. Plan the new head
            # instead (this task is the one _plan_from_queue would wait on,
            # so it steps aside first).
            logger.info("Live session %s: planned item %s is no longer pending (%s) — replanning",
                        session_id, item.id, current.status.value if current else "gone")
            auto["plan_task"] = None
            if auto["controller"].phase in auto_mode.QUESTION_PHASES:
                _plan_from_queue(auto, why=f"{why}; replanned")
            return
        topic = verdict.topic
        if topic:
            queue.set_topic(item.id, topic)
        open_form = False
        if verdict.failed is not None and verdict.failed.startswith("CDSRunaway"):
            await audit.log(user["id"], "cds.runaway", None, None,
                            {"session_id": session_id, "call": "topic", "reason": "cap",
                             "detail": verdict.failed, "elapsed_ms": verdict.elapsed_ms,
                             "cap": cds.AUTO_TOPIC_MAX_TOKENS,
                             "at_audio_s": round(session.audio_seconds, 1)})
        if verdict.failed is not None:
            await audit.log(user["id"], "auto.topic_failed", None, None,
                            {"session_id": session_id, "reason": verdict.failed,
                             "agenda_version": version, "index": index,
                             "elapsed_ms": verdict.elapsed_ms})
        elif auto_mode.match_action(topic.casefold(), auto["opened_topics"],
                                    AUTO_TOPIC_MATCH_THRESHOLD) is None:
            # A NEW topic by meaning, not by string (owner decision
            # 2026-09-07, pilot 486 F4): "this chest pain" and "the pain"
            # are one topic.
            open_form = True
        lay_used = False
        if open_form:
            utterance = auto_mode.TemplateUtterance("tell_me_more", topic)
            spoken = speech.render_template("tell_me_more", topic)
        else:
            # Lay wording (owner decision 2026-09-09, the D1 extension):
            # the verbatim ask is spoken in the topic call's plain-English
            # wording of the SAME question when that wording passes the
            # subject guard; otherwise — drift, an unusable wording, a
            # timeout or a failed call — the original, verbatim, as
            # before. The item's identity stays the original text.
            utterance = auto_mode.AgendaUtterance(version, index)
            spoken = text
            if verdict.lay is not None:
                ok, score = speech.lay_accepted(verdict.lay, text)
                if ok:
                    utterance = auto_mode.LayUtterance(version, index, verdict.lay)
                    spoken = verdict.lay
                    lay_used = True
                else:
                    await audit.log(user["id"], "auto.lay_rejected", None, None,
                                    {"session_id": session_id, "question": text,
                                     "lay": verdict.lay, "score": score,
                                     "threshold": speech.AUTO_LAY_MIN_SIMILARITY,
                                     "queue_item": item.id, "agenda_version": version,
                                     "at_audio_s": round(session.audio_seconds, 1)})
                    logger.info("Live session %s: lay wording rejected (%.3f < %.2f): %r for %r",
                                session_id, score, speech.AUTO_LAY_MIN_SIMILARITY,
                                verdict.lay, text)
        auto["queued"] = {"utterance": utterance, "kind": "question", "text": spoken,
                          "agenda_version": version, "index": index, "question": text,
                          "item_id": item.id, "topic": topic, "open_form": open_form,
                          "lay": lay_used}
        auto["handover"] = None
        logger.info("Live session %s: auto question planned from queue %s (v%d[%d]; %s, %s): %r",
                    session_id, item.id, version, index, why,
                    "open" if open_form else ("lay" if lay_used else "verbatim"), spoken)
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
        queue: agenda_queue.AgendaQueue = auto["queue"]
        plan = auto["queued"]
        verdict = auto.get("officer_verdict")
        trigger = {"quiet_s": round(quiet_s, 1),
                   "handed_back": bool(verdict.handed_back) if verdict else False}
        detail = None
        if plan["kind"] == "question":
            item = queue.get(plan["item_id"])
            if item is None or not item.pending:
                # The planned item was consumed by a doctor's tap or dropped
                # by a merge since the plan: its audio is for words the
                # queue no longer offers. Plan the head instead.
                logger.info("Live session %s: queued item %s is no longer pending (%s) — replanning",
                            session_id, plan["item_id"], item.status.value if item else "gone")
                auto["queued"] = None
                if not _plan_from_queue(auto, why="queued item gone at issue"):
                    _plan_handover(auto, entry["agenda"].current_version)
                return
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
        # No plan is issued before its pre-synthesis has finished (owner
        # decision 2026-09-09, G7): the plan task — the topic call is back
        # by now; what remains is the synthesis — is awaited, bounded by
        # AUTO_PRESYNTH_WAIT_S, so the issue is a cache hit. Past the bound
        # the issue synthesises at issue, as before, and says so.
        task = auto["plan_task"]
        if task is not None and not task.done():
            waited_from = time.monotonic()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=AUTO_PRESYNTH_WAIT_S)
            except asyncio.TimeoutError:
                waited_ms = int(round((time.monotonic() - waited_from) * 1000))
                await audit.log(user["id"], "auto.presynth_fallback", None, None,
                                {"session_id": session_id, "text": plan["text"],
                                 "kind": plan["kind"], "waited_ms": waited_ms,
                                 "bound_s": AUTO_PRESYNTH_WAIT_S,
                                 "at_audio_s": round(session.audio_seconds, 1)})
                logger.info("Live session %s: pre-synthesis still running after %d ms — "
                            "synthesising at issue", session_id, waited_ms)
            except Exception:  # noqa: BLE001 - the plan task's own fault surfaces at issue
                pass
            if auto["queued"] is not plan:
                return                     # the plan changed under the wait (a tap, a pause)
            free_now = not session.speaking and entry["pending_utterance"] is None
            if not free_now:
                return
        issued_at = time.monotonic()          # the issue instant: one reading for all three numbers
        if plan["kind"] == "question":
            if auto["turn_ended_at"] is not None:
                # The number to beat, per question (spec §7): from the turn
                # end that permitted this ask (auto.turn_ended, or the
                # golden exit's) to the issue — the decision to speak, after
                # any wait for the pre-synthesis (G7); synthesis and
                # transport are in issue_to_speech_ms. 486 baseline: 27.7 s.
                detail["turn_end_to_issue_ms"] = int(
                    round((issued_at - auto["turn_ended_at"]) * 1000))
            # Consume THIS item by id (spec §2, §5) — not whatever is head by
            # now — before the slot is taken; if the issue fails the item
            # goes straight back to its rank.
            consumed = queue.consume(plan["item_id"], by="auto")
        prepared = await auto_issue(plan["utterance"], phase=ctl.phase, trigger=trigger,
                                    detail=detail)
        if prepared is None:
            if plan["kind"] == "question":
                await _audit_queue_events((queue.requeue(plan["item_id"]),), {"issue": "failed"})
            return                     # in flight or a fault: try again on the next report
        auto["queued"] = None
        auto["think_used"] = False           # the wait is over; the next one starts fresh
        auto["last_issued"] = {**plan, "utterance_id": prepared.utterance_id,
                               "issued_at": issued_at,
                               "turn_ended_at": auto["turn_ended_at"],
                               "turn_end_to_issue_ms": (detail or {}).get("turn_end_to_issue_ms")}
        auto["turn_ended"] = False       # the next turn end is the answer's
        auto["awaiting_speech"] = plan["kind"] != "handover"   # F5: a turn must start before it can end
        auto["reasked"] = False
        if plan["kind"] == "question":
            auto["last_asked_text"] = plan["question"]   # the original: the identity (lay or not)
            auto["asked_item_id"] = plan["item_id"]    # answered at the answer's turn end (F4)
            # The spoken text beside the original (owner decision 2026-09-09):
            # the row's `text` is the item's identity; `spoken` is what the
            # patient heard — the lay wording, the template, or the same.
            await _audit_queue_events((consumed,), {"utterance_id": prepared.utterance_id,
                                                    "spoken": plan["text"],
                                                    "lay": bool(plan.get("lay"))})
            if plan["open_form"]:
                auto["opened_topics"].add(plan["topic"].casefold())
            auto["awaiting_answer"] = True
        elif plan["kind"] == "anything_else":
            auto["anything_else_done"] = True
            auto["awaiting_answer"] = True
        elif plan["kind"] == "handover":
            auto["awaiting_answer"] = False   # nothing follows but the exam

    async def _note_question_latency(utterance: speech.Utterance) -> None:
        """The number to beat (AGENDA_QUEUE_SPEC.md §7): turn end → Alba
        speaking, per question. The client's speak_started is the moment
        playback actually began (the same report that opens the exclusion
        window), so it is the far end of the measurement; the near end is
        the turn end that permitted the ask. Audited auto.question_latency
        for every auto QUESTION whose issue followed a turn end, with
        turn_end_to_issue_ms, issue_to_speech_ms and turn_end_to_speech_ms.
        486 baseline: 27.7 s mean."""
        auto = entry["auto"]
        if auto is None:
            return
        last = auto.get("last_issued")
        if (last is None or last.get("utterance_id") != utterance.utterance_id
                or last.get("kind") != "question" or last.get("turn_ended_at") is None):
            return
        now = time.monotonic()
        reask = bool(last.get("reask"))
        await audit.log(user["id"], "auto.question_latency", None, None,
                        {"session_id": session_id, "utterance_id": utterance.utterance_id,
                         "text": last.get("text"), "queue_item": last.get("item_id"),
                         # The F5 re-ask has no turn end of its own (owner
                         # decision 2026-09-09, G8): its row is marked and
                         # carries only issue → speech; it is excluded from
                         # the turn-end mean by that mark.
                         "reask": reask,
                         "turn_end_to_issue_ms": None if reask else last.get("turn_end_to_issue_ms"),
                         "issue_to_speech_ms": int(round((now - last["issued_at"]) * 1000)),
                         "turn_end_to_speech_ms": (None if reask else
                                                   int(round((now - last["turn_ended_at"]) * 1000))),
                         "phase": auto["controller"].phase.value,
                         "at_audio_s": round(session.audio_seconds, 1)})

    async def on_fresh_agenda(version: int) -> None:
        """maybe_run_cds landed the pass auto mode asked for (D2), and it
        has merged into the standing queue: plan the next ask from the
        queue's head — or, if nothing is pending after a post-answer
        revision, the handover sequence (spec §5, §6 as amended). A plan
        already under way (or a question already queued) is left alone:
        the merge may have changed the head, which is fine."""
        auto = entry["auto"]
        if auto is None or auto["revision"] != "running":
            return
        auto["revision"] = None
        if auto["controller"].phase not in auto_mode.QUESTION_PHASES:
            return
        _ask_after_pass(auto, version, "post-answer revision")

    async def on_auto_utterance_ended(utterance: speech.Utterance, reason: str,
                                      *, rms: float | None = None) -> None:
        """The lifecycle end of an AUTO utterance, from handle_speak_ended.
        A politeness-aborted QUESTION (or handover phrase) is requeued and
        re-issued at the next permitting quiet — unlike an encourager,
        which is dropped; the examination handover, played through, ends
        the auto run (machine HANDOVER, audit auto.handover). A
        politeness-aborted enable disclosure or chained invitation is
        retried on the next quiet report, then the machine switches itself
        off (owner decision 2026-09-09, pilot 488 G1); `rms` is the
        client's reading at the abort."""
        auto = entry["auto"]
        if auto is None:
            return
        chain = auto.get("enable_chain")
        if (chain is not None and chain.get("utterance_id") == utterance.utterance_id
                and reason == "politeness_abort"):
            await _on_enable_chain_aborted(auto, utterance, rms)
            return
        last = auto.get("last_issued")
        if last is None or last.get("utterance_id") != utterance.utterance_id:
            return
        if reason == "politeness_abort":
            auto["queued"] = {k: v for k, v in last.items() if k != "utterance_id"}
            auto["awaiting_answer"] = False
            auto["awaiting_speech"] = False    # nothing was asked; no answer is awaited (F5)
            auto["asked_item_id"] = None       # and nothing to count as asked (F4)
            if last["kind"] == "question":
                # The queue item goes back to pending at its rank (spec §2
                # as built): the question was never put to the patient.
                # The prepared plan is kept for the re-issue — the audio is
                # cached — and consumes the item again when it plays.
                item = auto["queue"].get(last.get("item_id"))
                if item is not None and item.status is agenda_queue.ItemStatus.ASKED:
                    await _audit_queue_events((auto["queue"].requeue(item.id),),
                                              {"utterance_id": utterance.utterance_id})
            logger.info("Live session %s: auto %s politeness-aborted, requeued",
                        session_id, last["kind"])
            return
        if last["kind"] == "handover" and reason == "complete":
            ctl: auto_mode.AutoModeController = auto["controller"]
            by_doctor = auto.get("handover_by_doctor", False)
            if by_doctor and ctl.is_legal(auto_mode.AutoEvent.HANDOVER_REQUESTED):
                # The doctor asked (slice 6), from OPEN/CLOSED: the machine
                # records that, not an empty agenda.
                await auto_transition(ctl.handover_requested(),
                                      detail={"by": "doctor",
                                              "agenda_version": last["agenda_version"]})
            elif not by_doctor and ctl.is_legal(auto_mode.AutoEvent.AGENDA_EXHAUSTED):
                await auto_transition(ctl.agenda_exhausted(),
                                      detail={"agenda_version": last["agenda_version"]})
            if ctl.phase is auto_mode.AutoPhase.HANDOVER:
                auto["handover"] = None
                await audit.log(user["id"], "auto.handover", None, None,
                                {"session_id": session_id,
                                 "agenda_version": last["agenda_version"],
                                 "requested_by": "doctor" if by_doctor else "agenda_empty",
                                 "at_audio_s": round(session.audio_seconds, 1)})
                await websocket.send_json({"type": "auto_toggled", "on": _auto_on(ctl),
                                           "phase": ctl.phase.value})

    async def on_doctor_tap(utterance: speech.Utterance, *, confirmed: bool = False) -> None:
        """A doctor's tap while auto mode is on (spec §3, hard rule 5): the
        queued auto utterance is cancelled, the tap is audited as an
        intervention naming what it displaced and whether the doctor
        confirmed the displacement (owner decision 2026-09-07: a tap over a
        planned or queued question is answered with speak_confirm first,
        handle_speak), and the answer that follows is treated like any
        other — its turn end triggers the revision.

        A tapped EXAMINATION HANDOVER in GOLDEN, OPEN or CLOSED ends the
        auto run exactly as the Handover control does (owner decision
        2026-09-01, pilot defect D5): in 482 the doctor tapped "Thank you —
        Dr … will examine you now" during the golden minutes and the
        machine, whose flow state a tap did not touch, said "Mm-hm." 1.8 s
        later. The doctor has handed over; the history is finished."""
        auto = entry["auto"]
        if auto is None or auto["controller"].phase is auto_mode.AutoPhase.OFF:
            return
        displaced = auto["queued"]
        auto["queued"] = None
        for key in ("plan_task", "rerank_task"):
            if auto[key] is not None and not auto[key].done():
                auto[key].cancel()       # the tap's answer will re-rank and plan afresh
            auto[key] = None
        auto["topic_pending"] = False
        await audit.log(user["id"], "auto.doctor_tap", None, None,
                        {"session_id": session_id, "phase": auto["controller"].phase.value,
                         "ref_kind": utterance.ref_kind, "ref_detail": utterance.ref_detail,
                         "utterance_id": utterance.utterance_id,
                         "displaced": ({"kind": displaced["kind"], "text": displaced["text"]}
                                       if displaced else None),
                         "confirmed": confirmed,
                         "at_audio_s": round(session.audio_seconds, 1)})
        if (utterance.ref_kind == "phrase"
                and utterance.ref_detail.get("id") == "examination_handover"
                and auto["controller"].phase in auto_mode.LISTENING_PHASES):
            await _end_run_by_tapped_handover(auto, utterance)
            return
        if (utterance.ref_kind == "cds_question"
                and auto["controller"].phase in auto_mode.LISTENING_PHASES):
            if auto["controller"].phase in auto_mode.QUESTION_PHASES:
                auto["awaiting_answer"] = True
                auto["turn_ended"] = False
                auto["last_asked_text"] = utterance.text
            # The doctor's ask counts too (F4, D-E): a tapped question that
            # is a pending queue item consumes it (by=tap) and Alba
            # continues from the new head; one the queue never held — an
            # older panel version's item, or one not merged — is recorded
            # as asked (auto.queue_asked_externally) so it can never
            # re-enter; a re-tap of the item already asked (the aborted
            # one) is awaited the same way. In every case its answer's
            # turn end marks the item answered. An already-answered
            # question the doctor asks again is theirs to ask; nothing is
            # recorded twice. In GOLDEN too (owner decision 2026-09-09,
            # pilot 488 G9): the bookkeeping ran only in the question
            # phases, so 488's two tapped questions left the queue
            # untouched and Alba could have asked them again; the flow
            # flags above stay the question phases' — no answer is awaited
            # in the golden minutes, and the exit marks the item answered.
            queue: agenda_queue.AgendaQueue = auto["queue"]
            item = queue.find(utterance.text)
            asked_id = None
            if item is None:
                event = queue.add_asked(utterance.text, by="tap",
                                        version=utterance.ref_detail.get("assessment_version"))
                await _audit_queue_events((event,), {"utterance_id": utterance.utterance_id})
                asked_id = event["id"]
            elif item.pending:
                await _audit_queue_events((queue.consume(item.id, by="tap"),),
                                          {"utterance_id": utterance.utterance_id})
                asked_id = item.id
            elif item.status is agenda_queue.ItemStatus.ASKED:
                asked_id = item.id
            if auto["controller"].phase is auto_mode.AutoPhase.GOLDEN:
                if asked_id is not None:
                    auto["golden_tapped"].append(asked_id)   # every golden tap, answered at the exit
            else:
                auto["asked_item_id"] = asked_id

    async def _end_run_by_tapped_handover(auto: dict, utterance: speech.Utterance) -> None:
        """The tapped handover phrase IS the handover: the same edge the
        Handover control fires (handover_requested → HANDOVER), audited
        auto.doctor_handover with via=tap and auto.handover with
        requested_by=doctor, the officer and any plan or sequence stood
        down, and the client told the run has ended (auto_toggled off) —
        so no encourager, ask or machine handover can follow the doctor's
        own words. The run ends at the tap, not at the phrase's end: a
        cut-off phrase is still the doctor's decision."""
        ctl: auto_mode.AutoModeController = auto["controller"]
        await audit.log(user["id"], "auto.doctor_handover", None, None,
                        {"session_id": session_id, "phase": ctl.phase.value, "via": "tap",
                         "utterance_id": utterance.utterance_id,
                         "at_audio_s": round(session.audio_seconds, 1)})
        _cancel_officer(auto)          # drops the queue, any plan and the revision
        auto.update(turn_ended=False, awaiting_answer=False, think_used=False,
                    handover=None, handover_by_doctor=True, last_issued=None)
        await auto_transition(ctl.handover_requested(), detail={"by": "doctor", "via": "tap"})
        await audit.log(user["id"], "auto.handover", None, None,
                        {"session_id": session_id,
                         "agenda_version": entry["agenda"].current_version,
                         "requested_by": "doctor", "via": "tap",
                         "at_audio_s": round(session.audio_seconds, 1)})
        await websocket.send_json({"type": "auto_toggled", "on": _auto_on(ctl),
                                   "phase": ctl.phase.value})

    async def _repause_suppressed(actions: list[dict], assessment_version: int,
                                  pre_answer: bool) -> bool:
        """The resume ratchet's one answer's chance, made real (owner
        decision 2026-09-01, pilot defect D4, spec §7 as amended).

        In 482 the CDS pass in flight when RESUME AUTO was acknowledged
        landed 2.0 s later with the same "Bedside ECG" still unarranged
        and re-paused, cutting "Mm-hm." after 450 ms — the stutter the
        owner heard. Nobody could have arranged anything in 2 s; the
        pass predated the resume. So: a pass that was in flight at the
        resume, or was launched before the first turn end after it, may
        NOT re-pause on actions the doctor has already acknowledged. It
        is audited instead (auto.repause_suppressed, with the assessment
        version). A genuinely NEW action in the same pass still pauses —
        the widening rule of slice 5 — and a re-fire while already paused
        is untouched (the block exists only after a resume, in a listening
        phase). "The same action" is judged by meaning (owner decision
        2026-09-07, pilot 485 E3): auto_mode.match_action against the
        pending and acknowledged texts, every match audited as
        auto.action_matched with both texts and the score.
        """
        auto = entry["auto"]
        ctl: auto_mode.AutoModeController = auto["controller"]
        if ctl.phase not in auto_mode.LISTENING_PHASES:
            return False
        texts = [str(a.get("action", "")) for a in actions if a.get("action")]
        if not texts:
            return False
        # "The same action" is matched by meaning, not wording (owner
        # decision 2026-09-07, pilot 485 E3): the CDS re-worded the hospital
        # action on every pass and the text-keyed ratchet re-paused each
        # time. Every action must match something already pending or
        # acknowledged; one genuinely new action and the pass pauses,
        # widening the pending set as slice 5 pinned.
        known = ctl.acknowledged_actions | ctl.pending_actions | auto["action_aliases"]
        matches = [(text, auto_mode.match_action(text, known, AUTO_ACTION_MATCH_THRESHOLD))
                   for text in texts]
        if any(match is None for _, match in matches):
            return False
        # A matched re-wording joins the acknowledged set as an alias of
        # what it matched, so a chain of re-wordings (486: admission →
        # referral → specialist referral → admission) stays one action.
        auto["action_aliases"].update(text for text, _ in matches)
        if not pre_answer:
            # An acknowledged action does not re-pause (owner decision
            # 2026-09-07, pilot 486 F1). In 486 every one of seven
            # post-answer passes re-issued the acknowledged "Bedside ECG"
            # (with the hospital action re-worded five ways) and the ratchet
            # paused on each: eight RESUME taps, every question planned
            # from the resume handler. Once the doctor has acknowledged an
            # action, its re-fire — same by the E3 match — pauses nothing;
            # it stays on the live page's standing strip (auto_standing)
            # until the transcript shows it arranged or the consultation
            # ends. Every skipped re-pause is on the record.
            for text, (matched, score) in matches:
                await audit.log(user["id"], "auto.repause_skipped_acknowledged", None, None,
                                {"session_id": session_id, "candidate": text, "matched": matched,
                                 "score": score, "exact": text == matched,
                                 "threshold": AUTO_ACTION_MATCH_THRESHOLD,
                                 "assessment_version": assessment_version,
                                 "phase": ctl.phase.value,
                                 "at_audio_s": round(session.audio_seconds, 1)})
            logger.info("Live session %s: re-pause skipped on v%d (%s): every action is "
                        "already acknowledged", session_id, assessment_version, texts)
            return True
        for text, (matched, score) in matches:
            await audit.log(user["id"], "auto.action_matched", None, None,
                            {"session_id": session_id, "candidate": text, "matched": matched,
                             "score": score, "exact": text == matched,
                             "threshold": AUTO_ACTION_MATCH_THRESHOLD,
                             "assessment_version": assessment_version,
                             "phase": ctl.phase.value,
                             "at_audio_s": round(session.audio_seconds, 1)})
        await audit.log(user["id"], "auto.repause_suppressed", None, None,
                        {"session_id": session_id, "actions": texts,
                         "matched": [matched for _, (matched, _score) in matches],
                         "assessment_version": assessment_version,
                         "phase": ctl.phase.value,
                         "reason": "pass predates the first post-resume turn end",
                         "at_audio_s": round(session.audio_seconds, 1)})
        logger.info("Live session %s: re-pause suppressed on v%d (%s): the pass predates "
                    "the first answer after the resume", session_id, assessment_version, texts)
        return True

    def _standing_actions() -> list[str]:
        """The acknowledged-but-open actions: every urgent action the LATEST
        assessment still lists that matches (E3) something the doctor has
        acknowledged. Empty once the transcript shows them arranged (the
        pass then lists nothing — `arranged` latches in app/cds.py) or
        when nothing acknowledged is still open."""
        auto = entry["auto"]
        if auto is None or entry["assessment"] is None:
            return []
        ctl: auto_mode.AutoModeController = auto["controller"]
        texts = [str(a.get("action", "")) for a in entry["assessment"].get("urgent_actions", [])
                 if a.get("action")]
        known = ctl.acknowledged_actions | auto["action_aliases"]
        return [t for t in texts if auto_mode.match_action(t, known, AUTO_ACTION_MATCH_THRESHOLD)]

    async def _audit_queue_events(events, extra: dict | None = None) -> None:
        """Every state change the queue reports goes on the record as
        auto.<kind> — queue_merged, queue_dropped_absent, queue_capped,
        queue_consumed, queue_answered, ... (spec §7) — with the module's
        flat details, the session and the audio time."""
        for event in events:
            await audit.log(user["id"], f"auto.{event.kind}", None, None,
                            {"session_id": session_id, **dict(event.details),
                             **(extra or {}),
                             "at_audio_s": round(session.audio_seconds, 1)})

    def _merge_pass(assessment_version: int, assessment: dict) -> tuple:
        """A CDS pass has landed and been versioned: merge its
        questions_to_ask into the standing queue (spec §2) — pending
        matches refreshed, asked or answered matches DISCARDED (the
        never-re-enter guarantee), the rest appended; then D-A absence,
        the baseline order and the D-D cap, all inside the module. Only
        while auto mode is on: with the machine OFF, or its run ended, the
        pass is the doctor's panel and nothing more, and the queue is left
        exactly as it was. Returns the queue's events for the caller to
        audit — auto.queue_merged with the counts (added / refreshed /
        discarded / dropped_absent / capped) and the version, plus a row
        per drop."""
        auto = entry["auto"]
        if auto is None or not _auto_on(auto["controller"]):
            return ()
        questions = [str(q) for q in (assessment or {}).get("questions_to_ask", []) or []]
        events = auto["queue"].merge(assessment_version, questions)
        merged = events[0]
        logger.info("Live session %s: queue merged v%d — added %d, refreshed %d, discarded %d, "
                    "dropped_absent %d, capped %d, pending %d", session_id, assessment_version,
                    merged["added"], merged["refreshed"], merged["discarded"],
                    merged["dropped_absent"], merged["capped"], merged["pending"])
        return events

    async def _seed_queue() -> None:
        """Seed the queue at toggle-on (owner decision 2026-09-08). When the
        doctor switches auto mode on and the current agenda already holds
        questions_to_ask — passes landed while the machine was OFF are the
        doctor's panel and never merged — they are merged at once as a
        pass with the current agenda version, so the first ask after the
        golden exit comes from the queue's head rather than waiting for
        the exit's own pass. Audited auto.queue_merged with seeded=true.
        An empty agenda (auto pressed at the very start) is a no-op. The
        queue is also the asked-memory and lives for the session, so at a
        toggle off and on the seed's copy of an asked question is
        discarded like any pass's — asked stays asked."""
        auto = entry["auto"]
        current = entry["agenda"].current
        if auto is None or current is None or not current.questions:
            return
        events = auto["queue"].merge(current.version, list(current.questions))
        merged = events[0]
        logger.info("Live session %s: queue seeded at toggle-on from v%d — added %d, refreshed %d, "
                    "discarded %d, pending %d", session_id, current.version, merged["added"],
                    merged["refreshed"], merged["discarded"], merged["pending"])
        await _audit_queue_events(events, {"seeded": True})

    async def _push_standing(assessment_version: int | None) -> None:
        """The persistent pending-actions strip (owner decision 2026-09-07,
        pilot 486 F1): with re-pauses on acknowledged actions gone, the
        alarm must not clear silently — the live page keeps the
        acknowledged-but-open actions in view (auto_standing, in the urgent
        panel) until the transcript shows them arranged or the consultation
        ends. Pushed on every pass landing and every acknowledgement, only
        when the list changes."""
        auto = entry["auto"]
        if auto is None:
            return
        standing = _standing_actions()
        if standing == auto["standing_sent"]:
            return
        auto["standing_sent"] = standing
        await websocket.send_json({"type": "auto_standing", "actions": standing,
                                   "assessment_version": assessment_version})

    async def on_urgent_alarm(actions: list[dict], assessment_version: int) -> None:
        """The urgency pause (Phase 7c slice 5, spec §7, hard rule 2).

        A CDS pass returned non-empty urgent_actions while the machine is
        in GOLDEN, OPEN or CLOSED: the machine pauses (urgent_alarm — first
        fire, or the widening self-edge while already paused), the current
        and queued auto utterances are cut through the server stop with
        reason urgency_pause, the officer is stood down, and the pause is
        audited (auto.paused: the action texts, the assessment_snapshot
        version, the transition) and shown to the client (auto_pause, with
        EVERY pending action text — the banner must display all of them at
        acknowledgement time). Listening and transcription continue; the
        quiet reporter stays on but earns nothing while paused. In any
        other phase — auto off, disclosure, handover, taken over — nothing
        happens beyond today's alarm behaviour.
        """
        auto = entry["auto"]
        ctl: auto_mode.AutoModeController = auto["controller"]
        texts = [str(a.get("action", "")) for a in actions if a.get("action")]
        if not texts or not ctl.is_legal(auto_mode.AutoEvent.URGENT_ALARM):
            return
        already_paused = ctl.phase is auto_mode.AutoPhase.PAUSED_URGENT
        if ctl.phase is auto_mode.AutoPhase.GOLDEN:
            auto["golden_spent"] += ctl.seconds_in_phase()
        transition = ctl.urgent_alarm(texts)
        pending = sorted(ctl.pending_actions)
        if not already_paused:
            auto["pause_versions"] = []
            await cancel_auto_playback(entry, websocket, "urgency_pause")
            _cancel_officer(auto)          # also drops the queue and any plan
            auto.update(turn_ended=False, awaiting_answer=False, think_used=False,
                        revision=None, last_issued=None, awaiting_speech=False, reasked=False)
        auto["pause_versions"].append(assessment_version)
        await auto_transition(transition, detail={"actions": texts, "pending": pending,
                                                  "assessment_version": assessment_version,
                                                  "refire": already_paused})
        await audit.log(user["id"], "auto.paused", None, None,
                        {"session_id": session_id, "actions": texts, "pending": pending,
                         "assessment_version": assessment_version,
                         "refire": already_paused,
                         "paused_from": (ctl.paused_from.value if ctl.paused_from else None),
                         "transition": {"from": transition.from_phase.value,
                                        "to": transition.to_phase.value,
                                        "trigger": transition.trigger.value},
                         "at_audio_s": round(session.audio_seconds, 1)})
        await websocket.send_json({"type": "auto_pause", "pending": pending,
                                   "actions": texts, "refire": already_paused,
                                   "paused_from": (ctl.paused_from.value
                                                   if ctl.paused_from else None),
                                   "assessment_version": assessment_version})
        logger.info("Live session %s: auto PAUSED (%s) on %s — pending %s", session_id,
                    "re-fire" if already_paused else "alarm", texts, pending)

    def _golden_elapsed(auto: dict) -> float:
        """The golden window elapsed: seconds spent before any pause plus
        the seconds in GOLDEN since the last transition (there is no timer
        object — this arithmetic IS the window)."""
        return auto["golden_spent"] + auto["controller"].seconds_in_phase()

    async def _note_golden_window(auto: dict, elapsed: float, *, seen_on: str,
                                  quiet_s: float, reason: str = "elapsed") -> None:
        """Owner decision 2026-09-01 (pilot D1): the first observation of
        elapsed >= AUTO_GOLDEN_MINUTES_S in GOLDEN — on a quiet report or
        a verdict — sets golden_window_ran and audits it once
        (auto.golden_window_ran, with golden_s). Before this the window's
        end was invisible unless it coincided with an exit; in 482 and 483
        it did not, and the record could not say when the minutes ran.

        A window can also end EARLY (owner decision 2026-09-09): the
        caller passes reason="unanswered_encouragers" when
        AUTO_ENCOURAGER_MAX_UNANSWERED encouragers have gone unanswered and
        a further qualifying silence has arrived; the row then carries that
        reason and a golden_s short of window_s, which is how the record
        tells the two ends apart."""
        if auto["golden_window_ran"]:
            return
        if reason == "elapsed" and elapsed < AUTO_GOLDEN_MINUTES_S:
            return
        auto["golden_window_ran"] = True
        await audit.log(user["id"], "auto.golden_window_ran", None, None,
                        {"session_id": session_id, "golden_s": round(elapsed, 1),
                         "window_s": AUTO_GOLDEN_MINUTES_S, "seen_on": seen_on,
                         "reason": reason, "quiet_s": round(quiet_s, 1),
                         **({"encouragers": auto["golden_encourager_count"],
                             "unanswered": auto["golden_unanswered"]}
                            if reason == "unanswered_encouragers" else {}),
                         "at_audio_s": round(session.audio_seconds, 1)})
        logger.info("Live session %s: golden window ran (%.1fs of %.0fs, seen on %s, %s)",
                    session_id, elapsed, AUTO_GOLDEN_MINUTES_S, seen_on, reason)

    async def _exit_golden(auto: dict, detail: dict, why: str) -> auto_mode.Transition:
        """GOLDEN → OPEN (the golden_timer_elapsed edge): the window has run
        and the turn has ended, by whichever rule judged it. The exit is
        itself a turn end, so the D2 revision is asked for at once."""
        transition = auto["controller"].golden_timer_elapsed()
        await auto_transition(transition, detail=detail)
        auto["turn_ended"] = True
        auto["turn_ended_at"] = time.monotonic()
        auto["think_used"] = False           # a new wait begins
        await _answer_golden_tap(auto)
        auto["repause_block"] = False        # a turn has ended (pilot D4)
        _request_revision(auto, why)
        return transition

    async def _answer_golden_tap(auto: dict) -> None:
        """A question the doctor tapped in GOLDEN (G9) was answered in the
        golden minutes; the exit — the golden turn's end — marks its queue
        item answered, as an answer's turn end does in the question phases."""
        tapped, auto["golden_tapped"] = list(auto.get("golden_tapped") or ()), []
        for item_id in tapped:
            item = auto["queue"].get(item_id)
            if item is not None and item.status is agenda_queue.ItemStatus.ASKED:
                await _audit_queue_events((auto["queue"].answered(item_id),), {"at": "golden_exit"})

    async def _end_turn(auto: dict, *, by: str, quiet_s: float, verdict=None) -> None:
        """One turn-end rule in every phase (owner decision 2026-09-07,
        pilot 485 defect E1). Outside GOLDEN, a patient's turn ends at the
        first of: an officer verdict that says finished or handed back
        (`by="verdict"`), or quiet of AUTO_EOT_FALLBACK_S on the report
        itself, whether or not the officer answered or answered "not
        finished" (`by="quiet_fallback"`) — the rule the post-window golden
        exit already used. In 485 the officer said "not finished" three
        times across 7 s of silence after an answered question; the
        answer never ended a turn, no revision was requested and no next
        question came. Every turn end is audited (auto.turn_ended); if it
        is the answer's end, the D2 revision is requested (question
        phases) or the handover sequence continues (the doctor's handover
        from GOLDEN)."""
        ctl: auto_mode.AutoModeController = auto["controller"]
        if auto["turn_ended"]:
            return
        auto["turn_ended"] = True
        auto["turn_ended_at"] = time.monotonic()   # the zero of the number to beat (spec §7)
        auto["think_used"] = False           # a new wait: "Let me think" may be said once in it
        auto["repause_block"] = False        # a patient turn has ended (pilot D4)
        answer = bool(auto["awaiting_answer"])
        if verdict is not None and verdict.handed_back:
            logger.info("Live session %s: hand-back detected in %s (quiet %.1fs)",
                        session_id, ctl.phase.value, quiet_s)
        trace = auto.get("last_trace")
        # H3 (owner decision 2026-09-10, pilot 491): the span start against
        # the transcript's last word, when both are known. In 491 the span
        # began at the final's ARRIVAL, 2.1-3.7 s after the last word, and
        # every answer waited that much longer than the rule; the span is
        # now keyed on energy alone, so last_word_to_span_start_s should
        # read near zero (or negative: the final may not have arrived yet,
        # in which case last_final is the previous turn's — its age says).
        # commit_latency_s is the transcriber's own: the final's arrival on
        # the session clock minus its last word's end.
        last_final, span_start = entry.get("last_final"), auto.get("span_start")
        if last_final is not None and span_start is not None:
            latency = {"last_word_end_s": round(last_final["end"], 2),
                       "span_start_s": round(span_start["audio_s"], 2),
                       "last_word_to_span_start_s": round(span_start["audio_s"] - last_final["end"], 2),
                       "commit_latency_s": round(last_final["committed_at_audio_s"] - last_final["end"], 2),
                       "last_final_age_s": round(time.monotonic() - last_final["at"], 2)}
        else:
            latency = {"last_word_to_span_start_s": None, "commit_latency_s": None}
        await audit.log(user["id"], "auto.turn_ended", None, None,
                        {"session_id": session_id, "phase": ctl.phase.value, "by": by,
                         "quiet_s": round(quiet_s, 1), "answer": answer,
                         "fallback_s": AUTO_EOT_FALLBACK_S, **latency,
                         **({"handed_back": verdict.handed_back,
                             "finished_thought": verdict.finished_thought,
                             "officer_ms": verdict.elapsed_ms,
                             **({"officer_failed": verdict.failed} if verdict.failed else {})}
                            if verdict is not None else {}),
                         # G6 (owner decision 2026-09-09): the client's RMS
                         # trace of the last AUTO_TRACE_S seconds, as sent
                         # with the latest quiet report — newest sample
                         # last — so the next run can say what the trailing
                         # energy after an answer is.
                         **({"trace": trace["samples"], "trace_step_ms": trace["step_ms"],
                             "trace_s": AUTO_TRACE_S, "trace_quiet_s": trace["quiet_s"],
                             "trace_age_ms": int(round((time.monotonic() - trace["at"]) * 1000)),
                             "floor": trace["floor"]}
                            if trace is not None else {"trace": None}),
                         "at_audio_s": round(session.audio_seconds, 1)})
        if not answer:
            # A turn end with nothing asked and nothing awaited — the span
            # after the golden exit's pass landed mid-speech, or after a
            # doctor's word — is still a moment the machine may speak in:
            # if nothing is queued and the queue has a head, plan it now
            # (spec §5); an empty queue with a pass running keeps waiting
            # for the merge, and the handover phrase, when queued, issues
            # on this turn end as before.
            if (ctl.phase in auto_mode.QUESTION_PHASES and auto["queued"] is None
                    and auto["handover"] is None):
                _plan_from_queue(auto, why=f"turn ended with nothing asked ({by})")
            return
        auto["awaiting_answer"] = False
        item_id, auto["asked_item_id"] = auto.get("asked_item_id"), None
        if item_id is not None:
            # Asked and answered (F4, the F5 rule: the turn started with the
            # patient's speech and has ended): the queue item is ANSWERED,
            # and every later pass's copy of it is discarded at the merge.
            item = auto["queue"].get(item_id)
            if item is not None and item.status is agenda_queue.ItemStatus.ASKED:
                await _audit_queue_events((auto["queue"].answered(item_id),))
        if ctl.phase in auto_mode.QUESTION_PHASES:
            _request_revision(auto, f"answer's turn ended ({by})", rerank=True)
        elif ctl.phase is auto_mode.AutoPhase.HANDOVER and auto["handover"] is not None:
            # Slice 6: the doctor's handover from GOLDEN — the anything-else
            # answer has ended; no return path from HANDOVER, so the
            # examination handover follows directly.
            _plan_handover(auto, entry["agenda"].current_version)

    async def handle_quiet(payload: dict) -> None:
        """A quiet report from the client's reporter (spec §5). Measurement
        is the client's; every decision is here.

        In GOLDEN: every report first checks the window (owner decision
        2026-09-01, pilot D1/D3). Once it has run — golden_window_ran —
        no encourager is issued, and quiet of AUTO_EOT_FALLBACK_S exits
        to OPEN on the report itself, whether or not the officer has
        answered: in 483 a healthy officer answering "not finished" to
        every 3 s and 6 s ask, with the machine's own encouragers wiping
        the quiet span every ~8 s, kept the golden minutes open for 19 s
        after the window had run, and the fallback was never consulted
        because it applied only to a FAILED officer. Before the window:
        quiet of AUTO_ENCOURAGER_MIN_QUIET_S earns the window's ONE
        encourager — "go on", once per golden window, spent at issue
        (a politeness abort drops it — the moment has passed; owner
        decision 2026-09-01 replacing the three-phrase rotation on a
        cooldown). Quiet of AUTO_EOT_QUIET_S starts the end-of-turn
        officer, once per quiet span and again each time the quiet has
        grown by that much, so a "not finished" at 3 s is re-asked at 6 s
        rather than sticking. Its verdict is applied by
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
        # A fresh quiet span is never invisible (owner decision 2026-09-09,
        # pilot 489 G3). The client numbers its spans — `span`, incremented
        # at every activity() — and a fresh span is a new number. Before,
        # the test was quiet_s < last_quiet_s, and the client rounds every
        # threshold report to 0.1 s, so a new span whose first report
        # equalled the previous span's last (1.8 after 1.8: the patient
        # began 1.75–3 s after the last span began, the common case after a
        # question's playback) was invisible: in 489 Q3's answer was never
        # seen, the 5 s fallback could not end the turn, and the grace
        # re-asked an answered question. A report without a span (an older
        # page) keeps the old test.
        span = payload.get("span")
        if isinstance(span, (int, float)) and not isinstance(span, bool):
            span = int(span)
            fresh = auto["last_span"] is None or span != auto["last_span"]
            auto["last_span"] = span
        else:
            fresh = auto["last_quiet_s"] is None or quiet_s < auto["last_quiet_s"]
        # G6 instrumentation (owner decision 2026-09-09): the report's RMS
        # trace is kept for the turn_ended row, and the report itself is
        # audited — the first of every span always, then at most one per
        # AUTO_QUIET_REPORT_AUDIT_S. 489/490 could not say where a span
        # began or what the energy around it was.
        raw_trace = payload.get("trace")
        if isinstance(raw_trace, list) and raw_trace:
            samples = []
            for v in raw_trace[-int(AUTO_TRACE_S * 10) - 1:]:
                try:
                    samples.append(round(float(v), 5))
                except (TypeError, ValueError):
                    samples.append(None)
            auto["last_trace"] = {"samples": samples, "at": time.monotonic(),
                                  "quiet_s": round(quiet_s, 1),
                                  "step_ms": int(payload.get("trace_step_ms") or 100),
                                  "floor": payload.get("floor")}
        now = time.monotonic()
        # H1 (owner decision 2026-09-10, pilot 491): a fresh span the client
        # stamped "speech" whose start falls inside one of our own utterance
        # windows (requested to ended, plus AUTO_OWN_VOICE_TAIL_S) is our
        # voice through the microphone, not the patient's — a page whose
        # meter still counts our playback, or the room's tail of it. It is
        # read as playback below and says so on the record.
        own_voice = None
        if fresh and payload.get("since") != "playback":
            own_voice = _own_voice_at(entry, now - quiet_s)
        # H3 (owner decision 2026-09-10, pilot 491): where this span began,
        # on the session clock — for the turn_ended row's comparison with
        # the transcript's last word.
        auto["span_start"] = {"audio_s": session.audio_seconds - quiet_s, "at": now - quiet_s,
                              "span": span if isinstance(span, int) else None}
        if fresh or auto["quiet_audit_at"] is None or now - auto["quiet_audit_at"] >= AUTO_QUIET_REPORT_AUDIT_S:
            auto["quiet_audit_at"] = now
            rms = payload.get("rms")
            await audit.log(user["id"], "auto.quiet_report", None, None,
                            {"session_id": session_id, "quiet_s": round(quiet_s, 1),
                             "span": payload.get("span"), "since": payload.get("since"),
                             "rms": (round(float(rms), 5) if isinstance(rms, (int, float)) else None),
                             "floor": payload.get("floor"), "fresh": fresh,
                             "own_voice": own_voice is not None,
                             **({"own_voice_utterance": own_voice} if own_voice else {}),
                             "phase": ctl.phase.value,
                             "at_audio_s": round(session.audio_seconds, 1)})
        if fresh:
            # A fresh quiet span (by the client's span number, G3): the
            # patient spoke (or we did) in between. The officer is re-asked
            # either way; a judged turn end is cleared only when the
            # PATIENT spoke (owner decision 2026-09-07, pilot 485 E2): our
            # own utterances restart the client's span too, and in 485 the
            # bridge 1 s after the golden exit erased the turn end the exit
            # had set, so the first ask needed a second judgement in a
            # silent room. The client says what began the span (`since`:
            # "playback" or "speech"); a report without it is read as
            # speech, the cautious side — unless its start falls inside our
            # own utterance window (H1, above): then it is ours.
            auto["officer_last_run_quiet_s"] = None
            auto["officer_verdict"] = None
            auto["quiet_span_seq"] += 1      # every fresh span, whatever began it
            if own_voice is not None:
                logger.info("Live session %s: fresh span at quiet %.1f s began inside our own "
                            "utterance %s — read as playback", session_id, quiet_s, own_voice)
            if payload.get("since") != "playback" and own_voice is None:
                auto["turn_ended"] = False
                auto["span_seq"] += 1        # the patient's span moved on (E4: a late verdict is stale)
                auto["awaiting_speech"] = False   # the patient has spoken since the question (F5)
                auto["golden_unanswered"] = 0     # the patient spoke: the encouragers were answered
        auto["last_quiet_s"] = quiet_s
        in_golden = ctl.phase is auto_mode.AutoPhase.GOLDEN
        in_questions = ctl.phase in auto_mode.QUESTION_PHASES
        # Slice 6: the doctor's Handover from GOLDEN runs its two-phrase
        # sequence from HANDOVER — the queued ask and the officer work there
        # for exactly that.
        in_handover_seq = (ctl.phase is auto_mode.AutoPhase.HANDOVER
                           and auto["handover"] is not None)
        chain = auto.get("enable_chain")
        if (chain is not None and chain.get("aborted")
                and ctl.phase in (auto_mode.AutoPhase.DISCLOSURE, auto_mode.AutoPhase.INVITATION)):
            # The enable's disclosure (or chained invitation) stands
            # politeness-aborted: this report is the retry's moment (owner
            # decision 2026-09-09, pilot 488 G1). In 488 DISCLOSURE ignored
            # every report and the machine sat silent for 41 s.
            await _retry_enable_chain(auto, quiet_s)
            return
        if not (in_golden or in_questions or in_handover_seq):
            return
        if in_golden:
            # 0. The window, on every report. Once it has run, quiet of the
            #    fallback length is the exit — evaluated here, not only
            #    when a verdict is applied (owner decision 2026-09-01).
            elapsed = _golden_elapsed(auto)
            await _note_golden_window(auto, elapsed, seen_on="quiet", quiet_s=quiet_s)
            encourager_due = (not auto["golden_window_ran"]
                              and quiet_s >= AUTO_ENCOURAGER_MIN_QUIET_S
                              and auto["golden_encourager_span"] != auto["quiet_span_seq"])
            if encourager_due and auto["golden_unanswered"] >= AUTO_ENCOURAGER_MAX_UNANSWERED:
                # Owner decision 2026-09-09: AUTO_ENCOURAGER_MAX_UNANSWERED
                # encouragers with no patient speech between them, and now
                # a further qualifying silence — the patient has nothing
                # more to add. The window ends early, audited with the
                # reason, and the questions begin exactly as when the
                # seconds elapse (the exit below, on this or a later
                # report, once the quiet reaches the fallback).
                await _note_golden_window(auto, elapsed, seen_on="quiet", quiet_s=quiet_s,
                                          reason="unanswered_encouragers")
            if (auto["golden_window_ran"] and quiet_s >= AUTO_EOT_FALLBACK_S
                    and ctl.is_legal(auto_mode.AutoEvent.GOLDEN_TIMER_ELAPSED)):
                verdict = auto["officer_verdict"]
                await _exit_golden(
                    auto,
                    {"quiet_s": round(quiet_s, 1), "golden_s": round(elapsed, 1),
                     "by": "quiet_fallback", "fallback_s": AUTO_EOT_FALLBACK_S,
                     **({"handed_back": verdict.handed_back, "officer_ms": verdict.elapsed_ms,
                         **({"officer_failed": verdict.failed} if verdict.failed else {})}
                        if verdict is not None else {})},
                    "golden exit: window run, fallback quiet")
                return                     # OPEN from the next report on
        elif auto["awaiting_speech"] and quiet_s >= AUTO_NO_ANSWER_GRACE_S:
            # 0. A turn must start before it can end (owner decision
            #    2026-09-07, pilot 486 F5). The patient has said nothing
            #    since the question: inside the grace nothing ends; at the
            #    grace the question is re-asked once (audited); at a second
            #    grace the ordinary path below proceeds, so silence never
            #    traps the run.
            free = not session.speaking and entry["pending_utterance"] is None
            last = auto.get("last_issued")
            if not auto["reasked"] and last is not None and free:
                prepared = await auto_issue(last["utterance"], phase=ctl.phase,
                                            trigger={"quiet_s": round(quiet_s, 1), "reask": True},
                                            detail=({"topic": last.get("topic"),
                                                     "open_form": last.get("open_form")}
                                                    if last.get("kind") == "question" else None))
                if prepared is not None:
                    auto["reasked"] = True
                    # G8 (owner decision 2026-09-09): the re-ask's latency
                    # row is marked reask and measured from its own issue —
                    # never from the original's turn end (489: a 43.6 s
                    # artefact).
                    auto["last_issued"] = {**last, "utterance_id": prepared.utterance_id,
                                           "reask": True, "issued_at": time.monotonic(),
                                           "turn_end_to_issue_ms": None}
                    await audit.log(user["id"], "auto.reask_no_answer", None, None,
                                    {"session_id": session_id, "phase": ctl.phase.value,
                                     "quiet_s": round(quiet_s, 1), "text": last.get("text"),
                                     "grace_s": AUTO_NO_ANSWER_GRACE_S,
                                     "utterance_id": prepared.utterance_id,
                                     "at_audio_s": round(session.audio_seconds, 1)})
                    logger.info("Live session %s: no answer in %.0f s — re-asked once: %r",
                                session_id, AUTO_NO_ANSWER_GRACE_S, last.get("text"))
                    return                 # the re-ask's playback starts a fresh span
            elif auto["reasked"]:
                auto["awaiting_speech"] = False   # the second grace: the ordinary path proceeds
                if quiet_s >= AUTO_EOT_FALLBACK_S and not auto["turn_ended"]:
                    await _end_turn(auto, by="quiet_fallback", quiet_s=quiet_s,
                                    verdict=auto["officer_verdict"])
        elif (quiet_s >= AUTO_EOT_FALLBACK_S and not auto["turn_ended"]
              and not auto["awaiting_speech"]):
            # 0. Outside GOLDEN the same rule (owner decision 2026-09-07,
            #    pilot 485 E1): quiet of the fallback length ends the turn
            #    on the report itself, however the officer answered — once
            #    the patient has spoken since the question (F5).
            await _end_turn(auto, by="quiet_fallback", quiet_s=quiet_s,
                            verdict=auto["officer_verdict"])
        free = not session.speaking and entry["pending_utterance"] is None
        # 1. The golden encourager (owner decision 2026-09-09, reversing the
        #    1 Sept one-per-window rule): one per quiet span, whenever the
        #    patient has been quiet for AUTO_ENCOURAGER_MIN_QUIET_S — the
        #    client's span restarts at the patient's speech AND at the end
        #    of Alba's own phrase, so the quiet is counted from the later of
        #    the two — never once the window has run; go_on and
        #    tell_me_more_short alternate; spent at issue (a politeness
        #    abort drops it, and the patient's voice that caused it starts
        #    the next span).
        golden_wants = (in_golden and not auto["golden_window_ran"]
                        and quiet_s >= AUTO_ENCOURAGER_MIN_QUIET_S
                        and auto["golden_encourager_span"] != auto["quiet_span_seq"])
        if golden_wants and free:
            phrase_id = speech.GOLDEN_ENCOURAGER_IDS[auto["golden_encourager_count"]
                                                    % len(speech.GOLDEN_ENCOURAGER_IDS)]
            prepared = await auto_issue(auto_mode.PhraseUtterance(phrase_id),
                                        phase=ctl.phase,
                                        trigger={"quiet_s": round(quiet_s, 1),
                                                 "encourager": auto["golden_encourager_count"] + 1,
                                                 "unanswered": auto["golden_unanswered"] + 1})
            if prepared is not None:
                auto["golden_encourager_count"] += 1     # spent at issue, like the nudge
                auto["golden_unanswered"] += 1
                auto["golden_encourager_span"] = auto["quiet_span_seq"]
                free = False
        # 1b. "Let me think for a moment." in the question phases (owner
        #    decision 2026-09-09; replaces the bridge "go on" entirely). At
        #    most once per wait, only when the patient's turn has ended and
        #    no question is ready: the queue is empty and a pass is in
        #    flight or just requested (empty_queue), or the plan under way
        #    has already run AUTO_THINK_THRESHOLD_S past the turn end with
        #    nothing queued (slow_preparation). Not a question: nothing is
        #    consumed, awaited or reset — the judged turn end stands, and
        #    the client keeps its span across the phrase. In 489/490 the
        #    bridge was said into finished answers three times (G13).
        plan_running = any(auto[k] is not None and not auto[k].done()
                           for k in ("plan_task", "rerank_task"))
        think_reason = None
        if (in_questions and auto["turn_ended"] and auto["queued"] is None
                and auto["handover"] is None and not auto["think_used"]):
            if not auto["queue"].has_pending and auto["revision"] is not None:
                think_reason = "empty_queue"
            elif (plan_running and auto["turn_ended_at"] is not None
                  and time.monotonic() - auto["turn_ended_at"] >= AUTO_THINK_THRESHOLD_S):
                think_reason = "slow_preparation"
        if think_reason is not None and free:
            since_turn_end = time.monotonic() - auto["turn_ended_at"] if auto["turn_ended_at"] else None
            prepared = await auto_issue(auto_mode.PhraseUtterance(speech.THINKING_ID),
                                        phase=ctl.phase,
                                        trigger={"quiet_s": round(quiet_s, 1),
                                                 "thinking": think_reason})
            if prepared is not None:
                auto["think_used"] = True
                free = False
                await audit.log(user["id"], "auto.thinking", None, None,
                                {"session_id": session_id, "reason": think_reason,
                                 "phase": ctl.phase.value, "quiet_s": round(quiet_s, 1),
                                 "since_turn_end_ms": (int(round(since_turn_end * 1000))
                                                       if since_turn_end is not None else None),
                                 "pending": len(auto["queue"].pending),
                                 "revision": auto["revision"],
                                 "pass_in_flight": _pass_in_flight(),
                                 "threshold_s": AUTO_THINK_THRESHOLD_S,
                                 "utterance_id": prepared.utterance_id,
                                 "at_audio_s": round(session.audio_seconds, 1)})
                logger.info("Live session %s: \"Let me think\" (%s) at quiet %.1f s",
                            session_id, think_reason, quiet_s)
        # 2. The queued ask, once the turn has ended in this span. (A
        #    doctor-requested handover sequence is issued as soon as the
        #    room is quiet enough for the officer to have judged — the same
        #    turn-end rule.)
        if ((in_questions or in_handover_seq) and auto["queued"] is not None
                and auto["turn_ended"] and free):
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
                auto["officer_span"] = auto["span_seq"]
                if cds_task is not None and not cds_task.done():
                    # A busy model is a wait, not a failure (owner decision
                    # 2026-09-07, pilot 485 E4): the model serves one request
                    # at a time, and in 485 all seven officer timeouts fell
                    # inside a CDS pass's call windows — the officer was
                    # blind for the whole of every revision. While a pass is
                    # in flight the officer's bound stretches to cover it,
                    # capped by AUTO_OFFICER_MAX_WAIT_S; the deferral is
                    # audited with the version the pass will land as, and
                    # the verdict is applied when it arrives.
                    pass_version = entry["agenda"].current_version + 1
                    auto["officer_deferred"] = pass_version
                    await audit.log(user["id"], "auto.officer_deferred", None, None,
                                    {"session_id": session_id, "quiet_s": round(quiet_s, 1),
                                     "phase": ctl.phase.value, "pass_version": pass_version,
                                     "max_wait_s": cds.AUTO_OFFICER_MAX_WAIT_S,
                                     "at_audio_s": round(session.audio_seconds, 1)})
                    auto["officer_task"] = asyncio.create_task(
                        engine.end_of_turn(transcript, timeout_s=cds.AUTO_OFFICER_MAX_WAIT_S))
                else:
                    auto["officer_deferred"] = None
                    auto["officer_task"] = asyncio.create_task(engine.end_of_turn(transcript))
        elif auto["officer_verdict"] is not None and auto["officer_verdict"].failed is not None:
            # A failed officer earlier in this span: the silence rule keeps
            # being consulted as the quiet grows.
            await apply_officer_verdict(auto["officer_verdict"], quiet_s)

    async def apply_officer_verdict(verdict, quiet_s: float) -> auto_mode.Transition | None:
        """Turn the officer's word (or its absence) into phase behaviour.
        Returns the transition it caused, if any (the verdict audit, in
        maybe_apply_officer, records whether one did).

        GOLDEN (spec §6 as amended 2026-09-01): a hand-back exits to OPEN
        at once; otherwise OPEN only once the golden window has run AND
        the turn has ended — never at a bare timer boundary. After the
        window a turn end is the first of: finished_thought, handed_back,
        or quiet of AUTO_EOT_FALLBACK_S — the fallback applies whether or
        not the officer answered (pilot D3: a healthy "not finished"
        could hold GOLDEN indefinitely while a failed one exited at 5 s).
        Entering OPEN, the D2 revision is asked for at once (the golden
        exit is itself a turn end).

        OPEN/CLOSED (and the doctor's handover sequence): a turn end —
        finished, or handed back, or quiet of AUTO_EOT_FALLBACK_S whatever
        the officer said (owner decision 2026-09-07, pilot 485 E1) — marks
        the span through _end_turn; if it is the answer's turn ending, the
        D2 revision is requested. Anything the machine says is illegal
        from here is simply not fired."""
        auto = entry["auto"]
        ctl: auto_mode.AutoModeController = auto["controller"]
        auto["officer_verdict"] = verdict
        detail = {"quiet_s": round(quiet_s, 1), "handed_back": verdict.handed_back,
                  "officer_ms": verdict.elapsed_ms,
                  **({"officer_failed": verdict.failed} if verdict.failed else {})}
        ended = verdict.handed_back or turn_finished(verdict, quiet_s, AUTO_EOT_FALLBACK_S)
        if ended and ctl.phase in auto_mode.LISTENING_PHASES:
            # A patient turn has ended after any resume: the ratchet may
            # re-pause on passes launched from here on (pilot D4).
            auto["repause_block"] = False
        if ctl.phase is auto_mode.AutoPhase.GOLDEN:
            if verdict.handed_back and ctl.is_legal(auto_mode.AutoEvent.HAND_BACK):
                transition = ctl.hand_back()
                await auto_transition(transition, detail=detail)
                auto["turn_ended"] = True
                auto["turn_ended_at"] = time.monotonic()
                auto["think_used"] = False
                await _answer_golden_tap(auto)
                _request_revision(auto, "golden exit: hand-back")
                return transition
            elapsed = _golden_elapsed(auto)
            await _note_golden_window(auto, elapsed, seen_on="verdict", quiet_s=quiet_s)
            ended_post_window = (ended or verdict.finished_thought
                                 or quiet_s >= AUTO_EOT_FALLBACK_S)
            if (auto["golden_window_ran"] and ended_post_window
                    and ctl.is_legal(auto_mode.AutoEvent.GOLDEN_TIMER_ELAPSED)):
                return await _exit_golden(
                    auto, {**detail, "golden_s": round(elapsed, 1),
                           "by": ("verdict" if (verdict.finished_thought or verdict.handed_back)
                                  else "quiet_fallback")},
                    "golden exit: window run, turn ended")
            return None
        in_handover_seq = (ctl.phase is auto_mode.AutoPhase.HANDOVER
                           and auto["handover"] is not None)
        if ((ctl.phase in auto_mode.QUESTION_PHASES or in_handover_seq) and not auto["turn_ended"]
                and not auto["awaiting_speech"]):
            # One turn-end rule (owner decision 2026-09-07, pilot 485 E1):
            # gated by F5 — no turn end until the patient has spoken since
            # the question; the grace path in handle_quiet is the way out.
            # the officer's finished/handed-back word ends it now; quiet of
            # AUTO_EOT_FALLBACK_S ends it whatever the officer said — here
            # when the verdict itself arrives past the fallback, and on
            # every later quiet report in handle_quiet.
            if verdict.finished_thought or verdict.handed_back:
                await _end_turn(auto, by="verdict", quiet_s=quiet_s, verdict=verdict)
            elif quiet_s >= AUTO_EOT_FALLBACK_S:
                await _end_turn(auto, by="quiet_fallback", quiet_s=quiet_s, verdict=verdict)
        return None

    async def maybe_push_plan_state() -> None:
        """The visible thinking state (owner decision 2026-09-07, pilot 485,
        item 5): the phase indicator shows "preparing a question" from the
        moment a revision is requested until the question is issued (or the
        handover sequence starts). Derived from the wiring's own truth on
        every tick — a revision requested or running, a plan in flight, or
        a question queued — and pushed as auto_plan only when it changes;
        the queued text travels so the guarded tap's confirmation can show
        it. In 485 the doctor tapped his own question 0.9 s after the
        machine had queued one, with nothing on screen to say so."""
        auto = entry["auto"]
        if auto is None:
            return
        ctl: auto_mode.AutoModeController = auto["controller"]
        plan_running = any(auto[k] is not None and not auto[k].done()
                           for k in ("plan_task", "rerank_task"))
        if ctl.phase not in auto_mode.QUESTION_PHASES or auto["handover"] is not None:
            state: tuple[str, str | None] = ("idle", None)
        elif auto["queued"] is not None and auto["queued"]["kind"] == "question":
            state = ("queued", auto["queued"]["text"])
        elif auto["revision"] is not None or plan_running:
            state = ("preparing", None)
        else:
            state = ("idle", None)
        if state == auto["plan_state"]:
            return
        auto["plan_state"] = state
        await websocket.send_json({"type": "auto_plan", "state": state[0], "text": state[1],
                                   "phase": ctl.phase.value})

    async def maybe_apply_officer() -> None:
        """Called on the loop's tick, like maybe_run_cds: when the officer
        has answered, audit a failure (auto.officer_failed — fail-soft
        visibility, spec §11), apply the verdict, and audit the verdict
        itself.

        EVERY officer verdict is audited as auto.officer_verdict (owner
        decision 2026-09-01, pilot defect D2): the 1 Sept runs left no
        record of what the officer answered, because only failures and
        transitions were written — so the golden minutes that never ended
        could not be explained from the trail. The row carries the quiet
        the officer was asked about, the golden window elapsed when in
        GOLDEN (golden_spent + seconds in phase, read BEFORE the verdict
        is applied), both booleans, the failure if any, the call's
        milliseconds, the phase it was applied in, and the transition it
        produced — or null when it produced none, which is the case the
        record most needed."""
        auto = entry["auto"]
        if auto is None or auto["officer_task"] is None or not auto["officer_task"].done():
            return
        task, quiet_s = auto["officer_task"], auto["officer_quiet_s"]
        deferred, asked_in_span = auto["officer_deferred"], auto["officer_span"]
        auto["officer_task"] = None
        auto["officer_quiet_s"] = None
        auto["officer_deferred"] = None
        try:
            verdict = task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001 - end_of_turn never raises; belt and braces
            logger.warning("Live session %s: officer task failed unexpectedly: %s", session_id, exc)
            return
        if asked_in_span != auto["span_seq"]:
            # The patient spoke again while the officer was out (a deferred
            # call can be out for many seconds): its word is about a pause
            # that no longer exists. Recorded, never applied — a "finished"
            # from before their new words must not end the turn they have
            # re-opened. Err toward waiting.
            await audit.log(user["id"], "auto.officer_verdict", None, None,
                            {"session_id": session_id, "quiet_s": round(quiet_s or 0.0, 1),
                             "phase": auto["controller"].phase.value, "stale": True,
                             "finished_thought": verdict.finished_thought,
                             "handed_back": verdict.handed_back, "failed": verdict.failed,
                             "elapsed_ms": verdict.elapsed_ms, "transition": None,
                             **({"deferred": deferred} if deferred is not None else {}),
                             "at_audio_s": round(session.audio_seconds, 1)})
            return
        if verdict.failed is not None and verdict.failed.startswith("CDSRunaway"):
            await audit.log(user["id"], "cds.runaway", None, None,
                            {"session_id": session_id, "call": "officer", "reason": "cap",
                             "detail": verdict.failed, "elapsed_ms": verdict.elapsed_ms,
                             "cap": cds.AUTO_OFFICER_MAX_TOKENS,
                             "at_audio_s": round(session.audio_seconds, 1)})
        if verdict.failed is not None:
            await audit.log(user["id"], "auto.officer_failed", None, None,
                            {"session_id": session_id, "reason": verdict.failed,
                             "quiet_s": round(quiet_s or 0.0, 1),
                             "elapsed_ms": verdict.elapsed_ms,
                             "fallback_s": AUTO_EOT_FALLBACK_S})
        ctl: auto_mode.AutoModeController = auto["controller"]
        phase_before = ctl.phase
        golden_elapsed = (auto["golden_spent"] + ctl.seconds_in_phase()
                          if phase_before is auto_mode.AutoPhase.GOLDEN else None)
        transition = await apply_officer_verdict(verdict, quiet_s or 0.0)
        await audit.log(user["id"], "auto.officer_verdict", None, None,
                        {"session_id": session_id,
                         "quiet_s": round(quiet_s or 0.0, 1),
                         "phase": phase_before.value,
                         **({"golden_elapsed_s": round(golden_elapsed, 1)}
                            if golden_elapsed is not None else {}),
                         "finished_thought": verdict.finished_thought,
                         "handed_back": verdict.handed_back,
                         "failed": verdict.failed,
                         "elapsed_ms": verdict.elapsed_ms,
                         **({"deferred": deferred} if deferred is not None else {}),
                         "transition": ({"from": transition.from_phase.value,
                                         "to": transition.to_phase.value,
                                         "trigger": transition.trigger.value}
                                        if transition is not None else None),
                         "at_audio_s": round(session.audio_seconds, 1)})

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
                    elif kind == "auto_ack":
                        await handle_auto_ack(payload)  # Phase 7c slice 5: RESUME AUTO / TAKE OVER
                    elif kind == "auto_handover":
                        await handle_auto_handover(payload)   # Phase 7c slice 6: the Handover control
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
                if committed:
                    # H3 (owner decision 2026-09-10, pilot 491): the last
                    # transcribed word's end on the session clock, and when
                    # it was committed — the transcript commit latency the
                    # auto.turn_ended row measures against the span start.
                    entry["last_final"] = {"end": committed[-1].end,
                                           "committed_at_audio_s": session.audio_seconds,
                                           "at": time.monotonic()}
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
            await maybe_push_plan_state()   # the indicator's thinking state follows the tick
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
        await websocket.send_json({"type": "done", "consultation_id": cid,
                                   # How long finalisation will wait for the
                                   # "Who spoke?" answer — the prompt says so.
                                   "speaker_wait_s": entry.get("speaker_wait_s")})
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
