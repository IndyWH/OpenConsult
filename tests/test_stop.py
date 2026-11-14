"""Stop in order (spec 15.10, the details of step 6c: Stop, in order, as it
now stands; ruling 7; 15.9 rulings 17 and 37; R2; V1_LESSONS 1.7, 1.12,
2.2; 10.4; review point 3). The check of who spoke no longer runs at
Stop: its tests are in test_who_check.py.
Made-up doors, made-up replies; the words a model would say are never
asserted, only what code does with a reply's numbers and labels."""

import hashlib
import json
import time

import pytest

from openconsult import words
from openconsult.app import build_app
from openconsult.bench.speech import jobs as bench_jobs
from openconsult.bench.speech import model_lines
from openconsult.consult import labels, speakers, stop
from openconsult.consult.live import FINAL, SPINNING, STOPPING
from openconsult.llm import jobs as app_jobs
from openconsult.llm.engine import EngineTimeout
from openconsult.prompts import loader
from openconsult.settings import store
from openconsult.speech.choices import NEMOTRON
from openconsult.speech.door import Door as SpeechDoor
from tests.conftest import ORIGIN, PORT, browser, log_in, refusal_on, set_up, text_of
from tests.fakes import FakeEngine, MadeUpWorker
from tests.test_live import CAPTURE, LOUD, Room, live_seg
from tests.test_sound import socket_to
from tests.test_start import PATIENT, TICKS

LINES = [live_seg(1, 0.0, 0.5, "What brings you in today?", "S1"), live_seg(2, 0.6, 1.2, "A pain in my chest.", "S2"),
         live_seg(3, 1.3, 1.5, "Yes.", None), live_seg(4, 1.6, 2.0, "Tell me more.", "S1")]
CHECK = {"lines": [{"line": 1, "label": "doctor"}, {"line": 2, "label": "patient"}, {"line": 3, "label": "patient"},
                   {"line": 4, "label": "unsure"}]}


# The wait for a step a slow runner may take long over: GitHub's Windows
# run of 30 Oct 2026 took 31 minutes for the suite and the retention test's
# wait for the conversion step timed out at 10 s (15.12 ruling 28).
SLOW_RUNNER_S = 60.0


def until(condition, timeout_s=10.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def room_stopped(tmp_path, clock, check=CHECK, worker=None, engine=None):
    """A consultation fed four lines and stopped, waiting at who-spoke."""
    worker = worker or MadeUpWorker(live=[LINES, [], [], []])
    engine = engine or FakeEngine({"label_check": [check]})
    r = Room(tmp_path, clock, worker=worker, engine=engine)
    c = r.consultation
    c.on_stop = stop.finalise
    c.begin_sound(CAPTURE)
    for _ in range(4):
        c.sound(LOUD)
    c.wait_for_pass()
    assert c.stop()
    assert until(lambda: c.stop_stage == "who_spoke")
    return r, c


def test_ruling_7_15_9_ruling_37_who_spoke_is_asked_once_waits_without_limit_and_no_check_of_who_spoke_runs_at_stop(tmp_path, clock):
    r, c = room_stopped(tmp_path, clock)
    try:
        # The lines at Stop are written as the choice gave them, labels unsure until the answer (1.7).
        rows = r.rows.transcript_lines(c.id)
        assert [(x["n"], x["raw_speaker"], x["label"], x["unsure"]) for x in rows] == [
            (1, "S1", "unsure", 1), (2, "S2", "unsure", 1), (3, None, "unsure", 1), (4, "S1", "unsure", 1)]
        assert speakers.options(rows) == [{"speaker": "S1", "n": 1, "words": "What brings you in today?"},
                                          {"speaker": "S2", "n": 2, "words": "A pain in my chest."}]
        clock.advance(hours=5)                                     # no limit on a human answer (2.2)
        time.sleep(0.2)
        assert c.stop_stage == "who_spoke" and r.engine.calls_for("label_check") == []
        assert not stop.answer(c, "S9")                            # not a speaker the choice gave
        assert stop.answer(c, "S1") and not stop.answer(c, "S2")   # once
        assert until(lambda: c.state == FINAL)
        assert r.audit.lines()[1].event == "speakers.answered" or any(l.event == "speakers.answered" for l in r.audit.lines())
        assert r.rows.get(c.id)["doctor_speaker"] == "S1"
        # 15.9 ruling 37: no check of who spoke is called at Stop; the labels are those the answer set, and not one word differs.
        assert r.engine.calls_for("label_check") == [] and "label_check" not in [row["job"] for row in r.rows.model_calls(c.id)]
        final = r.rows.transcript_lines(c.id)
        assert [(x["n"], x["label"], x["changed_by_check"], x["unsure"]) for x in final] == [
            (1, "doctor", 0, 0),        # S1, the speaker the doctor picked
            (2, "patient", 0, 0),       # the other speaker
            (3, "unsure", 0, 1),        # no speaker from the choice: unsure, never guessed (15.9 ruling 4)
            (4, "doctor", 0, 0)]
        assert [x["text"] for x in final] == [x["text"] for x in rows]
        assert r.rows.check_runs(c.id) == [] and "label_check" not in stop.STAGES and "label_check" not in SPINNING
    finally:
        r.close()


def test_15_9_ruling_17_the_label_check_prompt_is_one_file_with_the_approved_bytes_and_the_job_has_the_benchs_limits():
    assert hashlib.sha256(loader.prompt_bytes("label_check")).hexdigest() == loader.APPROVED_BYTES["label_check"]
    assert loader.APPROVED_BYTES["label_check"] == bench_jobs.PROMPT_SHA256["label_check"]
    assert bench_jobs.prompt_bytes("label_check") == loader.prompt_bytes("label_check")       # the bench reads the same file
    assert bench_jobs.form_of("label_check") == loader.form("label_check")
    assert not (bench_jobs.PROMPTS / "label_check.prompt.txt").exists()
    job = app_jobs.job("label_check")
    assert (job.max_tokens, job.timeout_s, job.prompt, job.form) == (3000, 120.0, "label_check", "label_check")
    # The text the app sends is the bench's text, word for word, for a made-up page.
    rows = [{"n": 1, "text": "made up one"}, {"n": 2, "text": "made up two"}]
    assert labels.lines_text(rows) == model_lines.lines_text(rows)
    assert labels.lines_text(rows) == "TRANSCRIPT:\n[1] made up one\n[2] made up two"
    assert bench_jobs.check_labels is labels.check_labels


def test_10_4_a_worker_that_dies_at_stop_is_reported_plainly_and_the_live_lines_are_the_transcript(tmp_path, clock):
    worker = MadeUpWorker(live=[LINES, [], [], []], die_after=6)          # open, four pieces, then dead at stop
    r, c = room_stopped(tmp_path, clock, worker=worker)
    try:
        rows = r.rows.transcript_lines(c.id)
        assert [x["text"] for x in rows] == [line["text"] for line in LINES]
        warning = r.rows.warnings(c.id)[0]
        assert warning["kind"] == "speech_failed" and "exit code 3" in warning["detail"]
        assert worker.starts == 1
    finally:
        r.close()


# ---------------------------------------------------------- through the pages

def app_on(tmp_path, clock, machine, worker):
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=lambda: worker, installed=lambda: True)}
    app = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock,
                    engines={"vllm": FakeEngine(version=None), "ollama": FakeEngine({"label_check": [CHECK, CHECK, CHECK]})},
                    doors=doors)
    client = browser(app)
    return app, client


def test_R2_R15_the_who_spoke_page_asks_once_and_the_answer_is_audited(tmp_path, clock, machine):
    app, client = app_on(tmp_path, clock, machine, MadeUpWorker(live=[LINES]))
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    with socket_to(client, "/consultations/1/sound") as socket:
        socket.receive_text()
        socket.send_text(json.dumps(CAPTURE_MESSAGE))
        socket.send_bytes(LOUD)
        socket.receive_text()
    consultation = app.state.parts.running[1]
    assert until(lambda: len(consultation.transcript.heard) == 4)
    client.post("/consultations/1/stop")
    assert until(lambda: consultation.stop_stage == "who_spoke")
    page = text_of(client.get("/consultations/1"))
    assert words.WHO_SPOKE_TITLE in page and 'http-equiv="refresh"' not in page
    assert words.SPEAKER_OPTION.format(n=1, words="What brings you in today?") in page
    assert words.SPEAKER_OPTION.format(n=2, words="A pain in my chest.") in page and words.CANNOT_TELL in page
    refused = client.post("/consultations/1/speakers", data={})
    assert refused.status_code == 400 and refusal_on(refused.text, "answer") == words.PICK_ONE
    done = client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert done.status_code == 303 and done.headers["location"] == "/consultations/1"
    assert until(lambda: consultation.state == FINAL)
    again = client.post("/consultations/1/speakers", data={"speaker": "S2"})
    assert again.status_code == 303 and again.headers["location"] == "/consultations/1"     # answered already: the page moved on
    assert app.state.parts.consultations.get(1)["doctor_speaker"] == "S1"
    events = [line.event for line in app.state.parts.audit.lines()]
    assert events.index("consultation.final") < events.index("speakers.answered") < events.index("consultation.stopped")
    assert "Stop to final" in app.state.parts.audit.lines()[0].detail
    final = text_of(client.get("/consultations/1"))
    assert words.REVIEW_TITLE in final and "[1] Doctor" in final and "[2] Patient" in final and "[3] Unsure" in final
    assert words.LABEL_UNSURE in final and app.state.parts.consultations.check_runs(1) == []        # no check of who spoke at Stop
    assert not app.state.parts.logins.consultation_running
    consultation.close()                                     # the Stop thread's conversion step ends before the test does


CAPTURE_MESSAGE = {"type": "capture", "echo_cancellation": False, "noise_suppression": False, "auto_gain": False, "rate": 48000}


def test_1_12_a_consultation_left_live_or_stopping_at_a_restart_is_carried_on(tmp_path, clock, machine):
    # Two consultations: one left live with sound and lines, one left stopping at who-spoke.
    app, client = app_on(tmp_path, clock, machine, MadeUpWorker(live=[LINES, [], LINES]))
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    first = app.state.parts.running[1]
    first.begin_sound(CAPTURE)
    first.sound(LOUD)
    first.sound(LOUD)
    first.stop()
    assert until(lambda: first.stop_stage == "who_spoke")
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/2", data=TICKS)
    second = app.state.parts.running[2]
    second.begin_sound(CAPTURE)
    second.sound(LOUD)
    assert len(second.transcript.heard) == 4 and second.state == "live"
    for c in (first, second):
        c.close()
    # The app starts again on the same folder.
    app2, client2 = app_on(tmp_path, clock, machine, MadeUpWorker())
    rows = app2.state.parts.consultations
    assert rows.in_state("live") == []
    assert [r["id"] for r in rows.in_state("stopping")] == [1, 2]
    assert rows.get(2)["stop_stage"] == "who_spoke" and rows.warnings(2)[0]["detail"] == words.APP_RESTARTED
    assert [x["text"] for x in rows.transcript_lines(2)] == [line["text"] for line in LINES]
    assert sorted(app2.state.parts.running) == [1, 2] and app2.state.parts.logins.consultation_running
    log_in(client2)
    home = text_of(client2.get("/"))
    assert words.HOME_WAITING in home and home.count(words.CONTINUE_CONSULTATION) == 2
    for cid in (1, 2):
        page = text_of(client2.get(f"/consultations/{cid}"))
        assert words.WHO_SPOKE_TITLE in page
        assert client2.post(f"/consultations/{cid}/speakers", data={"speaker": "S2"}).status_code == 303
        assert until(lambda: app2.state.parts.running[cid].state == FINAL)
        assert words.REVIEW_TITLE in text_of(client2.get(f"/consultations/{cid}"))    # the review page from the tables (6b)
    assert rows.get(1)["final_at"] and rows.get(2)["final_at"] and rows.in_state("stopping") == []
    assert words.HOME_WAITING not in text_of(client2.get("/"))
    assert not app2.state.parts.logins.consultation_running
    for c in app2.state.parts.running.values():
        c.close()




def test_1_12_15_9_ruling_37_a_consultation_left_at_the_stage_of_the_check_goes_on_from_the_checks_for_missing_speech_with_no_check(tmp_path, clock, machine):
    # The details of step 6c, Stop in order: the stage label_check is gone; one found there at a restart goes on with no check of who spoke.
    app, client = app_on(tmp_path, clock, machine, MadeUpWorker(live=[LINES]))
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    first = app.state.parts.running[1]
    first.begin_sound(CAPTURE)
    first.sound(LOUD)
    first.stop()
    assert until(lambda: first.stop_stage == "who_spoke")
    rows = app.state.parts.consultations
    # As an app before 6c left it when it closed during the check: the answer taken, its labels set, the stage label_check.
    rows.set_labels(1, speakers.labels_from_answer(rows.transcript_lines(1), "S1"))
    rows.set(1, doctor_speaker="S1", stop_stage="label_check")
    first.close()
    engine = FakeEngine({"label_check": [CHECK]})
    doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=MadeUpWorker, installed=lambda: True)}
    app2 = build_app(store.build(tmp_path, PORT), machine=machine, clock=clock, engines={"vllm": FakeEngine(version=None), "ollama": engine}, doors=doors)
    client2 = browser(app2)
    resumed = app2.state.parts.running[1]
    assert resumed.stop_stage == "checks" and resumed.doctor_speaker == "S1"
    log_in(client2)
    client2.get("/consultations/1")
    assert until(lambda: resumed.state == FINAL)
    rows2 = app2.state.parts.consultations
    assert engine.calls_for("label_check") == [] and rows2.check_runs(1) == []
    assert [(x["label"], x["changed_by_check"], x["unsure"]) for x in rows2.transcript_lines(1)] == [
        ("doctor", 0, 0), ("patient", 0, 0), ("unsure", 0, 1), ("doctor", 0, 0)]
    assert words.REVIEW_TITLE in text_of(client2.get("/consultations/1"))
    resumed.close()



def test_ruling_8_1_12_the_gates_refusal_is_remembered_after_a_restart_at_the_note_stage_and_no_note_is_drafted(tmp_path, clock, machine):
    # The plan review of 6c, point 3: the note stage reads the refusal from the stored warnings, not from an object that is gone.
    from openconsult.consult import gate
    found = {}
    for name, live in (("refused", [live_seg(1, 0.0, 0.5, "Hello.", "S1")]), ("judged_fit", LONG_LINES)):
        folder = tmp_path / name
        app, client = app_on(folder, clock, machine, MadeUpWorker(live=[live]))
        set_up(client)
        log_in(client)
        client.post("/patients", data=PATIENT)
        client.post("/consultations/start/1", data=TICKS)
        first = app.state.parts.running[1]
        first.begin_sound(CAPTURE)
        first.sound(LOUD)
        first.stop()
        assert until(lambda: first.stop_stage == "who_spoke")
        # As the app leaves it when it closes after the gate and before the note: the answer, the gate's warnings, the stage note.
        rows = app.state.parts.consultations
        rows.set_labels(1, speakers.labels_from_answer(rows.transcript_lines(1), "S1"))
        verdict = gate.judge([r for r in rows.transcript_lines(1) if r["n"] is not None], first.speech_door.declares, "made-up")
        for warning in verdict.warnings:
            rows.add_warning(1, **warning)
        rows.set(1, doctor_speaker="S1", stop_stage="note")
        first.close()
        engine = FakeEngine({"note": [NOTE]})
        doors = {NEMOTRON.name: SpeechDoor(NEMOTRON, make_worker=MadeUpWorker, installed=lambda: True)}
        app2 = build_app(store.build(folder, PORT), machine=machine, clock=clock, engines={"vllm": FakeEngine(version=None), "ollama": engine}, doors=doors)
        client2 = browser(app2)
        resumed = app2.state.parts.running[1]
        assert resumed.stop_stage == "note" and resumed.final.refused is False          # the new object has judged nothing
        log_in(client2)
        client2.get("/consultations/1")
        assert until(lambda: resumed.state == FINAL)
        found[name] = (verdict.refused, len(engine.calls_for("note")), len(app2.state.parts.notes.drafts(1)), resumed.final.refused,
                       words.NOTE_GATE_REFUSED.split(":")[0] in text_of(client2.get("/consultations/1")))
        resumed.close()
    assert found["refused"] == (True, 0, 0, True, True)         # no note call, no draft, and the page says why (R3)
    assert found["judged_fit"] == (False, 1, 1, False, False)   # the twin: a transcript the gate passed gets its note



NOTE = {"reasoning": "made up.", "subjective": [{"text": "made up history", "turns": [1]}], "objective": [],
        "assessment": [{"text": "made up impression", "turns": [0, 3]}], "plan": [{"text": "uncited plan", "turns": [9]}]}


LONG_LINES = [live_seg(1, 0.0, 0.5, "What brings you in today?", "S1"), live_seg(2, 0.6, 1.2, "A pain in my chest. " + "word " * 60, "S2"),
              live_seg(3, 1.3, 1.5, "Yes.", None), live_seg(4, 1.6, 2.0, "Tell me more.", "S1")]


def test_the_note_is_drafted_at_the_end_of_stop_after_the_gate_with_its_stamp_and_a_fourth_figure(tmp_path, clock):
    r, c = room_stopped(tmp_path, clock, worker=MadeUpWorker(live=[LONG_LINES, [], [], []]),
                        engine=FakeEngine({"label_check": [CHECK], "note": [NOTE]}))
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        assert stop.STAGES[-1] == "note" and stop.NEXT["gate"] == "note" and "note" in SPINNING
        draft = r.notes.current_draft(c.id)
        assert (draft["n"], draft["asked_by"], draft["entries_total"], draft["entries_cited"], draft["refused"], draft["failure"]) == (
            1, "stop", 3, 2, 0, None)
        assert (draft["engine"], draft["model_tag"], draft["model_digest"]) == ("made-up", "made-up/tag", "d")     # the row's stamp (R20)
        assert draft["prompt_sha256"] == loader.APPROVED_BYTES["note"] and draft["call_id"] == r.rows.model_calls(c.id)[-1]["id"]
        assert draft["transcript"].startswith("TRANSCRIPT:\n[0] Doctor: What brings you in today?\n[1] Patient: A pain in my chest. word")
        # 15.9 ruling 37: written from the labels as the answer set them; the line with no speaker is a turn of its own.
        assert draft["transcript"].endswith("\n[2] Unknown: Yes.\n[3] Doctor: Tell me more.") and r.engine.calls_for("label_check") == []
        entries = r.notes.entries(draft["id"])
        assert [(e["section"], e["lines"], e["uncited"]) for e in entries] == [
            ("subjective", [2], 0), ("assessment", [1, 4], 0), ("plan", [], 1)]      # four turns; turn 9 does not exist
        assert "note" in [row["job"] for row in r.rows.model_calls(c.id)] and "The patient is" not in r.engine.calls_for("note")[0].user
        assert c.final.figures["note_s"] is not None and "Note" in r.audit.lines()[0].detail
        assert any(line.event == "note.drafted" for line in r.audit.lines())
    finally:
        r.close()


def test_R3_ruling_8_the_gates_refusal_drafts_no_note(tmp_path, clock):
    short = MadeUpWorker(live=[[live_seg(1, 0.0, 0.5, "Hello.", "S1")], [], [], []])
    r, c = room_stopped(tmp_path, clock, worker=short, check={"lines": [{"line": 1, "label": "doctor"}]},
                        engine=FakeEngine({"label_check": [{"lines": [{"line": 1, "label": "doctor"}]}], "note": [NOTE]}))
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        assert c.final.refused and r.notes.drafts(c.id) == [] and r.engine.calls_for("note") == []
        assert c.final.figures.get("note_s") is None
    finally:
        r.close()


def test_R30_10_4_a_failed_note_call_is_said_plainly_and_nothing_is_asked_a_second_time_by_itself(tmp_path, clock):
    r, c = room_stopped(tmp_path, clock, worker=MadeUpWorker(live=[LONG_LINES, [], [], []]),
                        engine=FakeEngine({"label_check": [CHECK], "note": [EngineTimeout("no answer")]}))
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        draft = r.notes.current_draft(c.id)
        assert draft["failure"].startswith("too_slow") and draft["entries_total"] == 0 and r.notes.entries(draft["id"]) == []
        assert len(r.engine.calls_for("note")) == 1 and r.audit.lines()[1].event == "note.failed"
    finally:
        r.close()


def test_the_small_fix_of_7b_no_thread_of_the_consultation_outlives_it(tmp_path, clock, machine):
    """15.11, A small fix for 7b: two tests left the Stop thread converting
    after the database was closed. close() now joins the Stop thread and
    the pass pool, and the app's shutdown closes every consultation."""
    import threading

    def mine(cid):
        return [t.name for t in threading.enumerate() if t.name.startswith((f"stop-{cid}", f"consultation-{cid}"))]

    r, c = room_stopped(tmp_path, clock)
    assert mine(c.id) and c._stop_thread.is_alive()                  # waiting at who-spoke
    stop.answer(c, "S1")
    assert until(lambda: c.state == FINAL)
    c.close()
    assert not mine(c.id) and not c._stop_thread.is_alive()
    r.db.close()                                                     # nothing writes after this
    # A consultation closed while it waits at who-spoke: the thread returns at once and the stage is kept.
    r2, c2 = room_stopped(tmp_path / "waiting", clock)
    c2.close()
    assert not mine(c2.id) and c2.stop_stage == "who_spoke"
    r2.db.close()
    # Through the app: the lifespan's shutdown closes every running consultation.
    app, client = app_on(tmp_path / "app", clock, machine, MadeUpWorker(live=[LINES]))
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    consultation = app.state.parts.running[1]
    consultation.begin_sound(CAPTURE)
    consultation.sound(LOUD)
    consultation.wait_for_pass()
    client.post("/consultations/1/stop")
    assert until(lambda: consultation.stop_stage == "who_spoke")
    client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert until(lambda: consultation.state == FINAL)
    with browser(app):                                               # the lifespan runs: start, then shutdown
        pass
    assert consultation.closed and not mine(1)


def test_ruling_28_R15_the_who_spoke_page_changes_after_the_answer_and_a_second_answer_is_refused(tmp_path, clock, machine):
    """2 Nov 2026, consultations 7 and 8: the question stood on screen after
    the answer, so the owner picked twice. The finaliser is held here, so
    the stage stays who_spoke under the test's hand and the moment after
    the answer is pinned, not raced."""
    app, client = app_on(tmp_path, clock, machine, MadeUpWorker(live=[LINES]))
    set_up(client)
    log_in(client)
    client.post("/patients", data=PATIENT)
    client.post("/consultations/start/1", data=TICKS)
    c = app.state.parts.running[1]
    c.on_stop = None
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    c.wait_for_pass()
    assert until(lambda: len(c.transcript.heard) == 4)
    client.post("/consultations/1/stop")
    stop.final_lines(c)
    c.set_stage("who_spoke")
    page = client.get("/consultations/1")
    assert words.WHO_SPOKE_TITLE in text_of(page) and 'type="radio"' in page.text and 'http-equiv="refresh"' not in page.text
    done = client.post("/consultations/1/speakers", data={"speaker": "S1"})
    assert done.status_code == 303 and done.headers["location"] == "/consultations/1"
    assert c.doctor_speaker == "S1" and app.state.parts.consultations.get(1)["doctor_speaker"] == "S1"
    # The page after the answer, the stage still who_spoke: it says so, the choices are gone, and it moves by itself.
    after = client.get("/consultations/1")
    text = text_of(after)
    assert words.STAGE_LINES["answered"] in text and words.WHO_SPOKE_TITLE not in text
    assert 'type="radio"' not in after.text and 'id="answer"' not in after.text
    assert 'http-equiv="refresh"' in after.text and 'class="spinner"' in after.text and 'class="spinner" hidden' not in after.text
    assert c.page_state()["answered"] and c.page_state()["spinning"] == "answered"
    again = client.post("/consultations/1/speakers", data={"speaker": "S2"})
    assert again.status_code == 303 and c.doctor_speaker == "S1"                        # refused: the first answer stands
    assert [line.event for line in app.state.parts.audit.lines()].count("speakers.answered") == 1
    assert words.WHO_SPOKE_TITLE not in text_of(client.get("/consultations/1"))
    c.close()
