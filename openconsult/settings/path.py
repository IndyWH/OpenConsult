"""The path of a consultation (spec 7.3; 10.3; 15.13, the details of run
9b): where the language model runs and where the transcription runs,
each on this computer or at its one cloud service, and whether the
whole recording is sent once after Stop. Two settings and one tick,
read once at Start and held by the consultation to its end. With a
suitable card both begin on this computer; with none both begin in the
cloud (10.3). Nothing here switches a path: only the doctor does, on
the settings page."""

from __future__ import annotations

from dataclasses import dataclass

THIS_COMPUTER, CLAUDE, SPEECHMATICS = "this_computer", "claude", "speechmatics"
LANGUAGE_MODELS = (THIS_COMPUTER, CLAUDE)
TRANSCRIPTIONS = (THIS_COMPUTER, SPEECHMATICS)


@dataclass(frozen=True)
class ChosenPath:
    language_model: str
    transcription: str
    better_accuracy: bool = False     # the tick: the recording sent once after Stop (15.9, ruling 36)

    @property
    def claude(self) -> bool:
        return self.language_model == CLAUDE

    @property
    def speechmatics_live(self) -> bool:
        return self.transcription == SPEECHMATICS

    @property
    def recording_after_stop(self) -> bool:
        """The tick counts only where the transcription runs on this
        computer: in cloud mode nothing is sent a second time (ruling 36)."""
        return self.better_accuracy and self.transcription == THIS_COMPUTER

    @property
    def holds_cloud(self) -> bool:
        return self.claude or self.speechmatics_live or self.recording_after_stop

    @property
    def services(self) -> tuple[str, ...]:
        """The cloud services the path uses, the transcription's first."""
        found = []
        if self.speechmatics_live or self.recording_after_stop:
            found.append(SPEECHMATICS)
        if self.claude:
            found.append(CLAUDE)
        return tuple(found)

    @property
    def needed_while_it_runs(self) -> tuple[str, ...]:
        """The services a consultation needs from Start to Stop: Claude on
        its path, Speechmatics live on its path. The recording after Stop
        needs its service only after Stop (the owner's word, 16 Nov 2026)."""
        return tuple(s for s in self.services if s == CLAUDE or self.speechmatics_live)

    def key(self) -> str:
        """The path in one plain line, for the audit log and the record."""
        return (f"language model {self.language_model}, transcription {self.transcription}, "
                f"recording after Stop {'yes' if self.recording_after_stop else 'no'}")


def beginning(machine_case: str) -> ChosenPath:
    """Where a machine begins before the doctor has chosen (10.3)."""
    if machine_case == "suitable":
        return ChosenPath(THIS_COMPUTER, THIS_COMPUTER)
    return ChosenPath(CLAUDE, SPEECHMATICS)


def path_of(row) -> ChosenPath:
    """The path a consultation started with, from its own row (7.3): an
    older row reads this computer for both."""
    return ChosenPath(row["language_model_path"], row["transcription_path"], bool(row["better_accuracy"]))
