"""Stop, in order (spec 15.10, Stop in order; rulings 7, 8 and 14; 11.5
rule 2; V1_LESSONS 1.12, 2.2; 10.4). One: the page stopped the
microphone and the recording is closed (live.py). Two: the door's stop
gives the final lines, written as the choice gave them. Three: the app
asks which speaker was you and waits, with no limit. Four: the label
check runs and its changes are marked. Five: the two checks for missing
speech run on the stored lines and the stored loudness. Six: the gate.
Seven: the note is drafted unless the gate refused (6b; rulings 3 and
8), and the review page is shown. Each step reads the rows, so a
consultation left stopping at a restart goes on from its stage
(review point 3). A worker that has died is reported plainly."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime

from openconsult.consult import gate, labels, note, opus, speakers
from openconsult.consult.consultations import line_as_row, row_as_line
from openconsult.consult.live import FINAL, STOPPING, Consultation
from openconsult.consult.recording import finish, folder_of
from openconsult.patients.patients import PatientRow
from openconsult.speech.lines import Line

STAGES = ("speech", "who_spoke", "label_check", "checks", "gate", "note")


def finalise(c: Consultation) -> None:
    """The steps from the consultation's stage on. Runs on the Stop thread."""
    if c.stop_stage == "speech":
        final_lines(c)
        c.set_stage("who_spoke")
    if c.stop_stage == "who_spoke":
        if not wait_for_answer(c):
            return                       # the app closed while waiting: the stage is kept for the next start
        c.set_stage("label_check")
    if c.stop_stage == "label_check":
        label_check(c)
        c.set_stage("checks")
    for stage, step in STEPS_AFTER.items():
        if c.stop_stage == stage:
            step(c)
            c.set_stage(NEXT[stage])
    show_final(c)
    # After Stop's final step (15.11 ruling 7): the WAV to Opus, on this thread, with the page already shown.
    opus.convert_consultation(c)


def checks(c: Consultation) -> None:
    """Five: the two checks for missing speech on the stored lines and the
    stored loudness (11.5 rule 2)."""
    row = c.rows.get(c.id)
    final = [row_as_line(r) for r in c.rows.transcript_lines(c.id) if r["n"] is not None]
    live = [row_as_line({**r, "raw_speaker": r["speaker"]}) for r in c.rows.live_lines(c.id) if not r["refused"]]
    windows = json.loads(row["loudness"] or "[]")
    for warning in gate.missing_speech(live, final, windows, c.speech_door.declares.second_transcript):
        c.rows.add_warning(c.id, **warning)


def judge(c: Consultation) -> None:
    """Six: the gate (ruling 8)."""
    rows = [r for r in c.rows.transcript_lines(c.id) if r["n"] is not None]
    verdict = gate.judge(rows, c.speech_door.declares, c.speech_door.choice.title)
    for warning in verdict.warnings:
        c.rows.add_warning(c.id, **warning)
    c.final.refused = verdict.refused


def draft_note(c: Consultation) -> None:
    """Seven: the note, the last stage before final, unless the gate
    refused (ruling 8; R3). The three figures of 6a are taken first, so
    Stop to final keeps its meaning; the note's seconds are a fourth."""
    c.final.figures = figures(c)
    if c.final.refused or c.notes is None:
        return
    started = c.timer()
    note.draft(c.llm, c.rows, c.notes, c.audit, c.id, "stop")
    c.final.figures["note_s"] = round(c.timer() - started, 2)


STEPS_AFTER = {"checks": checks, "gate": judge, "note": draft_note}
NEXT = {"checks": "gate", "gate": "note", "note": None}


# ------------------------------------------------------- two: the lines

def final_lines(c: Consultation) -> None:
    """The door's stop, and the lines written as the choice gave them,
    labels unsure until the answer (V1_LESSONS 1.7). A failed stop leaves
    the live lines as the transcript with the reason as a warning."""
    final = c.speech_door.stop(speakers=c.speakers_given) if c.speech.state == "open" else None
    with c.lock:
        c.speech = type(c.speech)("stopped")
        if final is not None and final.ok:
            heard = [(line, False) for line in final.lines] + [(r.line, True) for r in final.refused]
            revised = {r.id for r in final.revisions if r.applied}
            c.rows.set(c.id, stop_raw=json.dumps(list(final.raw), ensure_ascii=False))
        else:
            heard = [(s.line, s.refused) for s in c.transcript.shown]
            revised = {s.line.id for s in c.transcript.shown if s.revised}
            reason = (final.detail or final.failure) if final is not None else (c.speech_failure or c.speech.reason or "")
            c.rows.add_warning(c.id, "speech_failed", detail=reason)
        c.rows.set(c.id, loudness=json.dumps(_windows(c.speech_door.loudness_windows)))
        write_lines(c, heard, revised)


def write_lines(c: Consultation, heard: list[tuple[Line, bool]], revised: set) -> None:
    n = 0
    rows = []
    for line, refused in heard:
        n = n if refused else n + 1
        rows.append(line_as_row(line, None if refused else n, "unsure", refused=refused, unsure=True,
                                revised=line.id in revised))
    c.rows.add_transcript_lines(c.id, rows)


def _windows(windows: list[float]) -> list[float | None]:
    return [None if w == -math.inf else round(w, 1) for w in windows]


# ---------------------------------------------------- three: who spoke

def wait_for_answer(c: Consultation) -> bool:
    """No limit on a human answer that changes the transcript (2.2). False
    only when the app closed while waiting."""
    while c.doctor_speaker is None:
        c.answer_event.wait()
        if c.closed and c.doctor_speaker is None:
            return False
    rows = c.rows.transcript_lines(c.id)
    c.rows.set_labels(c.id, speakers.labels_from_answer(rows, c.doctor_speaker))
    return True


def answer(c: Consultation, doctor_speaker: str) -> bool:
    """The page's answer. False when it is not the time, or the speaker is
    not one the choice gave (and not I cannot tell)."""
    with c.lock:
        if c.state != STOPPING or c.stop_stage != "who_spoke" or c.doctor_speaker is not None:
            return False
        allowed = {o["speaker"] for o in speakers.options(c.rows.transcript_lines(c.id))} | {speakers.CANNOT_TELL}
        if doctor_speaker not in allowed:
            return False
        c.doctor_speaker = doctor_speaker
        c.rows.set(c.id, doctor_speaker=doctor_speaker)
        c.audit.record("speakers.answered", f"consultation {c.id}: {doctor_speaker}")
        c._changed()
    c.answer_event.set()
    return True


# ------------------------------------------------- four: the label check

def label_check(c: Consultation) -> None:
    rows = [r for r in c.rows.transcript_lines(c.id) if r["n"] is not None]
    if not rows:
        return
    found, outcome = labels.run(c.llm, rows, c.id)
    if found is None:
        c.rows.add_warning(c.id, f"label_check_{outcome['outcome']}", detail=outcome.get("detail") or outcome.get("failure"))
        return
    c.rows.set_labels(c.id, speakers.apply_check(rows, found))


# --------------------------------------------------- seven: the final page

def show_final(c: Consultation) -> None:
    with c.lock:
        c.final.lines = c.rows.transcript_lines(c.id)
        c.final.warnings = c.rows.warnings(c.id)
        c.final.figures = c.final.figures or figures(c)
        c.state = FINAL
        c.stop_stage = None
        final_at = c.clock()
        c.rows.set(c.id, state=FINAL, stop_stage=None, final_at=final_at.isoformat(timespec="seconds"))
        c.audit.record("consultation.final", f"consultation {c.id}: " + figures_line(c.final.figures))
        c._changed()
    if c.on_final is not None:
        c.on_final(c)


def figures(c: Consultation) -> dict:
    """The three figures of the room run, from the record: the wait from a
    spoken word to the page, the typical pass, and Stop to final."""
    waits = [r["shown_at_s"] - r["end_s"] for r in c.rows.live_lines(c.id) if not r["refused"]]
    walls = [p["result"].get("wall_ms", 0) / 1000 for p in c.rows.passes(c.id)]
    stop_to_final = (c.clock() - c.stopped_at).total_seconds() if c.stopped_at else None
    return {"wait_s": round(statistics.median(waits), 2) if waits else None,
            "pass_s": round(statistics.median(walls), 2) if walls else None,
            "stop_s": round(stop_to_final, 1) if stop_to_final is not None else None}


def figures_line(found: dict) -> str:
    from openconsult import words
    line = words.FIGURES_LINE.format(wait=found["wait_s"], pass_s=found["pass_s"], stop_s=found["stop_s"])
    return line + (words.FIGURE_NOTE.format(note_s=found["note_s"]) if found.get("note_s") is not None else "")


# ------------------------------------------------------- after a restart

def sweep(p) -> list[Consultation]:
    """At app start (review point 3; V1_LESSONS 1.12): every row left live
    moves to stopping with its recording finished as it stands and its
    live lines as the lines, with a warning; every row left stopping is
    built again and goes on from its stage when the doctor opens it.
    Nothing is deleted; no row stays live."""
    from openconsult import words
    resumed = []
    for row in p.consultations.in_state("live"):
        _close_left_live(p, row, words.APP_RESTARTED)
    for row in p.consultations.in_state("stopping"):
        resumed.append(resume(p, row))
    return resumed


def _close_left_live(p, row: dict, reason: str) -> None:
    cid = row["id"]
    if row["recording_file"]:
        path = folder_of(p.settings.data_folder) / row["recording_file"]
        if path.exists():
            finish(path)
    lines = [row_as_line({**r, "raw_speaker": r["speaker"]}) for r in p.consultations.live_lines(cid)]
    refused = {r["id"] for r in p.consultations.live_lines(cid) if r["refused"]}
    heard = [(line, r["refused"] == 1) for line, r in zip(lines, p.consultations.live_lines(cid))]
    p.consultations.add_transcript_lines(cid, [
        line_as_row(line, None if was_refused else n, "unsure", refused=was_refused, unsure=True)
        for n, (line, was_refused) in _numbered(heard)])
    p.consultations.add_warning(cid, "speech_failed", detail=reason)
    p.consultations.set(cid, state=STOPPING, stop_stage="who_spoke", stopped_at=p.clock().isoformat(timespec="seconds"))
    p.audit.record("consultation.stopped", f"consultation {cid}: {reason}")
    del refused


def _numbered(heard):
    n = 0
    for line, was_refused in heard:
        n = n if was_refused else n + 1
        yield n, (line, was_refused)


def resume(p, row: dict) -> Consultation:
    """A consultation object from its row, with no sound and no worker,
    held for the run; it finishes when the doctor opens it."""
    patient = p.patients.get(row["patient_id"])
    door = p.doors[row["speech_choice"]]
    c = Consultation(row["id"], patient, row["intended_minutes"], datetime.fromisoformat(row["started_at"]), door,
                     p.door, p.consultations, p.audit, p.settings.data_folder, p.clock, on_stop=p.finaliser, notes=p.notes,
                     converter=p.converter, guidelines=p.guidelines)
    c.state = STOPPING
    c.stop_stage = row["stop_stage"] if row["stop_stage"] in STAGES[1:] else "who_spoke"
    c.stopped_at = datetime.fromisoformat(row["stopped_at"]) if row["stopped_at"] else p.clock()
    c.doctor_speaker = row["doctor_speaker"]
    c.speech = type(c.speech)("stopped")
    c.speakers_given = int(row["speakers_given"])
    if c.doctor_speaker is not None:
        c.answer_event.set()
    p.running[row["id"]] = c
    p.logins.consultation_running = True
    c.resume_pending = True
    return c


def continue_resumed(c: Consultation) -> None:
    """When the doctor opens a resumed consultation: the stages after its
    own run on the Stop thread."""
    if c.resume_pending:
        c.resume_pending = False
        c.run_stop_thread(finalise)
