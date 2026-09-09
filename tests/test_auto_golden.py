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
import time

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
        self.timeouts: list[float | None] = []   # the bound each ask came with (E4)

    async def end_of_turn(self, transcript: str, *, timeout_s=None) -> OfficerVerdict:
        self.asked.append(transcript)
        self.timeouts.append(timeout_s)
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
        self.since = "speech"        # what began the current quiet span (E2)

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

    def play(self, utterance_id, reason="complete", frames=1, *, keeps_quiet_clock=False):
        self.ws.send_text(json.dumps({"type": "speak_started",
                                      "utterance_id": utterance_id, "seq": self.seq + 1}))
        for _ in range(frames):
            self.frame(TTS_AMPLITUDE)
        _until(self.ws, {"ack"})
        self.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                                      "seq": self.seq + 1, "reason": reason}))
        if not keeps_quiet_clock:             # "Let me think" keeps the span (2026-09-09)
            self.since = "playback"

    def auto(self, on: bool):
        self.ws.send_text(json.dumps({"type": "auto", "on": on}))

    def quiet(self, quiet_s: float):
        self.ws.send_text(json.dumps({"type": "quiet", "quiet_s": quiet_s, "since": self.since}))

    def commit_transcript(self, *lines: str):
        """Give the officer something to judge, without waking the CDS task
        (its growth threshold is satisfied by hand)."""
        def _inject():
            self.entry["transcript_parts"].extend(lines)
            self.entry["cds_sent_len"] = len("\n".join(self.entry["transcript_parts"]))
        self.ws.portal.call(_inject)
        self.since = "speech"                 # the patient spoke: a fresh span of theirs

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
        # The server creates the entry when it has processed the handshake;
        # a test whose first line reads the entry must not race it (the
        # suite's slower database showed the race twice on 2026-09-09).
        for _ in range(300):
            if session_id in state.live_sessions:
                break
            time.sleep(0.01)
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
        # REPINNED 2026-09-09 (owner decision, pilot 488 G1): the enable
        # never reports success while the disclosure has not played
        # through — the echo at issue says `starting`, and the on-echo
        # follows the disclosure's completion below.
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "disclosure",
                            "starting": True}
        assert s.phase is AutoPhase.DISCLOSURE
        # The disclosure plays through: given (spoken), and the invitation
        # is chained — through the AUTO path, not the tap chain.
        s.play(disclosure["utterance_id"])
        seen = _collect_until(s.ws, {"auto_toggled"})
        assert any(m.get("type") == "disclosure" and m["how"] == "spoken" for m in seen)
        assert not any(m.get("type") == "speak_ready" for m in seen), "the auto chain, not the tap chain"
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        assert invitation["ref_id"] == "invitation"
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "invitation"}, \
            "success is reported once the disclosure has played through"
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


def _abort(s: Session, utterance_id: str, rms: float = 0.0314) -> None:
    """The client's politeness abort, with the reading it took (488: 0.0314)."""
    s.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": utterance_id,
                               "seq": s.seq + 1, "reason": "politeness_abort", "rms": rms}))


def test_the_488_shape_an_aborted_enable_disclosure_is_retried_on_the_next_quiet_report(gate):
    """Owner decision 2026-09-09 (pilot 488 G1). The enable's disclosure is
    politeness-aborted 105 ms after issue (0.0314 RMS at the cafe); in 488
    nothing re-issued it and the machine sat in DISCLOSURE, on and silent,
    for 41 s. Now: the echo at issue says `starting` (not on — the
    disclosure has not played through), the next quiet report re-issues
    the disclosure (attempt 2, audited auto.enable_retry with the abort's
    RMS), and a disclosure that plays through on the second try chains the
    invitation as normal, with the on-echo reported then."""
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        first = next(m for m in seen if m.get("type") == "auto_speak")
        assert first["ref_id"] == "disclosure"
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "disclosure",
                            "starting": True}, "not success: the disclosure has not played"
        _abort(s, first["utterance_id"])                 # 105 ms later: the room was loud
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        assert s.phase is AutoPhase.DISCLOSURE and s.entry["disclosed"] is False
        s.quiet(1.8)                                     # the next quiet report: the retry
        seen = _collect_until(s.ws, {"auto_speak"})
        second = seen[-1]
        assert second["ref_id"] == "disclosure" and second["utterance_id"] != first["utterance_id"]
        assert not any(m.get("type") == "auto_toggled" for m in seen), "still not reported on"
        s.play(second["utterance_id"])                   # plays through on the second try
        seen = _collect_until(s.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        assert invitation["ref_id"] == "invitation", "the invitation chains as normal"
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "invitation"}
        assert s.entry["disclosed"] is True
        s.play(invitation["utterance_id"])
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        assert s.entry["auto"]["enable_chain"] is None
        cid = _stop(s)
    retries = _audit("auto.enable_retry", s.session_id)
    assert len(retries) == 1
    assert retries[0]["phrase"] == "disclosure" and retries[0]["attempt"] == 2
    assert retries[0]["abort_rms"] == 0.0314 and retries[0]["floor"] == 0.02
    assert retries[0]["retries"] == appmain.AUTO_ENABLE_RETRIES
    assert _audit("auto.disabled", s.session_id) == []
    rows = asyncio.run(system_utterances.for_consultation(cid))
    disclosures = [r for r in rows if r["ref_detail"]["id"] == "disclosure"]
    assert sorted(r["end_reason"] for r in disclosures) == ["complete", "politeness_abort"]
    retried = next(r for r in disclosures if r["end_reason"] == "complete")
    assert retried["ref_detail"]["trigger"] == {"via": "auto_enable_retry", "attempt": 2,
                                                "quiet_s": 1.8}


def test_three_aborts_switch_the_machine_off_with_too_loud_to_start_on_the_record_and_the_pill(gate):
    """Owner decision 2026-09-09 (G1): with the tries spent —
    AUTO_ENABLE_RETRIES attempts in all, the enable's own issue the first —
    the machine switches itself off: auto.disabled with reason
    too_loud_to_start, the measured RMS and the floor; the pill told in
    plain words ("Too loud to start: 0.031 against 0.020"); the machine
    OFF, not sitting in DISCLOSURE. The attack reaches its target: three
    disclosures were issued and every one was aborted."""
    assert appmain.AUTO_ENABLE_RETRIES == 3
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        issued = [next(m for m in seen if m.get("type") == "auto_speak")]
        _abort(s, issued[0]["utterance_id"], rms=0.0290)
        s.quiet(1.8)
        issued.append(_until(s.ws, {"auto_speak"}))                # attempt 2
        _abort(s, issued[1]["utterance_id"], rms=0.0350)
        s.quiet(1.8)
        issued.append(_until(s.ws, {"auto_speak"}))                # attempt 3, the last
        assert len({m["utterance_id"] for m in issued}) == 3
        assert all(m["ref_id"] == "disclosure" for m in issued)
        assert s.phase is AutoPhase.DISCLOSURE
        _abort(s, issued[2]["utterance_id"], rms=0.0314)          # the third abort: off
        off = _until(s.ws, {"auto_toggled"})
        assert off == {"type": "auto_toggled", "on": False, "phase": "off",
                       "reason": "Too loud to start: 0.031 against 0.020"}
        assert s.phase is AutoPhase.OFF
        assert s.entry["auto"]["enable_chain"] is None
        s.quiet(3.0)
        assert all(m.get("type") != "auto_speak" for m in s.probe()), "off means nothing more"
        _stop(s)
    retries = _audit("auto.enable_retry", s.session_id)
    assert [(r["attempt"], r["abort_rms"]) for r in retries] == [(2, 0.029), (3, 0.035)]
    disabled = _audit("auto.disabled", s.session_id)
    assert len(disabled) == 1
    assert disabled[0]["via"] == "too_loud_to_start" and disabled[0]["reason"] == "too_loud_to_start"
    assert disabled[0]["rms"] == 0.0314 and disabled[0]["floor"] == 0.02
    assert disabled[0]["attempts"] == 3 and disabled[0]["phrase"] == "disclosure"
    phases = [(d["from"], d["to"]) for d in _audit("auto.phase", s.session_id)]
    assert phases == [("off", "disclosure"), ("disclosure", "off")]


def test_the_retry_window_spent_switches_the_machine_off_at_the_next_report(gate, monkeypatch):
    """The window half of the rule: a retry is only ever issued inside
    AUTO_ENABLE_RETRY_WINDOW_S of the first issue. With the window already
    past when the report arrives — attempts still in hand — the machine
    switches itself off with the same reason."""
    monkeypatch.setattr(appmain, "AUTO_ENABLE_RETRY_WINDOW_S", 0.0)
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        first = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m.get("type") == "auto_speak")
        _abort(s, first["utterance_id"])
        s.quiet(1.8)
        off = _until(s.ws, {"auto_toggled"})
        assert off["on"] is False and off["reason"] == "Too loud to start: 0.031 against 0.020"
        assert s.phase is AutoPhase.OFF
        _stop(s)
    assert _audit("auto.enable_retry", s.session_id) == []
    assert [d["reason"] for d in _audit("auto.disabled", s.session_id)] == ["too_loud_to_start"]


def test_an_aborted_chained_invitation_is_retried_the_same_way(gate):
    """The chained invitation is the enable chain's second step (the
    decision names it): aborted, it is re-issued on the next quiet report
    and GOLDEN starts at its end as normal."""
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.auto(True)
        disclosure = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m.get("type") == "auto_speak")
        s.play(disclosure["utterance_id"])
        seen = _collect_until(s.ws, {"auto_toggled"})
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        assert invitation["ref_id"] == "invitation" and s.phase is AutoPhase.INVITATION
        _abort(s, invitation["utterance_id"], rms=0.041)
        assert s.phase is AutoPhase.INVITATION
        s.quiet(2.0)
        again = _until(s.ws, {"auto_speak"})
        assert again["ref_id"] == "invitation" and again["utterance_id"] != invitation["utterance_id"]
        s.play(again["utterance_id"])
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        _stop(s)
    retries = _audit("auto.enable_retry", s.session_id)
    assert [(r["phrase"], r["attempt"], r["abort_rms"]) for r in retries] == [("invitation", 2, 0.041)]


def test_the_connect_echo_says_off_and_the_config_carries_the_thresholds(gate):
    with live(gate) as s:
        first = _collect_until(s.ws, {"auto_toggled"})
        config = next(m for m in first if m["type"] == "speech_config")
        assert config["auto"] == {"enabled": True,
                                  "golden_s": appmain.AUTO_GOLDEN_MINUTES_S,
                                  "encourager_min_quiet_s": appmain.AUTO_ENCOURAGER_MIN_QUIET_S,
                                  "eot_quiet_s": appmain.AUTO_EOT_QUIET_S,
                                  "eot_fallback_s": appmain.AUTO_EOT_FALLBACK_S,
                                  # the RMS trace the client keeps (G6, 2026-09-09)
                                  "trace_s": appmain.AUTO_TRACE_S, "trace_step_ms": 100,
                                  # the floor from the room (G2, 2026-09-09):
                                  # no sound check for this fresh account
                                  "floor": 0.02, "floor_source": "no_sound_check"}
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

def test_a_quiet_report_in_golden_earns_the_first_encourager_go_on_after_the_minimum_quiet(gate):
    """REPINNED 2026-09-01 (owner decision, solo pilot F3/D1): slice 3
    pinned an encourager at AUTO_ENCOURAGER_QUIET_S (1.75 s), rotated from
    three; replaced by "go on" only after AUTO_ENCOURAGER_MIN_QUIET_S.
    REPINNED again 2026-09-09 (owner decision, after consultations
    487–490): the minimum quiet is now 4.0 s — reports at 1.8 s, 3.0 s and
    3.9 s earn nothing, 4.2 s earns "Go on." — and the row's trigger
    counts the encourager and how many stand unanswered."""
    assert appmain.AUTO_ENCOURAGER_MIN_QUIET_S == 4.0
    with live(gate) as s:
        s.enable_to_golden()
        for q in (1.8, 3.0, 3.9):
            s.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in s.probe()), f"encourager at {q}s"
        s.quiet(4.2)
        seen = _collect_until(s.ws, {"auto_speak"})
        encourager = seen[-1]
        assert encourager["text"] == "Go on." and encourager["ref_id"] == "go_on"
        s.play(encourager["utterance_id"])
        cid = _stop(s)
    rows = asyncio.run(system_utterances.for_consultation(cid))
    row = next(r for r in rows if r["text"] == "Go on.")
    assert row["ref_detail"] == {"id": "go_on", "via": "auto", "phase": "golden",
                                 "trigger": {"quiet_s": 4.2, "encourager": 1, "unanswered": 1}}
    assert row["end_reason"] == "complete"


def test_repeated_encouragers_at_four_seconds_quiet_alternate_and_count_from_albas_phrase_end(gate):
    """REPINNED 2026-09-09 (owner decision, after consultations 487–490;
    reversing the 1 Sept one-per-window rule that this test pinned). In
    GOLDEN an encourager may be spoken every time the patient has been
    quiet for AUTO_ENCOURAGER_MIN_QUIET_S, the quiet counted from the later
    of the patient's last speech and the end of Alba's own last phrase
    (the client's span restarts at both): after "Go on." plays, a span
    that began at its end earns nothing at 3.9 s and the next phrasing at
    4.1 s. Two phrasings alternate — go_on, tell_me_more_short, go_on.
    One per quiet span: a longer report in the same span earns nothing
    more. The window has not run and the machine stays in GOLDEN."""
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started last week, I think, and")
        s.quiet(4.3)
        first = _until(s.ws, {"auto_speak"})
        assert first["ref_id"] == "go_on"
        s.quiet(6.0)                                     # the same span: nothing more
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.play(first["utterance_id"])                    # the span restarts at Alba's phrase end
        s.quiet(3.9)                                     # since=playback, under the minimum
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.quiet(4.1)
        second = _until(s.ws, {"auto_speak"})
        assert second["ref_id"] == "tell_me_more_short" and second["text"] == "Please, tell me more."
        s.play(second["utterance_id"])
        s.commit_transcript("Well, mostly at night.")    # the patient speaks: a fresh span
        s.quiet(2.0)                                     # (its first report, as a real client sends)
        s.quiet(4.0)
        third = _until(s.ws, {"auto_speak"})
        assert third["ref_id"] == "go_on", "the phrasings alternate"
        s.play(third["utterance_id"])
        assert s.phase is AutoPhase.GOLDEN and s.entry["auto"]["golden_window_ran"] is False
        cid = _stop(s)
    rows = asyncio.run(system_utterances.for_consultation(cid))
    spoken = [r["ref_detail"]["id"] for r in rows if r["ref_detail"].get("via") == "auto"
              and r["ref_detail"]["id"] in speech.GOLDEN_ENCOURAGER_IDS]
    assert spoken == ["go_on", "tell_me_more_short", "go_on"]
    third_row = next(r for r in rows if r["ref_detail"]["id"] == "go_on"
                     and r["ref_detail"]["trigger"]["encourager"] == 3)
    assert third_row["ref_detail"]["trigger"]["unanswered"] == 1, "the patient's speech reset the count"
    assert _audit("auto.golden_window_ran", s.session_id) == []


def test_two_unanswered_encouragers_then_the_third_silence_ends_the_window_early(gate):
    """Owner decision 2026-09-09: after AUTO_ENCOURAGER_MAX_UNANSWERED (2)
    encouragers with no patient speech between them, the NEXT qualifying
    silence sets golden_window_ran early — audited auto.golden_window_ran
    with reason unanswered_encouragers and a golden_s short of window_s —
    and the questions begin exactly as when the 90 s elapse: the exit
    fires on the fallback quiet, here on the same report. No third
    encourager is spoken, and none after the window has run."""
    assert appmain.AUTO_ENCOURAGER_MAX_UNANSWERED == 2
    gate.cds_engine.verdicts = [OfficerVerdict(False, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started last week.")
        s.quiet(4.2)
        first = _until(s.ws, {"auto_speak"})
        s.play(first["utterance_id"])
        s.quiet(2.0)                                     # since=playback: no speech between
        s.quiet(4.2)
        second = _until(s.ws, {"auto_speak"})
        assert second["ref_id"] == "tell_me_more_short"
        s.play(second["utterance_id"])
        assert s.entry["auto"]["golden_unanswered"] == 2
        s.quiet(2.0)
        s.quiet(max(4.2, appmain.AUTO_EOT_FALLBACK_S + 0.2))   # the third qualifying silence
        seen = s.probe()
        assert all(m.get("type") != "auto_speak" for m in seen), "no third encourager"
        assert s.entry["auto"]["golden_window_ran"] is True
        assert s.phase is AutoPhase.OPEN, "the window ended early and the exit followed"
        _stop(s)
    ran = _audit("auto.golden_window_ran", s.session_id)
    assert len(ran) == 1
    assert ran[0]["reason"] == "unanswered_encouragers"
    assert ran[0]["golden_s"] < ran[0]["window_s"] == appmain.AUTO_GOLDEN_MINUTES_S
    assert ran[0]["encouragers"] == 2 and ran[0]["unanswered"] == 2
    exit_row = next(d for d in _audit("auto.phase", s.session_id) if d["to"] == "open")
    assert exit_row["trigger"] == "golden_timer_elapsed"


def test_patient_speech_between_encouragers_resets_the_unanswered_count(gate):
    """The count is "with no patient speech between them": speech after
    the second encourager resets it, so the next silences earn two more
    encouragers before a further silence can end the window."""
    gate.cds_engine.verdicts = [OfficerVerdict(False, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started last week.")
        for expected in ("go_on", "tell_me_more_short"):
            s.quiet(2.0)
            s.quiet(4.2)
            e = _until(s.ws, {"auto_speak"})
            assert e["ref_id"] == expected
            s.play(e["utterance_id"])
        assert s.entry["auto"]["golden_unanswered"] == 2
        s.commit_transcript("Oh — and it wakes me at night.")   # the patient answers
        assert s.entry["auto"]["golden_unanswered"] == 2, "reset on the next report, not the commit"
        s.quiet(2.0)                                     # since=speech: the count resets
        s.quiet(4.2)                                     # then a third encourager
        third = _until(s.ws, {"auto_speak"})
        assert third["ref_id"] == "go_on" and s.entry["auto"]["golden_unanswered"] == 1
        s.play(third["utterance_id"])
        s.quiet(2.0)
        s.quiet(4.2)
        fourth = _until(s.ws, {"auto_speak"})
        assert fourth["ref_id"] == "tell_me_more_short"
        s.play(fourth["utterance_id"])
        assert s.phase is AutoPhase.GOLDEN and s.entry["auto"]["golden_window_ran"] is False
        _stop(s)
    assert _audit("auto.golden_window_ran", s.session_id) == []


def test_no_encourager_while_an_utterance_is_in_flight(gate):
    """One utterance at a time holds for the loop too: a quiet report that
    lands while an utterance is pending or playing earns nothing, and the
    window's one encourager comes once the slot is free."""
    with live(gate) as s:
        s.enable_to_golden()
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "i_see"}}))
        tapped = _until(s.ws, {"speak_ready"})           # the doctor's tap, in flight
        s.quiet(5.5)
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.play(tapped["utterance_id"])
        s.quiet(5.6)                                     # released: the one comes
        assert _until(s.ws, {"auto_speak"})["ref_id"] == "go_on"
        _stop(s)


def test_a_politeness_aborted_encourager_is_dropped_not_requeued(gate):
    """An aborted encourager is dropped — the moment has passed — spent at
    issue like the nudge, so a longer report in the SAME span earns
    nothing more. REPINNED 2026-09-09 (owner decision, golden window
    encouragers): the patient's voice that caused the abort begins a fresh
    span, and that span earns the next phrasing after the minimum quiet —
    the 1 Sept "the window's one is spent" tail is deliberately replaced."""
    with live(gate) as s:
        s.enable_to_golden()
        s.quiet(4.5)
        e = _until(s.ws, {"auto_speak"})
        s.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": e["utterance_id"],
                                 "seq": s.seq + 1, "reason": "politeness_abort", "rms": 0.07}))
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.quiet(6.5)                                     # the same span: nothing
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        s.commit_transcript("Sorry — I was saying, it started last week.")   # the voice that aborted it
        s.quiet(4.1)
        again = _until(s.ws, {"auto_speak"})
        assert again["ref_id"] == "tell_me_more_short", "the next phrasing, on the fresh span"
        s.play(again["utterance_id"])
        cid = _stop(s)
    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert [r["end_reason"] for r in rows if r["text"] == "Go on."] == ["politeness_abort"]
    assert [r["end_reason"] for r in rows if r["text"] == "Please, tell me more."] == ["complete"]


def test_the_other_two_encouragers_stay_registered_and_tappable(gate):
    """"Mm-hm" and "I see" are unused by the automatic flow, not deleted:
    still in the phrase table, still a one-tap phrase for the doctor.
    Extended 2026-09-09: the golden window's second phrasing,
    tell_me_more_short ("Please, tell me more."), is registered too and
    pre-synthesised with the rest of the table."""
    assert set(speech.ENCOURAGER_IDS) == {"mm-hm", "i_see", "go_on", "tell_me_more_short"}
    assert speech.ENCOURAGER_ID == "go_on"
    assert speech.GOLDEN_ENCOURAGER_IDS == ("go_on", "tell_me_more_short")
    assert speech.PHRASES["tell_me_more_short"] == "Please, tell me more."
    assert "tell_me_more_short" not in speech.DISCLOSURE_GATED_PHRASES
    with live(gate) as s:
        s.enable_to_golden()
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "mm-hm"}}))
        assert _until(s.ws, {"speak_ready"})["text"] == "Mm-hm."
        _stop(s)


def test_outside_golden_no_encourager_is_spoken_only_the_thinking_phrase_once_per_wait(gate):
    """REPINNED 2026-09-01. Slice 3 pinned "nothing is spoken in OPEN", and
    that held after slice 4 only by accident: the 3.2 s quiet report that
    triggered the hand-back also issued a golden encourager (then at
    1.75 s) which the test never played, so the one-utterance slot stayed
    blocked for the rest of the run. With the golden encourager needing
    more quiet the slot is free, and what OPEN actually says shows.

    REPINNED 2026-09-07 (owner decision, pilot 485 E1): one bridge PER
    REVISION — never a rotation — so the bound was the number of revisions.

    REPINNED 2026-09-09 (owner decision, "Let me think" and the empty-queue
    rule): the bridge "go on" is gone from the question phases entirely.
    Outside GOLDEN no encourager is spoken at all; with the queue empty and
    a pass awaited the machine says "Let me think for a moment." — at most
    once per wait, so at most once per turn end — then the flow's own
    phrases (here the agenda is empty, so the anything-else phrase and the
    handover). Never a rotation of encouragers."""
    gate.cds_engine.verdicts = [OfficerVerdict(True, True)]      # a hand-back
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.", "That's all really.")
        s.quiet(3.2)
        assert all(m.get("type") != "auto_speak" for m in s.probe()), "3.2 s earns nothing in GOLDEN now"
        assert s.phase is AutoPhase.OPEN
        heard = []
        for q in (2.0, 3.5, 6.0, 9.0):
            s.quiet(q)
            for m in s.probe():
                if m.get("type") == "auto_speak":
                    heard.append(m["ref_id"])
                    s.play(m["utterance_id"], keeps_quiet_clock=(m["ref_id"] == "let_me_think"))
        assert not [r for r in heard if r in speech.ENCOURAGER_IDS], "no encourager outside GOLDEN"
        waits = 1 + len([d for d in _audit("auto.turn_ended", s.session_id)])
        # (this file's fake engine lands its empty pass instantly, so the
        # exit's wait is usually over before the first report — then there
        # is nothing to think about and the phrase is rightly absent)
        assert heard.count("let_me_think") <= waits
        assert set(heard) <= {"let_me_think", "anything_else", "examination_handover"}
        _stop(s)
    thinking = _audit("auto.thinking", s.session_id)
    assert len(thinking) == heard.count("let_me_think")
    assert all(t["reason"] == "empty_queue" for t in thinking)


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
    and the officer saying 'not finished', GOLDEN holds while the quiet is
    short; when the officer (re-asked as the quiet grows) says finished,
    GOLDEN exits.

    REPINNED 2026-09-01 (owner decision, pilot D3): the re-ask now happens
    at 4.9 s rather than 6.1 s, because post-window quiet of
    AUTO_EOT_FALLBACK_S (5.0) is itself the exit — see the 483-shape test
    below. The property kept: a "not finished" verdict alone holds GOLDEN,
    and a finished verdict exits it."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)     # window already run
    monkeypatch.setattr(appmain, "AUTO_EOT_QUIET_S", 1.5)          # re-ask inside the fallback span
    gate.cds_engine.verdicts = [OfficerVerdict(False, False), OfficerVerdict(True, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday and")
        s.quiet(1.6)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN, "not finished → hold, whatever the timer says"
        s.quiet(2.5)                                     # same span, officer not re-asked yet
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        assert len(gate.cds_engine.asked) == 1
        s.quiet(3.2)                                     # quiet grew by EOT: asked again
        s.probe()
        assert len(gate.cds_engine.asked) == 2
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == ("golden", "open", "golden_timer_elapsed")
    assert last["detail"]["handed_back"] is False
    assert last["detail"]["by"] == "verdict"


# --------------------------------------------------------------------------
# The post-window state (owner decisions 2026-09-01, pilot D1 and D3)

def test_the_483_shape_a_healthy_not_finished_officer_no_longer_holds_golden_past_the_fallback(gate, monkeypatch):
    """Owner decision 2026-09-01 (pilot D3, consultation 483): once the
    window has run, quiet of AUTO_EOT_FALLBACK_S exits GOLDEN on the quiet
    report itself, whether or not the officer answered. Before this the
    fallback applied only to a FAILED officer, so a healthy one answering
    "not finished" to every ask could hold the golden minutes open
    indefinitely — and did, for 19 s in 483. Here the officer is asked
    once, says not finished, is never re-asked, and the exit comes from
    the report past the fallback. REPINNED 2026-09-09 (owner decision,
    pilot 489/490 G6): the fallback is 3.5 s and the officer's trigger
    2.0 s, so the reports are 2.1 (asked), 3.4 (hold) and 3.6 (exit)."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    gate.cds_engine.verdicts = [OfficerVerdict(False, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("…this is not like a usual fever. I'm worried.")
        s.quiet(2.1)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN and len(gate.cds_engine.asked) == 1
        s.quiet(3.4)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN, "under the fallback span: hold"
        s.quiet(3.6)
        s.probe()
        assert s.phase is AutoPhase.OPEN
        assert len(gate.cds_engine.asked) == 1, "the exit came from the report, not a re-ask"
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == ("golden", "open", "golden_timer_elapsed")
    assert last["detail"]["by"] == "quiet_fallback" and last["detail"]["quiet_s"] == 3.6
    assert last["detail"]["fallback_s"] == appmain.AUTO_EOT_FALLBACK_S
    assert last["detail"]["handed_back"] is False, "the span's verdict travels in the record"


def test_a_finished_verdict_after_the_window_exits_golden_before_the_fallback(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    gate.cds_engine.verdicts = [OfficerVerdict(True, False, elapsed_ms=300)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        s.quiet(3.1)
        s.probe()
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert last["trigger"] == "golden_timer_elapsed" and last["detail"]["by"] == "verdict"
    assert last["detail"]["quiet_s"] == 3.1 and last["detail"]["officer_ms"] == 300


def test_no_encourager_once_the_window_has_run_and_the_run_is_audited_exactly_once(gate, monkeypatch):
    """Owner decision 2026-09-01 (pilot D1): after golden_window_ran no
    encourager is issued in GOLDEN — each one restarted the client's quiet
    span and was the livelock's engine — and auto.golden_window_ran is
    written once per run, on the first observation (a quiet report or a
    verdict), never again however many reports follow. REPINNED 2026-09-09
    (owner decision, G6): the fallback is 3.5 s, so the reports before it
    stop at 3.4 and the exit comes at 3.6."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    # The minimum quiet set BELOW the fallback, so "none after the window"
    # is pinned on its own and not by the two thresholds coinciding.
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 2.0)
    gate.cds_engine.verdicts = [OfficerVerdict(False, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday and")
        for q in (1.8, 2.5, 3.0, 3.2, 3.4):              # reports before the fallback
            s.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in s.probe()), f"encourager at {q}s"
        assert s.entry["auto"]["golden_window_ran"] is True
        assert s.phase is AutoPhase.GOLDEN
        s.quiet(3.6)
        s.probe()
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    ran = _audit("auto.golden_window_ran", s.session_id)
    assert len(ran) == 1
    assert ran[0]["golden_s"] >= 0.0 and ran[0]["window_s"] == 0.0 and ran[0]["seen_on"] == "quiet"


def test_before_the_window_has_run_encouragers_and_the_hold_are_unchanged(gate):
    """The pre-window behaviour is untouched by the exit rule: a long quiet
    with the window not run exits nothing, and auto.golden_window_ran is
    not written."""
    gate.cds_engine.verdicts = [OfficerVerdict(True, False)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        for q in (3.2, 5.5, 8.0):
            s.quiet(q)
            s.probe()
            assert s.phase is AutoPhase.GOLDEN
        assert s.entry["auto"]["golden_window_ran"] is False
        _stop(s)
    assert _audit("auto.golden_window_ran", s.session_id) == []


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
    """REPINNED 2026-09-09 (owner decision, G6): the officer is asked at
    2 s and the silence rule is 3.5 s; the property — a failed officer is
    audited and the silence rule alone decides the exit — is unchanged."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    gate.cds_engine.verdicts = [OfficerVerdict(False, False, failed="timeout", elapsed_ms=2001)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        s.quiet(2.2)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN, "2.2 s is under the fallback span"
        s.quiet(3.4)
        s.probe()
        assert s.phase is AutoPhase.GOLDEN
        s.quiet(3.6)                                     # ≥ AUTO_EOT_FALLBACK_S
        s.probe()
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    failed = _audit("auto.officer_failed", s.session_id)
    assert len(failed) == 1
    assert failed[0]["reason"] == "timeout" and failed[0]["quiet_s"] == 2.2
    assert failed[0]["fallback_s"] == appmain.AUTO_EOT_FALLBACK_S
    last = _audit("auto.phase", s.session_id)[-1]
    assert last["trigger"] == "golden_timer_elapsed"
    assert last["detail"]["officer_failed"] == "timeout"


def test_the_officer_is_not_asked_without_committed_transcript(gate, monkeypatch):
    """Nothing to judge, no model call; the silence rule alone can move a
    patient who never spoke once the window has run. REPINNED 2026-09-09
    (owner decision, G6): the silence rule is 3.5 s — 3.4 holds, 3.6 moves."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    with live(gate) as s:
        s.enable_to_golden()
        s.quiet(3.4)
        s.probe()
        assert gate.cds_engine.asked == []
        assert s.phase is AutoPhase.GOLDEN
        s.quiet(3.6)
        s.probe()
        assert s.phase is AutoPhase.OPEN
        _stop(s)


# ==========================================================================
# The officer's word, on the record (owner decision 2026-09-01, pilot D2)

def test_every_officer_verdict_is_audited_even_when_it_causes_no_transition(gate):
    """Owner decision 2026-09-01 (solo pilot diagnostic, defect D2): the
    1 Sept runs could not show what the officer answered, because only a
    failure or a transition left a row. Now EVERY verdict is audited as
    auto.officer_verdict — quiet_s, the golden window elapsed when in
    GOLDEN, both booleans, the call's milliseconds, the phase, and the
    transition it produced. The case that matters most is the one that
    used to vanish: a healthy verdict that causes no transition."""
    gate.cds_engine.verdicts = [OfficerVerdict(True, False, elapsed_ms=350)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        s.quiet(3.4)
        s.probe()                                        # the tick applies the verdict
        assert s.phase is AutoPhase.GOLDEN, "the window has not run: no transition"
        _stop(s)
    verdicts = _audit("auto.officer_verdict", s.session_id)
    assert len(verdicts) == 1
    row = verdicts[0]
    assert row["finished_thought"] is True and row["handed_back"] is False
    assert row["failed"] is None and row["elapsed_ms"] == 350
    assert row["quiet_s"] == 3.4 and row["phase"] == "golden"
    assert 0.0 <= row["golden_elapsed_s"] < 60.0
    assert row["transition"] is None
    assert _audit("auto.officer_failed", s.session_id) == [], "auto.officer_failed is for failures only"


def test_a_failed_verdict_and_a_transition_causing_verdict_are_audited_too(gate, monkeypatch):
    """auto.officer_failed stays exactly as it was (fail-soft visibility);
    the new row is written beside it, and a verdict that exits GOLDEN
    carries the transition it caused."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    monkeypatch.setattr(appmain, "AUTO_EOT_QUIET_S", 1.5)   # re-ask inside the fallback span
    gate.cds_engine.verdicts = [OfficerVerdict(False, False, failed="timeout", elapsed_ms=2001),
                                OfficerVerdict(True, True, elapsed_ms=410)]
    with live(gate) as s:
        s.enable_to_golden()
        s.commit_transcript("It started on Tuesday.")
        s.quiet(1.6)
        s.probe()                                        # the failed verdict
        assert s.phase is AutoPhase.GOLDEN
        s.quiet(3.2)
        s.probe()                                        # re-asked: the hand-back
        assert s.phase is AutoPhase.OPEN
        _stop(s)
    verdicts = _audit("auto.officer_verdict", s.session_id)
    assert [v["failed"] for v in verdicts] == ["timeout", None]
    assert verdicts[0]["transition"] is None
    assert verdicts[1]["handed_back"] is True
    assert verdicts[1]["transition"] == {"from": "golden", "to": "open", "trigger": "hand_back"}
    failed = _audit("auto.officer_failed", s.session_id)
    assert len(failed) == 1 and failed[0]["reason"] == "timeout"


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
