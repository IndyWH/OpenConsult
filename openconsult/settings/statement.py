"""The cloud statement, built by code from the path (spec 15.13, rulings
5, 31, 32 and 33; 7.3, rule 2; the details of run 9b). One statement
for the whole setup, from the owner's words alone, which stand in the
file of words letter for letter. A line shows only when it is true for
the path: the sound as it is spoken and the live part for Speechmatics
only when Speechmatics writes the live text; the words, the age and
sex, the earlier notes, the note for a letter, the guideline passages
and the part for Claude only when Claude is the language model; the
lines of ruling 33 only when the whole recording is sent after Stop.
The doctor ticks the text as shown, and its checksum is kept: a path
whose statement no longer has that checksum has not been ticked."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from openconsult import words
from openconsult.settings.path import ChosenPath


@dataclass(frozen=True)
class Statement:
    heading: str
    intro: str
    sent: tuple[str, ...]
    stays: tuple[str, ...]
    parts: tuple[tuple[str, tuple[str, ...]], ...]      # each cloud service in use: its heading and its lines
    prototype: str
    tick: str

    @property
    def text(self) -> str:
        """The statement as it is read, one plain text: what is ticked."""
        blocks = [self.heading, self.intro,
                  "\n".join([words.CLOUD_SENT_HEADING, *(f"- {line}" for line in self.sent)]),
                  "\n".join([words.CLOUD_STAYS_HEADING, *(f"- {line}" for line in self.stays)])]
        blocks += ["\n".join([heading, *(f"- {line}" for line in lines)]) for heading, lines in self.parts]
        return "\n\n".join([*blocks, self.prototype, f"[ ] {self.tick}"]) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _sent(path: ChosenPath, recording: bool) -> tuple[str, ...]:
    lines = []
    if path.speechmatics_live:
        lines.append(words.CLOUD_SENT_SOUND)
    if recording:
        lines.append(words.CLOUD_SENT_RECORDING)
    if path.claude:
        # Ruling 5: with transcription on this computer the words that name the second service are left out.
        said = words.CLOUD_SENT_WORDS if path.speechmatics_live else words.CLOUD_SENT_WORDS.removesuffix(words.CLOUD_SENT_WORDS_GO)
        lines += [said, words.CLOUD_SENT_AGE, words.CLOUD_SENT_EARLIER, words.CLOUD_SENT_NOTE, words.CLOUD_SENT_PASSAGES]
    return tuple(lines)


def _stays(path: ChosenPath, recording: bool) -> tuple[str, ...]:
    # Ruling 5: The recording. stands here when the transcription is on this computer; not when the recording is sent after Stop.
    middle = [words.CLOUD_STAYS_RECORDING] if not path.speechmatics_live and not recording else []
    return (words.CLOUD_STAYS_NAME, *middle, words.CLOUD_STAYS_APPROVED)


def _speechmatics(path: ChosenPath, recording: bool) -> tuple[str, ...]:
    where, live, training, cost = words.CLOUD_SPEECHMATICS_LINES
    if path.speechmatics_live:
        lines = [where, live, training, cost]
        if recording:                      # at the press after a lost connection both sets show (ruling 33)
            lines += [words.CLOUD_SPEECHMATICS_WHOLE_KEPT, words.CLOUD_SPEECHMATICS_WHOLE_COST]
        return tuple(lines)
    # No live sound goes: the line on live sound gives way to the line on a recording sent whole, and the last line
    # stands without its price of live sound (the owner's word, 16 Nov 2026).
    return (where, words.CLOUD_SPEECHMATICS_WHOLE_KEPT, training, cost.removesuffix(words.CLOUD_SPEECHMATICS_LIVE_COST),
            words.CLOUD_SPEECHMATICS_WHOLE_COST)


def _heading_and_tick(path: ChosenPath, recording: bool) -> tuple[str, str]:
    sound_leaves = path.speechmatics_live or recording
    if path.claude and sound_leaves:
        return words.CLOUD_HEADING_BOTH, words.CLOUD_TICK_BOTH
    if path.claude:
        return words.CLOUD_HEADING_MODEL, words.CLOUD_TICK_WORDS
    if path.speechmatics_live:
        return words.CLOUD_HEADING_TRANSCRIPTION, words.CLOUD_TICK_SOUND
    return words.CLOUD_HEADING_RECORDING, words.CLOUD_TICK_RECORDING


def statement_for(path: ChosenPath, at_the_press: bool = False) -> Statement | None:
    """The statement of a path, or None when nothing of it leaves this
    computer. at_the_press: the one press after a lost connection, which
    sends the recording of a consultation in cloud transcription once
    (ruling 29), so both sets of lines show."""
    recording = path.recording_after_stop or (at_the_press and path.speechmatics_live)
    if not path.holds_cloud:
        return None
    heading, tick = _heading_and_tick(path, recording)
    parts = []
    if path.speechmatics_live or recording:
        parts.append((words.CLOUD_SPEECHMATICS_HEADING, _speechmatics(path, recording)))
    if path.claude:
        parts.append((words.CLOUD_CLAUDE_HEADING, tuple(words.CLOUD_CLAUDE_LINES)))
    return Statement(heading, words.CLOUD_INTRO, _sent(path, recording), _stays(path, recording), tuple(parts),
                     words.CLOUD_PROTOTYPE, tick)


def mark_lines(path: ChosenPath) -> tuple[str, ...]:
    """The lines of the cloud mark for a path (15.13, ruling 5; the owner's
    words of 16 Nov 2026): one for each thing that is true of it, in this
    order; none for a path with nothing in the cloud, which has no mark."""
    lines = []
    if path.speechmatics_live:
        lines.append(words.CLOUD_MARK_SOUND)
    if path.claude:
        lines.append(words.CLOUD_MARK_WORDS)
    if path.recording_after_stop:
        lines.append(words.CLOUD_MARK_RECORDING)
    return tuple(lines)


def review_mark_lines(path: ChosenPath, request: str | None) -> tuple[str, ...]:
    """The mark on the review page (15.13, ruling 52). The lines for the
    sound and the words as the path gives them. The third says that the
    recording went, in the owner's words, by the tick or by the one
    press, wherever the request that carried it was made and the record
    cannot show that nothing left: any answer of the service, a refusal
    too. It is left out where the request was never made, or no
    connection to the service was ever opened. request: what the
    consultation's own record holds, or None when nothing was to be sent."""
    lines = [line for line in mark_lines(path) if line != words.CLOUD_MARK_RECORDING]
    if request == "made":
        lines.append(words.CLOUD_MARK_RECORDING_SENT)
    return tuple(lines)
