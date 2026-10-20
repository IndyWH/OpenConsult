"""Stop in order (spec 15.10, Stop in order; rulings 7 and 14; 15.9
rulings 4 and 17; R2; V1_LESSONS 1.7, 1.12, 2.2; 10.4; review point 3).
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
from openconsult.consult.live import FINAL, STOPPING
from openconsult.llm import jobs as app_jobs
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


def test_ruling_7_who_spoke_is_asked_once_waits_without_limit_and_the_check_runs_after_the_answer(tmp_path, clock):
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
        # The check ran after the answer, on the numbered lines with no labels, in the words of the details.
        call = r.engine.calls_for("label_check")[0]
        assert call.user == model_lines.lines_text([{"n": n, "text": t} for n, t in enumerate(
            ["What brings you in today?", "A pain in my chest.", "Yes.", "Tell me more."], start=1)])
        assert call.system == loader.prompt("label_check") and "S1" not in call.user
        final = r.rows.transcript_lines(c.id)
        assert [(x["n"], x["label"], x["changed_by_check"], x["unsure"]) for x in final] == [
            (1, "doctor", 0, 0),        # the answer and the check agree: the label stands
            (2, "patient", 0, 0),
            (3, "patient", 0, 1),       # no first reading: the check's label, still shown unsure (ruling 14)
            (4, "doctor", 0, 1)]        # the check said unsure: shown unsure, the label as it stood
        assert [x["text"] for x in final] == [x["text"] for x in rows]     # not one word differs
        assert r.rows.model_calls(c.id)[-1]["job"] == "label_check"
    finally:
        r.close()


def test_ruling_7_a_changed_label_is_marked_and_a_refused_or_failed_check_changes_nothing(tmp_path, clock):
    swapped = {"lines": [{"line": 1, "label": "patient"}, {"line": 2, "label": "doctor"}, {"line": 3, "label": "unsure"},
                         {"line": 4, "label": "patient"}]}
    r, c = room_stopped(tmp_path, clock, check=swapped)
    try:
        stop.answer(c, "S1")
        assert until(lambda: c.state == FINAL)
        final = r.rows.transcript_lines(c.id)
        assert [(x["label"], x["changed_by_check"], x["unsure"]) for x in final] == [
            ("patient", 1, 0), ("doctor", 1, 0), ("unsure", 0, 1), ("patient", 1, 0)]
        assert not [w for w in r.rows.warnings(c.id) if w["kind"].startswith("label_check")]
    finally:
        r.close()
    # The twin: a reply that misses a line, repeats one or names one that is not there is refused whole.
    for bad, detail in [({"lines": CHECK["lines"][:3]}, "missing 4"),
                        ({"lines": CHECK["lines"] + [{"line": 2, "label": "doctor"}]}, "repeated 2"),
                        ({"lines": CHECK["lines"] + [{"line": 9, "label": "doctor"}]}, "unknown 9")]:
        r, c = room_stopped(tmp_path / detail.replace(" ", "_"), clock, check=bad)
        try:
            stop.answer(c, "S2")
            assert until(lambda: c.state == FINAL)
            final = r.rows.transcript_lines(c.id)
            assert [(x["label"], x["changed_by_check"]) for x in final] == [("patient", 0), ("doctor", 0), ("unsure", 0), ("patient", 0)]
            warning = [w for w in r.rows.warnings(c.id) if w["kind"].startswith("label_check")][0]
            assert warning["kind"] == "label_check_refused" and detail in warning["detail"]
        finally:
            r.close()
    # A call that fails: the labels stand, the warning says why, nothing is asked twice.
    from openconsult.llm.engine import EngineTimeout
    r, c = room_stopped(tmp_path / "failed", clock, engine=FakeEngine({"label_check": [EngineTimeout("no answer")]}))
    try:
        stop.answer(c, speakers.CANNOT_TELL)
        assert until(lambda: c.state == FINAL)
        assert all(x["label"] == "unsure" and x["unsure"] for x in r.rows.transcript_lines(c.id))
        assert [w["kind"] for w in r.rows.warnings(c.id) if w["kind"].startswith("label_check")] == ["label_check_failed"]
        assert len(r.engine.calls_for("label_check")) == 1
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
    assert words.FINAL_TITLE in final and "[1] Doctor" in final and "[3] Patient" in final and words.LABEL_UNSURE in final
    assert not app.state.parts.logins.consultation_running


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
        assert words.FINAL_TITLE in text_of(client2.get(f"/consultations/{cid}"))
    assert rows.get(1)["final_at"] and rows.get(2)["final_at"] and rows.in_state("stopping") == []
    assert words.HOME_WAITING not in text_of(client2.get("/"))
    assert not app2.state.parts.logins.consultation_running


