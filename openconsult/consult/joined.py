"""The lines a model reads, and a long page in parts (spec 15.10, the
details of step 6c: The lines a model reads, A page in parts; 15.9
ruling 37). One rule for the app and the bench (spec 5.1). The speech
choices cut a page very differently, so the label check and the
drug-name call read lines made by one rule from the page's pieces: two
neighbours join when the first does not end a sentence, both carry the
same speaker from the speech choice, and less than a second lies
between them. A piece is never split, and no word is changed, added or
lost. A page too long for one reply is cut into parts, each a call of
its own; the labels are taken from every part or from none."""

from __future__ import annotations

import math

SENTENCE_END = (".", "?", "!")
# Two neighbouring pieces are joined when less than this lies between them.
JOIN_GAP_S = 1.0
# The longest page the bench of 5e read whole had 160 joined lines, its reply 2,139 tokens of the 3,000.
WHOLE_LINES = 160
# A line of the reply is about 13 tokens, so 120 new lines and the overlap are about 1,700 of the 3,000.
PART_LINES = 120
# A later part begins with these last lines of the part before, so the model never meets a part's first lines bare.
OVERLAP_LINES = 10


def ends_sentence(text: str) -> bool:
    stripped = text.rstrip()
    return bool(stripped) and stripped[-1] in SENTENCE_END


def lines_of(pieces: list[dict]) -> list[dict]:
    """Lines {n, speaker, start, end, text, pieces} from the smallest timed
    pieces {start, end, text, speaker}, numbered from 1. Two neighbours join
    when the first does not end a sentence, both carry the same label (two
    with no speaker carry the same label), and less than JOIN_GAP_S lies
    between them."""
    lines: list[dict] = []
    for index, piece in enumerate(pieces):
        text = str(piece["text"]).strip()
        if not text:
            continue
        last = lines[-1] if lines else None
        joins = (last is not None and not ends_sentence(last["text"]) and last["speaker"] == piece.get("speaker")
                 and float(piece["start"]) - last["end"] < JOIN_GAP_S)
        if joins:
            last["text"] += " " + text
            last["end"] = max(last["end"], float(piece["end"]))
            last["pieces"].append(index)
        else:
            lines.append({"n": len(lines) + 1, "speaker": piece.get("speaker"), "start": float(piece["start"]),
                          "end": float(piece["end"]), "text": text, "pieces": [index]})
    return lines


def of_rows(rows: list[dict]) -> list[dict]:
    """The joined lines of a consultation: its numbered lines as they stand,
    in order, each a piece with the speaker the speech choice gave. Each
    joined line remembers the lines of the page it holds (page_lines)."""
    numbered = [row for row in rows if row.get("n") is not None]
    lines = lines_of([{"start": row["start_s"], "end": row["end_s"], "text": row["text"], "speaker": row.get("raw_speaker")}
                      for row in numbered])
    for line in lines:
        line["page_lines"] = [numbered[index]["n"] for index in line["pieces"]]
    return lines


def unjoined(lines: list[dict], rows: list[dict]) -> list[dict]:
    """The joined lines cut back into the page's lines, {n, text}, by the
    length of each line's own words: what the proof that no word changed
    hashes beside the rows themselves (labels.texts_hash)."""
    text_of = {row["n"]: str(row["text"]).strip() for row in rows if row.get("n") is not None}
    found = []
    for line in lines:
        at = 0
        for n in line["page_lines"]:
            found.append({"n": n, "text": line["text"][at:at + len(text_of[n])]})
            at += len(text_of[n]) + 1
    return found


def cut(lines: list[dict], whole: int = WHOLE_LINES, part: int = PART_LINES, overlap: int = OVERLAP_LINES) -> list[dict]:
    """The page as the calls it takes: one part when it has no more than
    `whole` lines; otherwise the fewest parts of equal size, give or take
    one line, with at most `part` new lines each. Each part after the
    first begins with the last `overlap` lines of the part before. A part
    is {k, lines, overlap}: its lines in order, the first `overlap` of
    them carried from the part before."""
    if len(lines) <= whole:
        return [{"k": 1, "lines": list(lines), "overlap": 0}]
    count = math.ceil(len(lines) / part)
    size, longer = divmod(len(lines), count)
    parts, first = [], 0
    for k in range(count):
        new = size + (1 if k < longer else 0)
        carried = min(overlap, first)
        parts.append({"k": k + 1, "lines": lines[first - carried:first + new], "overlap": carried})
        first += new
    return parts


def numbered(part: dict) -> list[dict]:
    """A part's lines as the model reads them: numbered from 1."""
    return [{"n": i, "text": line["text"]} for i, line in enumerate(part["lines"], start=1)]


def merge(parts: list[dict], labels: list[dict[int, str] | None]) -> dict[int, str] | None:
    """The label of every joined line, by its number, from the labels each
    part's reply gave by the part's own numbers. A carried line keeps the
    label of the part before, never the later part's. All or nothing: one
    part with no labels, and no label is taken from any."""
    if len(labels) != len(parts) or any(found is None for found in labels):
        return None
    merged: dict[int, str] = {}
    for part, found in zip(parts, labels):
        for i, line in enumerate(part["lines"], start=1):
            if i > part["overlap"]:
                merged[line["n"]] = found[i]
    return merged
