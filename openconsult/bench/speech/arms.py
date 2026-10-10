"""The arms of the speech bench (spec 15.9, ruling 15): the four speech
choices as built, and the two arms that belong to the bench alone, the
tied Nemotron pair and WhisperX with v1's line. An arm names the Choice
its door is built with, which choice's environment runs its worker,
its worker file when it is not the app's own, and the cloud service it
sends sound to, if any, so that consent can be checked by code (ruling
14). The app's table of choices has no place for the two bench arms, and
only this module builds their doors."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from openconsult import words
from openconsult.speech import environment
from openconsult.speech.choices import (ASSEMBLYAI, NEMOTRON, NEMOTRON_TIME_SLACK_S, SPEECHMATICS, WHISPERX_PYANNOTE,
                                        Choice)
from openconsult.speech.door import Door, make_door
from openconsult.speech.lines import Declares
from openconsult.speech.worker import Worker

BENCH = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Arm:
    name: str
    choice: Choice
    environment_of: Choice            # whose environment in the data folder runs the worker
    worker_script: Path | None        # None: the app's own worker of the choice
    cloud_service: str | None = None  # the service its sound goes to, for consent

    @property
    def cloud(self) -> bool:
        return self.cloud_service is not None


# The two arms of the bench (ruling 15). Not in the app's table of choices.
# The tied pair (ruling 8): v1's pairing, no confidence, labels live, one
# transcript, and its times made as Nemotron's are, so the same figure.
TIED_PAIR = Choice(name="nemotron_tied_pair", title=words.ARM_TIED_PAIR,
                   declares=Declares(confidence="none", speakers="live", second_transcript=False,
                                     time_slack_s=NEMOTRON_TIME_SLACK_S),
                   folder="", environment=True)
# WhisperX with v1's line (ruling 3): the same live model, given the line.
V1_LINE = Choice(name="whisperx_v1_line", title=words.ARM_V1_LINE, declares=WHISPERX_PYANNOTE.declares,
                 folder="", environment=True)

ARMS: dict[str, Arm] = {
    "whisperx_pyannote": Arm("whisperx_pyannote", WHISPERX_PYANNOTE, WHISPERX_PYANNOTE, None),
    "whisperx_v1_line": Arm("whisperx_v1_line", V1_LINE, WHISPERX_PYANNOTE, BENCH / "v1line" / "worker.py"),
    "nemotron": Arm("nemotron", NEMOTRON, NEMOTRON, None),
    "nemotron_tied_pair": Arm("nemotron_tied_pair", TIED_PAIR, NEMOTRON, BENCH / "tied" / "worker.py"),
    "speechmatics": Arm("speechmatics", SPEECHMATICS, SPEECHMATICS, None, "speechmatics"),
    "assemblyai": Arm("assemblyai", ASSEMBLYAI, ASSEMBLYAI, None, "assemblyai"),
}


def door_for(arm: Arm, data_folder: Path, environ=os.environ) -> Door:
    """The arm's door: the app's own for a choice; for an arm of the bench
    its worker file run by the environment's Python, with no key."""
    if arm.worker_script is None:
        return make_door(data_folder, arm.choice, environ)
    command = [str(environment.python(data_folder, arm.environment_of)), str(arm.worker_script)]
    log = environment.log_path(data_folder, arm.environment_of).with_name(f"{arm.name}.log")
    return Door(arm.choice,
                make_worker=lambda: Worker(command, log_path=log, env=environment.worker_env(environ)),
                installed=lambda: environment.installed(data_folder, arm.environment_of))
