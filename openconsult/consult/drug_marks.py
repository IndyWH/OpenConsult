"""The drug names the language model doubts (spec 15.9 rulings 18 and 39;
15.10 rulings 6, 20, 21 and 23 and the details of step 6c: The drug-name
call at Stop, A mark, When the doctor types over). A medicine name that
speech recognition wrote wrongly is the error most likely to harm. At
Stop, after the gate, the model reads the final transcript once, as the
joined lines of joined.py, and points at the names it doubts: the line
and the words exactly as they stand. Code keeps an entry only when its
words stand on its line letter for letter. Each kept entry is a mark,
stored with the places its words stand in the lines of the page. The
drug the model thinks was meant is stored and shown on no page the
doctor works on: no guess is ever shown (ruling 6). The words of the
transcript are never changed by a mark. One function checks the reply
for the app and the bench (spec 5.1)."""

from __future__ import annotations

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


def places_of(heard: str, page_lines: list[int], text_of: dict[int, str]) -> list[dict]:
    """Every place the heard words stand on a joined line, as places in the
    lines of the page it holds: {line, first, last}, the letters
    text[first:last] of that line. The joined line is its lines' words
    with one space between, so a place is on one line or runs over
    neighbours, one piece on each. Empty when the words do not stand
    there letter for letter."""
    spans, at = [], 0
    for n in page_lines:
        raw = str(text_of[n])
        words = raw.strip()
        spans.append((n, at, at + len(words), len(raw) - len(raw.lstrip())))
        at += len(words) + 1
    whole = " ".join(str(text_of[n]).strip() for n in page_lines)
    places, start = [], whole.find(heard) if heard else -1
    while start >= 0:
        end = start + len(heard)
        for n, first, last, indent in spans:
            if start < last and end > first:
                places.append({"line": n, "first": max(start, first) - first + indent, "last": min(end, last) - first + indent})
        start = whole.find(heard, end)
    return places


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


def after_edit(rows: Consultations, consultation_id: int, n: int) -> int:
    """After the doctor edits the words of line n: a mark whose words
    still stand on its lines letter for letter is found again in the new
    words; one whose words no longer stand there is cleared, and stays in
    the record with the time. The call is never made again. The count of
    marks cleared."""
    text_of = {r["n"]: r["text"] for r in rows.transcript_lines(consultation_id) if r["n"] is not None}
    cleared = 0
    for mark in rows.drug_marks(consultation_id):
        if n not in mark["page_lines"]:
            continue
        places = places_of(mark["heard"], mark["page_lines"], text_of)
        if places:
            rows.set_mark_places(mark["id"], places)
        else:
            rows.clear_mark(mark["id"])
            cleared += 1
    return cleared


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


def review_data(rows: Consultations, consultation_id: int, lines: list[dict], entries: list[dict]) -> dict:
    """What the review page shows of the marks, in their three places
    (ruling 20). On each line: the doubted words, and the line's words
    cut at them. The warnings: the sentences that head them, which are
    not counted, and one row for each mark that stands, or one for a call
    that failed; each row counts on Approve and none blocks it. On each
    note entry: the first line of every mark whose lines the entry cites,
    so the sign is set by the line and not by the word, and shows when
    the note wrote the name differently. Nothing when the call has not
    run (a consultation from before 6c, or a gate that refused). The drug
    the model named is never read here."""
    call = rows.drug_call(consultation_id)
    for line in lines:
        line["doubted"], line["segments"] = [], [(line["text"], False)]
    for entry in entries:
        entry["drug_signs"] = []
    if call is None:
        return {"head": [], "rows": []}
    if call["outcome"] != "answered":
        return {"head": [], "rows": [{"kind": "drug_names_failed", "start_s": None, "end_s": None, "line_n": None,
                                      "text": words.DRUG_CHECK_FAILED.format(reason=call["reason"] or "")}]}
    marks = rows.drug_marks(consultation_id)
    spans = spans_of(marks)
    for line in lines:
        text, at, segments = line["text"], 0, []
        for first, last in spans.get(line["n"], []):
            segments += [(text[at:first], False), (text[first:last], True)]
            at = last
        line["segments"] = [s for s in segments + [(text[at:], False)] if s[0]]
        line["doubted"] = [piece for piece, marked in line["segments"] if marked]
    for entry in entries:
        cited = set(entry["lines"])
        entry["drug_signs"] = sorted({m["first_line"] for m in marks if cited & {place["line"] for place in m["places"]}})
    counted = (words.DRUG_MARKED.format(count=len(marks)) if len(marks) > 1 else words.DRUG_MARKED_ONE if marks
               else words.DRUG_MARKED_NONE)
    return {"head": [counted, words.DRUG_NOT_PROVEN],
            "rows": [{"kind": "drug_mark", "start_s": None, "end_s": None, "line_n": m["first_line"],
                      "text": words.WARN_DRUG_MARK.format(n=m["first_line"], heard=m["heard"])} for m in marks]}
