"""The table of speech choices (spec 11.1; 15.9). A choice names what it
declares (11.5 rule 5), the worker folder beside this file that runs it,
whether its worker needs an environment of its own in the data folder or
runs on the app's own Python (the cloud choices, spec 6.4), and the name
of the key it needs, if any. There is no field for a line of text a model
reads: no speech model is given one (ruling 3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openconsult import words
from openconsult.speech.lines import Declares

WORKERS = Path(__file__).parent


@dataclass(frozen=True)
class Choice:
    name: str
    title: str                 # the words the user reads
    declares: Declares
    folder: str
    environment: bool          # built in the data folder, or none: the app's own Python
    key: str | None = None     # the name of the key it needs

    @property
    def worker_folder(self) -> Path:
        return WORKERS / self.folder


WHISPERX_PYANNOTE = Choice(
    name="whisperx_pyannote",
    title=words.CHOICE_TITLE,
    declares=Declares(confidence="at_stop", speakers="at_stop", second_transcript=True),
    folder="whisperx",
    environment=True,
)

# Ruling 8: the English model alone writes the words and gives no
# confidence score; the speaker model beside it says who spoke, live.
NEMOTRON = Choice(
    name="nemotron",
    title=words.ROW_NEMOTRON,
    declares=Declares(confidence="none", speakers="live", second_transcript=False),
    folder="nemotron",
    environment=True,
)

# Ruling 9: each cloud service gives text with a confidence score and
# speaker labels live, through its EU address, and there is one transcript.
SPEECHMATICS = Choice(
    name="speechmatics",
    title=words.ROW_SPEECHMATICS,
    declares=Declares(confidence="live", speakers="live", second_transcript=False),
    folder="speechmatics",
    environment=False,
    key="SPEECHMATICS_API_KEY",
)

ASSEMBLYAI = Choice(
    name="assemblyai",
    title=words.ROW_ASSEMBLYAI,
    declares=Declares(confidence="live", speakers="live", second_transcript=False),
    folder="assemblyai",
    environment=False,
    key="ASSEMBLYAI_API_KEY",
)

CHOICES = {choice.name: choice for choice in (WHISPERX_PYANNOTE, NEMOTRON, SPEECHMATICS, ASSEMBLYAI)}
