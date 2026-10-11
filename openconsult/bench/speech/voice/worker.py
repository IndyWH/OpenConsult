"""The voice worker of the bench (spec 15.9, ruling 4; D53; the details of
part two of 5c): the doctor's voice is learnt from about a minute of the
doctor speaking alone, and each line of a page is then given its distance
from that voice, from the sound between the line's own times. Run by the
bench with the WhisperX environment's Python, one long-lived process. It
uses the voice model that environment already holds (pyannote's
wespeaker-voxceleb-resnet34-LM, pinned in the WhisperX choice's models.json),
loaded from disk by path with the hub's network off; nothing is downloaded.
It imports nothing from the app: the WhisperX models module, the frames
and the conversion are loaded by path.

Requests and replies, one reply to each:
    learn {rate, quiet_dbfs, window_s} + PCM        -> learnt {seconds, seconds_used, seconds_trimmed}
    score {rate, lines: [{n, start, end}]} + PCM     -> scored {lines: [{n, distance, seconds}], seconds}
    ping                                            -> pong
Before any request one unsolicited frame: ready {models, versions, device,
load_s, least_s}, or error {fatal: true, message} before exit.

PCM is mono 16-bit little-endian at 16,000 or 48,000 samples a second,
converted to 16,000 inside; any other rate is refused plainly. The log
never holds a word that was said: no text reaches this worker at all.
"""

from __future__ import annotations

import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEECH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "speech")
sys.path.insert(0, os.path.join(SPEECH, "whisperx"))
sys.path.insert(0, os.path.join(SPEECH, "common"))

import models  # noqa: E402 - the app's whisperx models module, by path; light at import
from frames import read_frame, write_frame  # noqa: E402

SAMPLE_RATE = 16000
# A stretch shorter than this cannot go through the model's frames: its
# distance is none, and the bench reads it as unsure.
LEAST_S = 0.2
INSTALL = "openconsult install-speech"


class RateRefused(Exception):
    pass


class Voice:
    """The embedding model, loaded once, and the doctor's voice once learnt."""

    def __init__(self, device: str):
        import numpy as np
        import torch
        from pyannote.audio import Inference, Model
        from scipy.spatial.distance import cdist
        self._np, self._torch, self._cdist = np, torch, cdist
        folder = models._snapshot(models.MODELS["embed"], offline=True)
        with torch.serialization.safe_globals(models._safe_globals()):
            model = Model.from_pretrained(str(folder / "pytorch_model.bin"))
        model = model.to(torch.device(device)).eval()
        self.inference = Inference(model, window="whole", device=torch.device(device))
        self.doctor = None

    def embed(self, samples):
        """One embedding for one whole stretch of sound at 16,000."""
        waveform = self._torch.from_numpy(self._np.ascontiguousarray(samples, dtype=self._np.float32))[None, :]
        found = self.inference({"waveform": waveform, "sample_rate": SAMPLE_RATE})
        return self._np.atleast_2d(self._np.asarray(found, dtype=self._np.float64))

    def learn(self, samples) -> None:
        self.doctor = self.embed(samples)

    def distance(self, samples) -> float:
        """The cosine distance from the doctor's voice, as pyannote's own
        clustering measures the distance between embeddings."""
        return float(self._cdist(self.embed(samples), self.doctor, metric="cosine")[0, 0])


def to_16k(pcm: bytes, rate: int):
    """The sound as float samples at 16,000, converted inside the worker as
    the local workers convert."""
    import numpy as np
    import resample
    try:
        converter = resample.Resampler(int(rate), SAMPLE_RATE)
    except resample.RateNotSupported:
        raise RateRefused(rate) from None
    return converter.convert(pcm).astype(np.float32) / 32768.0


def trim_quiet(samples, quiet_dbfs: float, window_s: float) -> tuple:
    """The sound less its quiet ends: windows of window_s at or below
    quiet_dbfs (the rule's own measure) are dropped from the start up to
    the first louder window and from the end back to the last."""
    import numpy as np
    window = max(1, int(round(SAMPLE_RATE * window_s)))
    count = len(samples) // window
    if count == 0:
        return samples, 0.0
    levels = np.sqrt(np.mean(samples[: count * window].reshape(count, window) ** 2, axis=1))
    loud = np.nonzero(levels > 10 ** (quiet_dbfs / 20))[0]
    if not len(loud):
        return samples, 0.0
    kept = samples[loud[0] * window:(loud[-1] + 1) * window]
    return kept, (len(samples) - len(kept)) / SAMPLE_RATE


def serve(inp, out, voice: Voice) -> int:
    while True:
        frame = read_frame(inp)
        if frame is None:
            return 0
        header, payload = frame
        kind = header.get("type")
        try:
            if kind == "ping":
                write_frame(out, {"type": "pong"})
            elif kind == "learn":
                write_frame(out, learn(voice, header, payload))
            elif kind == "score" and voice.doctor is None:
                write_frame(out, {"type": "error", "fatal": False, "message": "no voice has been learnt"})
            elif kind == "score":
                write_frame(out, score(voice, header, payload))
            else:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown request {kind!r}"})
        except RateRefused as refused:
            write_frame(out, {"type": "error", "fatal": False, "reason": "rate_not_supported",
                              "message": f"this worker takes sound at 16,000 or 48,000 samples a second, not {refused}"})
        except Exception as exc:  # noqa: BLE001 - reported, then the process ends
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "fatal": True, "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


def learn(voice: Voice, header: dict, payload: bytes) -> dict:
    started = time.perf_counter()
    samples = to_16k(payload, int(header.get("rate") or 0))
    kept, trimmed = trim_quiet(samples, float(header["quiet_dbfs"]), float(header["window_s"]))
    voice.learn(kept)
    return {"type": "learnt", "seconds": round(time.perf_counter() - started, 2),
            "seconds_used": round(len(kept) / SAMPLE_RATE, 3), "seconds_trimmed": round(trimmed, 3)}


def score(voice: Voice, header: dict, payload: bytes) -> dict:
    started = time.perf_counter()
    samples = to_16k(payload, int(header.get("rate") or 0))
    scored = []
    for line in header.get("lines") or []:
        first = max(0, int(round(float(line["start"]) * SAMPLE_RATE)))
        last = min(len(samples), int(round(float(line["end"]) * SAMPLE_RATE)))
        piece = samples[first:last]
        step = time.perf_counter()
        distance = voice.distance(piece) if len(piece) >= LEAST_S * SAMPLE_RATE else None
        if distance is not None and not math.isfinite(distance):
            distance = None
        scored.append({"n": line["n"], "distance": None if distance is None else round(distance, 4),
                       "seconds": round(time.perf_counter() - step, 3)})
    return {"type": "scored", "lines": scored, "seconds": round(time.perf_counter() - started, 2)}


def main() -> int:
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    sys.path.insert(0, HERE)
    import worker_quiet  # noqa: F401 - the same quiet logging as the WhisperX worker, loaded by path
    started = time.perf_counter()
    try:
        import torch  # noqa: F401 - first, as the WhisperX worker imports it

        models.check_present()
        device = models.device_name()
        voice = Voice(device)
        stamp = {"embed": models.stamp()["embed"]}
        ready = {"type": "ready", "models": stamp, "versions": models.versions(), "device": device,
                 "load_s": round(time.perf_counter() - started, 2), "least_s": LEAST_S}
    except models.ModelMissing as missing:
        write_frame(out, {"type": "error", "fatal": True, "reason": "model_missing",
                          "message": f"the model {missing} is not on this computer; run {INSTALL}"})
        return 1
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True, "message": f"could not load the model: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)
    return serve(inp, out, voice)


if __name__ == "__main__":
    sys.exit(main())
