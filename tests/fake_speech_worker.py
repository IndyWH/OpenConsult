"""A fake Nemotron speech worker for the test suite. Not a test module.

It runs the REAL request loop and framing of speech_nemotron/worker.py
(`serve`, `write_frame`), with a scripted stream in place of NeMo, so the
tests need no GPU and no Nemotron environment. Run as:

    python tests/fake_speech_worker.py SCRIPT.json

SCRIPT.json (all keys optional):
  "ready_delay_s":  sleep before saying ready
  "load_error":     say {"type": "error", "fatal": true} instead of ready, exit 1
  "replies":        list of dicts; each `audio` request pops the next one
                    (segments / revisions / watermark / partial), else empty
  "flush":          the flush reply's segments (and revisions)
  "flush_hang":     never answer the flush (the timeout test)
  "die_on_audio":   exit abruptly at this audio request (1-based)
  "audio_log":      path; every audio payload is appended to it, raw
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "speech_nemotron"))
import worker  # noqa: E402  (speech_nemotron/worker.py: imports stdlib only)

script = json.loads(Path(sys.argv[1]).read_text())
out = os.fdopen(os.dup(1), "wb")
os.dup2(2, 1)


class FakeStream:
    calls = 0

    def accept(self, pcm16: bytes) -> dict:
        FakeStream.calls += 1
        if script.get("audio_log"):
            with open(script["audio_log"], "ab") as fh:
                fh.write(pcm16)
        if script.get("die_on_audio") == FakeStream.calls:
            os._exit(3)
        replies = script.get("replies") or []
        reply = replies.pop(0) if replies else {}
        return {"segments": reply.get("segments", []), "revisions": reply.get("revisions", []),
                "watermark": reply.get("watermark", 0.0), "partial": reply.get("partial", ""),
                "processed_s": 0.0}

    def flush(self) -> dict:
        if script.get("flush_hang"):
            time.sleep(3600)
        flush = script.get("flush") or {}
        return {"segments": flush.get("segments", []), "revisions": flush.get("revisions", []),
                "watermark": None, "partial": "", "processed_s": 0.0}

    def stats(self) -> dict:
        return {"steps": FakeStream.calls, "fake": True}


time.sleep(float(script.get("ready_delay_s", 0)))
if script.get("load_error"):
    worker.write_frame(out, {"type": "error", "fatal": True, "message": script["load_error"]})
    sys.exit(1)
worker.write_frame(out, {"type": "ready", "load_s": 0.0, "max_speakers": 2, "fake": True})
sys.exit(worker.serve(sys.stdin.buffer, out, FakeStream))
