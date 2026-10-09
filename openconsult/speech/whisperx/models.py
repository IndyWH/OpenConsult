"""The models of WhisperX with pyannote (spec 11.1; 15.9): the pinned
table in models.json, where each is cached, how each is found or fetched
at install, and the two passes: the live stream on faster-whisper, and
the pass at Stop on WhisperX with pyannote. Run only by the speech
environment's own Python; the app never imports this (spec 5.1).

No text is given to any model: no prompt, no prefix, no hotwords
(ruling 3). The number of speakers is given to pyannote exactly, never
a range (V1_LESSONS 2.1). The models are v1's as Task 19 left them.
"""

from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE / "models.json").read_text(encoding="utf-8"))
LIBRARIES = ("faster-whisper", "whisperx", "ctranslate2", "pyannote.audio", "torch",
             "torchaudio", "onnxruntime", "numpy", "transformers")

SAMPLE_RATE = 16000
# The live path's figures are v1's (app/live.py): transcribe the buffer
# again once this much new sound has arrived, and a segment is final once
# it ends this far before the newest sound. A silent buffer keeps a tail.
PROCESS_INTERVAL_S = 1.5
COMMIT_MARGIN_S = 2.0
SILENT_BUFFER_LIMIT_S = 12.0
SILENT_KEEP_TAIL_S = 4.0
FLUSH_LEAST_S = 0.3
BEAM_SIZE = 5
BATCH_SIZE = 8


class RateNotSupported(Exception):
    pass


class ModelMissing(Exception):
    pass


# ------------------------------------------------------------ where they are

def pyannote_cache() -> Path:
    """pyannote's own cache, the same default it uses itself."""
    from pyannote.audio.core.model import CACHE_DIR
    return Path(os.getenv("PYANNOTE_CACHE", CACHE_DIR)).expanduser()


def hub_dir() -> Path:
    import torch
    return Path(torch.hub.get_dir())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _folder_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file() or p.is_symlink())


def _snapshot(entry: dict, offline: bool) -> Path:
    """A hub model at its pinned revision. Offline, from the cache only.
    The hub finds its own settings and sign-in; nothing here reads them."""
    from huggingface_hub import snapshot_download
    cache = str(pyannote_cache()) if entry["kind"] == "pyannote" else None
    return Path(snapshot_download(entry["repo"], revision=entry["revision"], cache_dir=cache,
                                  local_files_only=offline))


def _file_of(entry: dict) -> Path:
    """The model's file on disk. The voice activity model may sit in the
    folder of its pinned tag or in an older cached copy; the first folder
    that holds the file is taken, and the checksum decides."""
    if entry["kind"] == "torchaudio":
        return hub_dir() / "checkpoints" / entry["file"]
    for folder in entry["folders"]:
        if (hub_dir() / folder / entry["file"]).exists():
            return hub_dir() / folder / entry["file"]
    return hub_dir() / entry["folders"][0] / entry["file"]


def vad_folder() -> Path:
    """The folder the voice activity model is loaded from, by path."""
    entry = MODELS["vad"]
    return _file_of(entry).parents[len(Path(entry["file"]).parts) - 1]


def _found(name: str, entry: dict) -> dict:
    """Is the model on this computer at its pinned revision or checksum?"""
    report = {"model": f"{name}: {entry.get('repo') or entry.get('name')}", "found": False,
              "fetched": False, "bytes": 0, "pinned": entry.get("revision") or entry.get("sha256"),
              "ok": False, "error": None}
    try:
        if entry["kind"] in ("hub", "pyannote"):
            path = _snapshot(entry, offline=True)
            report.update(found=True, bytes=_folder_bytes(path), ok=True)
        else:
            path = _file_of(entry)
            if path.exists() and _sha256(path) == entry["sha256"]:
                report.update(found=True, bytes=path.stat().st_size, ok=True)
    except Exception as exc:  # noqa: BLE001 - a plain report, never a crash
        report["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return report


def find_all() -> list[dict]:
    return [_found(name, entry) for name, entry in MODELS.items()]


def fetch_all() -> list[dict]:
    """At install: find each model, fetch what is missing, and say so. The
    worker never fetches, so nothing downloads without a click (spec 6.4)."""
    reports = []
    for name, entry in MODELS.items():
        report = _found(name, entry)
        if not report["found"]:
            try:
                _fetch(entry)
                report = {**_found(name, entry), "fetched": True}
                if not report["found"]:
                    report.update(ok=False, error=report["error"] or "fetched, but not the pinned revision or checksum")
            except Exception as exc:  # noqa: BLE001
                report.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
        reports.append(report)
    return reports


def _fetch(entry: dict) -> None:
    if entry["kind"] in ("hub", "pyannote"):
        _snapshot(entry, offline=False)
    elif entry["kind"] == "torchaudio":
        import torchaudio
        getattr(torchaudio.pipelines, entry["name"]).get_model()
    else:
        import torch
        # At the pinned tag, which does not move; the checksum then decides.
        torch.hub.load(f"{entry['repo']}:{entry['ref']}", "silero_vad", source="github",
                       force_reload=False, onnx=False, trust_repo=True, skip_validation=True)


def check_present() -> None:
    """Before the worker loads anything: every model, or a plain failure
    that names the first one missing."""
    for report in find_all():
        if not report["ok"]:
            raise ModelMissing(report["model"])


def loaded_revision(entry: dict) -> str | None:
    """The revision a pyannote inner model is loaded at. The pipeline names
    its two inner models with no revision, so the hub serves whatever the
    cache's main ref points at: that ref is read from disk and stamped,
    beside the pinned value, so the stamp says only what is known (R20)."""
    ref = pyannote_cache() / f"models--{entry['repo'].replace('/', '--')}" / "refs" / "main"
    return ref.read_text(encoding="utf-8").strip() if ref.exists() else None


def stamp() -> dict:
    """Every model with the revision or checksum it is loaded at (R20)."""
    stamped = {}
    for name, entry in MODELS.items():
        known = {k: v for k, v in entry.items() if k in ("repo", "name", "sha256", "ref")}
        if entry["kind"] in ("hub",) or name == "diarise":
            known["revision"] = entry["revision"]          # loaded at this revision by name@revision
        elif entry["kind"] == "pyannote":
            known["pinned"] = entry["revision"]
            known["revision"] = loaded_revision(entry)     # what the pipeline's main ref loads
        elif entry["kind"] == "torchhub":
            known["folder"] = vad_folder().name
        stamped[name] = known
    return stamped


def versions() -> dict:
    found = {}
    for library in LIBRARIES:
        try:
            found[library] = importlib.metadata.version(library)
        except importlib.metadata.PackageNotFoundError:
            found[library] = None
    return found


def device_name() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# ---------------------------------------------------------------- the live path

class LiveModel:
    """faster-whisper, loaded once, from the cache only."""

    def __init__(self, device: str):
        from faster_whisper import WhisperModel
        path = _snapshot(MODELS["live"], offline=True)
        compute = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(str(path), device=device, compute_type=compute)

    def transcribe(self, audio) -> list[dict]:
        """Silence gives no segments. No initial_prompt, no prefix, no
        hotwords: the model is given sound and nothing else (ruling 3)."""
        segments, _ = self.model.transcribe(audio, language="en", beam_size=BEAM_SIZE,
                                            vad_filter=True, condition_on_previous_text=False)
        return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
                for s in segments if s.text.strip()]


class LiveStream:
    """One session's live path, ported from v1's LiveSession: sound
    accumulates; the buffer is transcribed again every 1.5 s of new sound;
    a segment that ends 2 s before the newest sound is final and its sound
    is dropped; the rest is pending and may change. The whole PCM is kept
    for the pass at Stop."""

    def __init__(self, model: LiveModel, rate: int):
        if rate != SAMPLE_RATE:
            raise RateNotSupported(rate)
        import numpy as np
        self._np = np
        self._model = model
        self._buffer = np.zeros(0, dtype=np.float32)
        self._offset_s = 0.0
        self._new = 0
        self._pending: list[dict] = []
        self.pcm = bytearray()

    @property
    def seconds(self) -> float:
        return len(self.pcm) / 2 / SAMPLE_RATE

    def accept(self, pcm: bytes) -> dict:
        np = self._np
        self.pcm += pcm
        chunk = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2").astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, chunk])
        self._new += len(chunk)
        if self._new / SAMPLE_RATE < PROCESS_INTERVAL_S:
            return {"segments": [], "pending": list(self._pending)}
        self._new = 0
        return self._process()

    def _process(self) -> dict:
        duration = len(self._buffer) / SAMPLE_RATE
        if duration < 1.0:
            return {"segments": [], "pending": list(self._pending)}
        segments = self._model.transcribe(self._buffer)
        if not segments:
            self._pending = []
            if duration > SILENT_BUFFER_LIMIT_S:
                self._drop(duration - SILENT_KEEP_TAIL_S)
            return {"segments": [], "pending": []}
        horizon = duration - COMMIT_MARGIN_S
        final = [s for s in segments if s["end"] <= horizon]
        self._pending = [self._absolute(s) for s in segments if s["end"] > horizon]
        committed = [self._absolute(s) for s in final]
        if final:
            self._drop(final[-1]["end"])
        return {"segments": committed, "pending": list(self._pending)}

    def finish(self) -> list[dict]:
        """At Stop: what is left in the buffer, transcribed once more, every
        segment final, so the live transcript has its end for the check at
        Stop (spec 11.5 rule 2; D45)."""
        if len(self._buffer) / SAMPLE_RATE < FLUSH_LEAST_S:
            return []
        tail = [self._absolute(s) for s in self._model.transcribe(self._buffer)]
        self._buffer = self._np.zeros(0, dtype=self._np.float32)
        self._pending = []
        return tail

    def _absolute(self, segment: dict) -> dict:
        return {"start": round(self._offset_s + segment["start"], 2),
                "end": round(self._offset_s + segment["end"], 2), "text": segment["text"]}

    def _drop(self, seconds: float) -> None:
        self._buffer = self._buffer[int(seconds * SAMPLE_RATE):]
        self._offset_s += seconds


# -------------------------------------------------------------- the pass at Stop

# pyannote 3.4's checkpoints hold omegaconf objects, which torch 2.8
# refuses by default. v1 replaced torch.load for the whole process. v2
# allows exactly these classes, for the load only, with torch's own scoped
# allow-list (V1_LESSONS 1.11). The list is settled against the real
# checkpoint: a class missing here is named by torch's own error.
def _safe_globals() -> list:
    import collections
    import typing

    import omegaconf
    import omegaconf.base
    import omegaconf.dictconfig
    import omegaconf.listconfig
    import omegaconf.nodes
    return [omegaconf.listconfig.ListConfig, omegaconf.dictconfig.DictConfig,
            omegaconf.base.ContainerMetadata, omegaconf.base.Metadata, omegaconf.nodes.AnyNode,
            typing.Any, collections.defaultdict, dict, list, int, float, str]


def _local_silero():
    """whisperx's own Silero class, but loaded from the folder on disk that
    install-speech checked, by path: no name is looked up and no connection
    is opened. whisperx itself would ask the hub by name at every Stop, and
    the hub would ask github.com which branch is the default."""
    import torch
    from whisperx.vads.silero import Silero
    from whisperx.vads.vad import Vad

    class LocalSilero(Silero):
        def __init__(self, folder: Path, **options):
            Vad.__init__(self, options["vad_onset"])
            self.vad_onset = options["vad_onset"]
            self.chunk_size = options["chunk_size"]
            self.vad_pipeline, utils = torch.hub.load(repo_or_dir=str(folder), model="silero_vad",
                                                      source="local", onnx=False, trust_repo=True)
            (self.get_speech_timestamps, _, self.read_audio, _, _) = utils

    # whisperx's own default values for its silero VAD.
    return LocalSilero(vad_folder(), chunk_size=30, vad_onset=0.500, vad_offset=0.363)


def stop_pass(pcm: bytes, speakers: int, device: str) -> tuple[list[dict], dict]:
    """WhisperX large-v3 with word times, then pyannote with the speaker
    count given, on exactly the sound that was fed. Returns every raw
    segment as it came (V1_LESSONS 1.7) and the seconds of each step.
    The models are loaded for the pass and freed after it, as v1 did."""
    import numpy as np
    import pandas as pd
    import torch
    import whisperx
    from pyannote.audio import Pipeline

    seconds = {}
    audio = np.frombuffer(bytes(pcm[: len(pcm) - len(pcm) % 2]), dtype="<i2").astype(np.float32) / 32768.0
    compute = "float16" if device == "cuda" else "int8"
    started = time.perf_counter()
    model = whisperx.load_model(str(_snapshot(MODELS["stop"], offline=True)), device,
                                compute_type=compute, vad_model=_local_silero(), language="en")
    seconds["load_stop"] = round(time.perf_counter() - started, 2)
    step = time.perf_counter()
    result = model.transcribe(audio, batch_size=BATCH_SIZE, language="en")
    seconds["transcribe"] = round(time.perf_counter() - step, 2)
    step = time.perf_counter()
    align_model, metadata = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(result["segments"], align_model, metadata, audio, device,
                            return_char_alignments=False)
    seconds["align"] = round(time.perf_counter() - step, 2)
    step = time.perf_counter()
    entry = MODELS["diarise"]
    with torch.serialization.safe_globals(_safe_globals()):
        pipeline = Pipeline.from_pretrained(f"{entry['repo']}@{entry['revision']}")
    pipeline = pipeline.to(torch.device(device))
    annotation = pipeline({"waveform": torch.from_numpy(audio[None, :]), "sample_rate": SAMPLE_RATE},
                          num_speakers=int(speakers))
    frame = pd.DataFrame(annotation.itertracks(yield_label=True), columns=["segment", "track", "speaker"])
    frame["start"] = frame["segment"].apply(lambda s: s.start)
    frame["end"] = frame["segment"].apply(lambda s: s.end)
    result = whisperx.assign_word_speakers(frame, result)
    seconds["diarise"] = round(time.perf_counter() - step, 2)
    segments = [_plain(seg) for seg in result["segments"]]
    del model, align_model, pipeline, result
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    seconds["stop"] = round(time.perf_counter() - started, 2)
    return segments, seconds


def _plain(segment: dict) -> dict:
    """A raw segment as plain JSON: text, times, and each word with its
    time, score and speaker where the models gave them."""
    words = []
    for word in segment.get("words") or []:
        plain = {"word": word.get("word")}
        for key in ("start", "end", "score"):
            if key in word:
                plain[key] = float(word[key])
        if word.get("speaker"):
            plain["speaker"] = str(word["speaker"])
        words.append(plain)
    return {"start": float(segment["start"]), "end": float(segment["end"]),
            "text": (segment.get("text") or "").strip(), "words": words}
