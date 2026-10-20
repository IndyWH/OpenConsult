"""The live transcript as shown (spec 15.10, The live page; V1_LESSONS
3.13): the lines the door made final, in the order they arrived, the
lines the rule against words from silence refused, kept and marked, the
text not yet final, and the text the model reads, which is the lines'
words joined by line breaks, as v1's live transcript and the 495 case of
the bench have it, with no speaker word (R12). A service's revision of a
label changes the label of a line already shown and nothing else."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from openconsult.speech.lines import Line, Live


@dataclass
class Shown:
    n: int                 # the order shown, from 1
    line: Line
    refused: bool
    shown_at_s: float      # seconds of sound fed when the line arrived
    revised: bool = False  # a service revised its label after it was shown


class Transcript:
    def __init__(self):
        self.shown: list[Shown] = []
        self.partial = ""
        self._chars_sent = 0
        self._lines_at_last_pass = 0

    @property
    def heard(self) -> list[Shown]:
        return [s for s in self.shown if not s.refused]

    def lines(self) -> list[Line]:
        return [s.line for s in self.heard]

    def text(self) -> str:
        return "\n".join(s.line.text for s in self.heard)

    def add(self, live: Live) -> list[Shown]:
        """What one feed gave, in the order the door gave it: the lines made
        final, then the refused ones; the partial text replaced; the
        revisions applied. Returns the new entries, for the record."""
        new = []
        for line in live.lines:
            new.append(Shown(len(self.shown) + len(new) + 1, line, False, live.fed_s))
        for refused in live.refused:
            new.append(Shown(len(self.shown) + len(new) + 1, refused.line, True, live.fed_s))
        self.shown += new
        self.partial = live.partial
        for revision in live.revisions:
            self.revise(revision.id, revision.speaker, revision.applied)
        return new

    def revise(self, line_id: int, speaker: str | None, applied: bool) -> None:
        if not applied:
            return
        for shown in self.shown:
            if shown.line.id == line_id and not shown.refused:
                shown.line = dataclasses.replace(shown.line, speaker=speaker)
                shown.revised = True

    # ------------------------------------------------- when a pass is due

    def new_chars(self) -> int:
        return len(self.text()) - self._chars_sent

    def new_lines_since_pass(self) -> bool:
        return len(self.heard) > self._lines_at_last_pass

    def mark_sent(self) -> str:
        """The text as sent to a pass; the counters move to it."""
        text = self.text()
        self._chars_sent = len(text)
        self._lines_at_last_pass = len(self.heard)
        return text
