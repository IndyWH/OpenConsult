"""The what-the-model-saw page (spec 15.12, rulings 11 and 28; 15.8 ruling
1; R2, R15, R20): one read-only page per final consultation, reached from
the review page and the patient's page, with the timeline at its head,
the averages per kind of call, the final line's figures, and every call in
time order, each opening to its parts by source and the reply word for
word. The readers and the figures are consult/seen.py and
consult/timeline.py; this file puts their results into sentences. GET
only: it writes no row and no audit line, and nothing on it acts, so it
has no script."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from openconsult import words
from openconsult.consult import seen as seen_module, timeline
from openconsult.web import guards
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import render
from openconsult.web.review import model_line_of, ran_with

router = APIRouter()


def kind_words(name: dict) -> str:
    """The call as the record names it, in words."""
    form = words.CALL_KINDS.get(name["kind"])
    if form is None:
        return words.CALL_UNKNOWN_KIND.format(job=name["kind"])
    if name.get("parts", 1) > 1:
        return words.CALL_CHECK_PART.format(n=name["part"], parts=name["parts"])
    return form.format(n=name.get("pass_n", name.get("n", "")), asked=words.CALL_ASKED_BY.get(name.get("asked_by", ""), ""),
                       specialty=name.get("specialty", ""))


def prompt_line(prompt: dict) -> str:
    if prompt["today"] == seen_module.SAME:
        return words.PROMPT_LINE_SAME.format(name=prompt["name"], hash=prompt["hash"])
    if prompt["today"] == seen_module.DIFFERS:
        return words.PROMPT_LINE_DIFFERS.format(name=prompt["name"], hash=prompt["hash"])
    return words.PROMPT_LINE_NONE.format(hash=prompt["hash"])


def passage_line(passage: dict) -> str:
    trail = words.PASSAGE_TRAIL.format(trail=passage["trail"]) if passage.get("trail") else ""
    similarity = passage.get("similarity")
    return words.PASSAGE_SENT.format(n=passage["n"], title=passage.get("title", ""), publisher=passage.get("publisher", ""),
                                     trail=trail, similarity=f"{similarity:.2f}" if isinstance(similarity, (int, float)) else "",
                                     cited=words.PASSAGE_CITED if passage.get("cited") else "")


def part_rows(found: seen_module.Seen) -> list[dict]:
    rows = []
    for part in found.parts:
        label = words.SOURCE_LABELS.get(part.source, part.source).format(file=part.file or "")
        rows.append({"source": part.source, "label": label, "text": part.text,
                     "sent": [passage_line(p) for p in part.items] if part.source == "passages" else []})
    return rows


def time_of(stamp: str) -> str:
    return f"{datetime.fromisoformat(stamp):%H:%M:%S}"


def call_row(found: seen_module.Seen) -> dict:
    call = found.call
    outcome = words.CALL_OUTCOMES.get(call["outcome"], call["outcome"])
    tokens = (words.CALL_TOKENS.format(read=call["prompt_tokens"], written=call["output_tokens"])
              if call["prompt_tokens"] is not None or call["output_tokens"] is not None else None)
    return {"id": call["id"], "kind": found.kind, "line": words.CALL_LINE.format(
                time=time_of(call["at"]), kind=kind_words(found.name), seconds=f"{call['wall_ms'] / 1000:.2f}", outcome=outcome),
            "model": words.LETTER_MODEL_LINE.format(model=call["model_tag"], engine=words.ENGINE_NAMES.get(call["engine"], call["engine"]),
                                                    version=call["engine_version"] or ""),
            "no_row": None if found.name["referenced"] else words.CALL_NO_ROW,
            "search": words.CALL_SEARCH_MS.format(ms=found.name["search_ms"]) if "search_ms" in found.name else None,
            "failure": words.CALL_FAILURE.format(detail=call["detail"]) if call["outcome"] != "ok" and call["detail"] else None,
            "tokens": tokens, "prompt": prompt_line(found.prompt), "parts": part_rows(found), "taken_apart": found.taken_apart,
            "not_taken_apart": None if found.taken_apart else words.NOT_TAKEN_APART.format(
                reason=words.NOT_TAKEN_APART_REASONS.get(found.reason, found.reason)),
            "whole": None if found.taken_apart else found.user_text,
            # The drug-name call (15.10 ruling 23): the named drug is left out and one line says so; a reply
            # that could not be read as its form is not shown at all.
            "answer_note": words.DRUG_NAMED_NOT_SHOWN if found.withheld == seen_module.NAMED_DRUG else None,
            "answer": (words.DRUG_REPLY_NOT_SHOWN if found.withheld == seen_module.UNREADABLE
                       else found.answer if found.answer is not None else words.NO_REPLY)}


def lead_words(lead: tuple[int, str]) -> str:
    n, unit = lead
    one, many = words.LEAD_WORDS[unit]
    return one if n == 1 else many.format(n=n)


def band_rows(found: dict) -> dict:
    """The band's figures put into words: the rows named, the passes'
    labels, the averages' lines, the after-final lines, the final line."""
    kind = words.KIND_WORDS
    averages = [words.AVERAGE_LINE.format(kind=kind.get(a["kind"], a["kind"]), count=a["count"], mean=a["mean_s"], slowest=a["slowest_s"],
                                          failed=words.AVERAGE_FAILED.format(failed=a["failed"]) if a["failed"] else "")
                for a in found["averages"]]
    after = [words.AFTER_FINAL_LINE.format(kind=kind.get(a["kind"], a["kind"]), when=time_of(a["at"]), lead=lead_words(a["lead"]))
             for a in found["after_final"]]
    passes = [{**p, "label": words.TIMELINE_PASS.format(n=p["n"]) + (", " + words.TIMELINE_LONG.format(seconds=p["seconds"]) if p["long"] else "")}
              for p in found["passes"]]
    typical = (words.TIMELINE_TYPICAL.format(seconds=found["typical_pass_s"]) if found["typical_pass_s"] is not None else words.TIMELINE_NO_PASS)
    if found["long_passes"]:
        typical += " " + words.TIMELINE_LONG_PASSES.format(passes=", ".join(words.TIMELINE_PASS.format(n=n) for n in found["long_passes"]))
    return {**found, "row_names": [(k, kind.get(k, k)) for k in found["rows"]], "passes": passes, "typical": typical,
            "length": words.TIMELINE_LENGTH.format(seconds=found["length_s"]), "average_lines": averages, "after_lines": after,
            "final": words.FINAL_FIGURES.format(line=found["final_line"]) if found["final_line"] else words.FINAL_FIGURES_NONE}


def page_data(p, row: dict) -> dict:
    cid = row["id"]
    found = seen_module.calls_of(p.consultations, p.notes, p.letters, p.sources, cid)
    band = timeline.band(row, [f.call for f in found], p.consultations.passes(cid), p.audit.lines())
    return {"cid": cid, "patient": p.patients.get(row["patient_id"]), "ran_with": ran_with(p, row),
            "date": words.plain_date(datetime.fromisoformat(row["started_at"])), "model_line": model_line_of(row),
            "band": band_rows(band), "calls": [call_row(f) for f in found]}


@router.get("/consultations/{consultation_id}/calls")
async def calls_page(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """The view, for a final consultation; a live or stopping one is read
    after it ends (ruling 28), so its address leads back to its page."""
    p = parts(request)
    row = p.consultations.get(consultation_id)
    if row is None:
        raise Redirect("/")
    if row["state"] != "final":
        raise Redirect(f"/consultations/{consultation_id}")
    return render(request, "calls.html", user=user, active="new_patient", page_path=f"/consultations/{consultation_id}/calls",
                  **page_data(p, row))
