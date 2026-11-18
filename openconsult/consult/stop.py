"""Stop, in order (spec 15.10, the details of step 6c: Stop, in order, as
it now stands; rulings 7 and 8; 15.9 ruling 37; 11.5 rule 2; V1_LESSONS
1.12, 2.2; 10.4). One: the page stopped the microphone and the
recording is closed (live.py). Two: the door's stop gives the final
lines, written as the choice gave them. Three: the app asks which
speaker was you and waits, with no limit; its answer sets the labels.
Four: the two checks for missing speech run on the stored lines and the
stored loudness. Five: the gate. Six: the language model reads the
final transcript once and marks the drug names it doubts (15.9 ruling
39), unless the gate refused. Seven: the note is drafted unless the
gate refused (6b; rulings 3 and 8), from the labels as the answer set
them, and the review page is shown. The check of who spoke does not run
here: it made well labelled pages worse, so the doctor asks for it on
the review page (15.9 ruling 37). Each step reads the rows, so a
consultation left stopping at a restart goes on from its stage
(review point 3). A worker that has died is reported plainly."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime

from openconsult.consult import drug_marks, gate, note, opus, speakers, whole
from openconsult.consult.consultations import line_as_row, row_as_line
from openconsult.consult.live import FINAL, STOPPING, Consultation
from openconsult.consult.recording import finish, folder_of
from openconsult.patients.patients import PatientRow
from openconsult.consult.transcript import moved
from openconsult.speech.choices import SPEECHMATICS as SPEECHMATICS_CHOICE
from openconsult.speech.lines import Line
from openconsult.speech.loudness import WINDOW_S

STAGES = ("speech", "lost", "upload", "who_spoke", "checks", "gate", "drug_name", "note")
# A consultation found at a restart in the stage that Stop no longer has goes on
# from the checks for missing speech, with no check of who spoke (15.9 ruling 37).
STAGE_GONE = {"label_check": "checks"}


def finalise(c: Consultation) -> None:
    """The steps from the consultation's stage on. Runs on the Stop thread."""
    if c.stop_stage == "speech":
        final_lines(c)
        c.set_stage(after_the_lines(c))
    if c.stop_stage == "lost":
        if not wait_for_press(c):
            return                       # the app closed while waiting: the stage is kept for the next start
        c.set_stage("upload" if c.send_after_loss else "who_spoke")
    if c.stop_stage == "upload":
        send_recording(c)
        c.set_stage("who_spoke")
    if c.stop_stage == "who_spoke":
        if not wait_for_answer(c):
            return                       # the app closed while waiting: the stage is kept for the next start
        c.set_stage("checks")
    for stage, step in STEPS_AFTER.items():
        if c.stop_stage == stage:
            step(c)
            c.set_stage(NEXT[stage])
    show_final(c)
    # After Stop's final step (15.11 ruling 7): the WAV to Opus, on this thread, with the page already shown.
    opus.convert_consultation(c)


def after_the_lines(c: Consultation) -> str:
    """The stage after the final lines (15.13, rulings 29 and 33): the
    question after a lost connection, on a path whose transcription runs
    in the cloud; the recording sent, where the tick for better accuracy
    stood at Start; otherwise the question which speaker was you."""
    row = c.rows.get(c.id)
    if c.whole is None:
        return "who_spoke"
    if row["transcription_path"] == "speechmatics" and any(s["lost_at_s"] is not None for s in c.rows.sessions(c.id)):
        return "lost"
    return "upload" if whole.way_of(row, None) == whole.TICK else "who_spoke"


def wait_for_press(c: Consultation) -> bool:
    """The question after a lost connection waits with no limit, as the
    question which speaker was you does (2.2). False only when the app
    closed while waiting."""
    while c.send_after_loss is None:
        c.press_event.wait()
        if c.closed and c.send_after_loss is None:
            return False
    return True


def press(c: Consultation, send: bool, statement_sha256: str | None = None) -> bool:
    """The doctor's press: send the recording once for the whole
    transcript, or go on without. Written to the audit log with the
    checksum of the lines that stood beside it. False when it is not the time."""
    with c.lock:
        if c.state != STOPPING or c.stop_stage != "lost" or c.send_after_loss is not None:
            return False
        c.send_after_loss = bool(send)
        said = f"send the recording once; the statement shown, sha256 {statement_sha256}" if send else "go on without"
        c.audit.record("recording.pressed", f"consultation {c.id}: {said}")
        c._changed()
    c.press_event.set()
    return True


def send_recording(c: Consultation) -> None:
    """The recording sent once, by the tick or by the press, and never by
    itself. Whatever happens in it, Stop goes on (R30)."""
    way = whole.way_of(c.rows.get(c.id), c.send_after_loss)
    if way is None and c.rows.upload(c.id) is None:
        return
    c.whole.run(c, way or c.rows.upload(c.id)["way"])


def checks(c: Consultation) -> None:
    """Four: the two checks for missing speech on the stored lines and the
    stored loudness (11.5 rule 2)."""
    row = c.rows.get(c.id)
    final = [row_as_line(r) for r in c.rows.transcript_lines(c.id) if r["n"] is not None]
    live = [row_as_line({**r, "raw_speaker": r["speaker"]}) for r in c.rows.live_lines(c.id) if not r["refused"]]
    windows = json.loads(row["loudness"] or "[]")
    for warning in gate.missing_speech(live, final, windows, c.speech_door.declares.second_transcript):
        c.rows.add_warning(c.id, **warning)
    # The stretch a lost connection left with no transcript, named by its times (ruling 29); not where the whole
    # recording was sent and its transcript made, which has no such stretch.
    if not any(w["kind"] == whole.MADE for w in c.rows.warnings(c.id)):
        for start, end in lost_stretches(c):
            c.rows.add_warning(c.id, "no_transcript", start_s=start, end_s=end)


def final_choice(c: Consultation):
    """The speech choice that made the final transcript: the service's,
    where the record holds that the transcript from the whole recording
    was made; otherwise the consultation's own. Where the upload failed
    the live lines stay final, and so does the choice that made them."""
    made = any(w["kind"] == whole.MADE for w in c.rows.warnings(c.id))
    return SPEECHMATICS_CHOICE if made else c.speech_door.choice


def judge(c: Consultation) -> None:
    """Five: the gate (ruling 8), by the speech choice that made the final
    transcript and not by the one that wrote the live lines: in the room
    check of 17 Nov 2026 the page said that confidence was not measured
    and named this computer's choice, though the lines shown were the
    service's and carried scores."""
    rows = [r for r in c.rows.transcript_lines(c.id) if r["n"] is not None]
    choice = final_choice(c)
    verdict = gate.judge(rows, choice.declares, choice.title)
    for warning in verdict.warnings:
        c.rows.add_warning(c.id, **warning)
    c.final.refused = verdict.refused


def drug_names(c: Consultation) -> None:
    """Six: the drug-name call, on every final transcript whichever speech
    choice made it (ruling 21); not when the gate refused, which is read
    from the stored warnings; and once: a call that has its row is never
    made again, also after a restart (10.4)."""
    if gate.refused_in(c.rows.warnings(c.id)) or c.rows.drug_call(c.id) is not None:
        return
    drug_marks.run(c.llm, c.rows, c.audit, c.id)


def draft_note(c: Consultation) -> None:
    """Seven: the note, the last stage before final, unless the gate
    refused (ruling 8; R3). The three figures of 6a are taken first, so
    Stop to final keeps its meaning; the note's seconds are a fourth."""
    c.final.figures = figures(c)
    # The refusal is read from the stored warnings, not from this object's memory: a consultation
    # that went on from this stage after a restart was judged by an object that is gone (ruling 8).
    c.final.refused = gate.refused_in(c.rows.warnings(c.id))
    if c.final.refused or c.notes is None:
        return
    started = c.timer()
    note.draft(c.llm, c.rows, c.notes, c.audit, c.id, "stop")
    c.final.figures["note_s"] = round(c.timer() - started, 2)


STEPS_AFTER = {"checks": checks, "gate": judge, "drug_name": drug_names, "note": draft_note}
NEXT = {"checks": "gate", "gate": "drug_name", "drug_name": "note", "note": None}


# ------------------------------------------------------- two: the lines

def final_lines(c: Consultation) -> None:
    """The door's stop, and the lines written as the choice gave them,
    labels unsure until the answer (V1_LESSONS 1.7). A failed stop leaves
    the live lines as the transcript with the reason as a warning."""
    final = c.speech_door.stop(speakers=c.speakers_given) if c.speech.state == "open" else None
    with c.lock:
        c.speech = type(c.speech)("stopped")
        # The lines of the sessions that ended before the one in use, as they were shown: a session that was lost
        # can give nothing more, so what it gave live is what it gave (15.13, ruling 29). None for one session.
        earlier = [(s.line, s.refused, s.session) for s in c.transcript.shown if s.session < c.session]
        if final is not None and final.ok:
            at = c.session_offset_s
            heard = (earlier + [(moved(line, at), False, c.session) for line in final.lines]
                     + [(moved(r.line, at), True, c.session) for r in final.refused])
            revised = {(c.session, r.id) for r in final.revisions if r.applied}
            c.rows.set(c.id, stop_raw=json.dumps(list(final.raw), ensure_ascii=False))
        else:
            heard = [(s.line, s.refused, s.session) for s in c.transcript.shown]
            revised = {(s.session, s.line.id) for s in c.transcript.shown if s.revised}
            reason = (final.detail or final.failure) if final is not None else (c.speech_failure or c.speech.reason or "")
            c.rows.add_warning(c.id, "speech_failed", detail=reason)
        # Where a session was lost, the loudness is the whole recording's, so that speech no session heard is found
        # by the check for missing speech; with one unbroken session it is the door's own, as before.
        whole = c.loudness is not None and bool(c.rows.sessions(c.id))
        c.rows.set(c.id, loudness=json.dumps(_windows(c.loudness.windows if whole else c.speech_door.loudness_windows)))
        write_lines(c, heard, revised)


def write_lines(c: Consultation, heard: list[tuple[Line, bool, int]], revised: set) -> None:
    n = 0
    rows = []
    for line, refused, session in heard:
        n = n if refused else n + 1
        rows.append({**line_as_row(line, None if refused else n, "unsure", refused=refused, unsure=True,
                                   revised=(session, line.id) in revised), "session": session})
    c.rows.add_transcript_lines(c.id, rows)


def lost_stretches(c: Consultation) -> list[tuple[float, float]]:
    """Each stretch of the recording that no session heard, by its times
    (ruling 29): from the second a session was lost to the second the
    next one opened, or to the recording's end."""
    row = c.rows.get(c.id)
    end = len(json.loads(row["loudness"] or "[]")) * WINDOW_S
    sessions = c.rows.sessions(c.id)
    found = []
    for index, session in enumerate(sessions):
        if session["lost_at_s"] is None:
            continue
        until = sessions[index + 1]["opened_at_s"] if index + 1 < len(sessions) else max(end, session["lost_at_s"])
        found.append((round(session["lost_at_s"], 1), round(until, 1)))
    return found


def _windows(windows: list[float]) -> list[float | None]:
    return [None if w == -math.inf else round(w, 1) for w in windows]


# ---------------------------------------------------- three: who spoke

def wait_for_answer(c: Consultation) -> bool:
    """No limit on a human answer that changes the transcript (2.2). False
    only when the app closed while waiting. The labels are set session by
    session: each session's lines by that session's own answer, because a
    service names its speakers afresh in each (ruling 29; 15.9, ruling 4).
    A line never takes a speaker from the answer given for another session."""
    while c.doctor_speaker is None:
        c.answer_event.wait()
        if c.closed and c.doctor_speaker is None:
            return False
    rows = c.rows.transcript_lines(c.id)
    asked = speakers.sessions_to_ask(rows)
    answers = c.doctor_speakers or {s["n"]: s["doctor_speaker"] for s in c.rows.sessions(c.id) if s["doctor_speaker"]}
    if len(asked) <= 1:
        c.rows.set_labels(c.id, speakers.labels_from_answer(rows, c.doctor_speaker))
        return True
    labels = {}
    for session in sorted({r["session"] for r in rows}):
        labels.update(speakers.labels_from_answer([r for r in rows if r["session"] == session],
                                                  answers.get(session, speakers.CANNOT_TELL)))
    c.rows.set_labels(c.id, labels)
    return True


def answer(c: Consultation, doctor_speaker: str) -> bool:
    """The page's answer where one session is asked. False when it is not
    the time, or the speaker is not one the choice gave (and not I cannot
    tell), or more than one session waits for its own answer."""
    asked = speakers.sessions_to_ask(c.rows.transcript_lines(c.id))
    if len(asked) > 1:
        return False
    return answer_parts(c, {(asked[0] if asked else 1): doctor_speaker})


def answer_parts(c: Consultation, answers: dict[int, str]) -> bool:
    """One answer for each session that is asked, taken together or not at
    all: each must be a speaker that its own session gave, or I cannot tell."""
    with c.lock:
        if c.state != STOPPING or c.stop_stage != "who_spoke" or c.doctor_speaker is not None:
            return False
        rows = c.rows.transcript_lines(c.id)
        asked = speakers.sessions_to_ask(rows) or [1]
        if sorted(answers) != sorted(asked):
            return False
        for session, picked in answers.items():
            allowed = {o["speaker"] for o in speakers.options([r for r in rows if r["session"] == session])} | {speakers.CANNOT_TELL}
            if picked not in allowed:
                return False
        c.doctor_speakers = dict(answers)
        for session, picked in answers.items():
            c.rows.answer_session(c.id, session, picked)
        c.doctor_speaker = answers[asked[0]]
        c.rows.set(c.id, doctor_speaker=c.doctor_speaker)
        said = c.doctor_speaker if len(asked) == 1 else ", ".join(f"part {n} {answers[s]}" for n, s in enumerate(asked, start=1))
        c.audit.record("speakers.answered", f"consultation {c.id}: {said}")
        c._changed()
    c.answer_event.set()
    return True


# ------------------------------------------------------- the final page

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
                     p.door_for(row["id"]), p.consultations, p.audit, p.settings.data_folder, p.clock, on_stop=p.finaliser, notes=p.notes,
                     converter=p.converter, guidelines=p.guidelines, whole=p.whole)
    c.state = STOPPING
    stage = STAGE_GONE.get(row["stop_stage"], row["stop_stage"])
    c.stop_stage = stage if stage in STAGES[1:] else "who_spoke"
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
