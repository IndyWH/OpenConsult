"""Which speech pipeline transcribes the live consultation (Task 13, v1.1).

Two pipelines, chosen by SPEECH_PIPELINE:

- **whisper** (the default): today's path, unchanged. faster-whisper
  transcribes live in this process, and at Stop the finalisation
  pipeline unloads the CDS model, re-transcribes the recording with
  WhisperX and diarises it with pyannote.
- **nemotron**: NVIDIA Nemotron 3.5 ASR streaming plus
  Nemotron-3-Diarization run live in a separate process, from their own
  environment (speech_nemotron/), in the way Piper does. Speaker-tagged
  lines are stored as they arrive. At Stop the final transcript is built
  from those stored lines: the CDS model stays loaded, and neither
  WhisperX nor pyannote is loaded.

There is **no silent fallback** between them. With nemotron chosen and
its process not ready, recording does not start, and the live page says
why. An unknown value is a configuration error, reported the same way;
it is never quietly read as whisper.

This is a research and education prototype, not a medical device.
"""

from __future__ import annotations

import os
from pathlib import Path

WHISPER = "whisper"
NEMOTRON = "nemotron"
PIPELINES = (WHISPER, NEMOTRON)

SPEECH_PIPELINE = os.getenv("SPEECH_PIPELINE", WHISPER).strip().lower()

# The most speakers the live diariser keeps apart. The default is the
# count today's pyannote call uses, finalize.DEFAULT_SPEAKERS (2) — the
# owner's instruction at approval of Task 13: the same number as today,
# and 4 only if today's call set none. It is an upper bound for the
# streaming diariser, not an exact count as pyannote's is.
SPEECH_MAX_SPEAKERS = int(os.getenv("SPEECH_MAX_SPEAKERS", "2"))

# Where speech_nemotron/setup.sh builds the environment (its own default).
NEMOTRON_HOME = Path(os.path.expanduser(
    os.getenv("NEMOTRON_HOME", "~/.local/share/openconsult-nemotron")))


def configuration_error() -> str | None:
    """A plain sentence when the settings cannot be acted on, else None."""
    if SPEECH_PIPELINE not in PIPELINES:
        return (f"SPEECH_PIPELINE is set to '{SPEECH_PIPELINE}', which is not "
                f"one of: {', '.join(PIPELINES)}. Recording is off until it is "
                "corrected and the service restarted.")
    if SPEECH_MAX_SPEAKERS < 1:
        return "SPEECH_MAX_SPEAKERS must be 1 or more."
    return None


def uses_nemotron() -> bool:
    """True when anything other than plain whisper is configured — an
    invalid value counts, so it blocks recording instead of falling back."""
    return SPEECH_PIPELINE != WHISPER
