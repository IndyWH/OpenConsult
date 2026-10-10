"""The tied Nemotron pair, an arm of the bench only (spec 15.9, rulings 8
and 15): v1's pairing as v1's own worker runs it, the 3.5 model tied to
the speaker model through NeMo's SpeakerTaggedASR with Option 2 of the
speaker model's integration guide, so that the bench can set it beside
the Nemotron choice. Run only by the Nemotron environment's Python of
5b; the app never imports this and cannot reach it.

Carried from v1's nemotron_stream.py: the Option 2 settings word for
word; both checkpoints restored on the CPU then moved to the card, the
speaker model in bf16 and the 3.5 model's weights fp32 under bf16
autocast; cuFFT's plan cache capped; CUDA graphs off in the decoder;
v1's feature splice driving NeMo's own streaming buffer; v1's commit
rule. Written fresh: the defaults of NeMo's MultitalkerTranscriptionConfig
(the example script at commit 1688cc3d, which the environment does not
install), the two small loaders of that script, and the lines in the
door's form. v1 sent a later text of a committed line as a revision; the
door of 5b takes a revision as a label only, so late changes are kept in
the notes at Stop and the line stands as it was given.

The 3.5 model is given a language tag, en-GB, as v1 gives it: a key of
the model's own prompt dictionary, a setting and not a text, stamped."""

from __future__ import annotations

import importlib.metadata
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE / "models.json").read_text(encoding="utf-8"))
LIBRARIES = ("nemo-toolkit", "torch", "numpy", "huggingface-hub", "omegaconf", "scipy")

SAMPLE_RATE = 16000
FEATURE_STRIDE_S = 0.01
HOP = 160
STABLE_MARGIN_FRAMES = 4
RECOMPUTE_FRAMES = 8
LEAD_FRAMES = 8
COMMIT_MARGIN_S = 3.0            # v1: sent_break_sec (1.0) + one 1.12 s chunk + slack
TARGET_LANG = "en-GB"
MAX_SPEAKERS_AT_LOAD = 2         # v1's default (SPEECH_MAX_SPEAKERS unset in Task 17); the session's count caps the slots
WARM_S = 4.0

# v1's OPTION_2, word for word.
OPTION_2 = {
    "masked_asr": True, "att_context_size": [56, 13], "parallel_speaker_strategy": True,
    "single_speaker_mode": False, "cache_gating": True, "binary_diar_preds": True, "fifo_len": 264,
    "spkcache_update_period": 222, "target_lang": TARGET_LANG, "strip_lang_tags": True,
    "generate_realtime_scripts": False, "deploy_mode": True, "log": False, "print_time": False, "verbose": False,
}

# The defaults of MultitalkerTranscriptionConfig in NeMo Speech's example
# speech_to_text_multitalker_streaming_infer.py at commit 1688cc3d, as a
# plain dictionary (Apache-2.0; NOTICE). Configuration, not a word a model
# reads. OPTION_2 overrides what it names.
DEFAULTS = {
    "diar_model": None, "max_num_of_spks": 4, "parallel_speaker_strategy": True, "masked_asr": False,
    "mask_preencode": False, "cache_gating": True, "cache_gating_buffer_size": 2, "single_speaker_mode": False,
    "feat_len_sec": 0.01, "session_len_sec": -1, "num_workers": 8, "random_seed": None, "log": True,
    "precision": "bf16", "streaming_mode": True, "spkcache_len": None, "spkcache_update_period": 144,
    "fifo_len": 188, "diar_right_context": 0, "cuda": None, "allow_mps": False, "matmul_precision": "highest",
    "asr_model": None, "device": "cuda", "audio_file": None, "manifest_file": None, "att_context_size": [70, 13],
    "use_amp": True, "debug_mode": False, "deploy_mode": False, "batch_size": 32, "chunk_size": -1,
    "shift_size": -1, "left_chunks": 5, "online_normalization": False, "target_lang": None,
    "strip_lang_tags": False, "lang_tag_pattern": None, "output_path": None, "diar_output_rttm_dir": None,
    "diar_collar": 0.0, "diar_ignore_overlap": False, "pad_and_drop_preencoded": False,
    "generate_realtime_scripts": False, "spk_supervision": "diar", "binary_diar_preds": True, "verbose": False,
    "word_window": 50, "sent_break_sec": 1.0, "fix_prev_words_count": 5, "update_prev_words_sentence": 5,
    "left_frame_shift": -1, "right_frame_shift": 0, "min_sigmoid_val": 1e-2, "discarded_frames": 8,
    "print_time": True, "print_sample_indices": [0], "colored_text": True, "real_time_mode": False,
    "print_path": None, "ignored_initial_frame_steps": 5, "finetune_realtime_ratio": 0.01,
}


class RateNotSupported(Exception):
    pass


class ModelMissing(Exception):
    pass


# ------------------------------------------------------------ where they are

def _checkpoint(entry: dict, offline: bool) -> Path:
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
    return {"words": {"repo": MODELS["words"]["repo"], "revision": MODELS["words"]["revision"], "target_lang": TARGET_LANG},
            "speakers": {"repo": MODELS["speakers"]["repo"], "revision": MODELS["speakers"]["revision"]},
            "pairing": {"option_2": OPTION_2, "commit_margin_s": COMMIT_MARGIN_S, "max_speakers_at_load": MAX_SPEAKERS_AT_LOAD}}


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
    """Both checkpoints, loaded once per worker process and kept loaded (v1)."""

    def __init__(self, device: str, max_speakers: int = MAX_SPEAKERS_AT_LOAD):
        import torch
        import nemo.collections.asr as nemo_asr
        from nemo.collections.asr.models.sortformer_diar_models import SortformerEncLabelModel
        from nemo.collections.asr.parts.submodules.subsampling import FeatureStacking
        from nemo.collections.asr.parts.utils.multispk_transcribe_utils import (configure_diar_streaming,
                                                                                 validate_feature_frame_strides)
        from omegaconf import OmegaConf

        cfg = OmegaConf.create({**DEFAULTS, **OPTION_2, "max_num_of_spks": int(max_speakers), "device": device})
        self.cfg, self.device = cfg, device
        torch.set_float32_matmul_precision(cfg.matmul_precision)
        if device == "cuda":
            torch.backends.cuda.cufft_plan_cache.max_size = 8
        cpu = torch.device("cpu")
        diar = SortformerEncLabelModel.restore_from(restore_path=str(_checkpoint(MODELS["speakers"], offline=True)),
                                                    map_location=cpu)
        self.use_bf16 = (str(cfg.precision).lower().startswith("bf16") and cfg.use_amp
                         and device == "cuda" and torch.cuda.is_bf16_supported())
        diar = diar.to(dtype=torch.bfloat16 if self.use_bf16 else torch.float32).to(device).eval()
        asr = nemo_asr.models.ASRModel.restore_from(restore_path=str(_checkpoint(MODELS["words"], offline=True)),
                                                    map_location=cpu)
        asr.encoder.set_default_att_context_size(att_context_size=list(cfg.att_context_size))
        _configure_asr(cfg, asr)
        asr = asr.to(device).eval()
        asr.decoding.decoding.disable_cuda_graphs()        # v1: a graph replay failed in the session after a long one
        validate_feature_frame_strides(asr_model=asr, diar_model=diar)
        streaming = asr.encoder.streaming_cfg
        configure_diar_streaming(diar_model=diar, cfg=cfg, output_subsampling_factor=asr.encoder.subsampling_factor,
                                 diar_chunk_len=streaming.valid_out_len + streaming.cache_drop_size)
        if isinstance(diar.encoder.pre_encode, FeatureStacking):
            cfg.pad_and_drop_preencoded = True
        cfg.batch_size = 1
        self.asr, self.diar = asr, diar

    def autocast(self):
        import torch
        return torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=self.use_bf16)


def _configure_asr(cfg, asr) -> None:
    """The example script's configure_asr_for_multitalker_streaming: the
    language prompt and the stripping of its tag, for a model that takes one."""
    if cfg.parallel_speaker_strategy and not cfg.masked_asr and not hasattr(asr, "set_speaker_targets"):
        raise RuntimeError("parallel speakers without masking need a model with set_speaker_targets")
    if hasattr(asr, "set_inference_prompt"):
        asr.set_inference_prompt(cfg.target_lang if cfg.target_lang is not None else "auto")
        asr.decoding.set_strip_lang_tags(cfg.strip_lang_tags, lang_tag_pattern=cfg.lang_tag_pattern)


# ------------------------------------------------------------------ a session

class Stream:
    """One session's streaming state, v1's: the feature splice, NeMo's own
    chunker, SpeakerTaggedASR, and the commit rule."""

    def __init__(self, models: Models, speakers: int):
        import numpy as np
        from omegaconf import OmegaConf
        from nemo.collections.asr.parts.utils.multispk_transcribe_utils import SpeakerTaggedASR
        from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer
        self._np = np
        self.m = models
        self.cfg = OmegaConf.create(OmegaConf.to_container(models.cfg))
        self.cfg.max_num_of_spks = int(speakers)        # the number is given, never worked out (V1_LESSONS 2.1)
        self.streamer = SpeakerTaggedASR(self.cfg, models.asr, models.diar)
        self.buf = CacheAwareStreamingAudioBuffer(model=models.asr, online_normalization=self.cfg.online_normalization,
                                                  pad_and_drop_preencoded=self.cfg.pad_and_drop_preencoded)
        self.tail = np.zeros(0, dtype=np.float32)
        self.tail_start = 0
        self.total_samples = 0
        self.store = None
        self.feat_t = 0
        self.step = 0
        self.emitted: dict[int, dict] = {}
        self.next_id = 1
        self.late_changes: list[dict] = []
        self.step_seconds: list[float] = []

    def _frames_for(self, samples: int) -> int:
        return samples // HOP + 1

    def _refresh_features(self) -> int:
        import torch
        np = self._np
        first = max(0, self.feat_t - RECOMPUTE_FRAMES)
        lead = max(0, first - LEAD_FRAMES)
        piece = self.tail[lead * HOP - self.tail_start:]
        features, _ = self.buf.preprocess_audio(np.ascontiguousarray(piece))
        new = features[:, :, first - lead:]
        end = first + int(new.size(-1))
        if end != self._frames_for(self.total_samples):
            raise RuntimeError(f"the preprocessor gave {end} frames for {self.total_samples} samples")
        if self.store is None or end > self.store.size(-1):
            capacity = max(end, 2 * (0 if self.store is None else self.store.size(-1)), 6000)
            grown = torch.zeros((1, new.size(1), capacity), dtype=new.dtype, device=new.device)
            if self.store is not None:
                grown[:, :, :self.feat_t] = self.store[:, :, :self.feat_t]
            self.store = grown
        self.store[:, :, first:end] = new
        self.feat_t = end
        self.buf.buffer = self.store[:, :, :end]
        self.buf.streams_length = torch.tensor([end], device=new.device)
        keep_from = max(0, end - RECOMPUTE_FRAMES - LEAD_FRAMES - 2) * HOP
        if keep_from > self.tail_start:
            self.tail = self.tail[keep_from - self.tail_start:].copy()
            self.tail_start = keep_from
        return end

    def _chunk_size(self) -> int:
        size = self.buf.streaming_cfg.chunk_size
        if isinstance(size, list):
            first = self.buf.buffer_idx == 0
            size = size[1] if (not first or self.cfg.pad_and_drop_preencoded) else size[0]
        return int(size)

    def _run_steps(self, final: bool) -> None:
        import torch
        if self.total_samples == 0:
            return
        if not final and self.buf.buffer_idx + self._chunk_size() + STABLE_MARGIN_FRAMES > self._frames_for(self.total_samples):
            return
        total = self._refresh_features()
        chunks = self.buf.iter_with_right_context(0)
        while True:
            if not final and self.buf.buffer_idx + self._chunk_size() + STABLE_MARGIN_FRAMES > total:
                return
            try:
                chunk, lengths, diar_chunk, diar_lengths = next(chunks)
            except StopIteration:
                return
            drop = (0 if self.step == 0 and not self.cfg.pad_and_drop_preencoded
                    else self.m.asr.encoder.streaming_cfg.drop_extra_pre_encoded)
            t0 = time.perf_counter()
            with torch.inference_mode(), self.m.autocast():
                self.streamer.perform_parallel_streaming_stt_spk(
                    step_num=self.step, chunk_audio=chunk, chunk_lengths=lengths, diar_chunk_audio=diar_chunk,
                    diar_chunk_lengths=diar_lengths, is_buffer_empty=self.buf.is_buffer_empty(), drop_extra_pre_encoded=drop)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            self.step_seconds.append(time.perf_counter() - t0)
            self.step += 1

    def accept(self, samples) -> dict:
        """float32 samples at 16,000; then every complete chunk."""
        if samples.size:
            self.tail = self._np.concatenate([self.tail, samples])
            self.total_samples += samples.size
        self._run_steps(final=False)
        return self._collect(final=False)

    def flush(self) -> dict:
        self._run_steps(final=True)
        return self._collect(final=True)

    def processed_s(self) -> float:
        return self.buf.buffer_idx * FEATURE_STRIDE_S

    def _sentences(self):
        states = self.streamer.instance_manager.batch_asr_states
        if not states:
            return
        for spk_idx, sentences in states[0]._speaker_wise_sentences.items():
            for pos, sentence in enumerate(sentences):
                yield spk_idx, sentence, pos == len(sentences) - 1

    def _collect(self, final: bool) -> dict:
        """New committed lines in the door's form, and the open text as the
        text not yet final. A line is sent once; a later change to its text
        is kept as a late change, never sent as a revision."""
        head = self.processed_s()
        new, open_lines = [], []
        for spk_idx, sentence, is_last in self._sentences():
            text = (sentence.get("words") or "").strip()
            key, end = id(sentence), float(sentence["end_time"])
            if key in self.emitted:
                sent = self.emitted[key]
                if text != sent["text"] or round(end, 3) != sent["end"]:
                    sent["text"], sent["end"] = text, round(end, 3)
                    self.late_changes.append({"id": sent["id"], "text": text, "end": sent["end"]})
                continue
            if not text:
                continue
            if final or not is_last or end < head - COMMIT_MARGIN_S:
                line = {"id": self.next_id, "speaker": f"S{int(spk_idx) + 1}", "start": round(float(sentence["start_time"]), 3),
                        "end": round(end, 3), "text": text, "confidence": None}
                self.next_id += 1
                self.emitted[key] = dict(line)
                new.append(line)
            else:
                open_lines.append((float(sentence["start_time"]), text))
        new.sort(key=lambda line: line["start"])
        pending = []
        if open_lines:
            pending = [{"start": round(min(s for s, _ in open_lines), 3), "end": round(head, 3),
                        "text": " ".join(t for _, t in sorted(open_lines))}]
        return {"segments": new, "pending": pending, "revisions": []}


class Session:
    """One session behind the door: the conversion, then v1's stream."""

    def __init__(self, models: Models, rate: int, speakers: int):
        import sys
        sys.path.insert(0, str(HERE.parents[2] / "speech" / "common"))
        import resample
        try:
            self._resampler = resample.Resampler(rate, SAMPLE_RATE)
        except resample.RateNotSupported:
            raise RateNotSupported(rate) from None
        import numpy as np
        self._np = np
        self.stream = Stream(models, max(1, int(speakers)))

    def accept(self, pcm: bytes) -> dict:
        samples = self._resampler.convert(pcm).astype(self._np.float32) / 32768.0
        return self.stream.accept(samples)

    def finish(self) -> dict:
        started = time.perf_counter()
        tail = self.stream.flush()
        steps = self.stream.step_seconds
        seconds = {"tail": round(time.perf_counter() - started, 2), "steps": len(steps),
                   "step_max": round(max(steps), 3) if steps else 0.0, "processed_s": round(self.stream.processed_s(), 3)}
        return {"last_live": tail["segments"], "revisions": [], "seconds": seconds,
                "notes": {"late_changes": list(self.stream.late_changes)}}


def warm_up(models: Models) -> None:
    """v1's warm-up: silence through the stream once for each count of
    active speakers, with the cache gating off so the words model runs."""
    import numpy as np
    for active in range(1, MAX_SPEAKERS_AT_LOAD + 1):
        warm = Stream(models, MAX_SPEAKERS_AT_LOAD)
        warm.streamer._cache_gating = False
        warm.streamer.n_active_speakers_per_stream = active
        warm.accept(np.zeros(int(WARM_S * SAMPLE_RATE), dtype=np.float32))
        warm.flush()
        del warm
    if models.device == "cuda":
        import torch
        torch.cuda.empty_cache()
