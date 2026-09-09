"""The urgency pause protocol (Phase 7c slice 5, PHASE_7C_SPEC.md §1 hard
rule 2, §7, §10, §11), driven over the real socket — dark behind
AUTO_MODE_ENABLED.

Item 1 (this section): the server-initiated stop. `cancel_auto_playback`
cuts the current utterance NOW — the client is told (auto_stop, with the
reason), the window closes at the cut, the row is resolved server-side
with the named reason (an unstarted one records the reason with no
span), the queued auto utterance is cleared, and the client's echoed
speak_ended is recognised rather than refused. Nothing breaks when
nothing is in flight.

The harness is tests/auto_harness.py (a real SpeechService on a fake
command; a scripted engine standing in for MedGemma).
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from app import speech, system_utterances
from app import main as appmain
from app.auto_mode import PhraseUtterance
from app.live import BYTES_PER_MS
from auto_harness import (Q_ONSET, OfficerVerdict, TTS_AMPLITUDE, _assessment, _audit,  # noqa: F401
                          _collect_until, _rows, _stop, _until, gate, live, needs_db)

pytestmark = needs_db


def _cancel(s, reason="urgency_pause"):
    return s.ws.portal.call(lambda: appmain.cancel_auto_playback(s.entry, _ws_of(s), reason))


class _Sink:
    """The server-side send for the helper's auto_stop, collected here; the
    real socket is what the test then plays the client's echo on."""

    def __init__(self, s):
        self.s, self.sent = s, []

    async def send_json(self, message):
        self.sent.append(message)


_sinks = {}


def _ws_of(s):
    return _sinks.setdefault(s.session_id, _Sink(s))


# ==========================================================================
# Item 1: the server-initiated stop

def test_a_playing_utterance_is_cut_and_its_window_closes_at_the_cut(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 5.0)   # the harness parks it
    with live(gate) as s:
        s.to_golden()
        s.quiet(5.5)                                   # → the window's encourager (GOLDEN)
        gate_up = [m for m in s.probe() if m.get("type") == "auto_speak"]
        assert gate_up, "an encourager was issued"
        e = gate_up[0]
        s.ws.send_text(json.dumps({"type": "speak_started",
                                   "utterance_id": e["utterance_id"], "seq": s.seq + 1}))
        s.frame(TTS_AMPLITUDE)                          # 0.25 s of us in the room
        _until(s.ws, {"ack"})
        row = _cancel(s)                                # the server cuts it
        sink = _ws_of(s)
        assert sink.sent == [{"type": "auto_stop", "reason": "urgency_pause",
                              "utterance_id": e["utterance_id"]}]
        assert row["end_reason"] == "urgency_pause"
        assert row["start_byte"] is not None
        assert row["end_byte"] == row["start_byte"] + 8000 + 200 * BYTES_PER_MS
        assert s.entry["pending_utterance"] is None
        assert not s.entry["session"].speaking, "the window is closed at the cut"
        # The client's echo — its stopSpeaking(reason) — is recognised, not
        # refused: no speak_refused follows it.
        s.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": e["utterance_id"],
                                   "seq": s.seq + 1, "reason": "urgency_pause"}))
        assert all(m.get("type") != "speak_refused" for m in s.probe())
        assert s.entry["server_cancelled_id"] is None
        # And the slot is free again (the window's one encourager is spent,
        # so a tap shows it rather than a second encourager).
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "i_see"}}))
        assert _until(s.ws, {"speak_ready"})["text"] == "I see."
        cid = _stop(s)
    rows = _rows(cid)
    cut = next(r for r in rows if r["utterance_id"] == e["utterance_id"])
    assert cut["end_reason"] == "urgency_pause"
    assert cut["started_offset_ms"] is not None
    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    assert (cut["started_offset_ms"] * BYTES_PER_MS, cut["ended_offset_ms"] * BYTES_PER_MS) in spans


def test_an_unstarted_utterance_is_cut_with_the_reason_and_no_span(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 5.0)
    with live(gate) as s:
        s.to_golden()
        s.quiet(5.5)
        e = next(m for m in s.probe() if m.get("type") == "auto_speak")
        row = _cancel(s)                                # never started playing
        assert row["end_reason"] == "urgency_pause"
        assert row["start_byte"] is None and row["end_byte"] is None
        assert _ws_of(s).sent[-1]["utterance_id"] == e["utterance_id"]
        cid = _stop(s)
    rows = _rows(cid)
    cut = next(r for r in rows if r["utterance_id"] == e["utterance_id"])
    assert cut["end_reason"] == "urgency_pause" and cut["started_offset_ms"] is None
    # Only the invitation's span exists; the cut, unstarted one adds none.
    assert len(asyncio.run(system_utterances.exclusion_spans(cid))) == 1


def test_a_queued_auto_utterance_is_cleared_and_never_requeued(gate):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        for _ in range(30):                             # let the plan land
            s.probe()
            if s.auto["queued"] is not None:
                break
        assert s.auto["queued"] is not None
        assert _cancel(s) is None                       # nothing in flight: nothing sent
        assert _ws_of(s).sent == []
        assert s.auto["queued"] is None
        assert s.auto["plan_task"] is None
        # A cut (not aborted) question is not requeued: the next report
        # earns nothing until a fresh revision plans again.
        s.quiet(4.0)
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        _stop(s)


def test_nothing_breaks_when_nothing_is_in_flight(gate):
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        assert _cancel(s) is None
        assert _cancel(s, "cancelled") is None
        assert _ws_of(s).sent == []
        assert s.entry["server_cancelled_id"] is None
        s.disclose()
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "invitation"}}))
        assert _until(s.ws, {"speak_ready"})["type"] == "speak_ready"
        _stop(s)


def test_a_tapped_utterance_is_cut_too(gate):
    """An urgency pause is not the moment for anyone's question: the helper
    cuts whatever is in flight, tap or auto."""
    with live(gate) as s:
        s.disclose()
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _until(s.ws, {"speak_ready"})
        s.ws.send_text(json.dumps({"type": "speak_started",
                                   "utterance_id": ready["utterance_id"], "seq": s.seq + 1}))
        s.frame(TTS_AMPLITUDE)
        _until(s.ws, {"ack"})
        row = _cancel(s)
        assert row["utterance_id"] == ready["utterance_id"]
        assert row["end_reason"] == "urgency_pause"
        _stop(s)
    played = [d for d in _audit_action("speech.spoken", ready["utterance_id"])]
    assert played and played[0]["server_stop"] is True and played[0]["reason"] == "urgency_pause"


def _audit_action(action, utterance_id):
    import os
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT detail FROM audit_event WHERE action = %s"
            " AND detail->>'utterance_id' = %s ORDER BY id", (action, utterance_id)).fetchall()
    return [r[0] for r in rows]


# ==========================================================================
# Item 3: the pause itself (spec §7, hard rule 2)
#
# An alarm is a CDS pass returning non-empty urgent_actions. The scripted
# engine's `update` is replaced per test so a chosen pass carries them; the
# pass is triggered by committing transcript that satisfies the first-call
# rule (no cds_sent_len bookkeeping) or by the D2 revision.

ECG = {"action": "Bedside ECG now", "reason": "exclude ACS"}
CALL = {"action": "Call 999", "reason": "possible STEMI"}


def _engine_with_alarms(engine, script):
    """`script` maps pass number (1-based) → urgent_actions list for that
    pass; other passes are quiet. Agendas keep their scripted order. A
    set `engine.gate_event` holds every pass until released, as the
    harness's own update does."""
    async def update(transcript, previous=None):
        if engine.gate_event is not None:
            await engine.gate_event.wait()
        engine.updates.append(transcript)
        questions = engine.agendas.pop(0) if len(engine.agendas) > 1 else engine.agendas[0]
        assessment = _assessment(questions, reasoning=f"pass {len(engine.updates)}")
        assessment["urgent_actions"] = list(script.get(len(engine.updates), []))
        return assessment
    engine.update = update


def _fire_pass(s, *lines):
    """Commit transcript so maybe_run_cds launches a pass on the next tick
    (the first-turn rule, or 150-char growth), then tick until it lands."""
    before = len(s.state.cds_engine.updates)
    def _inject():
        s.entry["transcript_parts"].extend(lines)
    s.ws.portal.call(_inject)
    for _ in range(40):
        s.probe()
        if len(s.state.cds_engine.updates) > before and s.entry["assessment"] is not None:
            # one more tick so the landing branch has run
            s.probe()
            return
    raise AssertionError("the CDS pass did not land")


LONG = "I have had this crushing central chest pain for an hour and it goes into my left arm and jaw and I feel sick. " * 2


@pytest.mark.parametrize("phase", ["golden", "open", "closed"])
def test_an_alarm_in_each_active_phase_pauses_cuts_and_audits(gate, monkeypatch, phase):
    """GOLDEN, OPEN, CLOSED: the machine pauses and remembers the phase it
    left, the current utterance is cut with urgency_pause, the queue is
    dropped, auto.paused carries the texts, the snapshot version and the
    transition, and the client is shown every pending text. Listening
    goes on: frames are still acked, the transcript still grows."""
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 5.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"],
                      ["Does the pain radiate to your jaw or arm?"], ["Any nausea?"]]
    alarm_pass = {"golden": 1, "open": 2, "closed": 3}[phase]
    _engine_with_alarms(engine, {alarm_pass: [ECG]})
    with live(gate) as s:
        s.to_golden()
        if phase == "golden":
            s.quiet(5.5)                                     # the encourager in flight
            e = next(m for m in s.probe() if m.get("type") == "auto_speak")
            s.ws.send_text(json.dumps({"type": "speak_started",
                                       "utterance_id": e["utterance_id"], "seq": s.seq + 1}))
            s.frame(TTS_AMPLITUDE)
            _until(s.ws, {"ack"})
            _fire_pass(s, LONG)                              # pass 1: the alarm
        else:
            s.commit_transcript("It started on Tuesday.", "That's all really.")
            s.quiet(3.1)
            s.probe()                                        # hand-back → OPEN, pass 1 (quiet)
            first = s.wait_for_auto_speak()
            s.play(first["utterance_id"])
            if phase == "open":
                s.turn_end("Tuesday night.")                 # pass 2: the alarm
                for _ in range(20):
                    if s.phase.value == "paused_urgent":
                        break
                    s.probe()
            else:
                s.turn_end("Tuesday night.")                 # pass 2 → verbatim → CLOSED
                second = s.wait_for_auto_speak()
                assert s.phase.value == "closed"
                s.play(second["utterance_id"])
                s.turn_end("No, it stays put.")              # pass 3: the alarm
                for _ in range(20):
                    if s.phase.value == "paused_urgent":
                        break
                    s.probe()
        assert s.phase.value == "paused_urgent"
        assert s.auto["controller"].paused_from.value == phase
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG now"})
        assert s.entry["pending_utterance"] is None and s.auto["queued"] is None
        # Listening goes on: frames acked, transcript still grows, quiet
        # earns nothing.
        s.commit_transcript("more talking")
        s.quiet(4.0)
        assert all(m.get("type") not in ("auto_speak",) for m in s.probe())
        assert s.phase.value == "paused_urgent"
        cid = _stop(s)
    paused = _audit("auto.paused", s.session_id)
    assert len(paused) == 1
    assert paused[0]["actions"] == ["Bedside ECG now"] and paused[0]["pending"] == ["Bedside ECG now"]
    assert paused[0]["assessment_version"] == alarm_pass
    assert paused[0]["transition"] == {"from": phase, "to": "paused_urgent", "trigger": "urgent_alarm"}
    assert paused[0]["refire"] is False
    phases = [(d["from"], d["to"]) for d in _audit("auto.phase", s.session_id)]
    assert (phase, "paused_urgent") in phases
    if phase == "golden":
        rows = _rows(cid)
        cut = next(r for r in rows if r["text"] == "Go on.")
        assert cut["end_reason"] == "urgency_pause"


def test_the_client_is_shown_every_pending_text_and_a_refire_widens_it(gate):
    """While paused the CDS keeps revising; a re-fire with a new action is
    the machine's self-edge: still paused, the prior phase kept, the
    pending set widened, audited as a re-fire, and the client shown ALL
    pending texts — never only the latest."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [ECG, CALL]})
    with live(gate) as s:
        s.to_golden()
        s.ws.portal.call(lambda: None)
        _fire_pass(s, LONG)                                  # pass 1: ECG → paused from GOLDEN
        first = [m for m in _drain(s) if m.get("type") == "auto_pause"]
        assert s.phase.value == "paused_urgent"
        _fire_pass(s, LONG + " and it is getting worse " * 8)  # pass 2: ECG + Call 999
        assert s.phase.value == "paused_urgent"
        assert s.auto["controller"].paused_from.value == "golden"
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG now", "Call 999"})
        _stop(s)
    paused = _audit("auto.paused", s.session_id)
    assert [p["refire"] for p in paused] == [False, True]
    assert paused[1]["pending"] == ["Bedside ECG now", "Call 999"]
    assert paused[1]["actions"] == ["Bedside ECG now", "Call 999"]
    assert paused[1]["transition"] == {"from": "paused_urgent", "to": "paused_urgent",
                                       "trigger": "urgent_alarm"}


def _drain(s):
    """Whatever the server has sent so far, up to the next ack."""
    return s.probe()


def test_the_auto_pause_message_lists_all_pending_texts(gate):
    engine = gate.cds_engine
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [ECG, CALL]})
    with live(gate) as s:
        s.to_golden()
        seen = []
        before = len(engine.updates)
        s.ws.portal.call(lambda: s.entry["transcript_parts"].append(LONG))
        for _ in range(40):
            seen += s.probe()
            if any(m.get("type") == "auto_pause" for m in seen):
                break
        pauses = [m for m in seen if m.get("type") == "auto_pause"]
        assert pauses[-1]["pending"] == ["Bedside ECG now"] and pauses[-1]["refire"] is False
        assert pauses[-1]["paused_from"] == "golden"
        # The stop for the (unstarted or playing) utterance, if any, precedes
        # the pause message; here nothing was in flight.
        seen = []
        s.ws.portal.call(lambda: s.entry["transcript_parts"].append(LONG * 2))
        for _ in range(40):
            seen += s.probe()
            if any(m.get("type") == "auto_pause" for m in seen):
                break
        pauses = [m for m in seen if m.get("type") == "auto_pause"]
        assert pauses[-1]["pending"] == ["Bedside ECG now", "Call 999"]
        assert pauses[-1]["refire"] is True
        _stop(s)


def test_an_alarm_with_auto_off_is_todays_behaviour_untouched(gate):
    """Gate up, auto never toggled: the alarm fires as it always has —
    first-fired time recorded, the CDS message sent, the unresolved action
    persisted at Stop for the review banner — and nothing pauses, nothing
    is cut, no auto.* row is written."""
    engine = gate.cds_engine
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG]})
    with live(gate) as s:
        s.disclose()
        _fire_pass(s, LONG)
        assert s.phase.value == "off"
        assert "Bedside ECG now" in s.entry["urgent_first_fired"]
        cid = _stop(s)
    assert _audit("auto.paused", s.session_id) == []
    assert _audit("auto.phase", s.session_id) == []
    from app import consultations
    review = asyncio.run(consultations.get_consultation(cid))
    assert [a["action"] for a in review["urgent_actions"]] == ["Bedside ECG now"]


def test_an_alarm_in_disclosure_or_after_handover_changes_nothing(gate):
    """Only the listening phases pause (spec §7); a machine waiting in
    DISCLOSURE, or one whose auto run has ended, is left alone."""
    engine = gate.cds_engine
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG]})
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.toggle(True)                                        # one-tap: DISCLOSURE, disclosure playing
        _collect_until(s.ws, {"auto_toggled"})
        assert s.phase.value == "disclosure"
        _fire_pass(s, LONG)
        assert s.phase.value == "disclosure"
        _stop(s)
    assert _audit("auto.paused", s.session_id) == []


def test_the_urgency_alarm_still_never_reaches_the_face():
    """The standing guard, restated where the alarm is now wired: nothing
    in the pause path names the face, and app/face.py has no urgency
    surface (tests/test_face_driver.py pins the module; this pins the
    wiring)."""
    from pathlib import Path
    main = Path("app/main.py").read_text()
    body = main[main.index("async def on_urgent_alarm("):main.index("async def handle_quiet(")]
    code = body.split('"""')[2]                 # the code after the docstring
    assert "face" not in code.lower()
    import app.face as face
    assert not any("urgen" in n.lower() or "alarm" in n.lower() for n in dir(face.FaceDriver))


# ==========================================================================
# Item 4: the banner's acknowledgements — RESUME AUTO / TAKE OVER, the
# ratchet end to end, and what the review page shows

def _ack(s, resolution):
    s.ws.send_text(json.dumps({"type": "auto_ack", "resolution": resolution}))
    return _collect_until(s.ws, {"auto_acknowledged", "auto_refused"})


def _pause_from_open(s, engine, monkeypatch, alarm_pass=2, actions=(ECG,)):
    """GOLDEN → OPEN by a hand-back, first ask played, then the D2 revision
    (pass `alarm_pass`) carries the alarm → PAUSED_URGENT from OPEN."""
    s.to_golden()
    s.commit_transcript("It started on Tuesday.", "That's all really.")
    s.quiet(3.1)
    s.probe()
    first = s.wait_for_auto_speak()
    s.play(first["utterance_id"])
    s.turn_end("Tuesday night.")
    for _ in range(30):
        if s.phase.value == "paused_urgent":
            break
        s.probe()
    assert s.phase.value == "paused_urgent"


def test_resume_returns_to_the_exact_prior_phase_and_the_ratchet_re_arms(gate, monkeypatch):
    """REPINNED for the owner decision of 2026-08-17 (spec §7 as amended):
    slice 5 built an immediate re-revision on resume, which re-paused before
    any answer could be given; that property is deliberately replaced, not
    weakened. RESUME AUTO: auto.acknowledged carries every pending text and
    the snapshot versions; the machine returns to exactly OPEN; auto.resumed
    is written; NO revision is requested — the next ask is planned from the
    alarm-bearing pass's agenda (its clarifying question), asked at the next
    turn end. Then the answer's turn end runs the D2 revision as always;
    here it leaves the alarm standing, so the SAME text re-fires.

    REPINNED 2026-09-07 (owner decision, pilot 486 F1): an acknowledged
    action does not re-pause. The re-fire is skipped and audited
    (auto.repause_skipped_acknowledged), the machine stays where it was
    (CLOSED, after the verbatim ask), and the action stays in view on the
    standing strip (auto_standing) rather than clearing silently. Before
    this the same text paused again and needed a fresh acknowledgement —
    in 486 that was eight RESUME taps in one run. The property kept: one
    acknowledgement is on the record with every text and version, the
    resume returns to the exact prior phase, and no revision runs at
    resume."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"]]
    _engine_with_alarms(engine, {2: [ECG], 3: [ECG], 4: []})
    with live(gate) as s:
        _pause_from_open(s, engine, monkeypatch)
        assert s.auto["controller"].paused_from.value == "open"
        passes_before = len(engine.updates)
        seen = _ack(s, "resume")
        assert seen[-1]["type"] == "auto_acknowledged"
        assert seen[-1]["resolution"] == "resume" and seen[-1]["actions"] == ["Bedside ECG now"]
        assert [m["actions"] for m in seen if m.get("type") == "auto_standing"] == [["Bedside ECG now"]], \
            "the strip is pushed at the acknowledgement (F1)"
        assert seen[-1]["phase"] == "open"
        assert s.phase.value == "open", "the exact prior phase"
        assert s.auto["controller"].pending_actions == frozenset()
        assert s.auto["controller"].acknowledged_actions == frozenset({"Bedside ECG now"})
        assert s.auto["revision"] is None, "no immediate revision on resume (owner decision 2026-08-17)"
        # The clarifying question from the ALARM-BEARING pass is asked at
        # the next turn end, with no new pass having run.
        s.commit_transcript("okay")                       # the room speaks again; a turn ends
        s.quiet(3.2)
        s.probe()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Any nausea?"
        assert len(engine.updates) == passes_before, "asked from the pass in hand, not a new one"
        s.play(ask["utterance_id"])
        # The answer's turn end runs the D2 revision (pass 3): the alarm is
        # still there → the SAME text re-fires → NOT paused again (F1): the
        # verbatim ask had narrowed OPEN → CLOSED and the machine stays there.
        s.turn_end("No, no nausea.")
        seen = []
        for _ in range(30):
            seen += s.probe()
            if len(engine.updates) == passes_before + 1 and s.auto["queued"] is not None:
                break
            time.sleep(0.02)
        assert len(engine.updates) == passes_before + 1
        assert s.phase.value == "closed", "no second pause on an acknowledged action"
        assert s.auto["controller"].pending_actions == frozenset()
        assert s.auto["standing_sent"] == ["Bedside ECG now"], "kept in view, not cleared silently"
        assert not [m for m in seen if m.get("type") == "auto_standing"], "unchanged: not re-pushed"
        cid = _stop(s)
    acks = _audit("auto.acknowledged", s.session_id)
    assert [a["resolution"] for a in acks] == ["resume"]
    assert acks[0]["actions"] == ["Bedside ECG now"] and acks[0]["assessment_versions"] == [2]
    assert acks[0]["paused_from"] == "open"
    resumed = _audit("auto.resumed", s.session_id)
    assert [r["phase"] for r in resumed] == ["open"]
    phases = [(d["from"], d["to"], d["trigger"]) for d in _audit("auto.phase", s.session_id)]
    assert phases.count(("paused_urgent", "open", "acknowledge_resume")) == 1
    assert phases.count(("open", "paused_urgent", "urgent_alarm")) == 1
    assert phases.count(("closed", "paused_urgent", "urgent_alarm")) == 0
    skipped = _audit("auto.repause_skipped_acknowledged", s.session_id)
    assert len(skipped) == 1 and skipped[0]["candidate"] == "Bedside ECG now"
    assert skipped[0]["matched"] == "Bedside ECG now" and skipped[0]["score"] == 1.0
    assert skipped[0]["assessment_version"] == 3
    # The consultation-linked summary carries the one acknowledgement.
    from app import audit as audit_mod
    summary = asyncio.run(audit_mod.for_subject("consultation", cid, "auto.acknowledgements"))
    assert len(summary) == 1
    assert [a["resolution"] for a in summary[0]["detail"]["acknowledgements"]] == ["resume"]


def test_after_resume_a_clarifying_answer_that_clears_the_alarm_continues_normally(gate, monkeypatch):
    """The one answer's chance, taken: the clarifying question is asked from
    the alarm-bearing agenda, the answer's revision comes back with no
    urgent actions, and the flow simply carries on to the next question —
    no pause, no second acknowledgement."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"],
                      ["How have you been sleeping?"]]
    _engine_with_alarms(engine, {2: [ECG], 3: []})
    with live(gate) as s:
        _pause_from_open(s, engine, monkeypatch)
        _ack(s, "resume")
        s.commit_transcript("okay")
        s.quiet(3.2)
        s.probe()
        ask = s.wait_for_auto_speak()
        assert ask["text"] == "Any nausea?"                # the alarm-bearing pass's question
        s.play(ask["utterance_id"])
        s.turn_end("No — and the ECG is being done now.")  # pass 3: alarm cleared
        nxt = s.wait_for_auto_speak()
        assert nxt["text"] == "Can you tell me more about your sleep?"
        assert s.phase.value in ("open", "closed")
        _stop(s)
    assert len(_audit("auto.paused", s.session_id)) == 1
    assert len(_audit("auto.acknowledged", s.session_id)) == 1


def test_no_ack_resume_loop_is_possible_without_an_intervening_answer(gate, monkeypatch):
    """After a resume nothing re-fires by itself: no revision runs until an
    answer's turn ends, so the machine cannot bounce pause → ack → pause
    on its own. Quiet reports under the fallback length and loop ticks
    alone leave it in OPEN with the alarm-bearing question queued and no
    new pass.

    REPINNED 2026-09-07 (owner decision, pilot 485 E1): quiet of
    AUTO_EOT_FALLBACK_S is now itself an answer's turn end in the question
    phases — silence after the asked question IS the answer running its
    course — so the reports below stay under 5 s for the "nothing by
    itself" property, and the tail pins that the one answer's chance ends
    by silence too: at 5 s the turn ends (audited, by quiet_fallback) and
    the revision runs.

    REPINNED again 2026-09-07 (owner decision, pilot 486 F1): that
    revision re-issues the acknowledged ECG and no longer re-pauses — the
    skip is audited and the machine stays in its phase.

    REPINNED once more 2026-09-07 (owner decision, pilot 486 F5): a turn
    must start before it can end — silence after the asked question no
    longer ends its turn until the patient has spoken since it. So the
    tail now plays the question, has the patient answer, and lets the
    fallback quiet after THAT end the turn.

    REPINNED 2026-09-09 (owner decision, pilot 489/490 G6): the fallback
    is 3.5 s and the officer's trigger 2.0 s — the answer's fresh span
    starts under the trigger and the turn ends by silence at 3.6 s."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"]]
    _engine_with_alarms(engine, {2: [ECG], 3: [ECG]})
    with live(gate) as s:
        _pause_from_open(s, engine, monkeypatch)
        passes = len(engine.updates)
        _ack(s, "resume")
        assert s.phase.value == "open"
        for _ in range(12):                                # ticks and quiet, no speech
            s.probe()
            s.quiet(2.0 + _ * 0.2)                         # 2.0 … 4.2 s: under the fallback
        # It may have ASKED the alarm-bearing question by now (a verbatim
        # ask narrows OPEN → CLOSED) — but nothing re-fired: no pass, no pause.
        assert s.phase.value in ("open", "closed")
        assert len(engine.updates) == passes, "no pass ran without an answer"
        assert len(_audit("auto.paused", s.session_id)) == 1
        # Silence alone ends nothing now (F5): the question is played, the
        # patient answers, and 5 s of quiet after the answer ends the turn;
        # the next pass runs — and re-issues the acknowledged ECG without
        # pausing (F1).
        if s.entry["pending_utterance"] is not None:
            s.play(s.entry["pending_utterance"].utterance_id)
        s.quiet(5.1)
        s.probe()
        assert len(engine.updates) == passes, "no speech since the question: no turn end (F5)"
        s.commit_transcript("Nobody has done an ECG.")
        s.quiet(1.9)
        s.probe()
        s.quiet(3.6)
        for _ in range(30):
            s.probe()
            if len(engine.updates) == passes + 1:
                s.probe()
                break
            time.sleep(0.02)
        assert len(engine.updates) == passes + 1
        assert s.phase.value in ("open", "closed"), "an acknowledged action does not re-pause"
        _stop(s)
    ended = [d for d in _audit("auto.turn_ended", s.session_id) if d["answer"]]
    assert ended and ended[-1]["by"] == "quiet_fallback" and ended[-1]["quiet_s"] == 3.6
    assert len(_audit("auto.paused", s.session_id)) == 1
    assert len(_audit("auto.repause_skipped_acknowledged", s.session_id)) == 1


# --------------------------------------------------------------------------
# The resume ratchet's one answer's chance (owner decision 2026-09-01, D4)

def _launch_gated_pass(s, engine, *lines):
    """Commit transcript so a CDS pass launches on the next tick, with the
    engine gated so it stays IN FLIGHT until the test releases it."""
    engine.gate_event = asyncio.Event()
    before = len(engine.updates)
    s.ws.portal.call(lambda: s.entry["transcript_parts"].extend(lines))
    s.probe()                                              # the tick launches it
    assert len(engine.updates) == before, "held in flight"


def _release_pass(s, engine):
    s.ws.portal.call(lambda: engine.gate_event.set())
    engine.gate_event = None
    for _ in range(40):
        s.probe()
        if s.entry["assessment"] is not None and s.entry["assessment"].get("reasoning", "").endswith(
                str(len(engine.updates))):
            s.probe()
            return
    raise AssertionError("the released pass did not land")


def test_the_482_shape_a_pass_in_flight_at_resume_does_not_re_pause(gate, monkeypatch):
    """Owner decision 2026-09-01 (pilot D4). 482: paused on v1 (ECG),
    RESUME AUTO, and the pass already in flight landed 2.0 s later with the
    ECG still unarranged — re-paused, and cut "Mm-hm." after 450 ms. Now:
    a pass in flight at the resume may not re-pause on an acknowledged
    action; the suppression is audited with the assessment version, the
    machine stays in GOLDEN, and the encourager plays through. Then the
    one answer's chance runs its course: after a turn end following the
    resume, a NEW pass with the action still unarranged lands.

    REPINNED 2026-09-07 (owner decision, pilot 486 F1): that later pass
    no longer re-pauses either — the action was acknowledged, and an
    acknowledged action does not re-pause; the skip is audited
    (auto.repause_skipped_acknowledged) while the in-flight case keeps its
    own auto.repause_suppressed row, so the two are told apart on the
    record."""
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 5.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [ECG], 3: [ECG]})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)                                    # pass 1: ECG → paused
        assert s.phase.value == "paused_urgent"
        _launch_gated_pass(s, engine, LONG + " and my arm is heavy " * 8)   # pass 2, in flight
        _ack(s, "resume")
        assert s.phase.value == "golden"
        s.quiet(5.5)                                           # the encourager, as in 482
        e = _until(s.ws, {"auto_speak"})
        assert e["ref_id"] == "go_on"
        s.ws.send_text(json.dumps({"type": "speak_started",
                                   "utterance_id": e["utterance_id"], "seq": s.seq + 1}))
        s.frame(TTS_AMPLITUDE)
        _until(s.ws, {"ack"})
        _release_pass(s, engine)                               # pass 2 lands: ECG, unarranged
        assert s.phase.value == "golden", "the pre-resume pass did not re-pause"
        assert s.entry["pending_utterance"] is not None, "nothing was cut"
        s.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": e["utterance_id"],
                                   "seq": s.seq + 1, "reason": "complete"}))
        s.probe()
        # The one answer's chance: the patient answers and stops (a turn
        # end after the resume); the NEXT pass may re-pause — and does.
        s.commit_transcript("Nobody has done an ECG yet.")
        s.quiet(3.2)
        s.probe()
        assert s.phase.value == "golden"
        assert s.auto["repause_block"] is False
        _fire_pass(s, LONG + " still nothing arranged " * 8)   # pass 3: ECG again → skipped (F1)
        assert s.phase.value == "golden"
        cid = _stop(s)
    suppressed = _audit("auto.repause_suppressed", s.session_id)
    assert len(suppressed) == 1
    assert suppressed[0]["actions"] == ["Bedside ECG now"]
    assert suppressed[0]["assessment_version"] == 2 and suppressed[0]["phase"] == "golden"
    skipped = _audit("auto.repause_skipped_acknowledged", s.session_id)
    assert len(skipped) == 1 and skipped[0]["assessment_version"] == 3
    paused = _audit("auto.paused", s.session_id)
    assert [p["assessment_version"] for p in paused] == [1]
    rows = _rows(cid)
    assert next(r for r in rows if r["text"] == "Go on.")["end_reason"] == "complete"


def test_a_pass_launched_after_resume_but_before_any_answer_does_not_re_pause_either(gate, monkeypatch):
    """The block is cleared by a turn end, not by the resume itself: a pass
    launched after the resume (transcript growth, no turn end judged yet)
    that re-fires the acknowledged action is suppressed too."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(False, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [ECG]})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)
        _ack(s, "resume")
        assert s.phase.value == "golden"
        _fire_pass(s, LONG + " it keeps going on and on " * 8)   # launched AFTER the resume
        assert s.phase.value == "golden"
        _stop(s)
    assert len(_audit("auto.repause_suppressed", s.session_id)) == 1
    assert len(_audit("auto.paused", s.session_id)) == 1


def test_a_genuinely_new_action_from_a_pre_resume_pass_still_pauses(gate, monkeypatch):
    """The suppression covers only what the doctor acknowledged: a pass in
    flight at the resume that brings a NEW action pauses again, its
    pending set widened to everything it carried (slice 5's rule)."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [ECG, CALL]})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)
        _launch_gated_pass(s, engine, LONG + " and now I cannot breathe " * 8)
        _ack(s, "resume")
        assert s.phase.value == "golden"
        _release_pass(s, engine)
        assert s.phase.value == "paused_urgent"
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG now", "Call 999"})
        _stop(s)
    assert _audit("auto.repause_suppressed", s.session_id) == []
    paused = _audit("auto.paused", s.session_id)
    assert len(paused) == 2 and paused[1]["actions"] == ["Bedside ECG now", "Call 999"]


ADMIT = {"action": "Consider hospital admission", "reason": "suspected unstable angina"}
REFER = {"action": "Immediate referral to hospital", "reason": "suspected angina/ACS"}
IV = {"action": "IV access", "reason": "in case of deterioration"}


def test_the_485_shape_a_reworded_action_after_resume_does_not_re_pause(gate, monkeypatch):
    """Owner decision 2026-09-07 (pilot 485, defect E3). 485: RESUME AUTO
    covered "Bedside ECG" and "Consider hospital admission"; the pass in
    flight at the resume landed 8 s later with "Bedside ECG" and
    "Immediate referral to hospital" — the same decision in new words — and
    the text-keyed ratchet re-paused. Now the reworded action matches the
    acknowledged one by meaning, the pass is suppressed inside the one
    answer's chance, and every comparison is on the record
    (auto.action_matched with both texts and the score)."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(False, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG, ADMIT], 2: [ECG, REFER]})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)                                    # pass 1: ECG + admission → paused
        assert s.phase.value == "paused_urgent"
        _launch_gated_pass(s, engine, LONG + " and my arm is heavy " * 8)   # pass 2, in flight
        _ack(s, "resume")
        assert s.phase.value == "golden"
        _release_pass(s, engine)                               # pass 2: ECG + referral (reworded)
        assert s.phase.value == "golden", "the reworded action did not re-pause"
        _stop(s)
    suppressed = _audit("auto.repause_suppressed", s.session_id)
    assert len(suppressed) == 1
    assert suppressed[0]["actions"] == ["Bedside ECG now", "Immediate referral to hospital"]
    assert suppressed[0]["matched"] == ["Bedside ECG now", "Consider hospital admission"]
    matched = _audit("auto.action_matched", s.session_id)
    assert len(matched) == 2
    reworded = next(m for m in matched if m["candidate"] == "Immediate referral to hospital")
    assert reworded["matched"] == "Consider hospital admission"
    assert reworded["exact"] is False and 0.6 <= reworded["score"] < 1.0
    assert reworded["threshold"] == appmain.AUTO_ACTION_MATCH_THRESHOLD == 0.6
    exact = next(m for m in matched if m["candidate"] == "Bedside ECG now")
    assert exact["exact"] is True and exact["score"] == 1.0
    assert len(_audit("auto.paused", s.session_id)) == 1


SPECIALIST = {"action": "Same-day specialist referral", "reason": "new-onset angina"}
ADMIT_NOW = {"action": "Immediate hospital admission", "reason": "suspected ACS"}
HOSPITAL = {"action": "Hospital admission", "reason": "suspected ACS"}


def _standing(messages):
    return [m["actions"] for m in messages if m.get("type") == "auto_standing"]


def test_the_486_shape_an_acknowledged_action_reworded_across_five_post_answer_passes_never_re_pauses(gate, monkeypatch):
    """Owner decision 2026-09-07 (pilot 486, finding F1). In 486 the doctor
    acknowledged "Bedside ECG" + a hospital action once; seven post-answer
    passes re-issued the ECG with the hospital action re-worded five ways,
    and the ratchet paused on every one — eight RESUME taps. Now: after
    the one acknowledgement, five post-answer passes carrying the same
    actions in new words pause nothing (each skip audited with both texts
    and the score), the standing strip carries them throughout, a
    genuinely new action still pauses and widens, and once the transcript
    shows them arranged (the pass lists nothing) the strip clears."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG, ADMIT], 2: [ECG, REFER], 3: [ECG, ADMIT_NOW],
                                 4: [ECG, SPECIALIST], 5: [ECG, HOSPITAL], 6: [ECG, REFER],
                                 7: [ECG, IV], 8: []})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)                                    # pass 1 → paused
        assert s.phase.value == "paused_urgent"
        seen = _ack(s, "resume")
        assert s.phase.value == "golden"
        assert _standing(seen)[-1] == ["Bedside ECG now", "Consider hospital admission"], \
            "acknowledged: on the strip at once"
        strip = []
        for i, words in enumerate(("nobody has done it", "still nothing", "no ECG yet",
                                   "they have not come", "I am still waiting"), start=2):
            s.commit_transcript(f"Doctor, {words}.")           # an answer: a turn end after the resume
            s.quiet(3.2)
            s.probe()
            assert s.auto["repause_block"] is False
            before = len(s.state.cds_engine.updates)
            s.ws.portal.call(lambda: s.entry["transcript_parts"].extend([LONG + f" pass {i} " * 8]))
            for _ in range(40):
                strip += _standing(s.probe())
                landed = (s.entry["assessment"] or {}).get("reasoning") == f"pass {before + 1}"
                if landed:
                    strip += _standing(s.probe())
                    break
                time.sleep(0.02)
            assert landed, f"pass {i} did not land"
            assert s.phase.value == "golden", f"pass {i} re-paused on an acknowledged action"
        assert len(_audit("auto.paused", s.session_id)) == 1
        skipped = _audit("auto.repause_skipped_acknowledged", s.session_id)
        assert [d["assessment_version"] for d in skipped] == [2, 2, 3, 3, 4, 4, 5, 5, 6, 6]
        assert all(d["score"] >= 0.6 for d in skipped)
        reworded = [d for d in skipped if not d["exact"]]
        assert {d["candidate"] for d in reworded} >= {"Immediate referral to hospital",
                                                      "Immediate hospital admission"}
        assert all("Bedside ECG now" in acts for acts in strip), "the ECG stayed on the strip throughout"
        # A genuinely new action still pauses and widens.
        s.commit_transcript("Doctor, I feel faint now.")
        s.quiet(3.2)
        s.probe()
        _fire_pass(s, LONG + " and I feel faint " * 8)         # pass 7: ECG + IV access
        assert s.phase.value == "paused_urgent"
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG now", "IV access"})
        seen = _ack(s, "resume")
        assert _standing(seen)[-1] == ["Bedside ECG now", "IV access"]
        # Arranged: the pass lists nothing → the strip clears.
        s.commit_transcript("The ECG is being done now.")
        s.quiet(3.2)
        s.probe()
        before = len(engine.updates)
        s.ws.portal.call(lambda: s.entry["transcript_parts"].extend([LONG + " arranged " * 8]))
        cleared = []
        for _ in range(40):
            cleared += _standing(s.probe())
            if (s.entry["assessment"] or {}).get("reasoning") == f"pass {before + 1}":
                cleared += _standing(s.probe())
                break
            time.sleep(0.02)
        assert cleared and cleared[-1] == [], "arranged → cleared, by the server's push"
        _stop(s)
    assert len(_audit("auto.paused", s.session_id)) == 2
    assert len(_audit("auto.acknowledged", s.session_id)) == 2


def test_a_genuinely_new_action_bedside_ecg_then_iv_access_still_pauses_and_widens(gate, monkeypatch):
    """The matcher never turns a new action into an old one: "IV access"
    shares no token with "Bedside ECG now", so the pass pauses and the
    pending set widens to both (slice 5's rule), with no action_matched
    row written."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(False, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [ECG, IV]})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)
        _launch_gated_pass(s, engine, LONG + " and I feel faint " * 8)
        _ack(s, "resume")
        assert s.phase.value == "golden"
        _release_pass(s, engine)
        assert s.phase.value == "paused_urgent"
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG now", "IV access"})
        _stop(s)
    assert _audit("auto.action_matched", s.session_id) == []
    assert _audit("auto.repause_suppressed", s.session_id) == []
    paused = _audit("auto.paused", s.session_id)
    assert len(paused) == 2 and paused[1]["actions"] == ["Bedside ECG now", "IV access"]


def test_resume_from_golden_keeps_the_golden_seconds_already_spent(gate, monkeypatch):
    """A pause does not restart the golden window: the seconds spent before
    it count. With a 0 s window, the resumed GOLDEN exits at the next turn
    end without waiting another window."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 0.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: []})
    with live(gate) as s:
        s.to_golden()
        _fire_pass(s, LONG)
        assert s.phase.value == "paused_urgent" and s.auto["controller"].paused_from.value == "golden"
        _ack(s, "resume")
        assert s.phase.value == "golden"
        assert s.auto["golden_spent"] >= 0.0
        s.commit_transcript("and that is all")
        s.quiet(3.2)
        s.probe()
        assert s.phase.value == "open"
        _stop(s)


def test_the_encourager_count_is_the_windows_across_a_pause_and_resume(gate, monkeypatch):
    """REPINNED 2026-09-09 (owner decision, golden window encouragers;
    reversing the 1 Sept one-per-window rule this test pinned). What is
    kept: the encourager bookkeeping counts the WINDOW, not the stretch —
    a pause and resume neither reset it nor start it over. An encourager
    spoken before the pause is the first (go_on, one unanswered); the
    resumed GOLDEN's fresh span earns the second phrasing
    (tell_me_more_short, two unanswered); the next qualifying silence
    then ends the window early — the count carried across the pause —
    and the exit follows on the fallback quiet."""
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 5.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(False, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: []})
    with live(gate) as s:
        s.to_golden()
        s.quiet(5.5)
        e = _until(s.ws, {"auto_speak"})
        assert e["ref_id"] == "go_on"
        s.play(e["utterance_id"])
        _fire_pass(s, LONG)                                   # paused
        _ack(s, "resume")
        assert s.phase.value == "golden"
        assert s.auto["golden_encourager_count"] == 1 and s.auto["golden_unanswered"] == 1
        s.quiet(5.5)                                          # a fresh span after the resume
        second = _until(s.ws, {"auto_speak"})
        assert second["ref_id"] == "tell_me_more_short", "the window's second, not a fresh first"
        s.play(second["utterance_id"])
        s.quiet(5.5)                                          # the third qualifying silence
        s.probe()
        assert s.auto["golden_window_ran"] is True
        assert s.phase.value == "open", "the window ended early and the exit followed"
        cid = _stop(s)
    spoken = [r["ref_detail"]["id"] for r in _rows(cid) if r["ref_detail"].get("via") == "auto"
              and r["ref_detail"]["id"] in speech.GOLDEN_ENCOURAGER_IDS]
    assert spoken == ["go_on", "tell_me_more_short"]
    ran = _audit("auto.golden_window_ran", s.session_id)
    assert len(ran) == 1 and ran[0]["reason"] == "unanswered_encouragers" and ran[0]["encouragers"] == 2


def test_the_window_runs_correctly_across_two_pauses_the_482_arithmetic(gate, monkeypatch):
    """Consultation 482: GOLDEN ran 55.7 s, paused, resumed, ran 2.0 s more,
    paused, resumed — golden_spent 57.7 — and the 90 s window therefore
    ran out 32.3 s into the third stretch. Pinned on an injected clock:
    the seconds spent before each pause are kept, auto.golden_window_ran
    is written once with the summed golden_s, and (owner decision
    2026-09-01) the post-window fallback quiet then exits to OPEN."""
    monkeypatch.setattr(appmain, "AUTO_GOLDEN_MINUTES_S", 90.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG], 2: [CALL], 3: []})
    clock = {"t": 1000.0}
    with live(gate) as s:
        s.ws.portal.call(lambda: setattr(s.auto["controller"], "_clock", lambda: clock["t"]))
        s.to_golden()
        clock["t"] += 55.7
        _fire_pass(s, LONG)                                   # pass 1: ECG → paused
        assert s.phase.value == "paused_urgent"
        assert s.auto["golden_spent"] == pytest.approx(55.7)
        seen = _ack(s, "resume")
        assert s.phase.value == "golden"
        resumed = next(m for m in seen if m.get("type") == "auto_phase" and m["phase"] == "golden")
        assert resumed["golden_spent"] == pytest.approx(55.7), "the countdown's input (D7)"
        s.commit_transcript("and then it eased a bit")          # a turn ends after the resume
        s.quiet(3.2)
        s.probe()
        assert s.phase.value == "golden", "55.7 s spent: the window has not run"
        clock["t"] += 2.0
        _fire_pass(s, LONG + " it is worse now " * 6)          # pass 2: a NEW action → paused again
        assert s.phase.value == "paused_urgent"
        assert s.auto["golden_spent"] == pytest.approx(57.7)
        _ack(s, "resume")
        assert s.phase.value == "golden"
        clock["t"] += 32.0                                     # 89.7 s: not yet
        s.quiet(6.0)
        s.probe()
        assert s.phase.value == "golden"
        assert s.auto["golden_window_ran"] is False
        clock["t"] += 0.6                                      # 90.3 s: run, and 7 s quiet → exit
        s.quiet(7.0)
        s.probe()
        assert s.phase.value == "open"
        _stop(s)
    ran = _audit("auto.golden_window_ran", s.session_id)
    assert len(ran) == 1
    assert ran[0]["golden_s"] == pytest.approx(90.3, abs=0.05)
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == ("golden", "open", "golden_timer_elapsed")
    assert last["detail"]["golden_s"] == pytest.approx(90.3, abs=0.05)
    assert last["detail"]["by"] == "quiet_fallback"


def test_take_over_is_terminal_and_standard_mode_works(gate, monkeypatch):
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"]]
    _engine_with_alarms(engine, {2: [ECG, CALL], 3: [ECG]})
    with live(gate) as s:
        _pause_from_open(s, engine, monkeypatch)
        seen = _ack(s, "take_over")
        assert seen[-1]["type"] == "auto_acknowledged" and seen[-1]["resolution"] == "take_over"
        assert sorted(seen[-1]["actions"]) == ["Bedside ECG now", "Call 999"]
        assert s.phase.value == "taken_over"
        toggled = [m for m in s.probe() if m.get("type") == "auto_toggled"]
        # (the auto_toggled echo came right after auto_acknowledged)
        # Standard mode: a tap works, quiet earns nothing, a further alarm
        # pauses nothing, and no auto event but auto-off is legal.
        s.quiet(5.0)
        assert all(m.get("type") != "auto_speak" for m in s.probe())
        version = s.entry["agenda"].current_version
        s.ws.send_text(json.dumps({"type": "speak", "ref": {
            "kind": "cds_question", "assessment_version": version, "index": 0}}))
        ready = _until(s.ws, {"speak_ready"})
        s.play(ready["utterance_id"])
        _fire_pass(s, LONG)                              # pass 3: alarm again → nothing
        assert s.phase.value == "taken_over"
        # Acknowledging again is refused: nothing is paused.
        seen = _ack(s, "resume")
        assert seen[-1]["type"] == "auto_refused" and "not paused" in seen[-1]["detail"]
        cid = _stop(s)
    assert len(_audit("auto.takeover", s.session_id)) == 1
    assert _audit("auto.acknowledged", s.session_id)[0]["resolution"] == "take_over"
    assert len(_audit("auto.paused", s.session_id)) == 1, "no pause after take-over"
    # Unresolved at Stop still flows to the review banner exactly as today.
    from app import consultations
    review = asyncio.run(consultations.get_consultation(cid))
    assert {a["action"] for a in review["urgent_actions"]} == {"Bedside ECG now"}
    assert review["urgent_ack_at"] is None, "the live ack does not pre-acknowledge the review banner"


def test_the_review_payload_shows_the_live_acknowledgements_and_keeps_the_gate(gate, monkeypatch):
    """Display only: the review payload carries who/when/which texts under
    its own key, and the acknowledge-gated banner's data is untouched —
    urgent_actions present, urgent_ack_at null, so approval is still gated."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"]]
    _engine_with_alarms(engine, {2: [ECG]})
    with live(gate) as s:
        _pause_from_open(s, engine, monkeypatch)
        _ack(s, "take_over")
        user = s.entry["user"]
        cid = _stop(s)
    from auto_harness import _client_for
    client = _client_for(user)
    payload = client.get(f"/api/consultations/{cid}").json()
    acks = payload["live_acknowledgements"]
    assert len(acks) == 1
    assert acks[0]["resolution"] == "take_over"
    assert acks[0]["actions"] == ["Bedside ECG now"]
    assert acks[0]["username"] == user["username"]
    assert acks[0]["at"] and acks[0]["assessment_versions"] == [2]
    assert [a["action"] for a in payload["urgent_actions"]] == ["Bedside ECG now"]
    assert payload["urgent_ack_at"] is None
    # And a consultation with no live acks carries an empty list, not an error.
    with live(gate, user) as s2:
        s2.disclose()
        cid2 = _stop(s2)
    assert _client_for(user).get(f"/api/consultations/{cid2}").json()["live_acknowledgements"] == []


def test_acknowledgement_refusals_are_answered(gate):
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        seen = _ack(s, "resume")                          # not paused
        assert seen[-1]["type"] == "auto_refused" and "not paused" in seen[-1]["detail"]
        s.ws.send_text(json.dumps({"type": "auto_ack", "resolution": "ignore"}))
        seen = _collect_until(s.ws, {"auto_refused"})
        assert "resolution" in seen[-1]["detail"]
        _stop(s)


def test_the_reconnect_echo_carries_the_pending_texts_while_paused(gate):
    engine = gate.cds_engine
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG, CALL]})
    from auto_harness import _client_for, _make_user
    user = _make_user()
    with live(gate, user) as s:
        s.to_golden()
        _fire_pass(s, LONG)
        assert s.phase.value == "paused_urgent"
        session_id = s.session_id
    client = _client_for(user)
    with client.websocket_connect("/ws/transcribe") as ws2:
        ws2.send_json({"session_id": session_id, "resume": True})
        seen = _collect_until(ws2, {"auto_toggled"})
        assert seen[-1] == {"type": "auto_toggled", "on": True, "phase": "paused_urgent",
                            "pending": ["Bedside ECG now", "Call 999"]}
        ws2.send_text("stop")
        _until(ws2, {"done"})


# ==========================================================================
# Slice 6: the live phase push and the doctor's Handover control

def test_every_transition_is_pushed_live_as_auto_phase(gate):
    """The indicator on the status line follows a push per transition, not
    only the toggle echo."""
    with live(gate) as s:
        s.disclose()
        s.toggle(True)
        seen = _collect_until(s.ws, {"auto_toggled"})
        pushes = [(m["from"], m["phase"], m["trigger"]) for m in seen if m.get("type") == "auto_phase"]
        assert pushes == [("off", "disclosure", "enable"),
                          ("disclosure", "invitation", "disclosure_completed")]
        invitation = next(m for m in seen if m.get("type") == "auto_speak")
        s.play(invitation["utterance_id"])
        seen = s.probe()
        golden = [m for m in seen if m.get("type") == "auto_phase"]
        assert [(m["from"], m["phase"]) for m in golden] == [("invitation", "golden")]
        assert golden[0]["golden_spent"] == 0.0, "the push carries the golden seconds spent (D7)"
        _stop(s)


def test_the_doctors_handover_from_open_runs_the_sequence_and_ends_by_the_doctors_event(gate, monkeypatch):
    """OPEN: anything-else once, its answer's revision (empty here), the
    examination handover; the machine fires handover_requested (the doctor
    asked), auto.doctor_handover and auto.handover(requested_by=doctor)
    are on the record, and the run ends."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], []]
    _engine_with_alarms(engine, {})
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()                    # the first question, playing
        s.play(first["utterance_id"])
        s.ws.send_text(json.dumps({"type": "auto_handover"}))
        started = _until(s.ws, {"auto_handover_started", "auto_refused"})
        assert started["type"] == "auto_handover_started" and started["phase"] == "open"
        s.turn_end("Tuesday night.")                       # the room goes quiet: anything-else
        anything = s.wait_for_auto_speak()
        assert anything["ref_id"] == "anything_else"
        s.play(anything["utterance_id"])
        s.turn_end("No, that's everything.")               # revision (pass 2): empty
        final = s.wait_for_auto_speak()
        assert final["ref_id"] == "examination_handover"
        s.play(final["utterance_id"])
        s.probe()
        assert s.phase.value == "handover"
        _stop(s)
    assert len(_audit("auto.doctor_handover", s.session_id)) == 1
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == ("open", "handover", "handover_requested")
    assert last["detail"]["by"] == "doctor"
    handover = _audit("auto.handover", s.session_id)
    assert len(handover) == 1 and handover[0]["requested_by"] == "doctor"


def test_the_doctors_handover_refill_path_returns_to_the_questions(gate, monkeypatch):
    """The agenda-refill return path applies to the doctor's handover
    identically: the anything-else answer refills the agenda → back to the
    questions, and the eventual end is the agenda's, not the doctor's."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Have you missed any of your tablets?"], []]
    _engine_with_alarms(engine, {})
    with live(gate) as s:
        s.to_golden()
        s.to_open()
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        s.ws.send_text(json.dumps({"type": "auto_handover"}))
        _until(s.ws, {"auto_handover_started"})
        s.turn_end("Tuesday night.")
        anything = s.wait_for_auto_speak()
        assert anything["ref_id"] == "anything_else"
        s.play(anything["utterance_id"])
        s.turn_end("Well — my tablets, I keep forgetting them.")   # pass 2: refill
        back = s.wait_for_auto_speak()
        assert back["text"] == "Can you tell me more about your tablets?"
        assert s.phase.value in ("open", "closed")
        s.play(back["utterance_id"])
        s.turn_end("Most mornings.")                       # pass 3: empty → final
        final = s.wait_for_auto_speak()
        assert final["ref_id"] == "examination_handover", "anything_else not spoken twice"
        s.play(final["utterance_id"])
        s.probe()
        assert s.phase.value == "handover"
        _stop(s)
    last = _audit("auto.phase", s.session_id)[-1]
    assert last["trigger"] == "agenda_exhausted"
    assert _audit("auto.handover", s.session_id)[0]["requested_by"] == "agenda_empty"


def test_the_doctors_handover_from_golden_ends_the_golden_minutes_and_speaks_the_sequence(gate, monkeypatch):
    """GOLDEN: the machine's own edge fires at once (GOLDEN → HANDOVER: the
    doctor has ended the golden minutes and the history) and the two
    phrases are spoken from HANDOVER — anything-else, its answer, the
    examination handover — with no refill path (stated in HANDOVER as the
    asymmetry the design left open)."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, False)]
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {})
    with live(gate) as s:
        s.to_golden()
        s.ws.send_text(json.dumps({"type": "auto_handover"}))
        seen = _collect_until(s.ws, {"auto_handover_started"})
        assert s.phase.value == "handover"
        assert any(m.get("type") == "auto_phase" and m["phase"] == "handover" for m in seen)
        s.commit_transcript("It started on Tuesday.")
        s.quiet(3.2)
        s.probe()
        anything = s.wait_for_auto_speak()
        assert anything["ref_id"] == "anything_else"
        s.play(anything["utterance_id"])
        s.turn_end("No, nothing else.")
        final = s.wait_for_auto_speak()
        assert final["ref_id"] == "examination_handover"
        s.play(final["utterance_id"])
        seen = s.probe()
        assert any(m.get("type") == "auto_toggled" and m["on"] is False for m in seen)
        assert s.phase.value == "handover"
        _stop(s)
    phases = [(d["from"], d["to"], d["trigger"]) for d in _audit("auto.phase", s.session_id)]
    assert phases[-1] == ("golden", "handover", "handover_requested")
    assert _audit("auto.handover", s.session_id)[0]["requested_by"] == "doctor"


@pytest.mark.parametrize("phase", ["golden", "open"])
def test_a_tapped_examination_handover_ends_the_run_like_the_control(gate, monkeypatch, phase):
    """Owner decision 2026-09-01 (pilot defect D5): in 482 the doctor
    tapped the examination handover during the golden minutes and "Mm-hm."
    followed it — a tap changed no flow state. Now a tapped handover in
    GOLDEN, OPEN or CLOSED ends the auto run exactly as the Handover
    control does: the same handover_requested edge to HANDOVER, audited
    auto.doctor_handover with via=tap and auto.handover with
    requested_by=doctor, the client told the run has ended, and no
    encourager, ask or machine handover afterwards."""
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_MIN_QUIET_S", 5.0)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"]]
    _engine_with_alarms(engine, {})
    with live(gate) as s:
        s.to_golden()
        if phase == "open":
            s.to_open()
        assert s.phase.value == phase
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase",
                                                            "id": "examination_handover"}}))
        seen = _collect_until(s.ws, {"speak_ready"})
        assert s.phase.value == "handover", "the run ended at the tap"
        pushes = [(m["from"], m["phase"], m["trigger"]) for m in seen if m.get("type") == "auto_phase"]
        assert (phase, "handover", "handover_requested") in pushes
        assert any(m.get("type") == "auto_toggled" and m["on"] is False for m in seen)
        s.play(seen[-1]["utterance_id"])
        # Silence afterwards earns nothing: no encourager, no ask, no
        # machine handover — the doctor has already said it.
        for q in (5.5, 9.0, 14.0):
            s.quiet(q)
            assert all(m.get("type") != "auto_speak" for m in s.probe()), f"spoke at {q}s"
        for _ in range(10):
            assert all(m.get("type") != "auto_speak" for m in s.probe())
        assert s.auto["queued"] is None and s.auto["handover"] is None
        cid = _stop(s)
    handovers = _audit("auto.doctor_handover", s.session_id)
    assert len(handovers) == 1 and handovers[0]["via"] == "tap" and handovers[0]["phase"] == phase
    ended = _audit("auto.handover", s.session_id)
    assert len(ended) == 1 and ended[0]["requested_by"] == "doctor" and ended[0]["via"] == "tap"
    last = _audit("auto.phase", s.session_id)[-1]
    assert (last["from"], last["to"], last["trigger"]) == (phase, "handover", "handover_requested")
    assert last["detail"] == {"by": "doctor", "via": "tap"}
    taps = _audit("auto.doctor_tap", s.session_id)
    assert taps[-1]["ref_detail"]["id"] == "examination_handover"
    auto_rows = [r for r in _rows(cid) if r["ref_detail"].get("via") == "auto"]
    assert [r["ref_detail"]["id"] for r in auto_rows if r["ref_detail"].get("id") in
            ("go_on", "mm-hm", "i_see", "anything_else", "examination_handover")] == []


def test_a_tapped_handover_after_the_run_has_ended_changes_nothing(gate):
    """Outside the listening phases a tapped handover is just a tap: in
    DISCLOSURE the machine keeps waiting; after HANDOVER it is over anyway."""
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.toggle(True)                                        # DISCLOSURE, disclosure in flight
        seen = _collect_until(s.ws, {"auto_toggled"})
        disclosure = next(m for m in seen if m.get("type") == "auto_speak")
        s.play(disclosure["utterance_id"])
        invitation = _until(s.ws, {"auto_speak"})
        assert s.phase.value == "invitation"
        s.ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase",
                                                            "id": "examination_handover"}}))
        _until(s.ws, {"speak_refused"})                       # one utterance at a time
        assert s.phase.value == "invitation"
        s.play(invitation["utterance_id"])
        s.probe()
        _stop(s)
    assert _audit("auto.doctor_handover", s.session_id) == []


def test_handover_refusals_are_answered(gate, monkeypatch):
    engine = gate.cds_engine
    engine.agendas = [["Q?"]]
    _engine_with_alarms(engine, {1: [ECG]})
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.ws.send_text(json.dumps({"type": "auto_handover"}))       # auto off
        assert "listening" in _until(s.ws, {"auto_refused"})["detail"]
        s.to_golden()
        _fire_pass(s, LONG)                                          # paused
        s.ws.send_text(json.dumps({"type": "auto_handover"}))
        assert "paused urgent" in _until(s.ws, {"auto_refused"})["detail"]
        _stop(s)
    assert _audit("auto.doctor_handover", s.session_id) == []
