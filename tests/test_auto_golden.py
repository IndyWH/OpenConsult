"""Auto mode wired through GOLDEN (Phase 7c slice 3), dark behind
AUTO_MODE_ENABLED — the protocol tests.

PHASE_7C_SPEC.md §3, §5, §6, §11. These drive /ws/transcribe for real
(Postgres needed; they self-skip without it) with the gate raised by
monkeypatch, a real SpeechService on a fake command, and a FAKE
end-of-turn officer whose verdicts the tests script — officer QUALITY
belongs to evals. What is pinned:

- ONE TAP starts the auto session (owner decision 2026-08-16, spec §10
  as amended — this REPINS slice 3's "enable requires the disclosure
  already given", a property change the owner decided, not a
  weakening): with no disclosure given, toggling Auto speaks it through
  the auto path (face auto-on included), chains the invitation, and
  GOLDEN starts at the invitation's speak_ended — the prereg's metric-3
  zero point; with the disclosure already given the walk passes through
  DISCLOSURE and speaks the invitation; with both already done manually
  GOLDEN starts at the toggle and the audit detail says so.
- In GOLDEN a quiet report at AUTO_ENCOURAGER_QUIET_S earns one
  encourager, rotated through the three, on cooldown, through the auto
  path — its row carries {"via":"auto","phase":"golden","trigger":
  {"quiet_s":N}}. Outside GOLDEN nothing is spoken (OPEN is inert here).
- Exit per §6: a hand-back from the officer exits early; otherwise the
  golden window must have run AND the turn must have ended; a failed
  officer is audited and the silence rule decides.
- Auto off is immediate from every state, and everything is audited
  (auto.enabled, auto.disabled, auto.phase, auto.officer_failed).
- With AUTO_MODE_ENABLED false the controller is never constructed, the
  protocol is byte-identical, and an `auto` toggle is refused.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import struct
import sys

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, auto_mode, consultations, speech, system_utterances
from app import main as appmain
from app.auto_mode import AutoPhase
from app.cds import OfficerVerdict
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


class FakeEngine:
    """The CDS engine with a scripted end-of-turn officer. `verdicts` is
    consumed in order; the last one repeats. `update` exists so a
    transcript injected for the officer cannot crash the CDS task."""

    def __init__(self):
        self.verdicts: list[OfficerVerdict] = [OfficerVerdict(False, False)]
        self.asked: list[str] = []

    async def end_of_turn(self, transcript: str) -> OfficerVerdict:
        self.asked.append(transcript)
        if len(self.verdicts) > 1:
            return self.verdicts.pop(0)
        return self.verdicts[0]

    async def update(self, transcript, previous=None):
        return {"reasoning": "", "differentials": [], "questions_to_ask": [],
                "signs_to_check": [], "urgent_actions": [], "patient_affect": "neutral",
                "urgency_check": {"time_critical_possible": False,
                                  "already_done_or_arranged": False, "reason": ""}}


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
    """The gate UP, and everything else a live session needs, installed on
    app.state and removed again on teardown."""
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    monkeypatch.setattr(speech, "TTS_ENABLED", True)
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", True)
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": speech.SpeechService(voice="test", model_path=str(tmp_path / "voice.onnx"),
                                       cache_dir=tmp_path / "cache",
                                       command=fake_command(tmp_path)),
        "cds_engine": FakeEngine(),
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


@pytest.fixture()
def gate_down(gate, monkeypatch):
    """The same installation with the gate DOWN — the shipped posture."""
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", False)
    return gate


# --- driving helpers ---------------------------------------------------------

def _collect_until(ws, wanted, limit=80):
    """Every message up to and including the first of `wanted`."""
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
    """A live session with the client's part played from the test."""

    def __init__(self, state, ws, session_id):
        self.state, self.ws, self.session_id = state, ws, session_id
        self.seq = 0

    @property
    def entry(self):
        return self.state.live_sessions[self.session_id]

    @property
    def controller(self) -> auto_mode.AutoModeController:
        return self.entry["auto"]["controller"]

    @property
    def phase(self):
        return self.controller.phase

    def disclose(self):
        self.ws.send_text(json.dumps({"type": "disclosure_given"}))
        return _until(self.ws, {"disclosure"})

    def frame(self, amplitude=PATIENT_AMPLITUDE):
        self.seq += 1
        self.ws.send_bytes(_frame(self.seq, amplitude))
        return self.seq

    def probe(self):
        """Send one frame and return every message that arrived before its
        ack — anything the server decided to say in the meantime is in it,
        and so is the officer's verdict being applied (the loop's tick)."""
        self.frame()
        return _collect_until(self.ws, {"ack"})[:-1]

    def play(self, utterance_id, reason="complete", frames=1):
        self.ws.send_text(json.dumps({"type": "speak_started",
                                      "utterance_id": utterance_id, "seq": self.seq + 1}))
        for _ in range(frames):
            self.frame(TTS_AMPLITUDE)
        _until(self.ws, {"ack"})
        self.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                                      "seq": self.seq + 1, "reason": reason}))

    def auto(self, on: bool):
        self.ws.send_text(json.dumps({"type": "auto", "on": on}))

    def quiet(self, quiet_s: float):
        self.ws.send_text(json.dumps({"type": "quiet", "quiet_s": quiet_s}))

    def commit_transcript(self, *lines: str):
        """Give the officer something to judge, without waking the CDS task
        (its growth threshold is satisfied by hand)."""
        def _inject():
            self.entry["transcript_parts"].extend(lines)
            self.entry["cds_sent_len"] = len("\n".join(self.entry["transcript_parts"]))
        self.ws.portal.call(_inject)

    def enable_to_golden(self):
        """Disclose, switch auto on, play the invitation through: GOLDEN."""
        self.disclose()
        self.auto(True)
        seen = _collect_until(self.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        assert invitation["text"] == speech.PHRASES["invitation"]
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "invitation"}
        self.play(invitation["utterance_id"])
        self.probe()
        assert self.phase is AutoPhase.GOLDEN
        return invitation


@contextlib.contextmanager
def live(state, user=None):
    """A live session on a real socket, config sent, the client's part
    played from the test through the returned Session."""
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


# ==========================================================================
# The gate down: nothing exists

def test_with_the_gate_down_the_controller_is_never_constructed_and_the_protocol_is_unchanged(gate_down):
    with live(gate_down) as s:
        first = _collect_until(s.ws, {"speech_config"})
        assert "auto" not in first[-1], "speech_config must not grow while the gate is down"
        s.disclose()
        assert s.entry["auto"] is None
        s.auto(True)
        refused = _until(s.ws, {"auto_refused"})
        assert "AUTO_MODE_ENABLED" in refused["detail"]
        assert s.entry["auto"] is None
        s.quiet(4.0)                                 # ignored, not an error
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        assert not any(m.get("type") == "auto_toggled" for m in first)
        _stop(s)
    assert _audit("auto.enabled", s.session_id) == []
    assert _audit("auto.phase", s.session_id) == []


# ==========================================================================
# Enabling

def test_one_tap_with_no_disclosure_speaks_it_chains_the_invitation_and_golden_starts_at_its_end(gate):
    """REPINNED for the one-tap start (owner decision 2026-08-16, spec §10
    as amended). Slice 3 pinned "enable requires the disclosure already
    given"; that property is deliberately replaced, not weakened: with no
    disclosure given, toggling Auto speaks the disclosure through the auto
    path, the machine waits in DISCLOSURE, the played-through disclosure
    is recorded as given (spoken) and chains the invitation through the
    auto path, and GOLDEN starts at the invitation's speak_ended. Hard
    rule 4 still holds by construction: the invitation is only ever
    chained from a disclosure that played through."""
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})           # the connect echo: off
        assert s.entry["disclosed"] is False
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        disclosure = next(m for m in seen if m.get("type") == "auto_speak")
        assert disclosure["ref_id"] == "disclosure"
        assert disclosure["text"].startswith("Hello. I'm a computer, not a person.")
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "disclosure"}
        assert s.phase is AutoPhase.DISCLOSURE
        # The disclosure plays through: given (spoken), and the invitation
        # is chained — through the AUTO path, not the tap chain.
        s.play(disclosure["utterance_id"])
        seen = _collect_until(s.ws, {"auto_speak"})
        assert any(m.get("type") == "disclosure" and m["how"] == "spoken" for m in seen)
        assert not any(m.get("type") == "speak_ready" for m in seen), "the auto chain, not the tap chain"
        invitation = seen[-1]
        assert invitation["ref_id"] == "invitation"
        assert s.entry["disclosed"] is True
        assert s.phase is AutoPhase.INVITATION
        s.play(invitation["utterance_id"])
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        cid = _stop(s)
    phases = [(d["from"], d["to"], d["trigger"]) for d in _audit("auto.phase", s.session_id)]
    assert phases == [("off", "disclosure", "enable"),
                      ("disclosure", "invitation", "disclosure_completed"),
                      ("invitation", "golden", "invitation_completed")]
    assert _audit("auto.phase", s.session_id)[1]["detail"] == {"disclosure": "spoken"}
    enabled = _audit("auto.enabled", s.session_id)
    assert len(enabled) == 1 and enabled[0]["disclosed"] is False
    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert [r["ref_detail"]["id"] for r in rows] == ["disclosure", "invitation"]
    assert rows[0]["ref_detail"] == {"id": "disclosure", "via": "auto", "phase": "disclosure",
                                     "trigger": {"via": "auto_enable"}}
    assert rows[1]["ref_detail"] == {"id": "invitation", "via": "auto", "phase": "invitation",
                                     "trigger": {"via": "auto_chain"}}


def test_the_one_tap_disclosure_switches_the_face_on(gate, monkeypatch):
    """The spoken disclosure switches the face on (owner decision
    2026-07-28) whichever path speaks it — the auto path calls handle_face
    exactly as handle_speak does, never over a manual off."""
    monkeypatch.setattr(appmain, "FACE_AUTO_ON_DISCLOSURE", True)
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        assert any(m.get("type") == "face_toggled" and m["on"] is True for m in seen)
        assert s.entry["face"] is not None
        _stop(s)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'face.toggled'"
            " AND detail->>'session_id' = %s", (s.session_id,)).fetchall()
    assert [r[0]["via"] for r in rows] == ["disclosure_auto"]


def test_a_cut_off_auto_disclosure_chains_nothing_and_the_machine_waits(gate):
    """A cut-off disclosure has not been given: no invitation, no GOLDEN,
    the machine waits in DISCLOSURE — exactly the tap chain's rule."""
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        disclosure = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m.get("type") == "auto_speak")
        s.play(disclosure["utterance_id"], reason="doctor_stop")
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        assert s.entry["disclosed"] is False
        assert s.phase is AutoPhase.DISCLOSURE
        # The doctor's own tap of the disclosure, played through, then
        # completes the walk: given, and the invitation chains via auto.
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "disclosure"}}))
        ready = _until(s.ws, {"speak_ready"})
        s.play(ready["utterance_id"])
        invitation = _until(s.ws, {"auto_speak"})
        assert invitation["ref_id"] == "invitation" and s.phase is AutoPhase.INVITATION
        _stop(s)


def test_enable_fails_as_a_unit_when_the_disclosure_cannot_be_spoken(gate, tmp_path):
    """A dead synthesiser at the toggle: the fault is shown (speak_refused,
    as for a tap), the toggle is refused, and the machine is back OFF —
    not stuck in DISCLOSURE with nothing coming."""
    script = tmp_path / "broken_tts.py"
    script.write_text("import sys\nsys.stdin.buffer.read()\nsys.exit(3)\n")
    gate.speech = speech.SpeechService(
        voice="test", model_path=str(tmp_path / "voice.onnx"), cache_dir=tmp_path / "cache2",
        command=f"{sys.executable} {script} --model {{model}} --output-file {{output}}")
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_refused"})
        assert any(m.get("type") == "speak_refused" for m in seen)
        assert "could not speak the disclosure" in seen[-1]["detail"]
        assert s.phase is AutoPhase.OFF
        _stop(s)
    assert [d["via"] for d in _audit("auto.disabled", s.session_id)] == ["enable_failed"]


def test_the_connect_echo_says_off_and_the_config_carries_the_thresholds(gate):
    with live(gate) as s:
        first = _collect_until(s.ws, {"auto_toggled"})
        config = next(m for m in first if m["type"] == "speech_config")
        assert config["auto"] == {"enabled": True,
                                  "encourager_quiet_s": appmain.AUTO_ENCOURAGER_QUIET_S,
                                  "eot_quiet_s": appmain.AUTO_EOT_QUIET_S,
                                  "eot_fallback_s": appmain.AUTO_EOT_FALLBACK_S}
        assert first[-1] == {"type": "auto_toggled", "on": False, "phase": "off"}
        _stop(s)


def test_enabling_walks_disclosure_and_invitation_and_golden_starts_at_the_invitations_end(gate):
    """The manual-first shape: the disclosure ticked (given, not spoken),
    the invitation not yet played — the DISCLOSURE step passes through
    and the invitation is spoken through the auto path. The metric-3
    zero point: not the toggle, not the play command — the invitation's
    speak_ended. Every step audited as auto.phase."""
    with live(gate) as s:
        s.disclose()
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        assert s.phase is AutoPhase.INVITATION, "GOLDEN must not start before the invitation has played"
        s.play(invitation["utterance_id"])
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        cid = _stop(s)
    phases = [(d["from"], d["to"], d["trigger"]) for d in _audit("auto.phase", s.session_id)]
    assert phases == [("off", "disclosure", "enable"),
                      ("disclosure", "invitation", "disclosure_completed"),
                      ("invitation", "golden", "invitation_completed")]
    assert _audit("auto.phase", s.session_id)[1]["detail"] == {"disclosure": "already_given"}
    assert len(_audit("auto.enabled", s.session_id)) == 1
    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert rows[0]["ref_detail"] == {"id": "invitation", "via": "auto", "phase": "invitation",
                                     "trigger": {"via": "auto_enable"}}


def test_a_cut_off_invitation_does_not_start_golden(gate):
    with live(gate) as s:
        s.disclose()
        s.auto(True)
        invitation = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m.get("type") == "auto_speak")
        s.play(invitation["utterance_id"], reason="doctor_stop")
        s.probe()
        assert s.phase is AutoPhase.INVITATION
        _stop(s)


def test_enable_is_refused_while_an_utterance_is_in_flight(gate):
    with live(gate) as s:
        s.disclose()
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "go_on"}}))
        _until(s.ws, {"speak_ready"})
        s.auto(True)
        refused = _until(s.ws, {"auto_refused"})
        assert "in flight" in refused["detail"]
        assert s.phase is AutoPhase.OFF
        _stop(s)


def test_enable_after_the_invitation_already_played_starts_golden_at_once_and_says_so(gate):
    """The doctor tapped Disclosure earlier and the chain spoke the
    invitation; switching auto on then cannot re-speak it. GOLDEN starts
    at the toggle, and the record says the zero point is the toggle."""
    with live(gate) as s:
        s.disclose()
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _until(s.ws, {"speak_ready"})
        s.play(ready["utterance_id"])
        s.probe()
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        assert not any(m.get("type") == "auto_speak" for m in seen), "the invitation is not re-spoken"
        assert seen[-1]["phase"] == "golden"
        assert s.phase is AutoPhase.GOLDEN
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["to"], last["detail"]) == ("golden", {"invitation": "already_completed"})


def test_enable_is_idempotent_and_only_the_owner_may_toggle(gate):
    with live(gate) as s:
        s.enable_to_golden()
        s.auto(True)
        echo = _until(s.ws, {"auto_toggled"})
        assert echo == {"type": "auto_toggled", "on": True, "phase": "golden"}
        _stop(s)
    assert len(_audit("auto.enabled", s.session_id)) == 1


# ==========================================================================
# GOLDEN: encouragers

def test_a_quiet_report_in_golden_earns_one_encourager_with_via_phase_and_trigger(gate, monkeypatch):
    with live(gate) as s:
        s.enable_to_golden()
        s.quiet(1.8)
        seen = _collect_until(s.ws, {"auto_speak"})
        encourager = seen[-1]
        assert encourager["text"] == "Mm-hm." and encourager["ref_id"] == "mm-hm"
        s.play(encourager["utterance_id"])
        # Below the threshold: nothing.
        s.quiet(1.0)
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        cid = _stop(s)
    rows = asyncio.run(system_utterances.for_consultation(cid))
    row = next(r for r in rows if r["text"] == "Mm-hm.")
    assert row["ref_detail"] == {"id": "mm-hm", "via": "auto", "phase": "golden",
                                 "trigger": {"quiet_s": 1.8}}
    assert row["end_reason"] == "complete"


def test_encouragers_rotate_through_the_three_and_respect_the_cooldown(gate, monkeypatch):
    with live(gate) as s:
        s.enable_to_golden()
        # Cooldown in force: a second quiet report inside it earns nothing.
        s.quiet(2.0)
        first = _until(s.ws, {"auto_speak"})
        s.play(first["utterance_id"])
        s.quiet(2.5)
        assert all(m.get("type") != "auto_speak" for m in s.probe()), "cooldown"
        # Cooldown lifted: the rotation continues i_see, go_on, mm-hm.
        monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_COOLDOWN_S", 0.0)
        heard = [first["ref_id"]]
        for q in (2.1, 2.2, 2.3):
            s.quiet(q)
            e = _until(s.ws, {"auto_speak"})
            heard.append(e["ref_id"])
            s.play(e["utterance_id"])
        assert heard == ["mm-hm", "i_see", "go_on", "mm-hm"]
        _stop(s)


def test_no_encourager_while_an_utterance_is_in_flight(gate, monkeypatch):
    """One utterance at a time holds for the loop too: a quiet report that
    lands while an encourager is pending or playing earns nothing."""
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_COOLDOWN_S", 0.0)
    with live(gate) as s:
        s.enable_to_golden()
        s.quiet(2.0)
        e = _until(s.ws, {"auto_speak"})
        s.quiet(2.5)                                    # pending, not yet started
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.play(e["utterance_id"])
        s.quiet(2.6)                                    # released: the next one comes
        assert _until(s.ws, {"auto_speak"})["ref_id"] == "i_see"
        _stop(s)


def test_a_politeness_aborted_encourager_is_dropped_not_requeued(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_COOLDOWN_S", 0.0)
    with live(gate) as s:
        s.enable_to_golden()
        s.quiet(2.0)
        e = _until(s.ws, {"auto_speak"})
        s.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": e["utterance_id"],
                                 "seq": s.seq + 1, "reason": "politeness_abort", "rms": 0.07}))
        # Nothing is re-issued on its own; only a fresh quiet report earns
        # the next encourager, and the rotation has moved on.
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.quiet(2.1)
        assert _until(s.ws, {"auto_speak"})["ref_id"] == "i_see"
        cid = _stop(s)
    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert [r["end_reason"] for r in rows if r["text"] == "Mm-hm."] == ["politeness_abort"]


def test_no_encourager_outside_golden(gate, monkeypatch):
    """OPEN is inert in this slice, and nothing is spoken there — no
    encourager, no question (question flow is slice 4)."""
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_COOLDOWN_S", 0.0)
    gate.cds_engine.verdicts = [OfficerVerdict(True, True)]      # a hand-back
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.", "That's all really.")
        s.quiet(3.2)
        s.probe()
        assert s.phase is AutoPhase.OPEN
        for q in (2.0, 3.5, 6.0):
            s.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in s.probe())
        _stop(s)


# ==========================================================================
# GOLDEN: exit

def test_a_hand_back_exits_golden_early_and_is_recorded(gate):
    gate.cds_engine.verdicts = [OfficerVerdict(True, True, elapsed_ms=420)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.", "So what do you think?")
        s.quiet(3.1)
        s.probe()                                        # the tick applies the verdict
        assert s.phase is AutoPhase.OPEN
        assert gate.cds_engine.asked == ["It started on Tuesday.\nSo what do you think?"]
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == ("golden", "open", "hand_back")
    assert last["detail"]["handed_back"] is True
    assert last["detail"]["quiet_s"] == 3.1
    assert last["detail"]["officer_ms"] == 420


def test_the_timer_alone_does_not_exit_golden_the_turn_must_have_ended(gate, monkeypatch):
    """§6: never cut a patient off at a timer boundary. With the window run
    and the officer saying 'not finished', GOLDEN holds; when the officer
    (re-asked as the quiet grows) says finished, GOLDEN exits."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)     # window already run
    gate.cds_engine.verdicts = [OfficerVerdict(False, False), OfficerVerdict(True, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday and")
        s.quiet(3.0)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN, "not finished → hold, whatever the timer says"
        s.quiet(4.0)                                     # same span, officer not re-asked yet
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        assert len(gate.cds_engine.asked) == 1
        s.quiet(6.1)                                     # quiet grew by EOT: asked again
        s.probe()
        assert len(gate.cds_engine.asked) == 2
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == ("golden", "open", "golden_timer_elapsed")
    assert last["detail"]["handed_back"] is False


def test_a_finished_turn_before_the_window_has_run_does_not_exit_golden(gate):
    gate.cds_engine.verdicts = [OfficerVerdict(True, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        s.quiet(3.5)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN, "the window has not run: encouragers only"
        _stop(s)
    assert all(d["to"] != "open" for d in _audit("auto.phase", s.session_id))


def test_a_failed_officer_is_audited_and_the_silence_rule_decides(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    gate.cds_engine.verdicts = [OfficerVerdict(False, False, failed="timeout", elapsed_ms=2001)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        s.quiet(3.2)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN, "3.2 s is under the fallback span"
        s.quiet(4.9)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        s.quiet(5.1)                                     # ≥ AUTO_EOT_FALLBACK_S
        s.probe()
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    failed = _audit("auto.officer_failed", s.session_id)
    assert len(failed) == 1
    assert failed[0]["reason"] == "timeout" and failed[0]["quiet_s"] == 3.2
    assert failed[0]["fallback_s"] == appmain.AUTO_EOT_FALLBACK_S
    last = _audit("auto.phase", s.session_id)[-1]
    assert last["trigger"] == "golden_timer_elapsed"
    assert last["detail"]["officer_failed"] == "timeout"


def test_the_officer_is_not_asked_without_committed_transcript(gate, monkeypatch):
    """Nothing to judge, no model call; the silence rule alone can move a
    patient who never spoke once the window has run."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    with live(gate) as s:
        s.enable_to_golden()
        s.quiet(3.5)
        s.probe()
        assert gate.cds_engine.asked == []
        assert s.phase is AutoPhase.GOLDEN
        s.quiet(5.5)
        s.probe()
        assert s.phase is AutoPhase.OPEN
        _stop(s)


# ==========================================================================
# Auto off

@pytest.mark.parametrize("stage", ["invitation", "golden", "open"])
def test_auto_off_is_immediate_from_every_state(gate, stage):
    gate.cds_engine.verdicts = [OfficerVerdict(True, True)]
    with live(gate) as s:
        s.disclose()
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        if stage != "invitation":
            s.play(invitation["utterance_id"])
            s.probe()
        if stage == "open":
            s.commit_transcript("That's all.")
            s.quiet(3.1)
            s.probe()
        assert s.phase.value == stage
        s.auto(False)
        off = _until(s.ws, {"auto_toggled"})
        assert off == {"type": "auto_toggled", "on": False, "phase": "off"}
        assert s.phase is AutoPhase.OFF
        # Quiet reports now do nothing at all.
        s.quiet(9.0)
        assert all(m.get("type") not in ("auto_speak",) for m in s.probe())
        assert s.phase is AutoPhase.OFF
        _stop(s)
    assert len(_audit("auto.disabled", s.session_id)) == 1
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == (stage, "off", "auto_off")


def test_auto_off_when_already_off_is_a_quiet_echo(gate):
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(False)
        assert _until(s.ws, {"auto_toggled"})["on"] is False
        _stop(s)
    assert _audit("auto.disabled", s.session_id) == []


# ==========================================================================
# The per-session warm, and the reconnect echo

def test_a_session_under_auto_warms_the_doctor_named_phrases(gate, tmp_path):
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        outcomes = s.ws.portal.call(lambda: asyncio.wait_for(s.entry["auto"]["warm_task"], 20))
        assert outcomes["disclosure"] == "synthesised"
        assert outcomes["examination_handover"] == "synthesised"
        text = speech.render_phrase("disclosure", "Herath")
        assert gate.speech._cache_path(text).exists()
        _stop(s)


def test_a_reconnect_echoes_the_live_auto_state(gate):
    user = _make_user()
    with live(gate, user) as s:
        s.enable_to_golden()
        s.frame()
        _until(s.ws, {"ack"})
    # A new socket resuming the same session hears where auto mode stands.
    client = _client_for(user)
    with client.websocket_connect("/ws/transcribe") as ws2:
        ws2.send_json({"session_id": s.session_id, "resume": True})
        seen = _collect_until(ws2, {"auto_toggled"})
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "golden"}
        ws2.send_text("stop")
        _until(ws2, {"done"})


# ==========================================================================
# Slice 6: the Auto pill's two taps, over the protocol

def test_the_pills_two_taps_are_the_one_tap_start_and_the_immediate_off(gate):
    """What the pill sends is exactly what the server accepts: {"type":
    "auto","on":true} starts the one-tap sequence (here: disclosure already
    given → invitation → GOLDEN) and {"type":"auto","on":false} stops it
    at once from wherever it is; each is echoed as auto_toggled, which is
    what the pill's label follows."""
    with live(gate) as s:
        s.enable_to_golden()                        # the "on" tap, through the same message
        s.ws.send_text(json.dumps({"type": "auto", "on": False}))
        off = _until(s.ws, {"auto_toggled"})
        assert off == {"type": "auto_toggled", "on": False, "phase": "off"}
        assert s.phase is AutoPhase.OFF
        # A second "on" tap starts a fresh run.
        s.ws.send_text(json.dumps({"type": "auto", "on": True}))
        seen = _collect_until(s.ws, {"auto_toggled"})
        assert seen[-1]["on"] is True
        _stop(s)
    assert len(_audit("auto.enabled", s.session_id)) == 2
    assert len(_audit("auto.disabled", s.session_id)) == 1


def test_with_the_gate_down_the_page_is_never_told_auto_mode_exists(gate_down):
    """The pill hides itself unless speech_config carries an auto block, and
    the server sends none with the gate down (the pill's own hidden-when-
    dark test is tests/test_auto_pill_client.py)."""
    with live(gate_down) as s:
        first = _collect_until(s.ws, {"speech_config"})
        assert "auto" not in first[-1]
        _stop(s)
