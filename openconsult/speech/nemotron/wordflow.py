"""The grouping of the English model's tokens into words (spec 15.9, ruling
8; the details of part two of 5c, fix one). A plain class with no library,
loaded by path by the worker and by the suite, as join.py is. The rules of
5b stay: a token that starts with the word mark begins a word, a token with
no word open begins one, any other token joins the open word, and Stop
closes the open word. One rule is added: a word is also complete once the
model has moved WORD_CLOSE_S past its last token, whether or not another
word follows. Without it the last word before a silence waited until Stop
(part one: 194 s on recording 477), because the line's own wait of 3.0 s
runs only from a complete word."""

from __future__ import annotations

from typing import Callable

WORD_MARK = "▁"      # the piece that starts a word in the model's tokenizer
# A word is complete once the decoded frames are this far past its last
# token. It equals the join's pause (join.py, PAUSE_S): no word holds a
# silence of a second inside it, and a token this long after the previous
# token of its word would open a new line anyway, so nothing the join would
# have put in one line is cut in two. It is under the line's own wait
# (models.py, LINE_WAIT_S), so the word is complete before the line is.
WORD_CLOSE_S = 1.0


class WordFlow:
    """Tokens in, complete words out, in order, with their times in seconds
    from the start of the session. text_of gives a word's text from its
    token ids (the tokenizer, or a stand-in in the suite)."""

    def __init__(self, text_of: Callable[[list], str], frame_s: float, close_s: float = WORD_CLOSE_S):
        self.text_of = text_of
        self.frame_s = float(frame_s)
        self.close_s = float(close_s)
        self.complete: list[dict] = []        # complete words, not yet taken
        self.open: dict | None = None         # the word still being spoken
        self.last_frame: int | None = None    # the frame of the last token taken
        # Counts for the proof on the card: the largest gap in frames between
        # two tokens of one word, and tokens that arrived with no word mark
        # after a close by time (such a token would have split a word).
        self.largest_gap_frames = 0
        self.tokens_after_close_by_time = 0
        self._closed_by_time = False

    def take(self, token_id, piece: str, frame: int) -> None:
        frame = int(frame)
        self.last_frame = frame
        if piece.startswith(WORD_MARK) or self.open is None:
            if self.open is not None:
                self._close()
            elif self._closed_by_time and not piece.startswith(WORD_MARK):
                self.tokens_after_close_by_time += 1
            self._closed_by_time = False
            self.open = {"ids": [token_id], "first": frame, "last": frame}
        else:
            self.largest_gap_frames = max(self.largest_gap_frames, frame - self.open["last"])
            self.open["ids"].append(token_id)
            self.open["last"] = frame

    def moved_to(self, frames_decoded: int) -> None:
        """The model has decoded this many frames. A word the model has moved
        WORD_CLOSE_S past is complete, next word or not."""
        if self.open is not None and (int(frames_decoded) - self.open["last"]) * self.frame_s >= self.close_s:
            self._close()
            self._closed_by_time = True

    def finish(self) -> None:
        if self.open is not None:
            self._close()

    def open_text(self) -> str:
        return self.text_of(self.open["ids"]).strip() if self.open else ""

    def _close(self) -> None:
        text = self.text_of(self.open["ids"]).strip()
        if text:
            self.complete.append({"word": text, "start": round(self.open["first"] * self.frame_s, 3),
                                  "end": round((self.open["last"] + 1) * self.frame_s, 3)})
        self.open = None
