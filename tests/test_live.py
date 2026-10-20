"""The live consultation as a class (spec 5.1; 15.10; R2, R12, R18, R30;
11.5 rule 3; ruling 10; 10.4; V1_LESSONS 5.2, 5.3). A made-up worker
stands behind the speech door and a made-up engine behind the language
model door; the sound is made by code; no model speaks."""

import threading
from datetime import date

import pytest

from openconsult.consult.consultations import Consultations
from openconsult.consult.live import FINAL, LIVE, OVER, STOPPING, WITHIN, Capture, Consultation, clock_state
from openconsult.db import open_database
from openconsult.llm.door import Door
from openconsult.llm.engine import EngineUnreachable
from openconsult.llm.record import ModelCalls
from openconsult.patients.audit import Audit
from openconsult.patients.patients import Patients
from openconsult.speech.choices import NEMOTRON
from openconsult.speech.door import Door as SpeechDoor
from tests.fakes import ASSESSMENT, FakeEngine, MadeUpWorker
from tests.test_loudness import sine

RATE = 48000
LOUD = sine(0.25, -20.0, rate=RATE)
CAPTURE = Capture(False, False, False, RATE)


def live_seg(number, start, end, text, speaker="S1"):
    return {"id": number, "start": start, "end": end, "text": text, "speaker": speaker, "confidence": None}


class Room:
    """One consultation with its doors and rows, built fresh for a test."""

    def __init__(self, tmp_path, clock, worker=None, engine=None, intended=15):
        self.db = open_database(tmp_path / "openconsult.db")
        self.audit = Audit(self.db, clock)
        self.rows = Consultations(self.db, clock)
        patient = Patients(self.db, self.audit, clock).add("Made-up", date(1990, 10, 21), "F")
        self.worker = worker or MadeUpWorker()
        self.engine = engine or FakeEngine()
        self.speech = SpeechDoor(NEMOTRON, make_worker=lambda: self.worker, installed=lambda: True)
        self.llm = Door(self.engine, ModelCalls(self.db, clock))
        cid = self.rows.start(patient.id, intended, "nemotron", "made-up", "0.0", "made-up/tag", "d", 2)
        self.consultation = Consultation(cid, patient, intended, clock(), self.speech, self.llm, self.rows, self.audit,
                                         tmp_path / "data", clock)

    def close(self):
        self.consultation.close()
        self.db.close()


@pytest.fixture
def room(tmp_path, clock):
    made = None

    def build(**kwargs):
        nonlocal made
        made = Room(tmp_path, clock, **kwargs)
        return made

    yield build
    if made:
        made.close()


def test_R12_every_pass_reads_the_whole_transcript_as_it_stands_with_the_stale_names(room):
    r = room(worker=MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "First made-up line.")], [],
                                       [live_seg(2, 0.3, 0.5, "x" * 160, "S2")], []]))
    c = r.consultation
    c.begin_sound(CAPTURE)
    for _ in range(4):
        c.sound(LOUD)
        c.wait_for_pass()
    assessments = r.engine.calls_for("assessment")
    assert len(assessments) == 2 and c.passes.n == 2
    assert assessments[0].user.endswith("First made-up line.")                      # the first pass on the first line
    assert assessments[1].user.endswith("First made-up line.\n" + "x" * 160)       # the whole transcript, no speaker word
    assert "Made-up condition A\nMade-up condition B" in assessments[1].user      # the stale names
    assert "S1" not in assessments[1].user and all(call.user.startswith("The patient is a 35-year-old woman.") for call in r.engine.calls)
    passes = r.rows.passes(c.id)
    assert passes[0]["transcript"] == "First made-up line."
    assert passes[1]["transcript"] == "First made-up line.\n" + "x" * 160 and passes[1]["shown"] == 1
    assert sorted(r["job"] for r in r.rows.model_calls(c.id)) == ["alarm", "alarm", "assessment", "assessment"]


def test_11_5_rule_3_the_three_microphone_values_and_the_rate_reach_the_record_and_the_door(room):
    r = room()
    c = r.consultation
    c.begin_sound(Capture(False, True, None, RATE))
    row = r.rows.get(c.id)
    assert (row["echo_cancellation"], row["noise_suppression"], row["auto_gain"], row["sample_rate"]) == (0, 1, None, RATE)
    assert r.worker.requested("open")[0][0] == {"type": "open", "session": "s1", "rate": RATE, "speakers": 2}
    assert row["speech_stamp"] and row["recording_file"] == f"consultation_{c.id}.wav"
    assert c.page_state()["speech"]["state"] == "open"
    # The capture message is taken once; a second changes nothing.
    c.begin_sound(Capture(True, True, True, 16000))
    assert r.rows.get(c.id)["sample_rate"] == RATE


def test_R18_sound_goes_to_the_file_first_and_sound_before_the_door_is_open_is_fed_after(room, tmp_path):
    r = room()
    c = r.consultation
    c.sound(LOUD)                                   # before the capture message: nothing to write to yet, kept in hand
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    c.sound(LOUD)
    assert c.recording.seconds == 0.5 and len(r.worker.requested("audio")) == 3     # the piece in hand was fed too
    assert (tmp_path / "data" / "recordings" / f"consultation_{c.id}.wav").stat().st_size == 44 + 2 * len(LOUD)


def test_10_4_a_speech_failure_is_said_with_its_reason_and_the_recording_goes_on(room):
    r = room(worker=MadeUpWorker(die_after=3))       # open, one piece, then dead
    c = r.consultation
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    c.sound(LOUD)
    state = c.page_state()["speech"]
    assert state["state"] == "failed" and "exit code 3" in state["reason"] and state["failure"] == state["reason"]
    assert r.rows.get(c.id)["speech_failure"] == state["reason"]
    c.sound(LOUD)
    c.sound(LOUD)
    assert c.recording.seconds == 1.0 and r.worker.starts == 1          # the file grows; nothing retried
    assert c.state == LIVE


def test_R30_a_failed_pass_never_stops_the_consultation_and_the_next_pass_runs(room):
    engine = FakeEngine({"alarm": [EngineUnreachable("gone")], "assessment": [EngineUnreachable("gone")]})
    r = room(engine=engine, worker=MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "a")], [live_seg(2, 0.3, 0.5, "b" * 160)]]))
    c = r.consultation
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    c.wait_for_pass()
    state = c.page_state()["passes"]
    assert state["alarm"]["state"] == "not_judged" and "gone" in state["alarm"]["reason"]
    assert state["assessment"]["failure"].startswith("unreachable") and state["assessment"]["differentials"] == []
    c.sound(LOUD)
    c.wait_for_pass()
    state = c.page_state()["passes"]
    assert state["n"] == 2 and state["alarm"]["state"] == "quiet"
    assert [d["condition"] for d in state["assessment"]["differentials"]] == ["Made-up condition A", "Made-up condition B"]
    assert c.state == LIVE


def test_5_2_5_3_the_page_state_is_computed_by_code_and_a_spinner_only_for_a_named_state(room, clock):
    r = room(worker=MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "made up")]], pending=[[], [{"start": 0.3, "end": 0.4, "text": "not yet"}]]))
    c = r.consultation
    before = c.page_state()
    assert before["state"] == LIVE and before["spinning"] is None and before["speech"]["state"] == "not_started"
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    c.wait_for_pass()
    c.sound(LOUD)
    state = c.page_state()
    assert state["transcript"]["lines"] == [{"n": 1, "speaker": "S1", "text": "made up", "start": 0.0, "end": 0.2, "confidence": None}]
    assert state["transcript"]["partial"] == "not yet"
    assert state["passes"]["n"] == 1 and state["passes"]["assessment"]["differentials"] == ASSESSMENT["differentials"]
    assert state["spinning"] is None and state["version"] > before["version"]
    assert state["intended_minutes"] == 15 and state["started_at"] == clock().isoformat(timespec="seconds")
    # A pass in flight is a named state; stopping stages are named; final spins nothing.
    c.passes.running = True
    assert c.page_state()["spinning"] == "pass_running"
    c.passes.running = False
    assert c.stop() and c.page_state()["spinning"] == "speech"
    c.set_stage("who_spoke")
    assert c.page_state()["spinning"] is None                # waiting on the doctor is not a spinner
    c.set_stage("label_check")
    assert c.page_state()["spinning"] == "label_check"
    c.set_stage(None)
    c.state = FINAL
    assert c.page_state()["spinning"] is None


def test_ruling_10_the_clock_changes_state_at_the_intended_time_and_the_time_is_stored(room, clock):
    r = room(intended=15)
    c = r.consultation
    assert clock_state(899.9, 15) == WITHIN and clock_state(900.0, 15) == OVER and clock_state(0, 60) == WITHIN
    clock.advance(minutes=14, seconds=59)
    assert c.page_state()["clock"] == WITHIN and c.page_state()["used_s"] == 899.0
    clock.advance(seconds=1)
    assert c.page_state()["clock"] == OVER
    assert r.rows.get(c.id)["intended_minutes"] == 15
    assert c.state == LIVE                                       # nothing else happens


def test_R2_stop_is_audited_closes_the_recording_and_a_second_stop_waits(room, clock):
    r = room()
    c = r.consultation
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    assert c.stop() is True
    assert c.state == STOPPING and not c.recording.open and c.stop_stage == "speech"
    row = r.rows.get(c.id)
    assert row["state"] == "stopping" and row["stopped_at"] == clock().isoformat(timespec="seconds")
    assert r.audit.lines()[0].event == "consultation.stopped"
    assert c.stop() is False and c.state == STOPPING            # the second waits: nothing changes
    c.sound(LOUD)                                                # sound after Stop goes nowhere
    assert len(r.worker.requested("audio")) == 1


def test_a_pass_that_lands_after_stop_is_recorded_and_not_shown(room):
    gate = threading.Event()

    class SlowEngine(FakeEngine):
        def chat(self, call):
            gate.wait(5)
            return super().chat(call)

    r = room(engine=SlowEngine(), worker=MadeUpWorker(live=[[live_seg(1, 0.0, 0.2, "made up")]]))
    c = r.consultation
    c.begin_sound(CAPTURE)
    c.sound(LOUD)
    assert c.passes.running and c.page_state()["spinning"] == "pass_running"
    c.stop()
    gate.set()
    c.wait_for_pass()
    assert r.rows.passes(c.id)[0]["shown"] == 0
    assert c.page_state()["passes"]["alarm"] is None and c.page_state()["passes"]["assessment"]["n"] == 0
