"""Concurrent capacity: finalisation serialised through the single-worker
queue; one live WebSocket session at a time (server-enforced).

Background (2026-07-24 investigation): two overlapping finalisations race
the GPU — both load WhisperX+pyannote while MedGemma reloads for
whichever notes first (24 GB total), and transcribe_and_diarise briefly
monkeypatches the process-global torch.load. Reachable today with one
doctor: the queue guard releases at Stop but finalisation keeps running.
"""

import asyncio
import os
import secrets

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import auth, consultations
from app import main as appmain

load_dotenv()


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def test_finalisation_worker_runs_jobs_strictly_one_at_a_time(monkeypatch):
    events = []
    running = {"now": 0, "peak": 0}

    async def fake_finalize(cid, wav_path):
        running["now"] += 1
        running["peak"] = max(running["peak"], running["now"])
        events.append(("start", cid))
        await asyncio.sleep(0.02)
        running["now"] -= 1
        events.append(("end", cid))

    monkeypatch.setattr(appmain, "finalize_consultation", fake_finalize)

    async def run():
        appmain.app.state.finalize_queue = asyncio.Queue()
        worker = asyncio.create_task(appmain.finalize_worker(appmain.app))
        for cid in range(3):
            appmain.app.state.finalize_queue.put_nowait((cid, f"{cid}.wav"))
        await appmain.app.state.finalize_queue.join()
        worker.cancel()

    asyncio.run(run())
    assert running["peak"] == 1, "two pipelines must never touch the GPU at once"
    assert events == [("start", 0), ("end", 0), ("start", 1), ("end", 1),
                      ("start", 2), ("end", 2)]  # FIFO, no interleaving


def test_worker_survives_a_failing_job(monkeypatch):
    done = []

    async def flaky_finalize(cid, wav_path):
        if cid == 0:
            raise RuntimeError("boom")
        done.append(cid)

    monkeypatch.setattr(appmain, "finalize_consultation", flaky_finalize)

    async def run():
        appmain.app.state.finalize_queue = asyncio.Queue()
        worker = asyncio.create_task(appmain.finalize_worker(appmain.app))
        appmain.app.state.finalize_queue.put_nowait((0, "0.wav"))
        appmain.app.state.finalize_queue.put_nowait((1, "1.wav"))
        await appmain.app.state.finalize_queue.join()
        worker.cancel()

    asyncio.run(run())
    assert done == [1]


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role
    ))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@needs_db
def test_second_concurrent_live_session_is_refused():
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    appmain.app.state.live_active = {"user": "someone_else"}
    try:
        with client.websocket_connect("/ws/transcribe") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "busy"
            assert "one live consultation at a time" in msg["detail"].lower()
    finally:
        appmain.app.state.live_active = None


@needs_db
def test_queued_status_visible_and_recoverable():
    doctor = _make_user("doctor")

    async def build() -> int:
        cid = await consultations.create_consultation(None, doctor["id"])
        await consultations.set_status(cid, "queued", audio_path="/tmp/x.wav")
        return cid

    cid = asyncio.run(build())
    rows = _client_for(doctor).get("/api/consultations").json()
    assert next(r for r in rows if r["id"] == cid)["status"] == "queued"
    # Startup recovery would re-enqueue it rather than strand the audio.
    assert (cid, "/tmp/x.wav") in asyncio.run(consultations.queued_finalisations())
