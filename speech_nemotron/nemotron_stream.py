"""Nemotron live speech + diarisation, one consultation at a time.

Runs ONLY inside the Nemotron environment (speech_nemotron/setup.sh) — it
imports NeMo and its own torch. The app never imports this file; it talks
to `worker.py`, which wraps it, over a pipe.

The pairing is the diarisation model card's ASR_INTEGRATION_GUIDE.md
Option 2: nvidia/nemotron-3.5-asr-streaming-0.6b with
nvidia/Nemotron-3-Diarization through NeMo's SpeakerTaggedASR, with
masked_asr=true, att_context_size=[56,13], fifo_len=264,
spkcache_update_period=222, parallel speakers, cache gating, binary
diarisation predictions. The target language is en-GB, and the language
tag the model appends is stripped from the text.

**How audio is fed** (revised after the first full run beside Gemma, where
recomputing over the whole recording at every step grew memory with the
consultation and cuFFT ran out of room). The guide's live loop is written for Option 1 and
skips two things Option 2 needs (a separate diarisation feature view and
the padded first chunk of a FeatureStacking diariser). So this module
drives NeMo's OWN chunker, `CacheAwareStreamingAudioBuffer`, as the
file-replay script does, and only changes when it is fed. The preprocessor
has normalize=NA and dither only in training, so a frame's log-mel
features depend only on the 512 samples around it (plus one sample of
pre-emphasis). New audio therefore changes only the last few frames: those
RECOMPUTE_FRAMES are recomputed from a short slice of audio that starts
LEAD_FRAMES earlier, so the slice's own edge never reaches a kept frame,
and spliced into a growing feature store. A chunk is taken only when it
sits STABLE_MARGIN_FRAMES clear of the end. At flush the remainder is
taken exactly as the replay script takes it. Task 13 Part 1 compares the
spliced features with one pass over the whole recording.

**When a line is final.** SpeakerTaggedASR keeps one open sentence per
speaker and extends it while the same voice continues within
sent_break_sec. A sentence is committed — emitted once, never revised —
when its speaker has started a later one, or when its end lies
COMMIT_MARGIN_S behind the audio already processed. Every commit carries
a WATERMARK: no line that starts before it can still arrive. The app uses
the watermark to put lines in the order they were spoken, whatever order
the speakers' streams commit them in.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

import numpy as np
import torch
from omegaconf import OmegaConf

SAMPLE_RATE = 16_000
FEATURE_STRIDE_S = 0.01          # 10 ms log-mel frames (both models)
HOP = 160                        # samples per feature frame
STABLE_MARGIN_FRAMES = 4         # STFT window (25 ms, centred) runs past the end
RECOMPUTE_FRAMES = 8             # tail frames recomputed when audio arrives
LEAD_FRAMES = 8                  # audio kept before them (n_fft/2 + pre-emphasis)
COMMIT_MARGIN_S = 3.0            # sent_break_sec (1.0) + one 1.12 s chunk + slack

ASR_MODEL = "nvidia/nemotron-3.5-asr-streaming-0.6b"
ASR_REVISION = "ea30d66debe3740a08b573244286791d423d6b3e"
DIAR_MODEL = "nvidia/Nemotron-3-Diarization"
DIAR_REVISION = "f667ed73aee57d40cc39428eb768b4fd87a0a29e"
TARGET_LANG = "en-GB"

# The guide's Option 2 settings. Everything else is the replay script's
# own default (MultitalkerTranscriptionConfig), loaded from the pinned
# checkout so the two cannot drift apart.
OPTION_2 = {
    "masked_asr": True,
    "att_context_size": [56, 13],
    "parallel_speaker_strategy": True,
    "single_speaker_mode": False,
    "cache_gating": True,
    "binary_diar_preds": True,
    "fifo_len": 264,
    "spkcache_update_period": 222,
    "target_lang": TARGET_LANG,
    "strip_lang_tags": True,
    "generate_realtime_scripts": False,
    "deploy_mode": True,
    "log": False,
    "print_time": False,
    "verbose": False,
}


def _speech_checkout() -> Path:
    """The pinned NeMo Speech checkout this interpreter belongs to: its
    venv is <checkout>/.venv, so sys.prefix's parent is the checkout."""
    import sys
    return Path(sys.prefix).parent


def _replay_script_module():
    path = (_speech_checkout() / "examples" / "asr" / "asr_cache_aware_streaming"
            / "speech_to_text_multitalker_streaming_infer.py")
    spec = importlib.util.spec_from_file_location("nemo_mt_infer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checkpoint(repo: str, revision: str) -> str:
    from huggingface_hub import hf_hub_download
    filename = repo.split("/")[1] + ".nemo"
    return hf_hub_download(repo, filename, revision=revision)


class Models:
    """Both checkpoints, loaded once per worker process and kept loaded."""

    def __init__(self, max_speakers: int, device: str = "cuda"):
        import nemo.collections.asr as nemo_asr
        from nemo.collections.asr.parts.utils.multispk_transcribe_utils import (
            configure_diar_streaming, validate_feature_frame_strides)

        infer = _replay_script_module()
        cfg = OmegaConf.structured(infer.MultitalkerTranscriptionConfig())
        for key, value in OPTION_2.items():
            cfg[key] = value
        cfg.max_num_of_spks = int(max_speakers)
        cfg.device = device
        self.cfg = cfg

        torch.set_float32_matmul_precision(cfg.matmul_precision)
        # The live feed hands cuFFT a slightly different length each time, and
        # each length is a new cached plan on the GPU. Cap the cache.
        torch.backends.cuda.cufft_plan_cache.max_size = 8
        # Both checkpoints are restored on the CPU and only then moved to the
        # GPU. Restoring straight onto the GPU holds the state dict and the
        # module there at once — about twice the ASR model's 2.4 GB of fp32
        # weights — and that transient alone ran out of memory beside Gemma
        # (Task 13, first attempt). The end state is the replay script's:
        # diariser in bf16, ASR weights fp32 under bf16 autocast.
        cpu = torch.device("cpu")
        diar = infer.load_diar_model(_checkpoint(DIAR_MODEL, DIAR_REVISION), cpu)
        self.use_bf16 = (str(cfg.precision).lower().startswith("bf16") and cfg.use_amp
                         and device == "cuda" and torch.cuda.is_bf16_supported())
        diar = diar.to(dtype=torch.bfloat16 if self.use_bf16 else torch.float32)
        diar = diar.to(device).eval()

        asr = nemo_asr.models.ASRModel.restore_from(
            restore_path=_checkpoint(ASR_MODEL, ASR_REVISION), map_location=cpu)
        asr.encoder.set_default_att_context_size(att_context_size=list(cfg.att_context_size))
        infer.configure_asr_for_multitalker_streaming(cfg, asr)
        asr = asr.to(device).eval()
        # CUDA graphs OFF in the RNNT greedy decoder (NeMo's own switch). With
        # them on, the decoder's graph replay hit an illegal memory access in
        # the session after a full-length one — reproduced in Task 13 with a
        # 300 s session followed by a second on the same loaded models, and
        # not cured by NeMo's reset_cuda_graphs_state(). A worker serves many
        # consultations on one load, so this must hold. Decoding then runs as
        # plain PyTorch; same model, same runtime, same SpeakerTaggedASR path.
        asr.decoding.decoding.disable_cuda_graphs()

        validate_feature_frame_strides(asr_model=asr, diar_model=diar)
        streaming = asr.encoder.streaming_cfg
        configure_diar_streaming(
            diar_model=diar, cfg=cfg,
            output_subsampling_factor=asr.encoder.subsampling_factor,
            diar_chunk_len=streaming.valid_out_len + streaming.cache_drop_size)
        from nemo.collections.asr.parts.submodules.subsampling import FeatureStacking
        if isinstance(diar.encoder.pre_encode, FeatureStacking):
            cfg.pad_and_drop_preencoded = True
        cfg.batch_size = 1
        self.asr, self.diar = asr, diar

    def autocast(self):
        return torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16,
                                  enabled=self.use_bf16)


class Stream:
    """One consultation's streaming state. Not shared between sessions."""

    def __init__(self, models: Models):
        from nemo.collections.asr.parts.utils.multispk_transcribe_utils import SpeakerTaggedASR
        from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer

        self.m = models
        cfg = models.cfg
        self.streamer = SpeakerTaggedASR(cfg, models.asr, models.diar)
        self.buf = CacheAwareStreamingAudioBuffer(
            model=models.asr, online_normalization=cfg.online_normalization,
            pad_and_drop_preencoded=cfg.pad_and_drop_preencoded)
        self.tail = np.zeros(0, dtype=np.float32)   # audio not yet safe to forget
        self.tail_start = 0                         # its first sample's index
        self.total_samples = 0
        self.store = None                           # (1, features, capacity)
        self.feat_t = 0                             # frames written so far
        self.step = 0
        self.emitted: dict[int, dict] = {}     # id(sentence) -> what was sent
        self.late_changes = 0                  # committed lines NeMo extended later
        self.step_seconds: list[float] = []
        self.flushed = False

    # --- feeding ----------------------------------------------------------

    def _frames_for(self, samples: int) -> int:
        return samples // HOP + 1        # centred STFT: floor(len / hop) + 1

    def _refresh_features(self) -> int:
        """Recompute the unstable tail of the features and splice it in."""
        first = max(0, self.feat_t - RECOMPUTE_FRAMES)       # first frame rewritten
        lead = max(0, first - LEAD_FRAMES)                   # slice starts here
        assert lead * HOP >= self.tail_start, "audio needed for the tail was dropped"
        piece = self.tail[lead * HOP - self.tail_start:]
        features, _ = self.buf.preprocess_audio(np.ascontiguousarray(piece))
        new = features[:, :, first - lead:]
        end = first + int(new.size(-1))
        assert end == self._frames_for(self.total_samples)
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
        sc = self.buf.streaming_cfg
        size = sc.chunk_size
        if isinstance(size, list):
            first = self.buf.buffer_idx == 0
            size = size[1] if (not first or self.m.cfg.pad_and_drop_preencoded) else size[0]
        return int(size)

    def _run_steps(self, final: bool) -> None:
        if self.total_samples == 0:
            return
        if (not final and self.buf.buffer_idx + self._chunk_size() + STABLE_MARGIN_FRAMES
                > self._frames_for(self.total_samples)):
            return                       # no complete chunk yet: nothing to compute
        total = self._refresh_features()
        chunks = self.buf.iter_with_right_context(0)
        while True:
            if not final and self.buf.buffer_idx + self._chunk_size() + STABLE_MARGIN_FRAMES > total:
                return
            try:
                chunk, lengths, diar_chunk, diar_lengths = next(chunks)
            except StopIteration:
                return
            drop = (0 if self.step == 0 and not self.m.cfg.pad_and_drop_preencoded
                    else self.m.asr.encoder.streaming_cfg.drop_extra_pre_encoded)
            t0 = time.perf_counter()
            with torch.inference_mode(), self.m.autocast():
                self.streamer.perform_parallel_streaming_stt_spk(
                    step_num=self.step, chunk_audio=chunk, chunk_lengths=lengths,
                    diar_chunk_audio=diar_chunk, diar_chunk_lengths=diar_lengths,
                    is_buffer_empty=self.buf.is_buffer_empty(),
                    drop_extra_pre_encoded=drop)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            self.step_seconds.append(time.perf_counter() - t0)
            self.step += 1

    def accept(self, pcm16: bytes) -> dict:
        """Append mono 16 kHz PCM16 and process every complete chunk."""
        if pcm16:
            samples = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
            self.tail = np.concatenate([self.tail, samples])
            self.total_samples += samples.size
        self._run_steps(final=False)
        return self._collect(final=False)

    def flush(self) -> dict:
        """Process the remainder and commit every line."""
        self._run_steps(final=True)
        self.flushed = True
        return self._collect(final=True)

    # --- lines ------------------------------------------------------------

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
        head = self.processed_s()
        new, open_starts = [], []
        for spk_idx, sentence, is_last in self._sentences():
            text = (sentence.get("words") or "").strip()
            key = id(sentence)
            if key in self.emitted:
                if text != self.emitted[key]["text"]:
                    self.late_changes += 1
                    self.emitted[key]["text"] = text   # counted once per change seen
                continue
            if not text:
                continue
            end = float(sentence["end_time"])
            if final or not is_last or end < head - COMMIT_MARGIN_S:
                line = {"speaker": int(spk_idx), "start": round(float(sentence["start_time"]), 3),
                        "end": round(end, 3), "text": text}
                self.emitted[key] = dict(line)
                new.append(line)
            else:
                open_starts.append(float(sentence["start_time"]))
        if final:
            watermark = None                        # everything has been sent
        else:
            watermark = round(min([head - COMMIT_MARGIN_S] + open_starts), 3)
        new.sort(key=lambda line: line["start"])
        return {"segments": new, "watermark": watermark, "processed_s": round(head, 3)}

    def stats(self) -> dict:
        steps = self.step_seconds
        return {"steps": len(steps), "audio_s": round(self.total_samples / SAMPLE_RATE, 3),
                "processed_s": round(self.processed_s(), 3),
                "step_max_s": round(max(steps), 4) if steps else None,
                "step_sum_s": round(sum(steps), 3),
                "late_changes": self.late_changes}
