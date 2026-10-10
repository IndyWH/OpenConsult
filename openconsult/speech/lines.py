"""What every speech choice gives the app (spec 11.4): lines of text, each
with a speaker or none, a start and an end time, and a confidence score or
none. What a choice declares about itself (11.5, rule 5). The stamp on
every result (R20). One result from every call: lines, or a failure with
its reason; never an exception into the app (15.9, the door)."""

from __future__ import annotations

from dataclasses import dataclass, field

WHEN = ("live", "at_stop", "none")

FAILURES = ("not_installed", "died", "no_answer", "worker_error", "bad_reply",
            "no_session", "session_open", "rate_not_supported", "bad_speakers",
            # The cloud choices (spec 7.2; 15.9, the details of 5b).
            "no_key", "key_refused", "no_credit", "no_internet", "service_down",
            "limit_reached", "address_refused", "connection_lost")


@dataclass(frozen=True)
class Line:
    speaker: str | None
    start: float
    end: float
    text: str
    confidence: float | None
    id: int | None = None      # given by a choice whose labels are live, so a label can be revised


@dataclass(frozen=True)
class Refused:
    """A line the rule against words from silence refused: kept and
    marked, never thrown away (V1_LESSONS 1.2)."""
    line: Line
    loudest_dbfs: float
    threshold_dbfs: float


@dataclass(frozen=True)
class Revision:
    """A service revised the label of a line already given (ruling 4). It
    changes the label and nothing else. applied says the door changed a
    line it had given; otherwise line is the refused line it named, or
    none when the door never saw that id. A revision never costs a line."""
    id: int
    speaker: str | None
    applied: bool
    line: Line | None


@dataclass(frozen=True)
class Declares:
    confidence: str        # live, at_stop or none
    speakers: str          # live, at_stop or none
    second_transcript: bool

    def __post_init__(self):
        if self.confidence not in WHEN or self.speakers not in WHEN:
            raise ValueError("a declaration says live, at_stop or none")


@dataclass(frozen=True)
class Stamp:
    choice: str
    models: dict      # each model: its name and its revision or checksum
    versions: dict    # each library of the worker: its version


@dataclass(frozen=True)
class Live:
    """One live call: the lines made final, what was refused, the text not
    yet final, and any labels revised."""
    ok: bool
    fed_s: float
    stamp: Stamp | None
    lines: tuple[Line, ...] = ()
    refused: tuple[Refused, ...] = ()
    partial: str = ""
    failure: str | None = None
    detail: str | None = None
    revisions: tuple[Revision, ...] = ()


@dataclass(frozen=True)
class Final:
    """The pass at Stop: the turns, the last live lines (made final at
    Stop), what was refused, and every raw segment as it came. For a
    choice with one transcript, lines is every line already given plus the
    last ones, raw is empty, and speakers records the number given at open
    and at Stop."""
    ok: bool
    stamp: Stamp | None
    lines: tuple[Line, ...] = ()
    last_live: tuple[Line, ...] = ()
    refused: tuple[Refused, ...] = ()
    raw: tuple[dict, ...] = ()
    seconds: dict = field(default_factory=dict)
    failure: str | None = None
    detail: str | None = None
    revisions: tuple[Revision, ...] = ()
    speakers: dict = field(default_factory=dict)


def failed_live(failure: str, detail: str, fed_s: float, stamp: Stamp | None) -> Live:
    _check(failure)
    return Live(False, fed_s, stamp, failure=failure, detail=detail)


def failed_final(failure: str, detail: str, stamp: Stamp | None) -> Final:
    _check(failure)
    return Final(False, stamp, failure=failure, detail=detail)


def _check(failure: str) -> None:
    if failure not in FAILURES:
        raise ValueError(f"not a failure: {failure}")
