"""The table of speech choices (spec 11.1; 15.9). 5a holds one: WhisperX
with pyannote. A choice names what it declares (11.5 rule 5) and the
worker folder beside this file that runs it. There is no field for a
line of text a model reads: no speech model is given one (ruling 3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openconsult.speech.lines import Declares

WORKERS = Path(__file__).parent


@dataclass(frozen=True)
class Choice:
    name: str
    declares: Declares
    folder: str

    @property
    def worker_folder(self) -> Path:
        return WORKERS / self.folder


WHISPERX_PYANNOTE = Choice(
    name="whisperx_pyannote",
    declares=Declares(confidence="at_stop", speakers="at_stop", second_transcript=True),
    folder="whisperx",
)

CHOICES = {choice.name: choice for choice in (WHISPERX_PYANNOTE,)}
