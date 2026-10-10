"""The models of the Nemotron choice (spec 11.1; 15.9, ruling 8): the
pinned table in models.json, how each is found or fetched at install,
and the two live streams. The English model alone writes the words, at
the revision and the setting of the third arm of Task 17 (OLD
task14_run.py, arm 2): att_context_size [70, 13], no language prompt,
fp32 weights under bf16 autocast, restored on the CPU and moved to the
card, cuFFT's plan cache capped, CUDA graphs off in the decoder. The
speaker model runs beside it and only says who spoke, in the Low latency
row of its own card (1.04 s). The two are given the same sound and share
nothing else: each has its own features, its own chunker and its own
cache. The join of words and stretches is join.py. Run only by the
speech environment's own Python; the app never imports this (spec 5.1).

No text is given to either model: no prompt, no word list (ruling 3).
The number of speakers is given at open and caps the speaker slots;
the worker never works one out (V1_LESSONS 2.1).
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE / "models.json").read_text(encoding="utf-8"))
LIBRARIES = ("nemo-toolkit", "torch", "numpy", "huggingface-hub", "omegaconf")

SAMPLE_RATE = 16000
ATT_CONTEXT_SIZE = [70, 13]     # arm 3 of Task 17: the 1.12 s chunk of the English model
# The speaker model's card, the Low latency row: 1.04 s of input buffer.
SPKCACHE_LEN, FIFO_LEN, CHUNK_LEN, RIGHT_CONTEXT, UPDATE_PERIOD = 264, 264, 9, 4, 222
# Features: 10 ms log-mel frames of 160 samples (both models). A frame
# depends only on the samples around it, so when sound arrives only the
# last RECOMPUTE_FRAMES are recomputed, from a slice that starts
# LEAD_FRAMES earlier so the slice's edge never reaches a kept frame; a
# chunk is taken only when it sits STABLE_MARGIN_FRAMES clear of the end
# (v1's nemotron_stream.py; Task 13 measured the splice at 1.9e-6).
FEATURE_STRIDE_S = 0.01
HOP = 160
RECOMPUTE_FRAMES = 8
LEAD_FRAMES = 8
STABLE_MARGIN_FRAMES = 4
# A line still open this long after its last word is closed by time
# (a draft for the owner, the 5b plan review).
LINE_WAIT_S = 3.0
WARM_S = 4.0


class RateNotSupported(Exception):
    pass


class ModelMissing(Exception):
    pass


# ------------------------------------------------------------ where they are

def _checkpoint(entry: dict, offline: bool) -> Path:
    """The model's file at its pinned revision. Offline, from the cache
    only. The hub finds its own settings and sign-in; nothing here reads them."""
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(entry["repo"], entry["file"], revision=entry["revision"], local_files_only=offline))


def _found(name: str, entry: dict) -> dict:
    report = {"model": f"{name}: {entry['repo']}", "found": False, "fetched": False, "bytes": 0,
              "pinned": entry["revision"], "ok": False, "error": None}
    try:
        path = _checkpoint(entry, offline=True)
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
                _checkpoint(entry, offline=False)
                report = {**_found(name, entry), "fetched": True}
            except Exception as exc:  # noqa: BLE001
                report.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
        reports.append(report)
    return reports


def check_present() -> None:
    for report in find_all():
        if not report["ok"]:
            raise ModelMissing(report["model"])


def stamp() -> dict:
    return {"words": {"repo": MODELS["words"]["repo"], "revision": MODELS["words"]["revision"],
                      "att_context_size": ATT_CONTEXT_SIZE},
            "speakers": {"repo": MODELS["speakers"]["repo"], "revision": MODELS["speakers"]["revision"],
                         "setting": {"spkcache_len": SPKCACHE_LEN, "fifo_len": FIFO_LEN, "chunk_len": CHUNK_LEN,
                                     "chunk_right_context": RIGHT_CONTEXT, "spkcache_update_period": UPDATE_PERIOD}}}


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


# ------------------------------------------------------------------ loading

class Models:
    """Both models, loaded once per worker process and kept loaded."""

    def __init__(self, device: str):
        import torch
        import nemo.collections.asr as nemo_asr
        from nemo.collections.asr.models import SortformerEncLabelModel

        self.device = device
        torch.set_float32_matmul_precision("highest")              # the replay script's default
        if device == "cuda":
            torch.backends.cuda.cufft_plan_cache.max_size = 8      # one plan per feed length otherwise
        self.use_bf16 = device == "cuda" and torch.cuda.is_bf16_supported()
        cpu = torch.device("cpu")
        words = nemo_asr.models.ASRModel.restore_from(restore_path=str(_checkpoint(MODELS["words"], offline=True)),
                                                      map_location=cpu)
        words.encoder.set_default_att_context_size(att_context_size=list(ATT_CONTEXT_SIZE))
        if hasattr(words, "set_inference_prompt"):
            raise RuntimeError("the English model takes no language prompt, but this one asks for one")
        words = words.to(device).eval()
        # Without this the decoder's CUDA-graph replay hit an illegal memory
        # access in the session after a long one (v1, Task 13); a worker
        # serves many sessions on one load.
        words.decoding.decoding.disable_cuda_graphs()
        if words.encoder.streaming_cfg is None:
            words.encoder.setup_streaming_params()
        self.words = words
        self.output_frame_s = float(words.cfg.preprocessor.window_stride) * int(words.encoder.subsampling_factor)

        speakers = SortformerEncLabelModel.restore_from(restore_path=str(_checkpoint(MODELS["speakers"], offline=True)),
                                                        map_location=cpu, strict=False)
        modules = speakers.sortformer_modules
        modules.spkcache_len, modules.fifo_len, modules.chunk_len = SPKCACHE_LEN, FIFO_LEN, CHUNK_LEN
        modules.chunk_right_context, modules.spkcache_update_period = RIGHT_CONTEXT, UPDATE_PERIOD
        speakers.streaming_mode = True
        speakers._check_streaming_parameters()
        speakers = speakers.to(dtype=torch.bfloat16 if self.use_bf16 else torch.float32).to(device).eval()
        self.speakers = speakers
        self.speaker_frame_s = float(speakers._cfg.preprocessor.window_stride) * int(speakers.output_subsampling_factor)
        for model in (words, speakers):
            if abs(float(model.cfg.preprocessor.window_stride) - FEATURE_STRIDE_S) > 1e-9:
                raise RuntimeError("a preprocessor's stride is not 10 ms")

    def autocast(self):
        import torch
        return torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=self.use_bf16)


# ----------------------------------------------------------------- features

class FeatureStore:
    """One model's log-mel features of the session so far, grown as sound
    arrives by recomputing only the unstable tail (the splice above)."""

    def __init__(self, preprocessor, device: str):
        import numpy as np
        import torch
        self._np, self._torch = np, torch
        self.preprocessor = preprocessor
        self.device = device
        self.tail = np.zeros(0, dtype=np.float32)
        self.tail_start = 0
        self.total_samples = 0
        self.store = None
        self.frames = 0

    @staticmethod
    def frames_for(samples: int) -> int:
        return samples // HOP + 1         # a centred STFT: floor(len / hop) + 1

    def add(self, samples) -> None:
        self.tail = self._np.concatenate([self.tail, samples])
        self.total_samples += samples.size

    def stable_frames(self) -> int:
        return max(0, self.frames_for(self.total_samples) - STABLE_MARGIN_FRAMES)

    def refresh(self) -> int:
        """Bring the store up to the sound in hand; returns its frame count."""
        np, torch = self._np, self._torch
        if self.total_samples == 0:
            return 0
        first = max(0, self.frames - RECOMPUTE_FRAMES)
        lead = max(0, first - LEAD_FRAMES)
        piece = np.ascontiguousarray(self.tail[lead * HOP - self.tail_start:])
        signal = torch.from_numpy(piece).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            features, _ = self.preprocessor(input_signal=signal, length=torch.tensor([piece.shape[0]], device=self.device))
        new = features[:, :, first - lead:]
        end = first + int(new.size(-1))
        if self.store is None or end > self.store.size(-1):
            capacity = max(end, 2 * (0 if self.store is None else self.store.size(-1)), 6000)
            grown = torch.zeros((1, new.size(1), capacity), dtype=new.dtype, device=new.device)
            if self.store is not None:
                grown[:, :, :self.frames] = self.store[:, :, :self.frames]
            self.store = grown
        self.store[:, :, first:end] = new
        self.frames = end
        keep_from = max(0, end - RECOMPUTE_FRAMES - LEAD_FRAMES - 2) * HOP
        if keep_from > self.tail_start:
            self.tail = self.tail[keep_from - self.tail_start:].copy()
            self.tail_start = keep_from
        return end

    def view(self, frames: int):
        return self.store[:, :, :frames]


# -------------------------------------------------------------- the words

class WordsStream:
    """The English model's plain cache-aware stream: tokens become words
    with times. The decoder's token timestamps are relative to each step,
    so the step's encoder frames before it are added here."""

    def __init__(self, models: Models):
        from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer
        import torch
        self.m = models
        self.torch = torch
        self.buf = CacheAwareStreamingAudioBuffer(model=models.words, online_normalization=False,
                                                  pad_and_drop_preencoded=False)
        self.features = FeatureStore(self.buf.preprocessor, models.device)
        self.cache = models.words.encoder.get_initial_cache_state(batch_size=1)
        self.hyps = None
        self.frames_before = 0
        self.tokens_seen = 0
        self.step = 0
        self.words: list[dict] = []          # complete words, not yet given
        self.open: dict | None = None        # the word still being spoken

    def add(self, samples) -> None:
        self.features.add(samples)

    def _chunk_size(self) -> int:
        size = self.buf.streaming_cfg.chunk_size
        if isinstance(size, list):
            size = size[1] if self.buf.buffer_idx != 0 else size[0]
        return int(size)

    def run(self, final: bool) -> None:
        if self.features.total_samples == 0:
            return
        stable = self.features.stable_frames()
        if not final and self.buf.buffer_idx + self._chunk_size() + STABLE_MARGIN_FRAMES > self.features.frames_for(self.features.total_samples):
            return
        total = self.features.refresh()
        self.buf.buffer = self.features.view(total)
        self.buf.streams_length = self.torch.tensor([total], device=self.m.device)
        chunks = iter(self.buf)
        while True:
            if not final and self.buf.buffer_idx + self._chunk_size() > stable:
                return
            try:
                chunk, lengths = next(chunks)
            except StopIteration:
                return
            self._step(chunk, lengths)

    def _step(self, chunk, lengths) -> None:
        torch, asr = self.torch, self.m.words
        drop = 0 if self.step == 0 else asr.encoder.streaming_cfg.drop_extra_pre_encoded
        with torch.inference_mode(), self.m.autocast():
            encoded, encoded_len, c1, c2, c3 = asr.encoder.cache_aware_stream_step(
                processed_signal=chunk, processed_signal_length=lengths, cache_last_channel=self.cache[0],
                cache_last_time=self.cache[1], cache_last_channel_len=self.cache[2],
                keep_all_outputs=self.buf.is_buffer_empty(), drop_extra_pre_encoded=drop)
            if hasattr(asr, "_apply_prompt_to_encoded"):
                encoded = asr._apply_prompt_to_encoded(encoded)
            self.hyps = asr.decoding.rnnt_decoder_predictions_tensor(
                encoder_output=encoded, encoded_lengths=encoded_len, return_hypotheses=True, partial_hypotheses=self.hyps)
        self.cache = (c1, c2, c3)
        hyp = self.hyps[0]
        ids = hyp.y_sequence.tolist() if hasattr(hyp.y_sequence, "tolist") else list(hyp.y_sequence)
        times = hyp.timestamp.tolist() if hasattr(hyp.timestamp, "tolist") else list(hyp.timestamp)
        new_ids, new_times = ids[self.tokens_seen:], times[self.tokens_seen:]
        self._take_tokens(new_ids, [t + self.frames_before for t in new_times])
        self.tokens_seen = len(ids)
        self.frames_before += int(encoded_len[0])
        self.step += 1

    def _take_tokens(self, ids: list, frames: list) -> None:
        tokenizer = self.m.words.tokenizer
        for token_id, frame in zip(ids, frames):
            piece = tokenizer.ids_to_tokens([token_id])[0]
            at = frame * self.m.output_frame_s
            if piece.startswith("▁") or self.open is None:
                if self.open is not None:
                    self._close_open()
                self.open = {"ids": [token_id], "start": at, "end": at + self.m.output_frame_s}
            else:
                self.open["ids"].append(token_id)
                self.open["end"] = at + self.m.output_frame_s

    def _close_open(self) -> None:
        text = self.m.words.tokenizer.ids_to_text(self.open["ids"]).strip()
        if text:
            self.words.append({"word": text, "start": round(self.open["start"], 3), "end": round(self.open["end"], 3)})
        self.open = None

    def open_text(self) -> str:
        return self.m.words.tokenizer.ids_to_text(self.open["ids"]).strip() if self.open else ""

    def finish(self) -> None:
        self.run(final=True)
        if self.open is not None:
            self._close_open()


# ----------------------------------------------------------- the speakers

class SpeakersStream:
    """The speaker model's own stream in the Low latency row: frame
    probabilities for up to eight speaker slots, chunk by chunk."""

    def __init__(self, models: Models):
        import torch
        self.m = models
        self.torch = torch
        model = models.speakers
        self.features = FeatureStore(model.preprocessor, models.device)
        self.state = model.sortformer_modules.init_streaming_state(
            batch_size=1, async_streaming=model.async_streaming, device=model.device)
        self.preds = torch.zeros((1, 0, model.sortformer_modules.n_spk), device=model.device)
        sub = int(model.encoder.subsampling_factor)
        self.chunk = CHUNK_LEN * sub
        self.right = RIGHT_CONTEXT * sub
        self.left = int(model.sortformer_modules.chunk_left_context) * sub
        self.done = 0

    def add(self, samples) -> None:
        self.features.add(samples)

    def run(self, final: bool) -> None:
        if self.features.total_samples == 0:
            return
        if not final and self.done + self.chunk + self.right + STABLE_MARGIN_FRAMES > self.features.frames_for(self.features.total_samples):
            return
        total = self.features.refresh()
        limit = total if final else self.features.stable_frames()
        while self.done < total:
            end = min(self.done + self.chunk, total)
            right = min(self.right, total - end)
            # Live, a chunk is taken only whole, with its whole right context, from stable frames.
            if not final and (end - self.done < self.chunk or right < self.right or end + right > limit):
                return
            self._step(self.done, end, min(self.left, self.done), right)
            self.done = end

    def _step(self, start: int, end: int, left: int, right: int) -> None:
        torch = self.torch
        chunk = self.features.view(end + right)[:, :, start - left:]
        lengths = torch.tensor([chunk.shape[2]], device=self.m.device)
        with torch.inference_mode(), self.m.autocast():
            self.state, self.preds = self.m.speakers.forward_streaming_step(
                processed_signal=chunk.transpose(1, 2), processed_signal_length=lengths, streaming_state=self.state,
                total_preds=self.preds, left_offset=left, right_offset=right)

    def probabilities(self) -> list[list[float]]:
        return self.preds[0].float().cpu().tolist()

    def scored_s(self) -> float:
        return self.preds.shape[1] * self.m.speaker_frame_s


# -------------------------------------------------------------- the session

class Session:
    """One session: the same sound to both streams, then the join."""

    def __init__(self, models: Models, rate: int, speakers: int):
        if int(rate) != SAMPLE_RATE:
            raise RateNotSupported(rate)
        import sys
        sys.path.insert(0, str(HERE))
        import join as join_module
        self._join = join_module
        self.m = models
        self.speakers = max(1, int(speakers))
        self.words = WordsStream(models)
        self.voices = SpeakersStream(models)
        self.fed_samples = 0
        self.next_id = 1
        self.step_seconds: list[float] = []

    @property
    def fed_s(self) -> float:
        return self.fed_samples / SAMPLE_RATE

    def accept(self, pcm: bytes) -> dict:
        import numpy as np
        started = time.perf_counter()
        samples = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2").astype(np.float32) / 32768.0
        self.fed_samples += samples.size
        self.words.add(samples)
        self.voices.add(samples)
        self.words.run(final=False)
        self.voices.run(final=False)
        lines = self._lines(final=False)
        self.step_seconds.append(time.perf_counter() - started)
        return {"segments": lines, "pending": self._pending(), "revisions": []}

    def finish(self) -> dict:
        started = time.perf_counter()
        self.words.finish()
        self.voices.run(final=True)
        tail = self._lines(final=True)
        return {"last_live": tail, "revisions": [], "seconds": {"tail": round(time.perf_counter() - started, 2),
                                                                "step_max": round(max(self.step_seconds), 3) if self.step_seconds else 0.0,
                                                                "steps": len(self.step_seconds)}}

    def _lines(self, final: bool) -> list[dict]:
        """Lines from the words the speaker model has scored, closed by the
        join's rules; the last one also by time, or at Stop."""
        scored = self.voices.scored_s()
        ready = self.words.words if final else [w for w in self.words.words if w["end"] <= scored]
        if not ready:
            return []
        stretches = self._join.stretches_of(self.voices.probabilities(), self.m.speaker_frame_s, self.speakers)
        lines = self._join.join(ready, stretches)
        if not final and self.fed_s - lines[-1]["end"] < LINE_WAIT_S:
            lines = lines[:-1]                 # the last line may still grow; the ones before it are closed
        taken = sum(len(line["words"]) for line in lines)
        self.words.words = self.words.words[taken:]
        made = []
        for line in lines:
            made.append({"id": self.next_id, "speaker": line["speaker"], "start": line["start"], "end": line["end"],
                         "text": line["text"], "confidence": None})
            self.next_id += 1
        return made

    def _pending(self) -> list[dict]:
        text = " ".join([w["word"] for w in self.words.words] + ([self.words.open_text()] if self.words.open else []))
        if not text.strip():
            return []
        start = self.words.words[0]["start"] if self.words.words else (self.words.open["start"] if self.words.open else self.fed_s)
        return [{"start": round(start, 3), "end": round(self.fed_s, 3), "text": text.strip()}]


def warm_up(models: Models) -> None:
    """Silence through both streams once, so the first session does not
    pay the first steps (v1 measured 0.6 and 2.2 s on them)."""
    import numpy as np
    session = Session(models, SAMPLE_RATE, 2)
    for _ in range(int(WARM_S / 0.25)):
        session.accept(np.zeros(SAMPLE_RATE // 4, dtype="<i2").tobytes())
    session.finish()
    if models.device == "cuda":
        import torch
        torch.cuda.empty_cache()
