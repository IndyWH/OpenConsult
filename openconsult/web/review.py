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
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from openconsult import words
from openconsult.consult import alarms, deletion, drug_marks, gate, note, reading, who_check, whole
from openconsult.consult.recording import folder_of
from openconsult.settings import thresholds
from openconsult.settings.path import path_of
from openconsult.settings.statement import review_mark_lines
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
                "NOT_SAVED_ERROR", "OPEN_ALL_LINES", "CLOSE_ALL_LINES", "TURN_NOT_SAVED", "VIEW_NOT_SAVED", "ENTRY_SAVED", "ENTRY_NOT_SAVED",
                "NOT_SAVED_NEW_DRAFT")
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
    entries = reading.entries_of(lines)
    numbers = reading.numbers_of(entries)
    for entry in entries:
        held = entry["lines"]
        ends = [line["end_s"] for line in held if line["end_s"] is not None]
        found.append({"number": numbers[held[0]["n"]], "first": held[0]["n"], "last": held[-1]["n"], "speaker": entry["speaker"],
                      "lines": held, "play_s": press_start(held[0]["start_s"]), "end_s": max(ends) if ends else None})
    return found


# The two areas of the page that have a simple and an advanced view (15.13, ruling 46), and the two views.
AREAS = ("note", "transcript")
SIMPLE, ADVANCED = "simple", "advanced"


def views_of(request: Request, refused: tuple | None, check_running: bool) -> dict:
    """The view of each area as the app sends the page (15.13, ruling 46
    and the details of step 9f): simple at every fresh visit; advanced
    where the address names it, which is how a view is chosen with no
    script; and advanced where the page comes back to something that
    stands in the advanced view alone, so that it is seen with no script
    too (R15): a Save of an entry that was refused; a Save or an Undo of
    a line that was refused, every line opened, the check of who spoke
    while it runs and each of its waits, with the load that shows its
    outcome. With a script the browser remembers the doctor's choice
    and sets it after the load; the app holds nothing of it."""
    asked = request.query_params
    control = refused[0] if refused else ""
    note = asked.get("note") == ADVANCED or control.startswith("entry-")
    transcript = (asked.get("transcript") == ADVANCED or asked.get("lines") == "open" or check_running
                  or asked.get("quiet", "").isdigit() or control.startswith(("save-line-", "undo-", "check-who")))
    return {"note": ADVANCED if note else SIMPLE, "transcript": ADVANCED if transcript else SIMPLE}


def view_addresses(consultation_id: int, views: dict) -> dict:
    """With no script each press of a view is a link that loads the page
    with that view, at that area; the other area keeps the view it has."""
    found = {}
    for area in AREAS:
        for view in (SIMPLE, ADVANCED):
            chosen = {**views, area: view}
            asked = "&".join(f"{name}={ADVANCED}" for name in AREAS if chosen[name] == ADVANCED)
            found[area, view] = f"/consultations/{consultation_id}" + (f"?{asked}" if asked else "") + f"#{area}"
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


def model_line_of(row: dict, whole_made: bool = False) -> str:
    """R20: from the row's stamps, not the running engine, so it is true
    after a restart. whole_made: the final transcript was made by the
    service from the whole recording, so the line does not name the
    consultation's own speech choice alone for lines another made."""
    choice = CHOICES.get(row["speech_choice"])
    line = words.MODEL_LINE_WHOLE if whole_made and row["speech_choice"] != "speechmatics" else words.MODEL_LINE
    return line.format(speech=choice.title if choice else row["speech_choice"], model=row["model_tag"],
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
    when the patient's details were corrected after it started. And the
    two values its gate used, from its own row too (7.3): what Settings
    holds now may differ, and a row from before they could be set was
    judged by the defaults."""
    born = datetime.fromisoformat(row["patient_date_of_birth"]).date() if row["patient_date_of_birth"] else None
    changed = p.patients.changed_after(row["patient_id"], row["started_at"])
    fewest_words, low_score = thresholds.of_row(row)
    return {"name": row["patient_name"], "born": words.plain_date(born) if born else "",
            "sex": words.SEX_WORDS.get(row["patient_sex"], ""),
            "gate": words.GATE_RAN_WITH.format(words=fewest_words, score=f"{low_score:.2f}"),
            "corrected": words.DETAILS_CORRECTED.format(date=words.plain_date(datetime.fromisoformat(changed))) if changed else None}


SENT_LINES = {whole.AWAITED: words.UPLOAD_MADE_AWAITED, whole.PROVEN: words.UPLOAD_MADE, whole.UNPROVEN: words.UPLOAD_MADE_ONLY}
# Where the service took the recording and no transcript was made from it (the owner's word of 20 Nov 2026): a line
# while the answer to the delete is awaited and one when it is proven; none when it is not, where his warning says it.
SENT_NONE_LINES = {whole.AWAITED: words.UPLOAD_NONE_AWAITED, whole.PROVEN: words.UPLOAD_NONE}
# Where a transcript came back and the app did not use it (his word of 20 Nov 2026, 10:57): his two lines for that.
SENT_UNUSED_LINES = {whole.AWAITED: words.UPLOAD_UNUSED_AWAITED, whole.PROVEN: words.UPLOAD_UNUSED}


def sent_lines(p, row: dict) -> tuple[str | None, str | None, str | None]:
    """For a consultation whose recording was to be sent after Stop: what
    its record can show of the request that carried it, for the mark's
    third line (ruling 52); the line above the note, by what the record
    holds of the delete at this moment (the owner's ruling of 18 Nov
    2026): the answer awaited, proven, or not proven, in his sentences
    for a transcript the service made, in his two for a recording it
    took that gave none, and in his two for a transcript that came back
    and was not used; and that state itself. No line and no state where
    the service took nothing."""
    sent = p.consultations.upload(row["id"])
    if sent is None:
        return None, None, None
    state = whole.proof_state(sent)
    if sent["result_at"] is None:
        return sent["request"], (SENT_UNUSED_LINES if whole.came_back(sent) else SENT_NONE_LINES).get(state), state
    return sent["request"], SENT_LINES.get(state, words.UPLOAD_MADE_ONLY), state


def page_data(p, row: dict) -> dict:
    cid = row["id"]
    lines = [r for r in p.consultations.transcript_lines(cid) if r["n"] is not None]
    # A line is marked by the score the consultation started with, as its gate judged it (7.3).
    _, low_score = thresholds.of_row(row)
    for line in lines:
        score = line.get("confidence")
        line["low_confidence"] = (words.LOW_CONFIDENCE_MARK.format(score=f"{score:.2f}")
                                  if score is not None and score < low_score else None)
    warning_rows = p.consultations.warnings(cid)
    gate_refused = any(w["kind"] in GATE_REFUSALS for w in warning_rows)
    gate_reason = " ".join(w["detail"] or words.WARNING_SENTENCES.get(w["kind"], "") for w in warning_rows if w["kind"] in GATE_REFUSALS)
    choice = CHOICES.get(row["speech_choice"])
    state = note_state(p, row, gate_refused)
    turns = turns_of(lines)
    # The chips of each entry (15.13, ruling 71): made now, from its lines as the record holds them and the turns as
    # the page shows them.
    numbers = {line["n"]: turn["number"] for turn in turns for line in turn["lines"]}
    for entry in state["entries"]:
        entry["chips"] = reading.chips_of(entry["lines"], numbers)
        # Ruling 75: an entry is edited when its words as they stand differ from the model's own, which the record keeps
        # beside them. One typed back to the model's words is not.
        entry["edited"] = entry["text"].strip() != entry["model_text"].strip()
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
    sent = sent_lines(p, row)
    return {"cid": cid, "row": row, "patient": p.patients.get(row["patient_id"]), "ran_with": ran_with(p, row),
            # The cloud mark among the details the consultation ran with (ruling 5); and what came of a recording sent after Stop.
            "mark": review_mark_lines(path_of(row), sent[0]), "recording_sent": sent[1],
            # While the service's answer to the delete is awaited the page asks for it by itself (sent.js).
            "sent_awaited": sent[2] == whole.AWAITED,
            "background_read": background_read(row), "letters": letters_web.section_data(p, row),
            "marks": marks, "marks_json": json.dumps(marks), "alarms": alarm_rows,
            "alarm_count": words.ALARM_ONE if len(alarm_rows) == 1 else words.ALARMS_COUNT.format(count=len(alarm_rows)),
            "lines": lines, "turns": turns, "warnings": warnings, "who_check": who, "drug_head": drug["head"],
            "drug_marks": drug["marks"],
            "player": player, "player_json": json.dumps(player),
            "audio_gone": None if player["available"] else words.AUDIO_GONE.format(
                date=words.plain_date(datetime.fromisoformat(row["started_at"]))),
            "conversion_failed": words.CONVERSION_FAILED.format(reason=row["conversion_failure"]) if row.get("conversion_failure") else None,
            "warning_count": words.WARNING_ONE if counted == 1 else words.WARNINGS_COUNT.format(count=counted),
            "differentials": differentials,
            "gate_refused": gate_refused, "gate_reason": gate_reason,
            "model_line": model_line_of(row, any(w["kind"] == whole.MADE for w in warning_rows)),
            "date": words.plain_date(datetime.fromisoformat(row["started_at"])), **state,
            "approved_line": words.APPROVED_LINE.format(date=_when(state["approval"]["at"])[0], time=_when(state["approval"]["at"])[1])
            if state["approval"] else None}


def review_page(request: Request, user, consultation_id: int, refused: tuple | None = None, asking_delete: bool = False,
                by_itself: bool = False):
    """by_itself: the page asked for by its own script, not by the doctor:
    nothing is started for it."""
    p = parts(request)
    row = final_row(request, consultation_id)
    if not by_itself:
        letters_web.ensure_list(p, consultation_id)  # the list call, once, at the first opening after Approve (15.12 ruling 2)
    data = page_data(p, row)
    # A turn is sent closed (ruling 43), but for two cases that work with no script: every turn after a press on the
    # control that opens all, and the turn of a line whose Save or Undo was refused, so that the sentence is seen (R15).
    data["lines_open"] = request.query_params.get("lines") == "open"
    at_line = refused[0].rpartition("-")[2] if refused and refused[0].startswith(("save-line-", "undo-")) else ""
    for turn in data["turns"]:
        turn["open"] = data["lines_open"] or (at_line.isdigit() and turn["first"] <= int(at_line) <= turn["last"])
    data["views"] = views_of(request, refused, data["who_check"]["running"])
    data["view_addresses"] = view_addresses(consultation_id, data["views"])
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


# The edits (rulings 7 and 11): Save of an entry, Swap, Save and Undo of a line and a row's tick stand in review_edits.py.

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


@router.get("/consultations/{consultation_id}/sent")
async def sent_state(request: Request, consultation_id: int, user=Depends(guards.logged_in_not_use)):
    """What the record holds, at this moment, of the delete of a recording
    sent after Stop: awaited, proven or not_proven, with the line that
    stands above the note for it (the owner's ruling of 18 Nov 2026).
    The review page asks this by itself while the answer is awaited, so
    it is never use (15.10 ruling 41). Every sentence is the app's."""
    p = parts(request)
    row = final_row(request, consultation_id)
    _, line, state = sent_lines(p, row)
    return JSONResponse({"state": state or "none", "line": line}, headers={"Cache-Control": "no-store"})


@router.get("/consultations/{consultation_id}/sent/page")
async def sent_page(request: Request, consultation_id: int, user=Depends(guards.logged_in_not_use)):
    """The review page as it stands, for its own script to take the
    changed parts from when the service has answered: the line above
    the note, the warning where the delete is not proven, the count on
    Approve. Asked by the page itself, so never use, and nothing is
    started for it."""
    return review_page(request, user, consultation_id, by_itself=True)


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
