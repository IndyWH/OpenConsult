"""The wait (spec 13.3 mark 5), how exact a choice's times are (ruling
12), and the count of the signs of the check for missing speech, from a
stored result. The clock of a result is the clock of the feed: a piece is
fed when its sound has ended, so a line's wait is the moment it arrived
minus the end of its own sound."""

from __future__ import annotations

import statistics

from openconsult.bench.speech.marks import _window
from openconsult.bench.speech.pages import Page
from openconsult.bench.speech.reference import Reference
from openconsult.speech.matching import align, normalise

SHOWN_WORDS = 2       # a line has shown when its first two words are in the text not yet final


def _holds(partial: str, words: list[str]) -> bool:
    tokens = normalise(partial)
    return any(tokens[i:i + len(words)] == words for i in range(len(tokens) - len(words) + 1))


def first_shown(pieces: list[dict], arrived_at: int, words: list[str]) -> float | None:
    """The moment the line's first words showed in the text not yet
    final: the earliest stored piece, back from the one before it
    arrived, whose partial holds them; None when they never showed."""
    shown = None
    for piece in sorted((p for p in pieces if p["n"] < arrived_at), key=lambda p: -p["n"]):
        if not _holds(piece["partial"], words):
            break
        shown = piece["t"]
    return shown


def live_lines(result: dict) -> list[dict]:
    """Every live line with the moment it was final."""
    found = []
    for piece in result["pieces"]:
        for line in piece["lines"]:
            found.append({**line, "t": piece["t"], "n": piece["n"]})
    stop = result["stop"]
    if stop:
        last = max((p["n"] for p in result["pieces"]), default=0) + 1
        found += [{**line, "t": stop["t"], "n": last} for line in stop["last_live"]]
    return found


def _speech_of_line(line_words: list[str], live_page: Page | None, reference: Reference, offset: int) -> int | None:
    if live_page is None:
        return None
    for k in range(len(line_words)):
        spoken = live_page.spoken_of.get(offset + k)
        if spoken is not None and live_page.kind_of.get(offset + k) == "heard":
            return reference.words[spoken].speech
    return None


def waits(result: dict, reference: Reference, live_page: Page | None = None,
          true_times: dict[int, tuple[float, float]] | None = None) -> dict:
    """For each live line: from the end of its sound, by the choice's own
    time, to the moment its first words showed and to the moment it was
    final; on the made recording also from the true end of its speech."""
    rows, offset = [], 0
    for line in live_lines(result):
        words = normalise(line["text"], reference.joinable)
        shown = first_shown(result["pieces"], line["n"], words[:SHOWN_WORDS]) if words else None
        row = {"text": line["text"], "start": line["start"], "end": line["end"], "t_final": line["t"],
               "to_final": round(line["t"] - line["end"], 3), "t_first": shown,
               "to_first": round(shown - line["end"], 3) if shown is not None else None}
        speech = _speech_of_line(words, live_page, reference, offset)
        offset += len(words)
        if speech is not None and true_times and speech in true_times:
            true_end = true_times[speech][1]
            row.update(speech=speech, to_final_true=round(line["t"] - true_end, 3),
                       to_first_true=round(shown - true_end, 3) if shown is not None else None)
        rows.append(row)
    return {"lines": rows, "to_final": _typical([r["to_final"] for r in rows]),
            "to_first": _typical([r["to_first"] for r in rows if r["to_first"] is not None]),
            "never_shown": sum(1 for r in rows if r["to_first"] is None),
            "to_final_true": _typical([r["to_final_true"] for r in rows if "to_final_true" in r])}


def _typical(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "longest": None}
    return {"n": len(values), "median": round(statistics.median(values), 3), "longest": round(max(values), 3)}


def speech_spans(page: Page, reference: Reference) -> dict[int, tuple[float, float]]:
    """For each speech, the start of the first piece and the end of the
    last piece holding one of its heard words."""
    spans: dict[int, list[float]] = {}
    for word in page.heard_indexes():
        speech = reference.words[page.spoken_of[word]].speech
        piece = page.pieces[page.word_piece[word]]
        span = spans.setdefault(speech, [piece["start"], piece["end"]])
        span[0], span[1] = min(span[0], piece["start"]), max(span[1], piece["end"])
    return {n: (s, e) for n, (s, e) in spans.items()}


def exactness_made(page: Page, reference: Reference, true_times: dict[int, tuple[float, float]], slack_s: float) -> dict:
    """On the made recording: each speech's first line start and last line
    end against the true start and end."""
    rows = []
    for speech, (start, end) in sorted(speech_spans(page, reference).items()):
        if speech in true_times:
            t_start, t_end = true_times[speech]
            rows.append({"speech": speech, "start_off": round(start - t_start, 3), "end_off": round(end - t_end, 3)})
    return _exactness_summary(rows, slack_s)


def word_times_from_whisperx(result: dict, reference: Reference) -> dict[int, tuple[float, float]]:
    """The time WhisperX gives each heard reference word at Stop, from the
    aligned words of its raw segments: the measure for the other arms on
    an old recording, which has no true times."""
    tokens, times = [], []
    for segment in result["stop"]["raw"]:
        if segment.get("refused"):
            continue
        for word in segment.get("words") or []:
            norm = normalise(str(word.get("word", "")), reference.joinable)
            if len(norm) == 1 and "start" in word and "end" in word:
                tokens.append(norm[0])
                times.append((float(word["start"]), float(word["end"])))
    return {p.spoken: times[p.page] for p in align(reference.norms, tokens) if p.kind == "heard"}


def exactness_old(page: Page, reference: Reference, word_times: dict[int, tuple[float, float]], slack_s: float) -> dict:
    """On an old recording: each piece's start and end against WhisperX's
    time for its first and last heard word."""
    rows = []
    for index, piece in enumerate(page.pieces):
        heard = [w for w in page.heard_indexes() if page.word_piece[w] == index and page.spoken_of[w] in word_times]
        if not heard:
            continue
        first, last = word_times[page.spoken_of[heard[0]]], word_times[page.spoken_of[heard[-1]]]
        rows.append({"piece": index, "start_off": round(piece["start"] - first[0], 3), "end_off": round(piece["end"] - last[1], 3)})
    return _exactness_summary(rows, slack_s)


def _exactness_summary(rows: list[dict], slack_s: float) -> dict:
    offsets = [abs(r["start_off"]) for r in rows] + [abs(r["end_off"]) for r in rows]
    return {"rows": rows, "n": len(rows), "median_abs": round(statistics.median(offsets), 3) if offsets else None,
            "largest_abs": round(max(offsets), 3) if offsets else None,
            "beyond_figure": sum(1 for o in offsets if o > slack_s), "figure_s": slack_s}


def missing_runs(page: Page, reference: Reference, agreed: set[int], least: int = 3) -> list[list[int]]:
    runs, run = [], []
    for index in range(len(reference.words) + 1):
        at = page.at_spoken.get(index)
        if index < len(reference.words) and index not in agreed and (at is None or page.kind_of[at] == "missing"):
            run.append(index)
            continue
        if len(run) >= least:
            runs.append(run)
        run = []
    return runs


def signs_counted(page: Page, reference: Reference, agreed: set[int], gaps, live_page: Page | None,
                  stretches, end_s: float) -> dict:
    """Signs that were right (over a run of three or more missing words)
    and signs that were false, for a page."""
    runs = missing_runs(page, reference, agreed)
    windows = [_window(page, run[0], run[-1], len(reference.words), end_s)[:2] for run in runs]
    right = false = 0
    for gap in gaps:
        words = range(gap.first_live_word, gap.first_live_word + len(gap.words))
        hit = live_page is not None and any(live_page.spoken_of.get(w) in {i for run in runs for i in run} for w in words)
        right, false = right + hit, false + (not hit)
    for stretch in stretches:
        hit = any(stretch.start_s < end and stretch.end_s > start for start, end in windows)
        right, false = right + hit, false + (not hit)
    return {"right": right, "false": false, "missing_runs": len(runs)}
