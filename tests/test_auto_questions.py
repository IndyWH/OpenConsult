"""The question phases wired (Phase 7c slice 4): D1 topic call, D2
strict-revise cadence, D3 topic-scoped cone, pre-synthesis, the requeue,
the doctor's tap, and the handover sequence — dark behind
AUTO_MODE_ENABLED, driven over the real socket.

PHASE_7C_SPEC.md §4, §5, §6, §9, §11 as amended 2026-08-16. The harness
is tests/test_auto_golden.py's (a real SpeechService on a fake command;
a scripted engine standing in for MedGemma — its officer verdicts, its
topics and its agendas are what the tests script; QUALITY of any of them
belongs to evals). What is pinned:

- Strict-revise (D2): after the answer's turn ends a CDS pass runs at
  once, bypassing CDS_MIN_NEW_CHARS, and the ask is ONLY from the agenda
  it returns; while it runs at most one bridging encourager.
- The cone (D3): a NEW topic is asked open-form through the tell_me_more
  template; a topic already opened is asked verbatim; the first verbatim
  ask moves OPEN → CLOSED; a genuinely new topic arriving late still gets
  its one open ask in CLOSED; a failed topic call asks verbatim, audited.
- A politeness-aborted question is requeued and re-issued at the next
  permitting quiet (an encourager is dropped — slice-3 rule).
- A doctor's tap displaces the queued auto ask and is audited as an
  intervention naming what it displaced.
- The handover sequence: agenda empty on a fresh post-answer revision →
  anything_else once → its answer's revision → refill returns to the
  questions; still empty → examination_handover, machine HANDOVER,
  auto.handover; anything_else is never spoken twice.
- The rows: {"via":"auto","phase":…,"trigger":{quiet_s, handed_back},
  "topic":…, "open_form":bool} and the agenda's rationale.
- With AUTO_MODE_ENABLED false none of it exists.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import struct
import sys
import time

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, auto_mode, consultations, speech, system_utterances
from app import main as appmain
from app.auto_mode import AutoPhase
from app.cds import OfficerVerdict, TopicVerdict
from app.transcription import SAMPLE_RATE


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

FRAME_SAMPLES = 4000
PATIENT_AMPLITUDE = 3000
TTS_AMPLITUDE = 20000

Q_RADIATE = "Does the pain radiate to your jaw or arm?"
Q_ONSET = "When did the chest pain first start?"
Q_SLEEP = "How have you been sleeping?"
Q_TABLETS = "Have you missed any of your tablets?"


def _tone(samples: int, amplitude: int) -> bytes:
    t = np.arange(samples)
    return (amplitude * np.sin(2 * np.pi * 440 * t / SAMPLE_RATE)).astype(np.int16).tobytes()


def _frame(seq: int, amplitude: int = PATIENT_AMPLITUDE) -> bytes:
    return struct.pack(">I", seq) + _tone(FRAME_SAMPLES, amplitude)


def fake_command(tmp_path, seconds: float = 0.5) -> str:
    script = tmp_path / f"fake_tts_{secrets.token_hex(4)}.py"
    script.write_text(
        "import sys, wave\n"
        "sys.stdin.buffer.read()\n"
        "with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        f"    w.writeframes(b'\\x00\\x00' * int({seconds} * 22050))\n")
    (tmp_path / "voice.onnx").write_bytes(b"never read")
    return f"{sys.executable} {script} --model {{model}} --output-file {{output}}"


class SilentTranscriber:
    def transcribe(self, buffer):
        return []


def _assessment(questions, reasoning="why these"):
    return {"reasoning": reasoning, "differentials": [], "questions_to_ask": list(questions),
            "signs_to_check": [], "urgent_actions": [], "patient_affect": "neutral",
            "urgency_check": {"time_critical_possible": False,
                              "already_done_or_arranged": False, "reason": ""}}


class ScriptedEngine:
    """MedGemma stood in for. `verdicts` (officer) and `agendas` (CDS
    passes) are consumed in order, the last repeating; `topics` maps a
    question to the topic the topic call names (missing → a failed topic
    verdict). `gate_event`, when set, holds every CDS pass until released."""

    def __init__(self):
        self.verdicts = [OfficerVerdict(True, False)]
        self.agendas = [[Q_RADIATE]]
        self.topics = {Q_RADIATE: "the chest pain", Q_ONSET: "the chest pain",
                       Q_SLEEP: "your sleep", Q_TABLETS: "your tablets"}
        self.asked: list[str] = []
        self.updates: list[str] = []
        self.topic_calls: list[str] = []
        self.gate_event: asyncio.Event | None = None

    async def end_of_turn(self, transcript):
        self.asked.append(transcript)
        return self.verdicts.pop(0) if len(self.verdicts) > 1 else self.verdicts[0]

    async def topic_for(self, question):
        self.topic_calls.append(question)
        topic = self.topics.get(question)
        if topic is None:
            return TopicVerdict(None, failed="unusable: ''", elapsed_ms=7)
        return TopicVerdict(topic, elapsed_ms=9)

    async def update(self, transcript, previous=None):
        if self.gate_event is not None:
            await self.gate_event.wait()
        self.updates.append(transcript)
        questions = self.agendas.pop(0) if len(self.agendas) > 1 else self.agendas[0]
        return _assessment(questions, reasoning=f"pass {len(self.updates)}")


def _make_user(role: str = "doctor") -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", "Herath", role))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def gate(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    monkeypatch.setattr(speech, "TTS_ENABLED", True)
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", True)
    # Encouragers are slice 3's subject (tests/test_auto_golden.py); here
    # they would only take the one utterance slot at the wrong moment, so
    # both thresholds — the golden window's minimum quiet and the bridge's
    # — are parked out of reach except where a test wants them.
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 100.0)
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 100.0)
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": speech.SpeechService(voice="test", model_path=str(tmp_path / "voice.onnx"),
                                       cache_dir=tmp_path / "cache",
                                       command=fake_command(tmp_path)),
        "cds_engine": ScriptedEngine(),
        "rag": object(),
        "live_sessions": {},
        "finalize_queue": asyncio.Queue(),
    }
    previous = {name: getattr(state, name, missing) for name in installed}
    for name, value in installed.items():
        setattr(state, name, value)
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    try:
        yield state
    finally:
        for name, old in previous.items():
            if old is missing:
                delattr(state, name)
            else:
                setattr(state, name, old)


def _collect_until(ws, wanted, limit=80):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if message.get("type") in wanted:
            return seen
        if message.get("type") in ("speak_refused", "auto_refused") and "refused" not in "".join(wanted):
            raise AssertionError(f"refused while waiting for {wanted}: {message['detail']}")
    raise AssertionError(f"none of {wanted} arrived; saw {[m.get('type') for m in seen]}")


def _until(ws, wanted, limit=80):
    return _collect_until(ws, wanted, limit)[-1]


class Session:
    def __init__(self, state, ws, session_id):
        self.state, self.ws, self.session_id = state, ws, session_id
        self.seq = 0
        self.quiet_s = 0.0
        self.since = "speech"        # what began the current quiet span (E2)

    @property
    def entry(self):
        return self.state.live_sessions[self.session_id]

    @property
    def auto(self):
        return self.entry["auto"]

    @property
    def phase(self):
        return self.auto["controller"].phase

    def disclose(self):
        self.ws.send_text(json.dumps({"type": "disclosure_given"}))
        return _until(self.ws, {"disclosure"})

    def frame(self, amplitude=PATIENT_AMPLITUDE):
        self.seq += 1
        self.ws.send_bytes(_frame(self.seq, amplitude))

    def probe(self):
        self.frame()
        return _collect_until(self.ws, {"ack"})[:-1]

    def play(self, utterance_id, reason="complete"):
        self.ws.send_text(json.dumps({"type": "speak_started",
                                      "utterance_id": utterance_id, "seq": self.seq + 1}))
        self.frame(TTS_AMPLITUDE)
        _until(self.ws, {"ack"})
        self.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                                      "seq": self.seq + 1, "reason": reason}))
        self.quiet_s = 0.0                    # our playback ended: a fresh span
        self.since = "playback"

    def abort(self, utterance_id):
        self.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                                      "seq": self.seq + 1, "reason": "politeness_abort",
                                      "rms": 0.07}))
        self.quiet_s = 0.0

    def toggle(self, on: bool):
        self.ws.send_text(json.dumps({"type": "auto", "on": on}))

    def quiet(self, quiet_s: float):
        self.quiet_s = quiet_s
        self.ws.send_text(json.dumps({"type": "quiet", "quiet_s": quiet_s, "since": self.since}))

    def commit_transcript(self, *lines: str):
        def _inject():
            self.entry["transcript_parts"].extend(lines)
            self.entry["cds_sent_len"] = len("\n".join(self.entry["transcript_parts"]))
        self.ws.portal.call(_inject)
        self.quiet_s = 0.0
        self.since = "speech"                 # the patient spoke: a fresh span of theirs

    def seed_agenda(self, *questions):
        """A pre-existing agenda version, as an earlier CDS pass would have
        left it — without running the engine."""
        return self.ws.portal.call(lambda: self.entry["agenda"].record(_assessment(questions)))

    def to_golden(self):
        self.disclose()
        self.toggle(True)
        seen = _collect_until(self.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        self.play(invitation["utterance_id"])
        self.probe()
        assert self.phase is AutoPhase.GOLDEN

    def to_open(self):
        """GOLDEN → OPEN by a hand-back at the end of the patient's turn.
        The engine's first officer verdict must be a hand-back."""
        self.commit_transcript("It started on Tuesday.", "That's all really.")
        self.quiet(3.1)
        self.probe()
        assert self.phase is AutoPhase.OPEN

    def turn_end(self, *said: str, quiet: float = 3.2):
        """The patient says something, goes quiet, and the officer judges
        the turn ended (the engine's current verdict must say so)."""
        self.commit_transcript(*said)
        self.quiet(quiet)
        self.probe()

    def wait_for_auto_speak(self, *, start_quiet=None, tries=40):
        """Keep the quiet span going with reports and loop ticks until the
        server issues an utterance (background work — the CDS pass, the
        topic call, pre-synthesis — needs ticks to land)."""
        q = start_quiet if start_quiet is not None else max(self.quiet_s, 3.3)
        for _ in range(tries):
            q += 0.7
            self.quiet(q)
            seen = self.probe()
            spoken = [m for m in seen if m.get("type") == "auto_speak"]
            if spoken:
                return spoken[0]
            time.sleep(0.03)
        raise AssertionError("no auto utterance was issued")

    def expect_silence(self, *, tries=6):
        q = max(self.quiet_s, 3.3)
        for _ in range(tries):
            q += 0.7
            self.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in self.probe())
            time.sleep(0.02)


@contextlib.contextmanager
def live(state, user=None):
    user = user or _make_user()
    client = _client_for(user)
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        yield Session(state, ws, session_id)


def _audit(action: str, session_id: str) -> list[dict]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT detail FROM audit_event WHERE action = %s"
            " AND detail->>'session_id' = %s ORDER BY id",
            (action, session_id)).fetchall()
    return [r[0] for r in rows]


def _stop(s: Session):
    s.ws.send_text("stop")
    return _until(s.ws, {"done"})["consultation_id"]


def _rows(cid):
    return asyncio.run(system_utterances.for_consultation(cid))


# ==========================================================================
# D2: strict-revise

def test_strict_revise_asks_only_from_the_fresh_agenda(gate):
    """The agenda that stood before the answer is never asked from: after
    the golden exit (itself a turn end) a CDS pass runs at once — no
    150-char growth needed — and the first ask comes from what it
    returned. Its row is a template ask (a new topic) with the §11 record."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]                       # the FRESH agenda
    with live(gate) as s:
        s.to_golden()
        s.seed_agenda(Q_SLEEP)                         # the STALE one, before the answer
        s.to_open()
        assert s.auto["revision"] in ("requested", "running")
        ask = s.wait_for_auto_speak()
        assert engine.updates, "the strict-revise pass ran"
        assert ask["text"] == "Can you tell me more about the chest pain?"
        assert ask["ref_id"] is None
        assert engine.topic_calls == [Q_ONSET]
        s.play(ask["utterance_id"])
        cid = _stop(s)
    rows = _rows(cid)
    row = next(r for r in rows if r["ref_kind"] == "template")
    assert row["ref_detail"] == {"template_id": "tell_me_more", "topic": "the chest pain",
                                 "via": "auto", "phase": "open",
                                 "trigger": {"quiet_s": row["ref_detail"]["trigger"]["quiet_s"],
                                             "handed_back": True},
                                 "topic": "the chest pain", "open_form": True}
    assert not any(Q_SLEEP in r["text"] or "your sleep" in r["text"] for r in rows)


def test_the_bridge_encourager_is_at_most_one_while_the_pass_runs(gate, monkeypatch):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    engine.gate_event = asyncio.Event()                # hold the pass
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 1.75)   # now they may come
        heard = []
        q = 3.3
        for _ in range(5):                            # a long quiet while the pass runs
            q += 0.8
            s.quiet(q)
            heard += [m for m in s.probe() if m.get("type") == "auto_speak"]
            for m in heard:
                if m["ref_id"] in speech.ENCOURAGER_IDS and s.entry["pending_utterance"]:
                    s.play(m["utterance_id"])
        encouragers = [m for m in heard if m["ref_id"] in speech.ENCOURAGER_IDS]
        assert len(encouragers) == 1, "one bridge, not a machine-gun"
        assert encouragers[0]["ref_id"] == "go_on", "the bridge's phrase (owner decision 2026-09-01)"
        assert not any(m["ref_id"] is None for m in heard), "no question before the pass lands"
        s.ws.portal.call(lambda: engine.gate_event.set())   # release the pass
        s.commit_transcript("still here")             # nothing more said, but a fresh span
        s.quiet(3.4)
        s.probe()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Can you tell me more about the chest pain?"
        _stop(s)


def test_ask_from_current_when_strict_revise_is_off_and_the_posture_is_recorded(gate, monkeypatch):
    """AUTO_STRICT_REVISE=false is the comparison posture: no post-answer
    pass is waited for — the ask comes from the agenda as it stands — and
    the posture is on the run's record (auto.enabled thresholds) so the
    mock-patient round can tell the two apart."""
    monkeypatch.setattr(appmain, "AUTO_STRICT_REVISE", False)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]                       # what a pass WOULD return
    with live(gate) as s:
        s.to_golden()
        s.seed_agenda(Q_SLEEP)                         # the current agenda
        s.to_open()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Can you tell me more about your sleep?"
        assert engine.updates == [], "no pass was waited for"
        _stop(s)
    enabled = _audit("auto.enabled", s.session_id)[0]
    assert enabled["thresholds"]["strict_revise"] is False
    assert enabled["thresholds"]["golden_s"] == appmain.AUTO_GOLDEN_MINUTES_S
    assert enabled["thresholds"]["presynth"] is True


# ==========================================================================
# D3: the topic-scoped cone

def test_new_topic_is_open_form_seen_topic_is_verbatim_and_open_closes_at_the_first_verbatim_ask(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE], [Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?"
        s.play(first["utterance_id"])
        assert s.phase is AutoPhase.OPEN
        # The answer ends → revision → Q_RADIATE, same topic → verbatim,
        # and the machine narrows to CLOSED before it is spoken.
        s.turn_end("It started on Tuesday, in the middle of the night.")
        second = s.wait_for_auto_speak()
        assert second["text"] == Q_RADIATE
        assert s.phase is AutoPhase.CLOSED
        s.play(second["utterance_id"])
        # A genuinely new topic arriving late still gets its one open ask,
        # in CLOSED.
        s.turn_end("No, it stays in the middle of my chest.")
        third = s.wait_for_auto_speak()
        assert third["text"] == "Can you tell me more about your sleep?"
        assert s.phase is AutoPhase.CLOSED
        s.play(third["utterance_id"])
        cid = _stop(s)
    phases = [(d["from"], d["to"], d["trigger"]) for d in _audit("auto.phase", s.session_id)]
    assert ("open", "closed", "narrative_exhausted") in phases
    closed = next(d for d in _audit("auto.phase", s.session_id) if d["to"] == "closed")
    assert closed["detail"] == {"first_verbatim_ask": Q_RADIATE}
    rows = _rows(cid)
    verbatim = next(r for r in rows if r["text"] == Q_RADIATE)
    assert verbatim["ref_kind"] == "cds_question"
    assert verbatim["ref_detail"]["open_form"] is False
    assert verbatim["ref_detail"]["topic"] == "the chest pain"
    assert verbatim["ref_detail"]["phase"] == "closed"
    assert verbatim["cds_rationale"] == "pass 2"      # the agenda's own reasoning
    late = next(r for r in rows if "your sleep" in r["text"])
    assert late["ref_detail"]["open_form"] is True and late["ref_detail"]["phase"] == "closed"


def test_a_failed_topic_call_asks_verbatim_and_is_audited(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [["Is the pain there now?"]]     # no topic scripted → failed
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Is the pain there now?"
        s.play(ask["utterance_id"])
        cid = _stop(s)
    failed = _audit("auto.topic_failed", s.session_id)
    assert len(failed) == 1 and failed[0]["reason"].startswith("unusable")
    row = next(r for r in _rows(cid) if r["text"] == "Is the pain there now?")
    assert row["ref_detail"]["open_form"] is False and row["ref_detail"]["topic"] is None


# ==========================================================================
# One turn-end rule in every phase (owner decision 2026-09-07, pilot 485 E1)

def test_the_485_shape_a_not_finished_officer_no_longer_holds_an_answered_question_open(gate):
    """Owner decision 2026-09-07 (pilot 485, defect E1). In 485 the doctor
    tapped a question, the patient answered, and the officer said "not
    finished" three times across 7 s of silence (quiet 3.0, 3.1, 7.1);
    the answer never ended a turn, no revision was requested, and no next
    question came before Stop. Now the rule the post-window golden exit
    already used applies in OPEN and CLOSED too: quiet of
    AUTO_EOT_FALLBACK_S ends the turn on the report itself, whatever the
    officer said. The turn end is audited (auto.turn_ended, by
    quiet_fallback), the revision runs, and the next question is planned
    and issued."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]   # hand-back, then never finished
    engine.agendas = [[Q_ONSET], [Q_RADIATE]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about the chest pain?"
        s.play(first["utterance_id"])
        s.commit_transcript("Medical camp last year said blood pressure was high.",
                            "I never followed up.")
        s.quiet(3.0)
        s.probe()                                     # officer asked: not finished
        assert len(engine.asked) == 2 and s.auto["turn_ended"] is False
        s.quiet(4.9)
        s.probe()
        assert s.auto["turn_ended"] is False and s.auto["awaiting_answer"] is True
        assert len(engine.updates) == 1, "under the fallback span: the answer is still open"
        s.quiet(5.1)
        s.probe()
        assert s.auto["turn_ended"] is True and s.auto["awaiting_answer"] is False
        # The answer's revision was asked for (the scripted pass may already
        # have landed on the same tick, in which case its plan is in flight).
        assert (s.auto["revision"] in ("requested", "running") or len(engine.updates) == 2
                or s.auto["plan_task"] is not None or s.auto["queued"] is not None)
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE, "planned from the fresh agenda and issued"
        assert len(engine.updates) == 2
        s.play(nxt["utterance_id"])
        _stop(s)
    ended = [d for d in _audit("auto.turn_ended", s.session_id) if d["answer"]]
    assert len(ended) == 1
    assert ended[0]["by"] == "quiet_fallback" and ended[0]["quiet_s"] == 5.1
    assert ended[0]["phase"] == "open" and ended[0]["fallback_s"] == appmain.AUTO_EOT_FALLBACK_S
    assert ended[0]["finished_thought"] is False, "the span's verdict travels in the record"


def test_a_finished_verdict_still_ends_the_answers_turn_before_the_fallback(gate):
    """The officer's word is not demoted: a finished_thought verdict ends
    the turn at once (here at 3.2 s, under the 5 s fallback), audited by
    verdict, and the revision runs from there."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False, elapsed_ms=610)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.commit_transcript("Father had a heart attack when he was around 60.")
        s.quiet(3.2)
        s.probe()
        assert s.auto["turn_ended"] is True and s.auto["awaiting_answer"] is False
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE
        assert len(engine.updates) == 2
        _stop(s)
    ended = [d for d in _audit("auto.turn_ended", s.session_id) if d["answer"]]
    assert len(ended) == 1
    assert ended[0]["by"] == "verdict" and ended[0]["quiet_s"] == 3.2
    assert ended[0]["finished_thought"] is True and ended[0]["officer_ms"] == 610


# ==========================================================================
# Our own utterances never erase a judged turn end (owner decision 2026-09-07, E2)

def test_the_bridge_does_not_erase_the_golden_exits_turn_end(gate, monkeypatch):
    """Owner decision 2026-09-07 (pilot 485, defect E2). The golden exit is
    a turn end; in 485 the bridge "Go on." 1 s later restarted the client's
    quiet span and the fresh-span rule cleared turn_ended, so the first ask
    needed a second judgement in a room where nobody spoke. Now a span
    that began with OUR playback keeps the judged turn end: golden exit →
    bridge → the revision lands → the queued question issues on the next
    report, with the officer never asked again and never saying finished."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET]]
    engine.gate_event = asyncio.Event()                # hold the revision
    with live(gate) as s:
        s.to_golden()
        s.to_open()                                    # the exit: turn_ended True
        assert s.auto["turn_ended"] is True
        asked = len(engine.asked)
        monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 1.75)
        s.quiet(3.5)
        bridge = next(m for m in s.probe() if m.get("type") == "auto_speak")
        assert bridge["ref_id"] == "go_on"
        s.play(bridge["utterance_id"])                 # our voice: the client's span restarts
        s.quiet(2.0)                                   # a fresh span, since=playback
        s.probe()
        assert s.auto["turn_ended"] is True, "our own utterance erased nothing"
        s.ws.portal.call(lambda: engine.gate_event.set())
        for _ in range(30):                            # the pass lands, the plan is prepared
            s.probe()
            if s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        assert s.auto["queued"] is not None
        s.quiet(2.6)                                   # under the officer's 3 s
        ask = next(m for m in s.probe() if m.get("type") == "auto_speak")
        assert ask["text"] == "Can you tell me more about the chest pain?"
        assert len(engine.asked) == asked, "no second judgement was needed"
        assert s.auto["turn_ended"] is False, "cleared at issue, and only there"
        s.play(ask["utterance_id"])
        _stop(s)


def test_the_patients_own_voice_still_reopens_the_turn(gate):
    """The other half of E2: a fresh span the PATIENT began (since=speech)
    clears the judged turn end as before, so a plan landing while they
    talk again waits for a new judgement — err toward waiting."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET]]
    engine.gate_event = asyncio.Event()
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        assert s.auto["turn_ended"] is True
        s.commit_transcript("Oh, and one more thing about the pain and")
        s.quiet(2.0)                                   # since=speech
        s.probe()
        assert s.auto["turn_ended"] is False, "the patient spoke: the turn is open again"
        s.ws.portal.call(lambda: engine.gate_event.set())
        for _ in range(30):
            s.probe()
            if s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        s.quiet(2.6)
        assert all(m.get("type") != "auto_speak" for m in s.probe()), "waits for a judgement"
        s.quiet(4.0)                                   # officer: not finished → still waits
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        _stop(s)


# ==========================================================================
# The requeue and the doctor's tap

def test_a_politeness_aborted_question_is_requeued_and_reissued(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        ask = s.wait_for_auto_speak()
        s.abort(ask["utterance_id"])                  # speech resumed: declined
        assert s.auto["queued"] is not None, "requeued, not dropped"
        # The patient's resumed turn ends; the same question comes again.
        s.turn_end("Sorry, one more thing — it woke me up.")
        again = s.wait_for_auto_speak()
        assert again["text"] == ask["text"]
        assert again["utterance_id"] != ask["utterance_id"]
        s.play(again["utterance_id"])
        cid = _stop(s)
    rows = [r for r in _rows(cid) if r["ref_kind"] == "template"]
    # (rows come ordered by start byte, the never-played abort last)
    assert sorted(r["end_reason"] for r in rows) == ["complete", "politeness_abort"]
    assert all(r["text"] == "Can you tell me more about the chest pain?" for r in rows)


def test_a_doctors_tap_displaces_the_queued_ask_and_is_audited(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        # Let the plan land while the patient is (still) talking: no quiet.
        for _ in range(30):
            s.probe()
            if s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        assert s.auto["queued"] is not None
        version = s.entry["agenda"].current_version
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": version, "index": 0}}))
        ready = _until(s.ws, {"speak_ready"})
        assert s.auto["queued"] is None, "the tap displaced the queued auto ask"
        s.play(ready["utterance_id"])
        # The answer that follows is treated like any other: its turn end
        # triggers the revision, and the next ask is from the fresh agenda.
        s.turn_end("It started on Tuesday.")
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE or nxt["text"].startswith("Can you tell me more about")
        _stop(s)
    taps = _audit("auto.doctor_tap", s.session_id)
    assert len(taps) == 1
    assert taps[0]["displaced"] == {"kind": "question",
                                    "text": "Can you tell me more about the chest pain?"}
    assert taps[0]["ref_kind"] == "cds_question" and taps[0]["phase"] == "open"


# ==========================================================================
# The handover sequence (§6 as amended)

def test_the_handover_sequence_with_the_agenda_refill_return_path(gate):
    """Agenda empty on the post-answer revision → anything_else once → its
    answer's revision refills → back to the questions → next revision
    empty → examination_handover, machine HANDOVER, auto.handover — and
    anything_else is not spoken a second time."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [], [Q_TABLETS], []]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")                  # revision → empty
        anything = s.wait_for_auto_speak()
        assert anything["ref_id"] == "anything_else"
        assert s.auto["anything_else_done"] is True
        s.play(anything["utterance_id"])
        s.turn_end("Well, my tablets — I keep forgetting them.")   # revision → refill
        back = s.wait_for_auto_speak()
        assert back["text"] == "Can you tell me more about your tablets?"
        assert s.phase in (AutoPhase.OPEN, AutoPhase.CLOSED)
        s.play(back["utterance_id"])
        s.turn_end("Most mornings, I just forget.")   # revision → empty again
        final = s.wait_for_auto_speak()
        assert final["ref_id"] == "examination_handover", "anything_else is not spoken twice"
        assert final["text"] == "Thank you — Dr Herath will examine you now."
        s.play(final["utterance_id"])
        s.probe()
        assert s.phase is AutoPhase.HANDOVER
        s.expect_silence()                            # the auto run has ended
        cid = _stop(s)
    assert len(_audit("auto.handover", s.session_id)) == 1
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["to"], last["trigger"]) == ("handover", "agenda_exhausted")
    texts = [r["text"] for r in _rows(cid)]
    assert texts.count(speech.PHRASES["anything_else"]) == 1
    assert len(engine.updates) == 4


def test_agenda_empty_counts_only_on_a_post_answer_revision(gate):
    """A stale empty agenda (seeded before the answer) does not start the
    handover; the fresh pass returns a question and that is asked."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.seed_agenda()                                # empty, stale
        s.to_open()
        ask = s.wait_for_auto_speak()
        assert ask["ref_id"] is None and "chest pain" in ask["text"]
        _stop(s)


# ==========================================================================
# The gate down

def test_with_the_gate_down_taps_are_not_interventions_and_nothing_is_planned(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", False)
    with live(gate) as s:
        s.disclose()
        assert s.entry["auto"] is None
        s.seed_agenda(Q_ONSET)
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": 1, "index": 0}}))
        ready = _until(s.ws, {"speak_ready"})
        s.play(ready["utterance_id"])
        s.quiet(4.0)
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        _stop(s)
    assert _audit("auto.doctor_tap", s.session_id) == []
    assert _audit("auto.topic_failed", s.session_id) == []
    assert gate.cds_engine.topic_calls == []
