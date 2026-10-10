"""A made-up cloud speech service for the suite: a websocket server on
loopback that speaks either service's protocol from a script and keeps
what it was sent. Nothing here hears any sound, and nothing a model said
is in it. The suite never reaches the internet."""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import threading
from http import HTTPStatus

from websockets.sync.server import serve

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

SPEECHMATICS = "speechmatics"
ASSEMBLYAI = "assemblyai"


class MadeUpService:
    """mode: ok (answers), refuse_handshake STATUS (the HTTP status before
    the websocket), close CODE REASON (opens, then closes with that code
    on the first audio), quiet (opens, answers the first message, then
    goes silent and never closes: the line is dead), error (answers the
    opening message with the service's own error).

    script: a dict of piece number -> list of messages (dicts) to send
    after that piece of audio; "stop" -> messages to send after the end
    message, before the service's own end."""

    def __init__(self, kind: str, mode: str = "ok", script: dict | None = None,
                 first: dict | None = None):
        self.kind, self.mode = kind, mode.split()
        self.script = script or {}
        self.first = first
        self.handshakes: list[dict] = []      # headers and path of each connection
        self.openings: list = []              # the opening JSON (speechmatics) or query (assemblyai)
        self.audio: list[bytes] = []
        self.ended: list = []
        self.connections = 0
        self._held: list = []
        if self.mode[0] == "quiet":
            self._server = None
            self._quiet = socket.create_server(("127.0.0.1", 0))
            self.port = self._quiet.getsockname()[1]
            self._thread = threading.Thread(target=self._serve_quiet, daemon=True)
        else:
            self._server = serve(self._handle, "127.0.0.1", 0, process_request=self._request)
            self.port = self._server.socket.getsockname()[1]
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.address = f"ws://127.0.0.1:{self.port}"
        self._thread.start()

    # ------------------------------------------------------ a dead line

    def _serve_quiet(self):
        """A line that dies without closing: the handshake and the first
        message by hand on a plain socket, then silence for ever, with the
        socket held open so no close ever reaches the client. The websocket
        library's own server cannot play this, because it closes the
        connection when its handler returns."""
        while True:
            try:
                conn, _ = self._quiet.accept()
            except OSError:
                return
            self.connections += 1
            self._held.append(conn)
            request = b""
            while b"\r\n\r\n" not in request:
                request += conn.recv(4096)
            head = request.decode("latin-1")
            key = next(line.split(":", 1)[1].strip() for line in head.split("\r\n") if line.lower().startswith("sec-websocket-key"))
            accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
            conn.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                         f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode())
            path = head.split(" ", 2)[1]
            self.handshakes.append({"path": path, "headers": {}})
            if self.kind == SPEECHMATICS:
                conn.recv(65536)                                   # the opening message, not read further
                first = {"message": "RecognitionStarted", "id": "made-up-id"}
            else:
                first = {"type": "Begin", "id": "made-up-id", "expires_at": 0, "configuration": {}}
            payload = json.dumps(first).encode()
            conn.sendall(bytes([0x81, 126]) + len(payload).to_bytes(2, "big") + payload if len(payload) > 125
                         else bytes([0x81, len(payload)]) + payload)
            # then nothing, ever: the socket stays open in self._held


    # ---------------------------------------------------------- handshake

    def _request(self, connection, request):
        self.handshakes.append({"path": request.path, "headers": {k.lower(): v for k, v in request.headers.items()}})
        if self.mode[0] == "refuse_handshake":
            return connection.respond(HTTPStatus(int(self.mode[1])), "made-up: refused\n")
        return None

    # ----------------------------------------------------------- sessions

    def _handle(self, ws):
        self.connections += 1
        if self.kind == SPEECHMATICS:
            self._speechmatics(ws)
        else:
            self._assemblyai(ws)

    def _send_all(self, ws, messages):
        for message in messages:
            ws.send(json.dumps(message))

    def _speechmatics(self, ws):
        opening = json.loads(ws.recv())
        self.openings.append(opening)
        if self.mode[0] == "error":
            self._send_all(ws, [self.first or {"message": "Error", "type": "not_authorised", "reason": "made-up: not allowed"}])
            ws.close(4001, "not_authorised")
            return
        self._send_all(ws, [self.first or {"message": "RecognitionStarted", "id": "made-up-id",
                                           "language_pack_info": {"language_description": "made-up"}}])
        pieces = 0
        for message in ws:
            if isinstance(message, bytes):
                pieces += 1
                self.audio.append(message)
                if self.mode[0] == "close":
                    ws.close(int(self.mode[1]), " ".join(self.mode[2:]))
                    return
                ws.send(json.dumps({"message": "AudioAdded", "seq_no": pieces}))
                self._send_all(ws, self.script.get(pieces, []))
                continue
            body = json.loads(message)
            if body.get("message") == "EndOfStream":
                self.ended.append(body)
                self._send_all(ws, self.script.get("stop", []))
                ws.send(json.dumps({"message": "EndOfTranscript"}))
                return

    def _assemblyai(self, ws):
        query = ws.request.path.partition("?")[2]
        self.openings.append(query)
        asked = dict(part.split("=", 1) for part in query.split("&") if part)
        echo = {"model": asked.get("speech_model"), "domain": asked.get("domain"),
                "speaker_labels": asked.get("speaker_labels") == "true",
                "max_speakers": int(asked["max_speakers"]) if "max_speakers" in asked else None,
                "sample_rate": int(asked.get("sample_rate", 16000)), "encoding": asked.get("encoding")}
        if self.mode[0] == "error":
            ws.send(json.dumps({"error": "made-up: unauthorized", "error_code": 1008}))
            ws.close(1008, "Unauthorized Connection: Missing Authorization header")
            return
        begin = self.first or {"type": "Begin", "id": "made-up-id", "expires_at": 0, "configuration": echo}
        ws.send(json.dumps(begin))
        pieces = 0
        for message in ws:
            if isinstance(message, bytes):
                pieces += 1
                self.audio.append(message)
                if self.mode[0] == "close":
                    ws.close(int(self.mode[1]), " ".join(self.mode[2:]))
                    return
                self._send_all(ws, self.script.get(pieces, []))
                continue
            body = json.loads(message)
            if body.get("type") == "Terminate":
                self.ended.append(body)
                self._send_all(ws, self.script.get("stop", []))
                ws.send(json.dumps({"type": "Termination", "audio_duration_seconds": len(b"".join(self.audio)) / 32000,
                                    "session_duration_seconds": 1.0}))
                return

    # ---------------------------------------------------------------- end

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
        else:
            self._quiet.close()
        self._thread.join(timeout=5)
        for conn in self._held:
            conn.close()
