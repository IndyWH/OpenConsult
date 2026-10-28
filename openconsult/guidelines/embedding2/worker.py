"""The EmbeddingGemma 2 worker of the bench (spec 15.9, ruling 25): one
long-lived process, the text part of the model loaded once from the
data folder with the network off, on the card in bfloat16 or on the
processor in float32, never float16 (precision.py). Run by the bench
with the environment's own Python; the app never imports it, and it
never imports the app: they share only the frames.

Requests and replies, one reply to each:
    embed {texts}   -> vectors {vectors, seconds}
    ping            -> pong
Before any request one unsolicited frame: ready {model, revision, device,
dtype, versions, load_s}, or error {fatal: true, message} before exit.
The text is encoded exactly as given: no prompt name and no prefix of the
worker's own, so the model reads what the bench sent (15.8 ruling 1).
Only stderr is free for logging: before any library is imported, file
descriptor 1 is pointed at stderr and the protocol keeps the real stdout.
The log never holds a text that was sent."""

from __future__ import annotations

import importlib.metadata
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "..", "speech", "common"))

import precision  # noqa: E402
from frames import read_frame, write_frame  # noqa: E402

DEVICES = {"card": "cuda", "processor": "cpu"}
LIBRARIES = ("sentence-transformers", "transformers", "torch", "huggingface-hub", "safetensors", "numpy")


def versions() -> dict:
    found = {}
    for library in LIBRARIES:
        try:
            found[library] = importlib.metadata.version(library)
        except importlib.metadata.PackageNotFoundError:
            found[library] = None
    return found


def load(model_folder: str, device: str):
    """The text part alone, in the page's own words (config_kwargs with
    the vision and audio parts None), in the format the table gives."""
    import torch
    from sentence_transformers import SentenceTransformer
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("the card was asked for, but no card is available to this worker")
    dtype = getattr(torch, precision.dtype_name(device))
    model = SentenceTransformer(model_folder, device=device, local_files_only=True,
                               config_kwargs={"vision_config": None, "audio_config": None},
                               model_kwargs={"torch_dtype": dtype})
    return model, precision.dtype_name(device)


def serve(inp, out, model) -> int:
    while True:
        frame = read_frame(inp)
        if frame is None:
            return 0
        header, _ = frame
        kind = header.get("type")
        try:
            if kind == "ping":
                write_frame(out, {"type": "pong"})
            elif kind == "embed":
                texts = [str(t) for t in (header.get("texts") or [])]
                started = time.perf_counter()
                vectors = model.encode(texts, convert_to_numpy=True) if texts else []
                seconds = round(time.perf_counter() - started, 4)
                write_frame(out, {"type": "vectors", "vectors": [[float(x) for x in v] for v in vectors],
                                  "seconds": seconds})
            else:
                write_frame(out, {"type": "error", "fatal": False, "message": f"unknown request {kind!r}"})
        except Exception as exc:  # noqa: BLE001 - reported, then the process ends (a CUDA error is final)
            traceback.print_exc(file=sys.stderr)
            write_frame(out, {"type": "error", "fatal": True, "message": f"{type(exc).__name__}: {exc}"[:500]})
            return 1


def main(argv: list[str]) -> int:
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "warning")
    model_folder = argv[argv.index("--model") + 1]
    where = argv[argv.index("--device") + 1]
    started = time.perf_counter()
    try:
        device = DEVICES[where]
        model, dtype = load(model_folder, device)
        model.encode(["warm"], convert_to_numpy=True)       # the first call is slow
        revision = ""
        marker = os.path.join(model_folder, ".revision")
        if os.path.isfile(marker):
            with open(marker, encoding="utf-8") as fh:
                revision = fh.read().strip()
        ready = {"type": "ready", "model": "google/embeddinggemma-2", "revision": revision, "device": device,
                 "dtype": dtype, "versions": versions(), "load_s": round(time.perf_counter() - started, 2)}
    except Exception as exc:  # noqa: BLE001 - reported to the bench, then exit
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True,
                          "message": f"could not load the model: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)
    return serve(inp, out, model)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
