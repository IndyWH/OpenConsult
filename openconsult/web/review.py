"""The review page (spec 15.10, rulings 4, 8, 11 and 12; R2, R4, R15,
R20), in the busy GP's order: the draft note first, each entry's line
numbers a press that shows the line, the model's last differentials
beside the assessment under a heading that says they are not part of
the note; Approve and Refuse, the Approve control carrying the count of
warnings; the warnings; the transcript with the player; the model line.
Built from the tables always, so a consultation opened after a restart
shows the same page. Draft the note for a final consultation that has
none; draft again after an edit, never by itself. The copy text is served
as plain text so that a test proves it holds the note alone."""

from __future__ import annotations

from datetime import datetime

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, PlainTextResponse

from openconsult import words
from openconsult.consult import alarms, deletion, drug_marks, gate, note, reading, who_check, whole
from openconsult.consult.recording import folder_of
from openconsult.consult.consultations import LABELS
from openconsult.consult.gate import LOW_CONFIDENCE
from openconsult.settings.path import path_of
from openconsult.settings.statement import mark_lines
from openconsult.speech.choices import CHOICES
from openconsult.speech.loudness import WINDOW_S
from openconsult.web import guards
from openconsult.web import letters as letters_web
from openconsult.web.guards import Redirect, parts
from openconsult.web.pages import form_fields, refuse, render

router = APIRouter()
GATE_REFUSALS = gate.REFUSALS
# A check of who spoke that failed or was refused at Stop before 6c: said at the control from its run, not among the warnings.
CHECK_KINDS = ("label_check_refused", "label_check_failed")
# The sentences the page scripts render, handed as data (15.6).
SCRIPT_WORDS = ("COPIED", "COPY_FAILED", "AUDIO_NOT_SUPPORTED", "ALARM_FIRED", "CLOSE", "NAME_NOT_SAVED", "NOT_SAVED_NO_ANSWER",
                "NOT_SAVED_ERROR", "OPEN_ALL_LINES", "CLOSE_ALL_LINES", "TURN_NOT_SAVED")
# A press that plays a line or a row starts this long before the line, and ends where it ended (15.10 ruling 38: in
# the room check of 15 Nov 2026 the sound of a row began late, and at one row the drug's name was gone).
PLAY_LEAD_S = 1.0
# The check of who spoke comes back at its own place, the top of the transcript: the press, each wait and the end.
CHECK_PLACE = "transcript"
# The loudness strip is drawn in this many columns, each the loudest of its windows.
STRIP_COLUMNS = 400


def strip_of(windows: list, columns: int = STRIP_COLUMNS) -> list:
    """The loudness strip (8.8): the stored windows folded into columns,
    each the loudest window in it, None where every window is silence."""
    if not windows:
        return []
    columns = min(columns, len(windows))
    found = []
    for k in range(columns):
        first, last = k * len(windows) // columns, max((k + 1) * len(windows) // columns, k * len(windows) // columns + 1)
        levels = [w for w in windows[first:last] if w is not None]
        found.append(max(levels) if levels else None)
    return found


def player_data(row: dict, lines: list[dict], warnings: list[dict], data_folder) -> dict:
    """What the player script reads (D51; V1_LESSONS 5.2): whether the file
    is there, the length, each line's times, the strip, and the warnings'
    stretches, all computed here and run by tests. And the name of the
    file the page is shown with: the review page is shown before the WAV
    is converted, so the script must be able to tell that the recording
    has changed under the player (the mend run of step 6d, fault one)."""
    windows = json.loads(row["loudness"] or "[]")
    file_there = bool(row["recording_file"]) and (folder_of(data_folder) / row["recording_file"]).is_file()
    return {"available": file_there, "file": row["recording_file"] if file_there else None,
            "length_s": round(len(windows) * WINDOW_S, 1),
            "lines": [{"n": line["n"], "start_s": line["start_s"], "end_s": line["end_s"]} for line in lines],
            "strip": strip_of(windows), "window_s": WINDOW_S,
            "stretches": [{"kind": w["kind"], "start_s": w["start_s"], "end_s": w["end_s"]} for w in warnings
                          if w["start_s"] is not None and w["end_s"] is not None]}


def press_start(start_s: float | None) -> float | None:
    """Where a press that plays a line or a row starts: one second before
    the line's own start, never before the start of the recording."""
    return None if start_s is None else max(0.0, round(start_s - PLAY_LEAD_S, 3))


def turns_of(lines: list[dict]) -> list[dict]:
    """The transcript as the reading view shows it (15.10 rulings 35 and
    42): one entry for each turn of speech by the one rule of
    reading.py, with the numbers of its first and last line and the
    stretch its one press plays (rulings 29 and 38): from one second
    before its first line's start to the latest end among its lines,
    for lines can overlap. Never a sum of its lines' lengths: lines of
    one word are 0.08 to 0.24 s long by the speech choice's times, and a
    turn must not be cut short by them. It is how the page is shown:
    nothing of it is stored."""
    found = []
    for entry in reading.entries_of(lines):
        held = entry["lines"]
        ends = [line["end_s"] for line in held if line["end_s"] is not None]
        found.append({"first": held[0]["n"], "last": held[-1]["n"], "speaker": entry["speaker"], "lines": held,
                      "play_s": press_start(held[0]["start_s"]), "end_s": max(ends) if ends else None})
    return found


def script_words() -> dict:
    return {name: getattr(words, name) for name in SCRIPT_WORDS}


def final_row(request: Request, consultation_id: int) -> dict:
    row = parts(request).consultations.get(consultation_id)
    if row is None or row["state"] != "final":
        raise Redirect("/")
    return row


def warning_lines(rows: list[dict], lines: list[dict], choice_title: str) -> list[dict]:
    """Each stored warning as its sentence (ruling 8), and one for each
    label the check changed (ruling 7), each with its place for the
    player: a stretch, a line, or none."""
    found = []
    for w in rows:
        kind, detail = w["kind"], w["detail"] or ""
        if kind == "speech_failed":
            text = words.WARN_SPEECH_FAILED.format(reason=detail) if detail != words.APP_RESTARTED else detail
        elif kind in CHECK_KINDS or kind == whole.MADE:
            continue            # the check's own lines stand at its control; a better transcript made is no warning: it stands with the details
        else:
            text = words.WARNING_SENTENCES.get(kind, "{detail}").format(
                start=w["start_s"], end=w["end_s"], n=w["line_n"], detail=detail, words=detail, score=detail, choice=choice_title)
        found.append({"kind": kind, "text": text, "start_s": w["start_s"], "end_s": w["end_s"], "line_n": w["line_n"]})
    for line in lines:
        if line["changed_by_check"]:
            found.append({"kind": "label_changed", "line_n": line["n"], "start_s": None, "end_s": None,
                          "text": words.WARN_LABEL_CHANGED.format(n=line["n"], label=words.LABEL_WORDS[line["label"]])})
    return found


def background_read(row: dict) -> bool:
    """The mark of 8.5 at review: the switch was on and notes were listed
    at Start, so the two calls of every pass read them (15.11 ruling 3)."""
    return bool(row["earlier_notes_shown"]) and json.loads(row["earlier_notes"] or "[]") != []


def model_line_of(row: dict) -> str:
    """R20: from the row's stamps, not the running engine, so it is true after a restart."""
    choice = CHOICES.get(row["speech_choice"])
    return words.MODEL_LINE.format(speech=choice.title if choice else row["speech_choice"], model=row["model_tag"],
                                   engine=words.ENGINE_NAMES.get(row["engine"], row["engine"]), version=row["engine_version"] or "")


def _when(stamp: str) -> tuple[str, str]:
    when = datetime.fromisoformat(stamp)
    return words.plain_date(when), f"{when:%H:%M}"


def note_state(p, row: dict, gate_refused: bool) -> dict:
    """What the page shows of the note and which controls can act (R15):
    the draft on the page, its entries by section, the approval, the
    doctor's refusal, and the reason for each control that cannot act."""
    cid = row["id"]
    drafts = p.notes.drafts(cid)
    draft = drafts[-1] if drafts else None
    approval = p.notes.approval(cid)
    refused_by_doctor = bool(draft and any(r["draft_id"] == draft["id"] for r in p.notes.refusals(cid)))
    entries = p.notes.entries(draft["id"]) if draft else []
    has_note = bool(draft and not draft["refused"] and not draft["failure"])
    later_edit = draft is not None and (p.consultations.last_edit_id(cid) or 0) > (draft["last_edit_id"] or 0)
    # Ruling 18: the check, or an Undo of its change, later than the draft on the page. The note is never touched
    # or drafted again by itself: the page says so above it, and Draft the note again is offered as after any edit.
    speakers_changed = has_note and any(e["kind"] in ("check", "undo") and e["id"] > (draft["last_edit_id"] or 0)
                                        for e in p.consultations.transcript_edits(cid))
    if approval:
        draft_reason = words.NOTE_READ_ONLY
    elif gate_refused:
        draft_reason = words.NOTE_GATE_REFUSED.format(reason="")
    elif has_note and not later_edit:
        draft_reason = words.DRAFT_AGAIN_NEEDS_EDIT      # a note stands: draft again waits for an edit (ruling 11)
    else:
        draft_reason = None
    if approval:
        approve_reason = words.ALREADY_APPROVED
    elif not has_note or refused_by_doctor:
        approve_reason = words.NOTHING_TO_APPROVE
    else:
        approve_reason = None
    refuse_reason = (words.ALREADY_APPROVED if approval else words.ALREADY_REFUSED if refused_by_doctor
                     else words.NOTHING_TO_APPROVE if not has_note else None)
    return {"draft": draft, "entries": entries, "sections": {s: [e for e in entries if e["section"] == s] for s in note.SECTIONS},
            "approval": approval, "refused_by_doctor": refused_by_doctor, "has_note": has_note, "speakers_changed": speakers_changed,
            "earlier": len(drafts) - 1 if drafts else 0,
            # After Approve the whole page is read-only; after Refuse the entries are, the transcript is not.
            "entries_read_only": bool(approval or refused_by_doctor), "transcript_read_only": bool(approval),
            "entries_reason": words.NOTE_READ_ONLY if approval else words.NOTE_NOT_EDITABLE if refused_by_doctor else None,
            "draft_control": words.DRAFT_AGAIN if has_note else words.DRAFT_THE_NOTE, "draft_reason": draft_reason,
            "approve_reason": approve_reason, "refuse_reason": refuse_reason, "asked_by": "again" if draft is not None else "draft"}


def ran_with(p, row: dict) -> dict:
    """The three details the consultation ran with, from its own row, never
    a join back to the patient (ruling 2); and the one line, with the date,
    when the patient's details were corrected after it started."""
    born = datetime.fromisoformat(row["patient_date_of_birth"]).date() if row["patient_date_of_birth"] else None
    changed = p.patients.changed_after(row["patient_id"], row["started_at"])
    return {"name": row["patient_name"], "born": words.plain_date(born) if born else "",
            "sex": words.SEX_WORDS.get(row["patient_sex"], ""),
            "corrected": words.DETAILS_CORRECTED.format(date=words.plain_date(datetime.fromisoformat(changed))) if changed else None}


def sent_lines(p, row: dict) -> tuple[tuple[str, ...], str | None]:
    """For a consultation whose recording was sent after Stop: the mark's
    third line in the past, where the one press after a lost connection
    sent it (the tick's own line stands in the mark already); and the
    sentence that the final transcript is the service's, with the delete
    as it was proven."""
    sent = p.consultations.upload(row["id"])
    if sent is None:
        return (), None
    past = (words.CLOUD_MARK_RECORDING_SENT,) if sent["way"] == whole.PRESS and sent["job_id"] else ()
    if sent["result_at"] is None:
        return past, None
    return past, words.UPLOAD_MADE if sent["gone"] else words.UPLOAD_MADE_ONLY


def page_data(p, row: dict) -> dict:
    cid = row["id"]
    lines = [r for r in p.consultations.transcript_lines(cid) if r["n"] is not None]
    for line in lines:
        score = line.get("confidence")
        line["low_confidence"] = (words.LOW_CONFIDENCE_MARK.format(score=f"{score:.2f}")
                                  if score is not None and score < LOW_CONFIDENCE else None)
    warning_rows = p.consultations.warnings(cid)
    gate_refused = any(w["kind"] in GATE_REFUSALS for w in warning_rows)
    gate_reason = " ".join(w["detail"] or words.WARNING_SENTENCES.get(w["kind"], "") for w in warning_rows if w["kind"] in GATE_REFUSALS)
    choice = CHOICES.get(row["speech_choice"])
    state = note_state(p, row, gate_refused)
    # The doubted drug names (rulings 20, 26 and 28): their rows head the warnings; one that is not settled counts on
    # Approve; the sentences above them are not counted.
    drug = drug_marks.review_data(p.consultations, cid, lines)
    warnings = drug["rows"] + warning_lines(warning_rows, lines, choice.title if choice else row["speech_choice"])
    # A press that plays a line plays that line and stops (ruling 29): each warning that names a line carries its start and end.
    by_number = {line["n"]: line for line in lines}
    for w in warnings:
        held = by_number.get(w["line_n"])
        w["line_start_s"], w["line_end_s"] = (held["start_s"], held["end_s"]) if held else (None, None)
        w["line_play_s"] = press_start(w["line_start_s"])
    # Ruling 38: each press on a line or a row is given its start, one second early. The player's data keeps the true
    # times, so the line marked while it plays is the line that is sounding; a warning's own stretch, the alarm's press
    # and the strip are not changed.
    for line in lines:
        line["play_s"] = press_start(line["start_s"])
    for mark in drug["marks"]:
        mark["play_s"] = press_start(mark["start_s"])
    if gate_refused:
        state["draft_reason"] = words.NOTE_GATE_REFUSED.format(reason=gate_reason)
    who = who_check.page_state(p.consultations, cid, state["transcript_read_only"], bool(lines))
    state["transcript_reason"] = words.NOTE_READ_ONLY
    if who["running"]:
        # While a run lasts nothing changes under it and no unsaved edit can be lost: no edit field, and every
        # control that writes answers with the running sentence (ruling 19; ruling 12; R15).
        state.update(entries_read_only=True, transcript_read_only=True, entries_reason=words.CHECK_RUNNING,
                     transcript_reason=words.CHECK_RUNNING, draft_reason=words.CHECK_RUNNING,
                     approve_reason=words.CHECK_RUNNING, refuse_reason=words.CHECK_RUNNING)
    player = player_data(row, lines, warnings + [{"kind": "drug_mark", **m} for m in drug["marks"]], p.settings.data_folder)
    # On Approve: each warning, each doubted name that is not settled (ruling 28), and the line of ruling 18 as one.
    counted = len(warnings) + drug["open"] + (1 if state["speakers_changed"] else 0)
    pass_rows = p.consultations.passes(cid)
    differentials = note.last_shown_differentials(pass_rows)
    marks = alarms.review_marks(pass_rows, [d.get("condition") for d in differentials if isinstance(d, dict)])
    alarm_rows = alarms.alarm_lines(pass_rows, p.consultations.live_lines(cid), datetime.fromisoformat(row["started_at"]),
                                    alarms.acknowledged_keys(p.audit.lines(), cid), words)
    return {"cid": cid, "row": row, "patient": p.patients.get(row["patient_id"]), "ran_with": ran_with(p, row),
            # The cloud mark among the details the consultation ran with (ruling 5); and what came of a recording sent after Stop.
            "mark": mark_lines(path_of(row)) + sent_lines(p, row)[0], "recording_sent": sent_lines(p, row)[1],
            "background_read": background_read(row), "letters": letters_web.section_data(p, row),
            "marks": marks, "marks_json": json.dumps(marks), "alarms": alarm_rows,
            "alarm_count": words.ALARM_ONE if len(alarm_rows) == 1 else words.ALARMS_COUNT.format(count=len(alarm_rows)),
            "lines": lines, "turns": turns_of(lines), "warnings": warnings, "who_check": who, "drug_head": drug["head"],
            "drug_marks": drug["marks"],
            "player": player, "player_json": json.dumps(player),
            "audio_gone": None if player["available"] else words.AUDIO_GONE.format(
                date=words.plain_date(datetime.fromisoformat(row["started_at"]))),
            "conversion_failed": words.CONVERSION_FAILED.format(reason=row["conversion_failure"]) if row.get("conversion_failure") else None,
            "warning_count": words.WARNING_ONE if counted == 1 else words.WARNINGS_COUNT.format(count=counted),
            "differentials": differentials,
            "gate_refused": gate_refused, "gate_reason": gate_reason, "model_line": model_line_of(row),
            "date": words.plain_date(datetime.fromisoformat(row["started_at"])), **state,
            "approved_line": words.APPROVED_LINE.format(date=_when(state["approval"]["at"])[0], time=_when(state["approval"]["at"])[1])
            if state["approval"] else None}


def review_page(request: Request, user, consultation_id: int, refused: tuple | None = None, asking_delete: bool = False):
    p = parts(request)
    row = final_row(request, consultation_id)
    letters_web.ensure_list(p, consultation_id)      # the list call, once, at the first opening after Approve (15.12 ruling 2)
    data = page_data(p, row)
    # A turn is sent closed (ruling 43), but for two cases that work with no script: every turn after a press on the
    # control that opens all, and the turn of a line whose Save or Undo was refused, so that the sentence is seen (R15).
    data["lines_open"] = request.query_params.get("lines") == "open"
    at_line = refused[0].rpartition("-")[2] if refused and refused[0].startswith(("save-line-", "undo-")) else ""
    for turn in data["turns"]:
        turn["open"] = data["lines_open"] or (at_line.isdigit() and turn["first"] <= int(at_line) <= turn["last"])
    data["asking_delete"] = asking_delete
    data["delete_question"] = words.DELETE_CONSULTATION_QUESTION.format(name=data["ran_with"]["name"], date=data["date"])
    draft = data["draft"]
    if draft and data["refused_by_doctor"]:
        when = [r["at"] for r in p.notes.refusals(consultation_id) if r["draft_id"] == draft["id"]][-1]
        data["refused_line"] = words.REFUSED_LINE.format(date=_when(when)[0], time=_when(when)[1])
    context = dict(user=user, active="new_patient", page_path=f"/consultations/{consultation_id}", timed_by_script=True,
                   words_json=json_words(), **data)
    if data["who_check"]["running"]:
        context["refresh_every"] = 1         # the page waits for the run as the stopping page waits for a stage
        # Each wait comes back at the check's place, and so does the load that shows the outcome. Each wait's address
        # differs by a count: an address that differed by nothing but its anchor would only be scrolled to, never loaded.
        waited = request.query_params.get("quiet", "")
        context["refresh_to"] = f"/consultations/{consultation_id}?quiet={int(waited) + 1 if waited.isdigit() else 1}#{CHECK_PLACE}"
    if refused:
        return refuse(request, "review.html", refused[0], refused[1], **context)
    return render(request, "review.html", **context)


def json_words() -> str:
    import json
    return json.dumps(script_words())


# ------------------------------------------------------------- the controls

@router.post("/consultations/{consultation_id}/note/draft")
async def draft(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Draft the note for a final consultation that has none, or draft it
    again after an edit (ruling 11); never by itself. Refused on the
    control when the gate refused, the note is approved, or nothing has
    been edited (R15)."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["draft_reason"]:
        # The same control stands a second time under the rows of the doubted names: a refusal answers where the press was (R15).
        control = "draft-rows" if (await form_fields(request)).get("where") == "rows" else "draft"
        return review_page(request, user, consultation_id, refused=(control, data["draft_reason"]))
    note.draft(p.door_for(consultation_id), p.consultations, p.notes, p.audit, consultation_id, data["asked_by"])
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/note/approve")
async def approve(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Approve: the approved note written as the copy text, audited (R2);
    after it the note is read-only."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["approve_reason"]:
        return review_page(request, user, consultation_id, refused=("approve", data["approve_reason"]))
    text = note.plain_text(data["entries"])
    p.notes.approve(consultation_id, data["draft"]["id"], text)
    p.audit.record("note.approved", f"consultation {consultation_id}: draft {data['draft']['n']}, {len(data['entries'])} entries")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/note/refuse")
async def refuse_note(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Refuse: recorded and audited; nothing enters the record."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["refuse_reason"]:
        return review_page(request, user, consultation_id, refused=("refuse", data["refuse_reason"]))
    p.notes.refuse(consultation_id, data["draft"]["id"])
    p.audit.record("note.refused", f"consultation {consultation_id}: draft {data['draft']['n']}")
    raise Redirect(f"/consultations/{consultation_id}")


# ---------------------------------------------- the edits (rulings 7 and 11)

@router.post("/consultations/{consultation_id}/entries/{entry_id}")
async def edit_entry(request: Request, consultation_id: int, entry_id: int, user=Depends(guards.logged_in)):
    """The doctor's edit of an entry's words; what stood before is kept."""
    p = parts(request)
    final_row(request, consultation_id)
    data = page_data(p, p.consultations.get(consultation_id))
    control = f"entry-{entry_id}"
    entry = p.notes.entry(entry_id)
    if entry is None or not data["draft"] or entry["draft_id"] != data["draft"]["id"]:
        raise Redirect(f"/consultations/{consultation_id}")
    if data["entries_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["entries_reason"]))
    text = (await form_fields(request)).get("text", "").strip()
    if not text:
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if text != entry["text"]:
        p.notes.set_entry_text(entry_id, text)
        p.audit.record("entry.edited", f"consultation {consultation_id}: entry {entry_id}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/swap")
async def swap_lines(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """v1's Swap: doctor and patient exchanged on every line; unsure stays."""
    p = parts(request)
    final_row(request, consultation_id)
    data = page_data(p, p.consultations.get(consultation_id))
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=("swap", data["transcript_reason"]))
    p.consultations.swap_labels(consultation_id)
    p.audit.record("labels.swapped", f"consultation {consultation_id}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/{n}")
async def edit_line(request: Request, consultation_id: int, n: int, user=Depends(guards.logged_in)):
    """The per-line label and the words, from one form; each change is
    recorded with what stood before, and draft again is then offered."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"save-line-{n}"
    line = p.consultations.line(consultation_id, n)
    if line is None:
        raise Redirect(f"/consultations/{consultation_id}")      # no such control on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["transcript_reason"]))
    fields = await form_fields(request)
    label, text = fields.get("label", ""), fields.get("text", "").strip()
    if label not in LABELS:
        return review_page(request, user, consultation_id, refused=(control, words.PICK_LABEL))
    # A line that holds words is never emptied here. One a drug-name correction left with no words may stay empty,
    # so that its speaker can still be set (the plan review of 6d, point 1).
    if not text and line["text"].strip():
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if text != line["text"]:
        p.consultations.set_line_words(consultation_id, n, text)
        p.audit.record("transcript.edited", f"consultation {consultation_id}: line {n}")
        # A doubted name typed over here: a mark whose words are gone leaves the page and stays in the record (ruling 20).
        drug_marks.after_edit(p.consultations, consultation_id, n, before={n: line["text"]})
    if label != line["label"]:
        p.consultations.set_line_label(consultation_id, n, label)
        p.audit.record("label.set", f"consultation {consultation_id}: line {n} to {label}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/lines/{n}/undo")
async def undo_label(request: Request, consultation_id: int, n: int, user=Depends(guards.logged_in)):
    """One press puts back the label that stood before the check changed
    it (ruling 7; the details of step 6c, Undo): not the answer's label,
    which a Swap may have changed since."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"undo-{n}"
    line = p.consultations.line(consultation_id, n)
    if line is None:
        raise Redirect(f"/consultations/{consultation_id}")      # no such control on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["transcript_reason"]))
    before = p.consultations.undo_change(consultation_id, n)
    if before is None:
        return review_page(request, user, consultation_id, refused=(control, words.NOT_CHANGED_BY_CHECK))
    p.audit.record("label.undone", f"consultation {consultation_id}: line {n} back to {before}")
    raise Redirect(f"/consultations/{consultation_id}")


@router.post("/consultations/{consultation_id}/marks/{mark_id}")
async def tick_mark(request: Request, consultation_id: int, mark_id: int, user=Depends(guards.logged_in)):
    """The row of a doubted drug name, the one place to settle it (rulings
    26 and 28). A press on a tick that is not ticked keeps what the field
    holds: where the words differ from those on the line, the line is
    corrected by the function its own box uses; then the mark is settled,
    with the time. A press on a ticked tick opens it again; the line keeps
    what was typed. The button says which press it is, so a press from a
    stale page never turns a mark the wrong way. A third press, keep, is
    sent by the page's script when the doctor leaves the box (ruling 33):
    the typed words go into the line as at the tick, and the mark is not
    settled, so a stray click never settles a name. A tick with the box
    empty takes the doubted words out of the line and settles the mark
    (ruling 40): a leftover piece of a name the speech choice cut over
    two lines would otherwise go to the note's model as if it had been
    said. The line stays, the record keeps the words as heard, and a
    second press opens the mark with an empty box, so that words can be
    typed back. The note is never corrected by this: Draft the note
    again is offered, never run."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    control = f"tick-{mark_id}"
    mark = next((m for m in p.consultations.drug_marks(consultation_id) if m["id"] == mark_id), None)
    if mark is None:
        raise Redirect(f"/consultations/{consultation_id}#warnings")      # no such row on the page
    if data["transcript_read_only"]:
        return review_page(request, user, consultation_id, refused=(control, data["transcript_reason"]))
    fields = await form_fields(request)
    # With no script a row's press comes back at its row. The page's script keeps the place itself and asks for no anchor,
    # which would carry the row to the top of the window, past the next one (ruling 34).
    back = f"/consultations/{consultation_id}" + ("" if fields.get("place") == "keep" else f"#drug-mark-{mark_id}")
    where = f"consultation {consultation_id}: line {mark['heard_first']}"
    if fields.get("press") == "open":
        if mark["settled_at"] is not None:
            p.consultations.settle_mark(mark_id, settled=False)
            p.audit.record("drug_name.opened", where)
        raise Redirect(back)
    if mark["settled_at"] is not None:
        raise Redirect(back)                                              # ticked already: its words are locked, for a tick and for a keep
    typed = fields.get("words", mark["standing"]).strip()
    # An empty box with the tick or the Enter key takes the doubted words out of the line (ruling 40). Leaving an empty
    # box takes nothing out: the page's script sends no keep for one, and a keep that a stale page sends is refused as built.
    if not typed and mark["standing"] and fields.get("press") == "keep":
        return review_page(request, user, consultation_id, refused=(control, words.ENTRY_EMPTY))
    if typed != mark["standing"]:
        drug_marks.correct(p.consultations, p.audit, consultation_id, mark, typed)
    if fields.get("press") == "keep":
        raise Redirect(back)                                              # kept in the line, not settled: the tick stays faded
    p.consultations.settle_mark(mark_id)
    p.audit.record("drug_name.settled", where)
    raise Redirect(back)


@router.post("/consultations/{consultation_id}/delete")
async def delete(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """Delete (15.11 ruling 8; D44): the first press shows the question
    once, with the patient's name and the date; the press with the
    confirmation calls the one function and goes to the patient's page. A
    consultation that is not final has no control and goes back to its
    page; one that is gone goes to the Patients page."""
    p = parts(request)
    row = p.consultations.get(consultation_id)
    if row is None:
        raise Redirect("/")
    if row["state"] != "final":
        raise Redirect(f"/consultations/{consultation_id}")
    if who_check.page_state(p.consultations, consultation_id, False, True)["running"]:
        return review_page(request, user, consultation_id, refused=("delete", words.CHECK_RUNNING))
    fields = await form_fields(request)
    if fields.get("confirm") != "yes":
        return review_page(request, user, consultation_id, asking_delete=True)
    deletion.delete_consultation(p, consultation_id)
    raise Redirect(f"/patients/{row['patient_id']}")


@router.get("/consultations/{consultation_id}/recording", dependencies=[Depends(guards.this_computer)])
async def recording(request: Request, consultation_id: int, user=Depends(guards.logged_in_not_use)):
    """The recording, played only to the logged-in user from this
    computer (8.8; D51; 15.6 ruling 6): the file is read and never
    written (R18); one that is not there is 404. The request is never
    use (15.10 ruling 41): the page makes it by itself; a press of play
    and sound that is playing are told by the page's script."""
    p = parts(request)
    row = final_row(request, consultation_id)
    path = folder_of(p.settings.data_folder) / (row["recording_file"] or "")
    if not row["recording_file"] or not path.is_file():
        return PlainTextResponse(words.AUDIO_GONE.format(date=words.plain_date(datetime.fromisoformat(row["started_at"]))),
                                 status_code=404)
    return FileResponse(path, media_type="audio/ogg" if path.suffix == ".ogg" else "audio/wav")


@router.get("/consultations/{consultation_id}/recording/file", dependencies=[Depends(guards.this_computer)])
async def recording_file(request: Request, consultation_id: int, user=Depends(guards.logged_in_not_use)):
    """The name of the recording's file as it is now, and nothing else
    (the mend run of step 6d, fault one). A page shown before the WAV was
    converted asks this at a press of play; a new name tells its player to
    take the recording's address afresh. 404 when there is no such
    consultation or no such file. Never use (ruling 41)."""
    p = parts(request)
    row = p.consultations.get(consultation_id)
    name = row["recording_file"] if row is not None and row["state"] == "final" else None
    if not name or not (folder_of(p.settings.data_folder) / name).is_file():
        return PlainTextResponse("", status_code=404)
    return PlainTextResponse(name)


@router.get("/consultations/{consultation_id}/note.txt")
async def note_text(request: Request, consultation_id: int, user=Depends(guards.logged_in)):
    """The copy text: the note alone in the four sections (ruling 4); the
    approved text once approved."""
    p = parts(request)
    row = final_row(request, consultation_id)
    data = page_data(p, row)
    if data["approval"]:
        return PlainTextResponse(data["approval"]["text"])
    if not data["has_note"]:
        return PlainTextResponse(words.NO_NOTE_YET, status_code=404)
    return PlainTextResponse(note.plain_text(data["entries"]))
