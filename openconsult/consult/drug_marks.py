"""The drug names the language model doubts (spec 15.9 rulings 18 and 39;
15.10 rulings 6, 20, 21, 23 and 26 to 28 and the details of steps 6c and
6d). A medicine name that speech recognition wrote wrongly is the error
most likely to harm. At Stop, after the gate, the model reads the final
transcript once, as the joined lines of joined.py, and points at the
names it doubts: the line and the words exactly as they stand. Code
keeps an entry only when its words stand on its line letter for letter.
Each kept entry is a mark, stored with the places its words stand in the
lines of the page. On the review page each mark is a row where the
doctor hears the name, types the right one over it and ticks it as
settled; only what the doctor types changes a line, by the function the
line's own box uses, and the note is then drafted again, never corrected
in place. The drug the model thinks was meant is stored and shown on no
page the doctor works on: no guess is ever shown (ruling 6). One
function checks the reply for the app and the bench (spec 5.1)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from openconsult import words
from openconsult.consult import joined
from openconsult.consult.consultations import Consultations
from openconsult.llm.door import Door, Result
from openconsult.patients.audit import Audit
from openconsult.prompts import loader
from openconsult.speech.matching import normalise

JOB = "drug_name"


def lines_text(lines: list[dict]) -> str:
    """The user text: the frame's heading, then one line for each joined
    line, its number in square brackets, a space and the words; no
    speaker. The frame's bytes are the label check's, so the words around
    the lines are those the bench sent."""
    numbered = "\n".join(f"[{line['n']}] {line['text']}" for line in lines)
    return loader.fill(loader.frame(JOB), transcript=numbered)


def check_doubtful(answer: dict | None, lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """The entries whose heard words stand on their line, letter for letter
    (and, listed beside, whether they stand there after the matching's
    normalisation), and the entries dropped (ruling 18)."""
    kept, dropped = [], []
    by_number = {line["n"]: line for line in lines}
    for entry in (answer or {}).get("doubtful", []):
        number, heard, meant = entry.get("line"), str(entry.get("heard", "")), str(entry.get("meant", ""))
        line = by_number.get(number) if isinstance(number, int) else None
        record = {"line": number, "heard": heard, "meant": meant}
        if line is None or not heard.strip():
            dropped.append({**record, "why": "no such line" if line is None else "nothing heard"})
            continue
        exact = heard in line["text"]
        normalised = _holds(normalise(line["text"]), normalise(heard))
        if exact:
            kept.append({**record, "normalised_too": normalised})
        else:
            dropped.append({**record, "why": "not on its line", "normalised_only": normalised})
    return kept, dropped


def _holds(words: list[str], part: list[str]) -> bool:
    return bool(part) and any(words[i:i + len(part)] == part for i in range(len(words) - len(part) + 1))


def occurrences_of(words: str, page_lines: list[int], text_of: dict[int, str]) -> list[list[dict]]:
    """Every place the words stand on a joined line, each as its pieces in
    the lines of the page it holds: {line, first, last}, the letters
    text[first:last] of that line. The joined line is its lines' words
    with one space between, so a place is on one line or runs over
    neighbours, one piece on each. A line left with no words holds no
    place. Empty when the words do not stand there letter for letter."""
    spans, held, at = [], [], 0
    for n in page_lines:
        raw = str(text_of[n])
        words_of_line = raw.strip()
        if not words_of_line:
            continue
        spans.append((n, at, at + len(words_of_line), len(raw) - len(raw.lstrip())))
        held.append(words_of_line)
        at += len(words_of_line) + 1
    whole = " ".join(held)
    found, start = [], whole.find(words) if words else -1
    while start >= 0:
        end = start + len(words)
        found.append([{"line": n, "first": max(start, first) - first + indent, "last": min(end, last) - first + indent}
                      for n, first, last, indent in spans if start < last and end > first])
        start = whole.find(words, end)
    return found


def places_of(words: str, page_lines: list[int], text_of: dict[int, str]) -> list[dict]:
    """Every piece of every place the words stand, in order."""
    return [piece for pieces in occurrences_of(words, page_lines, text_of) for piece in pieces]


def run(door: Door, rows: Consultations, audit: Audit, consultation_id: int) -> None:
    """The call at Stop: one call, the whole page as joined lines, no
    parts. A call that fails, or a page that does not fit, is kept with
    its reason and said plainly on the review page; nothing is asked
    again by itself, and no control asks again (10.4; R30)."""
    numbered = [r for r in rows.transcript_lines(consultation_id) if r["n"] is not None]
    lines = joined.of_rows(numbered)
    result: Result = door.ask(JOB, lines_text(lines), consultation_id=consultation_id)
    if not result.ok:
        reason = f"{result.failure}: {result.detail}"
        rows.add_drug_call(consultation_id, result.call_id, "failed", reason if reason.endswith(".") else reason + ".", 0, 0)
        audit.record("drug_names.checked", f"consultation {consultation_id}: failed: {result.failure}")
        return
    kept, dropped = check_doubtful(result.answer, lines)
    call = rows.add_drug_call(consultation_id, result.call_id, "answered", None, len(kept), len(dropped))
    text_of = {r["n"]: r["text"] for r in numbered}
    holds = {line["n"]: line["page_lines"] for line in lines}
    for entry in kept:
        page_lines = holds[entry["line"]]
        rows.add_drug_mark(consultation_id, call, entry["line"], entry["heard"], entry["meant"], page_lines,
                           places_of(entry["heard"], page_lines, text_of))
    audit.record("drug_names.checked", f"consultation {consultation_id}: {len(kept)} marked, {len(dropped)} dropped")


def after_edit(rows: Consultations, consultation_id: int, n: int, before: dict[int, str] | None = None, skip: int | None = None) -> int:
    """After the doctor edits the words of line n: a mark whose words, as
    they now stand, are still on its lines letter for letter is found
    again in the new words and keeps its state, settled or not; one whose
    words no longer stand there is cleared, and stays in the record with
    the time. A name whose words were taken out (ruling 40) has no words
    to find: it is never cleared, and the point they left moves with the
    letters around it (before: the words of each changed line as they
    stood). skip: the mark the correction itself has just placed. The call
    is never made again. The count of marks cleared."""
    text_of = {r["n"]: r["text"] for r in rows.transcript_lines(consultation_id) if r["n"] is not None}
    cleared = 0
    for mark in rows.drug_marks(consultation_id):
        if n not in mark["page_lines"] or mark["id"] == skip:
            continue
        if not mark["standing"]:
            rows.set_mark_places(mark["id"], [_moved(place, before or {}, text_of) for place in mark["places"]])
            continue
        places = places_of(mark["standing"], mark["page_lines"], text_of)
        if places:
            rows.set_mark_places(mark["id"], places)
        else:
            rows.clear_mark(mark["id"])
            cleared += 1
    return cleared


# ------------------------------------------- the doctor types the right name

def _put(text: str, first: int, last: int, typed: str) -> str:
    """The letters text[first:last] replaced by the typed words, or taken
    out: then one of the two spaces the piece leaves goes, and a space
    left at an end of the line goes. Where no letter stands there (first
    is last, the point a name that was taken out left) the typed words go
    in with one space each side where a word stands. No other letter
    changes."""
    left, right = text[:first], text[last:]
    if typed and first == last:
        return (left + (" " if left.strip() and not left.endswith(" ") else "") + typed
                + (" " if right.strip() and not right.startswith(" ") else "") + right)
    if typed:
        return left + typed + right
    if not left.strip():
        return right.lstrip()
    if not right.strip():
        return left.rstrip()
    return left + (right[1:] if left.endswith(" ") and right.startswith(" ") else right)


def _point(text: str, first: int, last: int) -> int:
    """Where the letters text[first:last] stood, in the line as _put leaves
    it when they are taken out: the point words typed back go in at."""
    left, right = text[:first], text[last:]
    if not left.strip():
        return 0
    return len(left.rstrip()) if not right.strip() else len(left)


def _boundary(text: str, at: int) -> int:
    """The point, moved on to the end of the word it stands in, if it
    stands in one: words typed back never land inside a word."""
    at = max(0, min(at, len(text)))
    while 0 < at < len(text) and not text[at - 1].isspace() and not text[at].isspace():
        at += 1
    return at


def point_after(at: int, before: str, now: str) -> int:
    """Where the point a taken-out name left stands after other letters
    of its line changed (ruling 40; the plan review of 6e, point 9). It
    keeps its place beside the letter that stood before it, where that
    letter still stands; else beside the letter that stood after it; and
    where the change went over both, it stands where the changed stretch
    ends. Never inside a word."""
    at = max(0, min(at, len(before)))
    same = [block for block in SequenceMatcher(None, before, now, autojunk=False).get_matching_blocks() if block.size]
    for a, b, size in same:
        if a < at <= a + size:
            return _boundary(now, b + at - a)
    for a, b, size in same:
        if a <= at < a + size:
            return _boundary(now, b + at - a)
    return _boundary(now, min([b for a, b, _ in same if a >= at], default=len(now)))


def _moved(place: dict, before: dict[int, str], text_of: dict[int, str]) -> dict:
    n = place["line"]
    now = str(text_of.get(n, ""))
    at = point_after(place["first"], str(before[n]), now) if n in before else _boundary(now, place["first"])
    return {"line": n, "first": at, "last": at}


def _corrected(typed: str, mark: dict, text_of: dict[int, str]) -> tuple[dict[int, str], list[dict]]:
    """The lines that change, {line: its new words}, and, when the words
    are taken out, the point each place leaves on its first line."""
    cuts: dict[int, list[tuple[int, int, bool]]] = {}       # by line: first, last, and whether the stretch takes the typed words
    if mark["standing"]:
        for pieces in occurrences_of(mark["standing"], mark["page_lines"], text_of):
            for k, piece in enumerate(pieces):
                cuts.setdefault(piece["line"], []).append((piece["first"], piece["last"], k == 0))
    else:
        for place in mark["places"]:
            if place["line"] in text_of:
                at = _boundary(str(text_of[place["line"]]), place["first"])
                cuts.setdefault(place["line"], []).append((at, at, True))
    changed, points = {}, []
    for n, line_cuts in cuts.items():
        text, moved = str(text_of[n]), 0
        for first, last, takes in sorted(line_cuts):
            first, last = first + moved, last + moved
            if takes and not typed:
                points.append({"line": n, "first": _point(text, first, last), "last": _point(text, first, last)})
            put = _put(text, first, last, typed if takes else "")
            text, moved = put, moved + len(put) - len(text)
        if text != text_of[n]:
            changed[n] = text
    return changed, points


def corrected(typed: str, mark: dict, text_of: dict[int, str]) -> dict[int, str]:
    """The lines that change when the doctor types over a mark's words as
    they stand, {line: its new words} (ruling 26; the details of step 6d:
    What the field changes). At every place the words stand, the typed
    words replace the piece on the first line and the pieces on the later
    lines are taken out. With no typed words every piece is taken out
    (ruling 40: a leftover piece of a drug name). Where the words were
    taken out before, typed words go back in at the point they left. No
    line is removed or given a new number, and no word that nobody spoke
    or typed is written into a line (15.9 ruling 1); a line can be left
    with no words."""
    return _corrected(typed, mark, text_of)[0]


def correct(rows: Consultations, audit: Audit, consultation_id: int, mark: dict, typed: str) -> list[int]:
    """The typed words into the lines, by the function the line's own box
    uses: for each line that changes one edit of the kind words with the
    words before, and the audit line, so Draft the note again is offered
    (ruling 11). The mark's words as they stand become the typed words and
    it is found where they now are; with no typed words they become empty
    and the mark keeps the point they left (ruling 40). Every other mark
    on those lines is found again or cleared, as after an edit in the
    line's box. The words heard and the drug the model named are never
    changed and never read. The lines changed."""
    text_of = {r["n"]: r["text"] for r in rows.transcript_lines(consultation_id) if r["n"] is not None}
    changed, points = _corrected(typed, mark, text_of)
    if not changed:
        raise RuntimeError("the mark's words do not stand on its lines")
    for n in sorted(changed):
        rows.set_line_words(consultation_id, n, changed[n])
        audit.record("transcript.edited", f"consultation {consultation_id}: line {n}")
    before = {n: text_of[n] for n in changed}
    text_of.update(changed)
    rows.set_mark_places(mark["id"], places_of(typed, mark["page_lines"], text_of) if typed else points, standing=typed)
    after_edit(rows, consultation_id, min(changed), before=before, skip=mark["id"])
    return sorted(changed)


# ------------------------------------------------ the marks on the review page

def spans_of(marks: list[dict]) -> dict[int, list[tuple[int, int]]]:
    """By line: the stretches of its letters that a standing mark doubts,
    in order, overlapping ones as one."""
    found: dict[int, list[tuple[int, int]]] = {}
    for mark in marks:
        for place in mark["places"]:
            found.setdefault(place["line"], []).append((place["first"], place["last"]))
    for n, spans in found.items():
        merged: list[tuple[int, int]] = []
        for first, last in sorted(spans):
            if merged and first <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], last))
            else:
                merged.append((first, last))
        found[n] = merged
    return found


def row_of(mark: dict, by_number: dict[int, dict]) -> dict:
    """The row of a doubted name (rulings 26 and 28; the plan review,
    points 2 and 6). The words of the lines the name was heard on, and of
    any other line of its joined line where its words now stand, as
    pieces: the words as they stand are the field at their first place,
    and every other place that would take the typed words is shown
    highlighted, so nothing on a line changes that the row did not show.
    Line {n} and the play stretch are read from the lines the name was
    heard on, never from typed words: the row can always play the whole
    name. Where the words were taken out (ruling 40) the field stands,
    empty, at the point they left. The drug the model named is never
    read here."""
    text_of = {n: line["text"] for n, line in by_number.items()}
    on = [place["line"] for place in mark["places"]]
    low, high = min([mark["heard_first"]] + on), max([mark["heard_last"]] + on)
    shown = [n for n in mark["page_lines"] if low <= n <= high and n in text_of]
    cuts: dict[int, list[tuple[int, int, str]]] = {}
    for k, pieces in enumerate(occurrences_of(mark["standing"], [n for n in mark["page_lines"] if n in text_of], text_of)):
        for j, piece in enumerate(pieces):
            kind = "later" if j else ("field" if k == 0 else "also")
            cuts.setdefault(piece["line"], []).append((piece["first"], piece["last"], kind))
    if not mark["standing"]:
        # A name whose words were taken out (ruling 40): the field, or the row's sentence, stands at the point they left.
        for k, place in enumerate(p for p in mark["places"] if p["line"] in text_of):
            cuts.setdefault(place["line"], []).append((place["first"], place["last"], "also" if k else "field"))
    segments: list[dict] = []
    for n in shown:
        text, at = str(text_of[n]).strip(), 0
        indent = len(str(text_of[n])) - len(str(text_of[n]).lstrip())
        if not text and n not in cuts:
            continue
        if segments:
            segments.append({"kind": "plain", "text": " "})
        for first, last, kind in sorted(cuts.get(n, [])):
            first, last = max(0, first - indent), max(0, last - indent)
            segments.append({"kind": "plain", "text": text[at:first]})
            if first == last:            # a point: a space each side where a word stands, as the line will have it
                segments.append({"kind": "plain", "text": " " if text[:first].strip() and not text[:first].endswith(" ") else ""})
            if kind != "later":          # a later piece of the same place is held in the field, which shows the whole words
                segments.append({"kind": kind, "text": mark["standing"]})
            if first == last:
                segments.append({"kind": "plain", "text": " " if text[last:].strip() and not text[last:].startswith(" ") else ""})
            at = last
        segments.append({"kind": "plain", "text": text[at:]})
    joined_up: list[dict] = []
    for segment in (s for s in segments if s["text"] or s["kind"] != "plain"):
        if joined_up and segment["kind"] == "plain" == joined_up[-1]["kind"]:
            # Where a later piece is held in the field, the space that joined the lines is in the field's words too.
            joined_up[-1]["text"] = re.sub(" {2,}", " ", joined_up[-1]["text"] + segment["text"])
        else:
            joined_up.append(dict(segment))
    first_line, last_line = by_number.get(mark["heard_first"]), by_number.get(mark["heard_last"])
    return {"id": mark["id"], "n": mark["heard_first"], "settled": mark["settled_at"] is not None, "standing": mark["standing"],
            "size": max(len(mark["standing"]), 4), "segments": joined_up,
            "start_s": first_line["start_s"] if first_line else None, "end_s": last_line["end_s"] if last_line else None}


def review_data(rows: Consultations, consultation_id: int, lines: list[dict]) -> dict:
    """What the review page shows of the marks, in their two places
    (rulings 20, 26, 27 and 28). The warnings: the sentences that head
    them, which are not counted; one row for each mark an edit has not
    cleared, settled or not, in the order the names were heard; or one
    warning for a call that failed. A mark that is not settled counts on
    Approve and none blocks it. On each line: the words a mark that is not
    settled doubts, and the line's words cut at them, for the line
    (segments) and for its turn in the reading view, where each doubted
    stretch is a press to its row (reading); a settled mark shows no
    highlight. No note entry carries a sign (ruling 27). Nothing when
    the call has not run (a consultation from before 6c, or a gate that
    refused). The drug the model named is never read here."""
    call = rows.drug_call(consultation_id)
    for line in lines:
        line["doubted"], line["segments"], line["reading"] = [], [(line["text"], False)], [(line["text"], None)]
    if call is None:
        return {"head": [], "rows": [], "marks": [], "open": 0}
    if call["outcome"] != "answered":
        failed = {"kind": "drug_names_failed", "start_s": None, "end_s": None, "line_n": None,
                  "text": words.DRUG_CHECK_FAILED.format(reason=call["reason"] or "")}
        return {"head": [], "rows": [failed], "marks": [], "open": 0}
    marks = rows.drug_marks(consultation_id)
    standing = [m for m in marks if m["settled_at"] is None]
    # A name whose words were taken out and which was opened again (ruling 40) has no words to highlight on its line.
    worded = [m for m in standing if m["standing"]]
    spans = spans_of(worded)
    # The mark whose row a doubted stretch leads to: the first heard of those that begin it (the reading view, step 6e).
    leads = {(place["line"], place["first"]): m["id"] for m in reversed(worded) for place in m["places"]}
    for line in lines:
        text, at, segments = line["text"], 0, []
        for first, last in spans.get(line["n"], []):
            segments += [(text[at:first], None), (text[first:last], leads[(line["n"], first)])]
            at = last
        line["reading"] = [s for s in segments + [(text[at:], None)] if s[0]]
        line["segments"] = [(piece, mark is not None) for piece, mark in line["reading"]]
        line["doubted"] = [{"piece": text[place["first"]:place["last"]], "mark": m["id"]}
                           for m in worded for place in m["places"] if place["line"] == line["n"]]
    counted = (words.DRUG_MARKED.format(count=len(marks)) if len(marks) > 1 else words.DRUG_MARKED_ONE if marks
               else words.DRUG_MARKED_NONE)
    by_number = {line["n"]: line for line in lines}
    return {"head": [counted, words.DRUG_NOT_PROVEN], "rows": [], "marks": [row_of(m, by_number) for m in marks],
            "open": len(standing)}
