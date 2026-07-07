"""Consultation AI — application entry point.

Phase 0: a minimal FastAPI app proving the environment works.
Later phases add the audio gateway, live transcription, and the
patient/consultation views described in PROJECT_PLAN.md.
"""

import asyncio
import contextlib
import logging
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from app import consultations
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
    consultations.ensure_schema()
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


@app.get("/live")
def live_page() -> FileResponse:
    """The live transcription page: mic capture + streaming transcript."""
    return FileResponse(STATIC_DIR / "live.html")


@app.get("/review/{cid}")
def review_page(cid: int) -> FileResponse:
    """Note review screen: editable draft note + diarised transcript."""
    return FileResponse(STATIC_DIR / "review.html")


@app.get("/api/consultations/{cid}")
async def consultation_state(cid: int) -> JSONResponse:
    consultation = await consultations.get_consultation(cid)
    if consultation is None:
        return JSONResponse(status_code=404, content={"error": "not found"})
    turns = await consultations.get_turns(cid)
    note = await consultations.latest_note(cid)
    plain = note_as_plain_text(note["content"]) if note else None
    return JSONResponse(
        content={**consultation, "turns": turns, "note": note, "plain_text": plain}
    )


class ApproveBody(BaseModel):
    text: str


@app.post("/api/consultations/{cid}/approve")
async def approve(cid: int, body: ApproveBody) -> JSONResponse:
    consultation = await consultations.get_consultation(cid)
    if consultation and consultation["urgent_actions"] and not consultation["urgent_ack_at"]:
        return JSONResponse(
            status_code=409,
            content={"error": "Unresolved urgent actions must be acknowledged first."},
        )
    await consultations.approve_note(cid, body.text)
    return JSONResponse(content={"ok": True})


@app.post("/api/consultations/{cid}/acknowledge-urgent")
async def acknowledge_urgent(cid: int) -> dict:
    return {"ok": True, "acknowledged_at": await consultations.acknowledge_urgent(cid)}


@app.post("/api/consultations/{cid}/regenerate")
async def regenerate(cid: int) -> dict:
    """Re-draft the note from the (possibly corrected) transcript."""
    await consultations.set_status(cid, "processing")
    await regenerate_note(cid)
    await consultations.set_status(cid, "awaiting_review")
    return {"ok": True}


@app.post("/api/consultations/{cid}/swap-roles")
async def swap_roles(cid: int) -> dict:
    """Override for the first-speaker-is-Doctor heuristic."""
    await consultations.swap_roles(cid)
    return {"ok": True}


class TurnBody(BaseModel):
    text: str


@app.patch("/api/consultations/{cid}/turns/{idx}")
async def edit_turn(cid: int, idx: int, body: TurnBody) -> dict:
    await consultations.update_turn_text(cid, idx, body.text)
    return {"ok": True}


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket) -> None:
    """Receive 16 kHz 16-bit mono PCM frames; stream transcript JSON back.

    Client → server: binary audio frames, or the text message "stop".
    Server → client: {"type": "final"|"partial"|"done", ...}
    """
    await websocket.accept()
    session = LiveSession(websocket.app.state.transcriber)
    engine: CDSEngine = websocket.app.state.cds_engine
    logger.info("Live session started")

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
        cid = await consultations.create_consultation()
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
