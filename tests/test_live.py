"""End-to-end test of the live transcription pipeline.

Streams a known recording through the WebSocket in browser-sized chunks and
checks that the words come back. Loads the Whisper model, so this is the
slow part of the suite (a few seconds on GPU).
"""

import json
import secrets
import struct
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth
from app.main import app

JFK_WAV = Path(__file__).parent / "data" / "jfk.wav"
CHUNK_BYTES = 4000 * 2  # 0.25 s of 16-bit samples at 16 kHz — what the browser sends


def test_websocket_streaming_transcription():
    with wave.open(str(JFK_WAV)) as w:
        assert w.getframerate() == 16000
        pcm = w.readframes(w.getnframes())

    finals: list[str] = []
    with TestClient(app) as client:  # `with` runs lifespan → loads the model
        # The WebSocket requires a clinical-role session (Phase 6 RBAC).
        auth.ensure_schema()
        response = client.post(
            "/api/register",
            json={"username": f"doc_{secrets.token_hex(4)}",
                  "password": "test-password-123",
                  "display_name": "Doc", "role": "doctor"},
        )
        assert response.status_code == 200
        with client.websocket_connect("/ws/transcribe") as ws:
            # Protocol since 2026-07-24: JSON config first, then binary
            # frames carrying a 4-byte big-endian sequence number.
            ws.send_text(json.dumps({"session_id": f"t_{secrets.token_hex(4)}"}))
            seq = 0
            for i in range(0, len(pcm), CHUNK_BYTES):
                seq += 1
                ws.send_bytes(struct.pack(">I", seq) + pcm[i : i + CHUNK_BYTES])
            ws.send_text("stop")
            while True:
                msg = ws.receive_json()
                if msg["type"] == "final":
                    finals.append(msg["text"])
                elif msg["type"] == "done":
                    break

    transcript = " ".join(finals).lower()
    assert "ask not what your country can do for you" in transcript
    assert "what you can do for your country" in transcript
