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
PASS_FILLER = "The patient describes the pain in detail, at length, over several sentences here. " * 3


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
        self.timeouts: list[float | None] = []   # the bound each ask came with (E4)

    async def end_of_turn(self, transcript, *, timeout_s=None):
        self.asked.append(transcript)
        self.timeouts.append(timeout_s)
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
        left it — without running the engine, so NOT merged into the
        standing queue (a seed is a panel the machine never saw land)."""
        return self.ws.portal.call(lambda: self.entry["agenda"].record(_assessment(questions)))

    def land_pass(self, *lines: str, tries: int = 60):
        """Let a CDS pass run on transcript growth — not one auto mode asked
        for — and wait for it to land (and, with the machine on, merge into
        the standing queue). As in tests/auto_harness.py."""
        before = self.entry["agenda"].current_version
        filler = lines or (PASS_FILLER,)
        def _inject():
            self.entry["transcript_parts"].extend(filler)
        self.ws.portal.call(_inject)
        for _ in range(tries):
            self.probe()
            if self.entry["agenda"].current_version > before:
                return self.entry["agenda"].current_version
            time.sleep(0.03)
        raise AssertionError("no CDS pass landed")

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
    pass is waited for — the ask comes from the standing queue as it
    stands — and the posture is on the run's record (auto.enabled
    thresholds) so the mock-patient round can tell the two apart.

    REPINNED 2026-09-07 (owner decision: the standing question queue,
    AGENDA_QUEUE_SPEC.md §5): "the agenda as it stands" is the queue, and
    the queue holds what PASSES merged while the machine was on — so the
    current agenda is landed as a pass in the golden minutes rather than
    seeded behind the machine's back. The property kept: with the flag
    off, the golden exit's ask comes from what is already in hand and no
    further pass runs for it."""
    monkeypatch.setattr(appmain, "AUTO_STRICT_REVISE", False)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_SLEEP], [Q_ONSET]]            # in hand; what a further pass WOULD return
    with live(gate) as s:
        s.to_golden()
        s.land_pass()                                  # the current agenda, merged
        assert [i.text for i in s.auto["queue"].pending] == [Q_SLEEP]
        s.to_open()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Can you tell me more about your sleep?"
        assert len(engine.updates) == 1, "no further pass was waited for"
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
# A turn must start before it can end (owner decision 2026-09-07, pilot 486 F5)

def _script_first_question(gate):
    """The officer: a hand-back to leave GOLDEN, then never finished — so
    only the rules under test can end a turn. Two agendas."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(False, False)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE]]
    return engine


def _ask_first(s):
    """GOLDEN → OPEN by hand-back, the first question issued and played."""
    s.to_golden()
    s.to_open()
    ask = s.wait_for_auto_speak()
    assert ask["text"] == "Can you tell me more about the chest pain?"
    s.play(ask["utterance_id"])
    assert s.auto["awaiting_speech"] is True and s.auto["awaiting_answer"] is True
    return ask


def test_quiet_after_a_question_with_no_speech_ends_no_turn(gate):
    """Owner decision 2026-09-07 (pilot 486 F5): in 486 the 5 s rule ended
    the "answer" of a question 10.6 s before the patient began it, and the
    revision ran without the answer. Now silence after an auto question
    counts toward a turn end only once the patient has spoken since it."""
    engine = _script_first_question(gate)
    with live(gate) as s:
        _ask_first(s)
        for q in (3.0, 5.1, 8.0, 11.0):                # since=playback: nobody has spoken
            s.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in s.probe())
        assert s.auto["turn_ended"] is False and s.auto["awaiting_answer"] is True
        assert len(engine.updates) == 1, "no revision ran on an unanswered question"
        assert not [d for d in _audit("auto.turn_ended", s.session_id) if d["answer"]]
        _stop(s)


def test_speech_then_five_seconds_of_quiet_ends_the_turn_as_before(gate):
    engine = _script_first_question(gate)
    with live(gate) as s:
        _ask_first(s)
        s.quiet(4.0)
        s.probe()
        s.commit_transcript("It started on Tuesday, in the night.")   # the patient speaks
        s.quiet(2.0)                                     # since=speech
        s.probe()
        assert s.auto["awaiting_speech"] is False
        s.quiet(5.1)
        s.probe()
        assert s.auto["turn_ended"] is True and s.auto["awaiting_answer"] is False
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE
        assert len(engine.updates) == 2
        _stop(s)
    ended = [d for d in _audit("auto.turn_ended", s.session_id) if d["answer"]]
    assert len(ended) == 1 and ended[0]["by"] == "quiet_fallback"
    assert _audit("auto.reask_no_answer", s.session_id) == []


def test_twelve_seconds_of_no_speech_re_asks_exactly_once_and_continued_silence_proceeds(gate):
    """At AUTO_NO_ANSWER_GRACE_S with no patient speech the question is
    re-asked once (audited); after the re-ask a second grace of silence
    lets the ordinary turn-end path proceed, so silence never traps the
    run — and no third asking happens."""
    _script_first_question(gate)
    with live(gate) as s:
        ask = _ask_first(s)
        s.quiet(11.9)
        assert all(m.get("type") != "auto_speak" for m in s.probe()), "under the grace: nothing"
        s.quiet(12.1)
        again = next(m for m in s.probe() if m.get("type") == "auto_speak")
        assert again["text"] == ask["text"] and again["utterance_id"] != ask["utterance_id"]
        assert s.auto["reasked"] is True and s.auto["awaiting_speech"] is True
        s.play(again["utterance_id"])                   # its playback starts a fresh span
        for q in (5.1, 8.0, 11.9):
            s.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in s.probe()), "still no turn end, no third ask"
        assert s.auto["turn_ended"] is False
        s.quiet(12.2)                                    # the second grace: the ordinary path
        s.probe()
        assert s.auto["awaiting_speech"] is False and s.auto["turn_ended"] is True
        assert s.auto["awaiting_answer"] is False, "the answer's (silent) turn ended"
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == Q_RADIATE, "the flow went on"
        _stop(s)
    reasks = _audit("auto.reask_no_answer", s.session_id)
    assert len(reasks) == 1
    assert reasks[0]["text"] == ask["text"] and reasks[0]["quiet_s"] == 12.1
    assert reasks[0]["grace_s"] == appmain.AUTO_NO_ANSWER_GRACE_S == 12.0
    ended = [d for d in _audit("auto.turn_ended", s.session_id) if d["answer"]]
    assert len(ended) == 1 and ended[0]["by"] == "quiet_fallback" and ended[0]["quiet_s"] == 12.2


# ==========================================================================
# Cap runaway generation (owner decision 2026-09-07, pilot 486 F3)

def test_a_runaway_revision_is_audited_keeps_the_previous_assessment_and_the_flow_asks_from_the_agenda_in_hand(gate):
    """In 486 a runaway held the flow for 3 min 18 s in "preparing". Now a
    pass that hits its cap or timeout is audited cds.runaway (tokens,
    elapsed), the previous assessment and agenda version are kept, and a
    revision auto mode was waiting for is answered from the agenda it
    already has — the question comes, the flow is never held."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_SLEEP]]
    healthy = engine.update
    async def runaway(transcript, previous=None):
        if not engine.updates:
            return await healthy(transcript, previous)    # the first pass lands: the agenda in hand
        engine.updates.append(transcript)
        exc = appmain.cds.CDSRunaway("assessment", reason="cap", tokens=1500, elapsed_ms=37210, cap=1500)
        exc.urgency = {"urgency_check": {"time_critical_possible": False,
                                         "already_done_or_arranged": False, "reason": "quiet"},
                       "urgent_actions": []}
        raise exc
    engine.update = runaway
    with live(gate) as s:
        s.to_golden()
        # REPINNED 2026-09-07 (the standing question queue): "the agenda in
        # hand" is the queue, so the pass that brings Q_SLEEP lands — and
        # merges — in the golden minutes rather than being seeded behind
        # the machine's back.
        version = s.land_pass()
        s.to_open()                                     # the revision is requested…
        ask = s.wait_for_auto_speak()                   # …fails at its cap, and the ask still comes
        assert ask["text"] == "Can you tell me more about your sleep?"
        assert s.entry["agenda"].current_version == version, "no new agenda version: the previous kept"
        assert len(engine.updates) == 2
        s.play(ask["utterance_id"])
        _stop(s)
    rows = _audit("cds.runaway", s.session_id)
    assert len(rows) == 1
    assert rows[0]["call"] == "assessment" and rows[0]["reason"] == "cap"
    assert rows[0]["tokens"] == 1500 and rows[0]["elapsed_ms"] == 37210 and rows[0]["cap"] == 1500
    assert rows[0]["kept_assessment_version"] == version and rows[0]["failures"] == 1


def test_a_runaway_passs_own_urgency_call_still_pauses(gate):
    """The alarm is never lost to a runaway: the urgency check ran on its
    own call, and its actions pause auto mode exactly as a landed pass's
    would; the acknowledgement then plans from the agenda in hand."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_SLEEP]]
    healthy = engine.update
    async def runaway(transcript, previous=None):
        if not engine.updates:
            return await healthy(transcript, previous)    # the first pass lands: the agenda in hand
        engine.updates.append(transcript)
        exc = appmain.cds.CDSRunaway("assessment", reason="timeout", tokens=None,
                                     elapsed_ms=60000, timeout_s=60.0)
        exc.urgency = {"urgency_check": {"time_critical_possible": True,
                                         "already_done_or_arranged": False, "reason": "red flags"},
                       "urgent_actions": [{"action": "Bedside ECG", "reason": "exclude ACS"}]}
        raise exc
    engine.update = runaway
    with live(gate) as s:
        s.to_golden()
        s.land_pass()          # REPINNED 2026-09-07 (the queue): the agenda in hand is what merged
        s.to_open()
        for _ in range(40):
            s.probe()
            if s.phase is AutoPhase.PAUSED_URGENT:
                break
            time.sleep(0.02)
        assert s.phase is AutoPhase.PAUSED_URGENT
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG"})
        assert s.entry["assessment"]["urgent_actions"] == [{"action": "Bedside ECG", "reason": "exclude ACS"}]
        s.ws.send_text(json.dumps({"type": "auto_ack", "resolution": "resume"}))
        _until(s.ws, {"auto_acknowledged"})
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Can you tell me more about your sleep?"
        _stop(s)
    rows = _audit("cds.runaway", s.session_id)
    assert len(rows) == 1 and rows[0]["reason"] == "timeout" and rows[0]["timeout_s"] == 60.0
    assert len(_audit("auto.paused", s.session_id)) == 1


# ==========================================================================
# No question is asked twice; the cone by meaning (owner decision 2026-09-07, F4)

Q_RISK = "Do you have any other risk factors for heart disease? (e.g., diabetes, high cholesterol)"
Q_PAIN_BEFORE = "Have you ever had chest pain like this before?"


def test_the_486_risk_factors_question_is_not_asked_again_after_it_was_asked_and_answered(gate):
    """Owner decision 2026-09-07 (pilot 486 F4). The agenda kept the
    risk-factors question at the top across four versions and it was
    asked twice — the patient objected aloud.

    REPINNED 2026-09-07 (owner decision: the queue is the asked-memory,
    AGENDA_QUEUE_SPEC.md §2). The asked-and-answered list and the
    auto.reask_suppressed skip are retired: the question's queue item is
    ANSWERED at its turn end, and v2's copy of it is DISCARDED at the
    merge (auto.queue_merged discarded 1, naming it) — it is never
    pending again, so it is never planned again. The property kept: the
    second ask is v2's other question, and the risk-factors question is
    asked exactly once."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.topics[Q_RISK] = "heart disease risk factors"
    engine.agendas = [[Q_RISK], [Q_RISK, Q_ONSET]]        # v2 keeps the asked one at the top
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about heart disease risk factors?"
        s.play(first["utterance_id"])
        s.turn_end("Well, I smoke, and my blood pressure was high at a camp.")
        risk = s.auto["queue"].find(Q_RISK)
        assert risk.status.value == "answered"
        second = s.wait_for_auto_speak()
        assert second["text"] == "Can you tell me more about the chest pain?", "v2's other question, not the asked one"
        assert risk.status.value == "answered" and [i.text for i in s.auto["queue"].pending] == []
        s.play(second["utterance_id"])
        _stop(s)
    assert _audit("auto.reask_suppressed", s.session_id) == [], "retired: the queue discards instead"
    merges = _audit("auto.queue_merged", s.session_id)
    assert [m["version"] for m in merges] == [1, 2]
    assert merges[1]["discarded"] == 1 and merges[1]["added"] == 1
    assert merges[1]["discarded_items"] == [{"id": risk.id, "text": Q_RISK, "status": "answered"}]
    assert [c["text"] for c in _audit("auto.queue_consumed", s.session_id)] == [Q_RISK, Q_ONSET]


def test_the_two_cone_re_asks_collapse_to_one_topic(gate):
    """"this chest pain" and "the pain" were two topics in 486, so the
    chest pain was opened twice. With the cone's identity matched by
    meaning (AUTO_TOPIC_MATCH_THRESHOLD), the second question on the same
    topic is asked verbatim, not opened again."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.topics[Q_ONSET] = "this chest pain"
    engine.topics[Q_PAIN_BEFORE] = "the pain"
    engine.agendas = [[Q_ONSET], [Q_PAIN_BEFORE]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        assert first["text"] == "Can you tell me more about this chest pain?"
        s.play(first["utterance_id"])
        s.turn_end("It is in the centre, like a tightness.")
        second = s.wait_for_auto_speak()
        assert second["text"] == Q_PAIN_BEFORE, "one topic: asked verbatim, not opened again"
        assert s.phase is AutoPhase.CLOSED
        _stop(s)
    assert appmain.AUTO_TOPIC_MATCH_THRESHOLD == 0.6
    assert all(m["discarded"] == 0 for m in _audit("auto.queue_merged", s.session_id)), \
        "two different questions on one topic: neither is a re-ask"


def test_a_genuinely_new_question_passes_and_a_spent_agenda_hands_over(gate):
    """A new text is asked as before; a pass made only of questions already
    asked and answered leaves the queue with nothing pending — spent —
    and the handover sequence follows. REPINNED 2026-09-07 (owner
    decision: the queue is the asked-memory): the evidence is the merge's
    discards, not a suppression row."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_SLEEP], [Q_ONSET, Q_SLEEP]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.turn_end("Tuesday night.")
        second = s.wait_for_auto_speak()
        assert second["text"] == "Can you tell me more about your sleep?", "new: passes"
        s.play(second["utterance_id"])
        s.turn_end("Badly, with the pain.")
        third = s.wait_for_auto_speak()
        assert third["ref_id"] == "anything_else", "both asked and answered: the agenda is spent"
        _stop(s)
    assert _audit("auto.reask_suppressed", s.session_id) == []
    third_merge = _audit("auto.queue_merged", s.session_id)[2]
    assert third_merge["version"] == 3 and third_merge["discarded"] == 2 and third_merge["pending"] == 0
    assert sorted(d["text"] for d in third_merge["discarded_items"]) == sorted([Q_ONSET, Q_SLEEP])


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
# A busy model is a wait, not a failure (owner decision 2026-09-07, E4)

def test_an_officer_asked_during_a_cds_pass_is_deferred_not_failed_and_its_verdict_applied_after(gate):
    """Owner decision 2026-09-07 (pilot 485, defect E4). In 485 all seven
    officer timeouts fell inside a CDS pass's call windows — the model
    serves one request at a time, so the officer's 2 s budget expired in
    the queue and the officer was blind for the whole of every revision.
    Now an officer asked while a pass is in flight is called with the
    stretched bound (AUTO_OFFICER_MAX_WAIT_S), the deferral is audited
    with the version the pass will land as, no auto.officer_failed is
    written, and the verdict is applied when it arrives — here it ends
    the answer's turn by verdict after the pass has landed."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET], [Q_RADIATE]]
    engine.gate_event = asyncio.Event()                # every pass held until released
    with live(gate) as s:
        s.to_golden()
        s.to_open()                                    # hand-back: no pass in flight yet
        assert engine.timeouts == [None], "no pass in flight: the 2 s default"
        # A queued request behind the pass: the officer answers only once the
        # pass is released, like a request Ollama serves after the CDS call.
        async def queued_officer(transcript, *, timeout_s=None):
            engine.asked.append(transcript)
            engine.timeouts.append(timeout_s)
            await engine.gate_event.wait()
            return OfficerVerdict(True, False, elapsed_ms=12000)
        engine.end_of_turn = queued_officer
        s.commit_transcript("Nobody has done an ECG yet.")   # the patient speaks during the pass
        s.quiet(2.0)                                   # a fresh span of theirs
        s.probe()
        s.quiet(3.1)
        s.probe()                                      # officer asked while the pass is in flight
        assert s.auto["officer_task"] is not None and not s.auto["officer_task"].done()
        assert engine.timeouts[-1] == appmain.cds.AUTO_OFFICER_MAX_WAIT_S
        for _ in range(6):                             # ticks pass; nothing fails
            s.probe()
            time.sleep(0.02)
        assert s.auto["officer_task"] is not None, "still waiting, not failed"
        assert _audit("auto.officer_failed", s.session_id) == []
        deferred = _audit("auto.officer_deferred", s.session_id)
        assert len(deferred) == 1 and deferred[0]["quiet_s"] == 3.1 and deferred[0]["phase"] == "open"
        assert deferred[0]["max_wait_s"] == appmain.cds.AUTO_OFFICER_MAX_WAIT_S
        s.ws.portal.call(lambda: engine.gate_event.set())   # the pass lands; the officer answers
        for _ in range(30):
            s.probe()
            if s.auto["officer_task"] is None and s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        assert s.auto["officer_task"] is None, "the deferred verdict arrived and was applied"
        assert deferred[0]["pass_version"] == s.entry["assessment"]["assessment_version"]
        _stop(s)
    verdicts = _audit("auto.officer_verdict", s.session_id)
    late = next(v for v in verdicts if v.get("deferred") is not None)
    assert late["failed"] is None and late["finished_thought"] is True
    assert late["deferred"] == deferred[0]["pass_version"] and late["elapsed_ms"] == 12000
    assert late.get("stale") is None, "the patient did not speak again: applied, not stale"


def test_a_deferred_verdict_from_a_span_the_patient_has_left_is_recorded_but_not_applied(gate):
    """The other edge of a long wait: if the patient speaks again while the
    officer is out, its word is about a pause that no longer exists. It is
    audited (stale: true, no transition) and not applied — a "finished"
    from before their new words never ends the turn they re-opened."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()                # the exit's own turn end permits the ask
        s.play(first["utterance_id"])
        held = asyncio.Event()                         # the officer's answer, held like a queued request
        async def queued_officer(transcript, *, timeout_s=None):
            engine.asked.append(transcript)
            await held.wait()
            return OfficerVerdict(True, False)
        engine.end_of_turn = queued_officer
        engine.gate_event = held
        s.commit_transcript("Well, it started on Tuesday")
        s.quiet(2.0)
        s.probe()
        s.quiet(3.2)
        s.probe()                                      # the officer is out
        assert s.auto["officer_task"] is not None
        s.commit_transcript("and then again on Thursday, and")   # the patient goes on
        s.quiet(2.0)                                   # a fresh span of THEIRS
        s.probe()
        s.ws.portal.call(lambda: engine.gate_event.set())
        for _ in range(20):
            s.probe()
            if s.auto["officer_task"] is None:
                break
            time.sleep(0.02)
        assert s.auto["turn_ended"] is False, "a stale 'finished' ended nothing"
        assert s.auto["awaiting_answer"] is True
        _stop(s)
    stale = [v for v in _audit("auto.officer_verdict", s.session_id) if v.get("stale")]
    assert len(stale) == 1 and stale[0]["finished_thought"] is True and stale[0]["transition"] is None


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
    """REPINNED 2026-09-07 (owner decision, pilot 485 item 5): a tap over a
    queued question is first answered with speak_confirm and displaces
    nothing; the doctor's "ask yours instead" is the same tap with
    confirm_displace, which is what displaces and is audited (confirmed
    true, the displaced text). The property kept: the confirmed tap
    displaces the queued auto ask, is audited as an intervention naming
    what it displaced, and the answer that follows is treated like any
    other."""
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
        confirm = _until(s.ws, {"speak_confirm", "speak_ready"})
        assert confirm["type"] == "speak_confirm", "a tap over a queued question asks first"
        assert s.auto["queued"] is not None, "nothing displaced yet"
        s.ws.send_text(json.dumps({"type": "speak", "confirm_displace": True, "ref": {
            "kind": "cds_question", "assessment_version": version, "index": 0}}))
        ready = _until(s.ws, {"speak_ready"})
        assert s.auto["queued"] is None, "the confirmed tap displaced the queued auto ask"
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
    assert taps[0]["confirmed"] is True


# ==========================================================================
# The doctor's side: the thinking state and the guarded tap (owner decision 2026-09-07, item 5)

def _plans(messages):
    return [(m["state"], m["text"]) for m in messages if m.get("type") == "auto_plan"]


def test_the_indicator_is_told_preparing_then_queued_then_idle(gate):
    """The phase indicator's thinking state follows auto_plan pushes: from
    the moment the revision is requested (the golden exit) "preparing";
    once the question is prepared "queued" with its text; "idle" when it
    is issued. Pushed only on change, so the sequence is exact."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    engine.gate_event = asyncio.Event()
    with live(gate) as s:
        s.to_golden()
        seen = []
        s.commit_transcript("It started on Tuesday.", "That's all really.")
        s.quiet(3.1)
        seen += s.probe()                                  # the exit: revision requested
        assert s.phase is AutoPhase.OPEN
        seen += s.probe()
        assert _plans(seen) == [("preparing", None)]
        s.ws.portal.call(lambda: engine.gate_event.set())
        for _ in range(30):
            seen += s.probe()
            if s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        seen += s.probe()
        assert _plans(seen) == [("preparing", None), ("queued", "Can you tell me more about the chest pain?")]
        s.quiet(3.5)
        seen += s.probe()                                  # issued
        seen += s.probe()
        assert _plans(seen)[-1] == ("idle", None)
        assert any(m.get("type") == "auto_speak" for m in seen)
        _stop(s)


def test_a_cancelled_tap_leaves_the_queue_intact_and_the_question_issues_at_the_next_quiet(gate):
    """The guarded tap's other branch: the doctor taps over a queued
    question, is asked, and does nothing (or chooses "let Alba ask" — a
    client-side choice that sends nothing). No auto.doctor_tap row, the
    queue untouched, and the machine's question issues at the next quiet."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        for _ in range(30):
            s.probe()
            if s.auto["queued"] is not None:
                break
            time.sleep(0.03)
        queued_text = s.auto["queued"]["text"]
        version = s.entry["agenda"].current_version
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": version, "index": 0}}))
        confirm = _until(s.ws, {"speak_confirm", "speak_ready", "speak_refused"})
        assert confirm["type"] == "speak_confirm"
        assert confirm["queued"] == {"kind": "question", "text": queued_text}
        assert confirm["ref"] == {"kind": "cds_question", "assessment_version": version, "index": 0}
        assert s.auto["queued"] is not None and s.auto["queued"]["text"] == queued_text
        assert s.entry["pending_utterance"] is None, "nothing was prepared for the doctor's tap"
        ask = s.wait_for_auto_speak()
        assert ask["text"] == queued_text, "the machine's question, at the next quiet"
        s.play(ask["utterance_id"])
        _stop(s)
    assert _audit("auto.doctor_tap", s.session_id) == []


def test_a_tap_while_the_question_is_still_being_prepared_is_guarded_too(gate):
    """"Planned or queued": with the revision running and nothing queued
    yet, the confirmation says a question is being prepared (queued null)."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    engine.gate_event = asyncio.Event()                    # the revision never lands
    with live(gate) as s:
        s.to_golden()
        s.seed_agenda(Q_SLEEP)
        s.to_open()
        assert s.auto["revision"] in ("requested", "running") and s.auto["queued"] is None
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": 1, "index": 0}}))
        confirm = _until(s.ws, {"speak_confirm", "speak_ready", "speak_refused"})
        assert confirm["type"] == "speak_confirm" and confirm["queued"] is None
        assert "preparing" in confirm["detail"]
        _stop(s)


def test_a_tap_with_nothing_planned_is_unchanged_and_audited_unconfirmed(gate):
    """Nothing planned or queued: the tap speaks at once, as before, and its
    row says confirmed false with nothing displaced."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(False, False)]
    with live(gate) as s:
        s.to_golden()
        s.seed_agenda(Q_SLEEP)
        assert s.auto["queued"] is None and s.auto["plan_task"] is None
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": 1, "index": 0}}))
        ready = _until(s.ws, {"speak_ready", "speak_confirm"})
        assert ready["type"] == "speak_ready"
        s.play(ready["utterance_id"])
        _stop(s)
    taps = _audit("auto.doctor_tap", s.session_id)
    assert len(taps) == 1 and taps[0]["confirmed"] is False and taps[0]["displaced"] is None


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
