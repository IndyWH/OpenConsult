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

from app.live import PROCESS_INTERVAL_S, LiveSession
from app.transcription import LiveTranscriber

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")
STATIC_DIR = Path(__file__).parent / "static"


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the Whisper model once, before serving traffic (takes a second or
    # two from the local cache; the first ever run downloads the model).
    app.state.transcriber = await asyncio.to_thread(LiveTranscriber)
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


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket) -> None:
    """Receive 16 kHz 16-bit mono PCM frames; stream transcript JSON back.

    Client → server: binary audio frames, or the text message "stop".
    Server → client: {"type": "final"|"partial"|"done", ...}
    """
    await websocket.accept()
    session = LiveSession(websocket.app.state.transcriber)
    logger.info("Live session started")
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
                    await websocket.send_json(
                        {"type": "final", "text": seg.text, "start": seg.start, "end": seg.end}
                    )
                await websocket.send_json({"type": "partial", "text": partial})

        # Client pressed stop: transcribe the tail end and finish cleanly.
        for seg in await session.flush():
            await websocket.send_json(
                {"type": "final", "text": seg.text, "start": seg.start, "end": seg.end}
            )
        await websocket.send_json({"type": "done"})
        await websocket.close()
    except WebSocketDisconnect:
        pass
    finally:
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
