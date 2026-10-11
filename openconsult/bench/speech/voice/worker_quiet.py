"""The quiet logging of the WhisperX worker, for the voice worker: the log
in the data folder never holds a word that was said (D44), and the
libraries are held to warnings and above. Imported by the voice worker
before any library loads."""

from __future__ import annotations

import logging
import os
import sys

QUIET_LOGGERS = ("pyannote", "transformers", "huggingface_hub", "torch", "torchaudio", "speechbrain",
                 "lightning", "pytorch_lightning")

logging.basicConfig(level=logging.WARNING, stream=sys.stderr, force=True)
for _name in QUIET_LOGGERS:
    logging.getLogger(_name).setLevel(logging.WARNING)
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "warning")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
