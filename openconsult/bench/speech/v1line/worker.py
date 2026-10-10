"""WhisperX with v1's line, an arm of the bench only (spec 15.9, rulings 3
and 15). The WhisperX choice's own worker and models, loaded by path, with
one change: the live model is given v1's line of drug names as
initial_prompt, exactly as v1's LiveTranscriber gives it. The pass at
Stop is the app's own and is given no text (V1_LESSONS 1.4). The line is
the file beside this one, v1's byte for byte with one line break after
it; the worker refuses to start if its checksum differs, and the hash
goes into the stamp, so every result of the arm carries it (R20). Run by
the bench with the WhisperX environment's Python; the app cannot reach it."""

from __future__ import annotations

import hashlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEECH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "speech")
sys.path.insert(0, os.path.join(SPEECH, "whisperx"))
sys.path.insert(0, os.path.join(SPEECH, "common"))

import models  # noqa: E402 - the app's whisperx models module, by path
import worker as whisperx_worker  # noqa: E402 - the app's whisperx worker module, by path
from frames import write_frame  # noqa: E402

LINE_FILE = os.path.join(HERE, "v1_live_line.txt")
LINE_SHA256 = "c72f4adcebbc7907cb6ad55b21c7bc1484f3aa5d2d428d70cf537cf0b2bb9981"


def read_line() -> str:
    """v1's line, from the file with the expected checksum, without the
    one line break the file ends with."""
    data = open(LINE_FILE, "rb").read()
    if hashlib.sha256(data).hexdigest() != LINE_SHA256:
        raise ValueError(f"the line file {LINE_FILE} does not have the expected checksum, so the arm did not start")
    return data.decode("utf-8")[:-1] if data.endswith(b"\n") else data.decode("utf-8")


class LineLiveModel(models.LiveModel):
    """The live model, given v1's line before it listens (v1's
    transcription.py: initial_prompt=self.initial_prompt)."""

    def __init__(self, device: str, line: str):
        super().__init__(device)
        self.line = line

    def transcribe(self, audio) -> list[dict]:
        segments, _ = self.model.transcribe(audio, language="en", beam_size=models.BEAM_SIZE, initial_prompt=self.line,
                                            vad_filter=True, condition_on_previous_text=False)
        return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()} for s in segments if s.text.strip()]


def main() -> int:
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    whisperx_worker.quiet_logs()
    started = time.perf_counter()
    try:
        line = read_line()
        import torch  # noqa: F401 - first, so ctranslate2 finds the CUDA libraries torch loads

        models.check_present()
        device = models.device_name()
        live = LineLiveModel(device, line)
        import numpy as np
        live.transcribe(np.zeros(whisperx_worker.SAMPLE_RATE_WARM, dtype=np.float32))
        stamp = {**models.stamp(), "live_line": {"sha256": LINE_SHA256, "given_to": "the live model only"}}
        ready = {"type": "ready", "models": stamp, "versions": models.versions(), "device": device,
                 "load_s": round(time.perf_counter() - started, 2)}
    except models.ModelMissing as missing:
        write_frame(out, {"type": "error", "fatal": True, "reason": "model_missing",
                          "message": f"the model {missing} is not on this computer; run {whisperx_worker.INSTALL}"})
        return 1
    except Exception as exc:  # noqa: BLE001 - reported, then exit
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True, "message": f"could not start: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)

    def open_stream(rate: int):
        try:
            return models.LiveStream(live, rate)
        except models.RateNotSupported:
            raise whisperx_worker.RateRefused(rate) from None

    # The pass at Stop is the app's own: no text reaches it.
    return whisperx_worker.serve(inp, out, open_stream, lambda pcm, speakers: models.stop_pass(pcm, speakers, device))


if __name__ == "__main__":
    sys.exit(main())
