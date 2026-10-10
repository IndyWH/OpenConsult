"""The pages of a stored result (spec 15.9, the details of 5c: what part
one scores). The page is the transcript the doctor would have: the lines
at Stop. For a choice with two transcripts the live lines are a page of
their own, because Alba will act on them. Each page is read in its
smallest timed pieces: for WhisperX at Stop the raw segments, so that a
turn joined across a pause cannot hide a word; for the rest, the lines as
the choice gave them. Every page word is aligned to the reference."""

from __future__ import annotations

from dataclasses import dataclass, field

from openconsult.bench.speech.reference import Reference
from openconsult.speech.loudness import QUIET_DBFS
from openconsult.speech.matching import Pair, align, normalise
from openconsult.speech.turns import speaker_of


@dataclass
class Page:
    name: str                              # stop or live
    pieces: list[dict]                     # the smallest timed pieces: start, end, text, speaker
    words: list[str] = field(default_factory=list)
    word_piece: list[int] = field(default_factory=list)   # the piece each word is in
    pairs: list[Pair] = field(default_factory=list)
    spoken_of: dict[int, int] = field(default_factory=dict)   # page word -> reference word it stands at
    kind_of: dict[int, str] = field(default_factory=dict)     # page word -> heard, replaced or nowhere
    at_spoken: dict[int, int] = field(default_factory=dict)   # reference word -> the page word standing at it

    def heard_indexes(self) -> list[int]:
        return [i for i, kind in self.kind_of.items() if kind == "heard"]


def _piece(start, end, text, speaker=None) -> dict:
    return {"start": float(start), "end": float(end), "text": str(text), "speaker": speaker}


def stop_pieces(result: dict) -> list[dict]:
    """The pieces of the page at Stop: raw segments that the rule did not
    refuse, for a choice with two transcripts; otherwise the lines."""
    stop = result["stop"]
    if stop["raw"]:
        return [_piece(s["start"], s["end"], s["text"], speaker_of(s)) for s in stop["raw"] if not s.get("refused")]
    return [_piece(line["start"], line["end"], line["text"], line.get("speaker")) for line in stop["lines"]]


def live_pieces(result: dict) -> list[dict]:
    """The live lines in the order they arrived, the last live lines last."""
    lines = [line for piece in result["pieces"] for line in piece["lines"]]
    return [_piece(ln["start"], ln["end"], ln["text"], ln.get("speaker")) for ln in lines + result["stop"]["last_live"]]


def build_page(name: str, pieces: list[dict], reference: Reference) -> Page:
    page = Page(name, pieces)
    for index, piece in enumerate(pieces):
        for word in normalise(piece["text"], reference.joinable):
            page.words.append(word)
            page.word_piece.append(index)
    page.pairs = align(reference.norms, page.words)
    for pair in page.pairs:
        if pair.page is not None:
            page.kind_of[pair.page] = pair.kind
            if pair.spoken is not None:
                page.spoken_of[pair.page] = pair.spoken
                page.at_spoken[pair.spoken] = pair.page
    return page


def pages_of(result: dict, reference: Reference) -> dict[str, Page]:
    """The stop page, and the live page for a choice with two transcripts."""
    found = {"stop": build_page("stop", stop_pieces(result), reference)}
    if result["stop"]["raw"]:
        found["live"] = build_page("live", live_pieces(result), reference)
    return found


def pauses_of(windows: list[float | None], window_s: float, least_s: float = 2.0,
              threshold: float = QUIET_DBFS) -> list[tuple[float, float]]:
    """Stretches of least_s or more where the sound stays at or below the
    quiet figure of the rule against words from silence (ruling 13)."""
    found, start = [], None
    for index, level in enumerate(windows + [0.0]):
        quiet = level is None or level <= threshold
        if quiet and start is None:
            start = index
        elif not quiet and start is not None:
            if (index - start) * window_s >= least_s:
                found.append((round(start * window_s, 3), round(index * window_s, 3)))
            start = None
    return found


def loudest_in(windows: list[float | None], window_s: float, start: float, end: float) -> float | None:
    first = max(0, int(start / window_s))
    last = max(first + 1, -(-int(round(end / window_s * 1000)) // 1000))
    levels = [w for w in windows[first:last] if w is not None]
    return max(levels) if levels else None
