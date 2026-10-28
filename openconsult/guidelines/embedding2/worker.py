"""The EmbeddingGemma 2 worker (spec 15.9, ruling 25; 15.12, The embedding
worker in the app; ruling 9): one long-lived process, the text part of
the model loaded once from the data folder with the network off, on the
card in bfloat16 or on the processor in float32, never float16
(precision.py); and, when asked with --reranker, the cross-encoder
reranker in the same formats on its own device. Run by the app and by
the bench with the environment's own Python; the app never imports it,
and it never imports the app: they share only the frames.

Requests and replies, one reply to each:
    embed {texts}            -> vectors {vectors, seconds}
    rerank {query, texts}    -> scores {scores, seconds}
    ping                     -> pong
Before any request one unsolicited frame: ready {model, revision, device,
dtype, reranker, reranker_revision, reranker_device, versions, load_s},
or error {fatal: true, message} before exit.
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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "speech", "common"))

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


def load_reranker(folder: str, device: str):
    """The cross-encoder from its folder, in the device's number format."""
    import torch
    from sentence_transformers import CrossEncoder
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("the card was asked for the reranker, but no card is available to this worker")
    dtype = getattr(torch, precision.dtype_name(device))
    return CrossEncoder(folder, device=device, local_files_only=True, model_kwargs={"torch_dtype": dtype})


def revision_of(folder: str) -> str:
    marker = os.path.join(folder, ".revision")
    if os.path.isfile(marker):
        with open(marker, encoding="utf-8") as fh:
            return fh.read().strip()
    return ""


def serve(inp, out, model, reranker=None) -> int:
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
            elif kind == "rerank" and reranker is None:
                write_frame(out, {"type": "error", "fatal": False, "message": "no reranker is loaded"})
            elif kind == "rerank":
                query = str(header.get("query") or "")
                texts = [str(t) for t in (header.get("texts") or [])]
                started = time.perf_counter()
                scores = reranker.predict([(query, t) for t in texts], convert_to_numpy=True) if texts else []
                write_frame(out, {"type": "scores", "scores": [float(x) for x in scores],
                                  "seconds": round(time.perf_counter() - started, 4)})
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
    reranker_folder = argv[argv.index("--reranker") + 1] if "--reranker" in argv else None
    reranker_where = argv[argv.index("--reranker-device") + 1] if "--reranker-device" in argv else where
    started = time.perf_counter()
    reranker = None
    try:
        device = DEVICES[where]
        model, dtype = load(model_folder, device)
        model.encode(["warm"], convert_to_numpy=True)       # the first call is slow
        ready = {"type": "ready", "model": "google/embeddinggemma-2", "revision": revision_of(model_folder), "device": device,
                 "dtype": dtype, "reranker": None, "reranker_revision": None, "reranker_device": None,
                 "versions": versions(), "load_s": round(time.perf_counter() - started, 2)}
        if reranker_folder:
            again = time.perf_counter()
            reranker = load_reranker(reranker_folder, DEVICES[reranker_where])
            reranker.predict([("warm", "warm")], convert_to_numpy=True)
            ready.update(reranker="BAAI/bge-reranker-v2-m3", reranker_revision=revision_of(reranker_folder),
                         reranker_device=DEVICES[reranker_where], reranker_load_s=round(time.perf_counter() - again, 2))
    except Exception as exc:  # noqa: BLE001 - reported to the app, then exit
        traceback.print_exc(file=sys.stderr)
        write_frame(out, {"type": "error", "fatal": True,
                          "message": f"could not load the model: {type(exc).__name__}: {exc}"[:500]})
        return 1
    write_frame(out, ready)
    return serve(inp, out, model, reranker)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
