"""Speech-to-text engine for the live path.

Wraps faster-whisper (CTranslate2). The model loads once at startup and is
reused by every connection. Runs on the GPU when available, falls back to
CPU (with a smaller compute type) otherwise.

Audio contract: mono float32 PCM at 16 kHz, the format Whisper expects.
"""

from __future__ import annotations

import ctypes
import glob
import logging
import os
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


def _preload_cuda_libraries() -> None:
    """Load the pip-installed NVIDIA cuBLAS/cuDNN libraries into the process.

    CTranslate2 needs these at runtime but the pip wheels put them inside
    site-packages, outside the system library path. Loading them with ctypes
    first means CTranslate2 finds them already present.
    """
    try:
        import nvidia  # noqa: F401  (namespace package from the nvidia-* wheels)
    except ImportError:
        return
    for nvidia_dir in nvidia.__path__:  # namespace package: may span several dirs
        for pkg in ("cublas", "cudnn"):
            lib_dir = os.path.join(nvidia_dir, pkg, "lib")
            for so_path in sorted(glob.glob(os.path.join(lib_dir, "*.so*"))):
                try:
                    ctypes.CDLL(so_path)
                except OSError:  # pragma: no cover - depends on local install
                    logger.debug("Could not preload %s", so_path)


@dataclass
class Segment:
    """One stretch of recognised speech, in seconds from the buffer start."""

    start: float
    end: float
    text: str


# Biases recognition toward clinical vocabulary. Whisper reads this as
# "text that came just before the audio", so phrasing it as a transcript
# description steers word choice without inventing content. Shared by the
# live path and the WhisperX finalisation pass (the 2026-07-17 recordings
# deviation report measured the cost of its absence in the final pass).
CLINICAL_INITIAL_PROMPT = os.getenv(
    "WHISPER_INITIAL_PROMPT",
    "A general practice consultation between a doctor and a patient, "
    "including medical terminology and medication names such as "
    "metformin, gliclazide, losartan, atorvastatin, omeprazole, "
    "salbutamol, beclometasone, and investigations such as HbA1c, "
    "full blood count, NS1 antigen, ECG.",
)


class LiveTranscriber:
    """Loads a Whisper model once and transcribes audio buffers on demand."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
    ) -> None:
        from faster_whisper import WhisperModel

        model_size = model_size or os.getenv("WHISPER_MODEL", "distil-large-v3")
        device = device or os.getenv("WHISPER_DEVICE", "auto")
        self.beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
        self.initial_prompt = CLINICAL_INITIAL_PROMPT

        if device in ("auto", "cuda"):
            _preload_cuda_libraries()

        try:
            self.model = WhisperModel(model_size, device=device, compute_type="auto")
        except (RuntimeError, ValueError):
            if device == "cpu":
                raise
            logger.warning("GPU unavailable, falling back to CPU (int8)")
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

        self.model_size = model_size
        logger.info(
            "Whisper model '%s' loaded on %s", model_size, self.model.model.device
        )

    def transcribe(self, audio: np.ndarray) -> list[Segment]:
        """Transcribe a float32 16 kHz mono buffer; silence yields no segments."""
        segments, _info = self.model.transcribe(
            audio,
            language="en",
            beam_size=self.beam_size,
            initial_prompt=self.initial_prompt,
            vad_filter=True,  # Silero VAD skips silence between phrases
            condition_on_previous_text=False,  # each pass independent; avoids drift
        )
        return [Segment(s.start, s.end, s.text.strip()) for s in segments if s.text.strip()]
