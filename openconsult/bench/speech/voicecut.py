"""The doctor's voice, cut from a recording itself (spec 15.9, ruling 33;
the details of 5e). From the page of WhisperX at Stop, with the times of
its aligned words: only stretches where the page matches the script word
for word through at least eight words of one speech of the doctor, and no
stretch nearer than half a second to a word of the patient. The script
says who speaks; no model's label is read. The stretches are taken in the
order spoken until they hold about a minute. The file is a voice alone:
learnt from, never replayed as a consultation, and never used on the
recording it was cut from. What is kept of a cut is times and counts,
never a word."""

from __future__ import annotations

import io
import wave

from openconsult.bench.speech.reference import Reference
from openconsult.speech.matching import align, normalise

LEAST_WORDS = 8          # words in a row, matched, inside one speech of the doctor
CLEAR_S = 0.5            # no word of the patient nearer than this
WANTED_S = 60.0          # about a minute
THIN_S = 30.0            # a voice shorter than this is said first in the report
EDGE_SILENCE_S = 1.0     # digital silence at each end, as the minute of part two had


def timed_tokens(result: dict, reference: Reference) -> list[dict]:
    """Every word of the page at Stop as the matching reads it, with the
    time WhisperX gave it; a word it gave no time has none."""
    tokens = []
    for segment in result["stop"]["raw"]:
        if segment.get("refused"):
            continue
        for word in segment.get("words") or []:
            timed = "start" in word and "end" in word
            for norm in normalise(str(word.get("word", "")), reference.joinable):
                tokens.append({"norm": norm, "start": float(word["start"]) if timed else None,
                               "end": float(word["end"]) if timed else None})
    return tokens


def stretches_of(tokens: list[dict], reference: Reference) -> list[dict]:
    """The stretches of the rule, in the order spoken."""
    pairs = [p for p in align(reference.norms, [t["norm"] for t in tokens]) if p.page is not None]
    pairs.sort(key=lambda p: p.page)
    # A word of the patient: a page word standing at a patient's word of the script, or standing where nothing
    # was spoken (it cannot be shown to be the doctor's, so it is kept away from as a patient's would be).
    others = [tokens[p.page] for p in pairs
              if tokens[p.page]["start"] is not None
              and (p.kind == "nowhere" or reference.words[p.spoken].speaker != "DOCTOR")]
    runs, run = [], []

    def close() -> None:
        if len(run) >= LEAST_WORDS:
            runs.append(list(run))
        run.clear()

    for pair in pairs:
        token = tokens[pair.page]
        matched = (pair.kind == "heard" and token["start"] is not None
                   and reference.words[pair.spoken].speaker == "DOCTOR")
        follows = bool(run) and pair.page == run[-1].page + 1 and pair.spoken == run[-1].spoken + 1 \
            and reference.words[pair.spoken].speech == reference.words[run[-1].spoken].speech
        if not matched or not follows:
            close()
        if matched:
            run.append(pair)
    close()
    found = []
    for run in runs:
        start, end = tokens[run[0].page]["start"], tokens[run[-1].page]["end"]
        near = any(other["end"] > start - CLEAR_S and other["start"] < end + CLEAR_S for other in others)
        if not near and end > start:
            found.append({"speech": reference.words[run[0].spoken].speech, "words": len(run),
                          "start": round(start, 3), "end": round(end, 3)})
    return found


def taken(stretches: list[dict], wanted_s: float = WANTED_S) -> list[dict]:
    """In the order spoken, until they hold wanted_s."""
    kept, held = [], 0.0
    for stretch in stretches:
        if held >= wanted_s:
            break
        kept.append(stretch)
        held += stretch["end"] - stretch["start"]
    return kept


def cut(pcm: bytes, rate: int, stretches: list[dict]) -> bytes:
    """The stretches' own samples, untouched, one after another, with
    digital silence at each end; as the bytes of a WAV file."""
    edge = b"\0\0" * int(rate * EDGE_SILENCE_S)
    body = b"".join(pcm[2 * int(round(s["start"] * rate)): 2 * int(round(s["end"] * rate))] for s in stretches)
    held = io.BytesIO()
    with wave.open(held, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(int(rate))
        out.writeframes(edge + body + edge)
    return held.getvalue()


def seconds_of(stretches: list[dict]) -> float:
    return round(sum(s["end"] - s["start"] for s in stretches), 3)
