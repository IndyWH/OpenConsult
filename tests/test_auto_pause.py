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
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 1.75)   # the harness parks it
    with live(gate) as s:
        s.to_golden()
        s.quiet(2.0)                                   # → an encourager (GOLDEN)
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
        # And the slot is free again.
        s.quiet(2.5)
        assert any(m.get("type") == "auto_speak" for m in s.probe())
        cid = _stop(s)
    rows = _rows(cid)
    cut = next(r for r in rows if r["utterance_id"] == e["utterance_id"])
    assert cut["end_reason"] == "urgency_pause"
    assert cut["started_offset_ms"] is not None
    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    assert (cut["started_offset_ms"] * BYTES_PER_MS, cut["ended_offset_ms"] * BYTES_PER_MS) in spans


def test_an_unstarted_utterance_is_cut_with_the_reason_and_no_span(gate, monkeypatch):
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 1.75)
    with live(gate) as s:
        s.to_golden()
        s.quiet(2.0)
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
    pass; other passes are quiet. Agendas keep their scripted order."""
    async def update(transcript, previous=None):
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
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 1.75)
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"],
                      ["Does the pain radiate to your jaw or arm?"], ["Any nausea?"]]
    alarm_pass = {"golden": 1, "open": 2, "closed": 3}[phase]
    _engine_with_alarms(engine, {alarm_pass: [ECG]})
    with live(gate) as s:
        s.to_golden()
        if phase == "golden":
            s.quiet(2.0)                                     # an encourager in flight
            e = next(m for m in s.probe() if m.get("type") == "auto_speak")
            s.ws.send_text(json.dumps({"type": "speak_started",
                                       "utterance_id": e["utterance_id"], "seq": s.seq + 1}))
            s.frame(TTS_AMPLITUDE)
            _until(s.ws, {"ack"})
            _fire_pass(s, LONG)                              # pass 1: the alarm
        else:
            monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 100.0)
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
        cut = next(r for r in rows if r["text"] == "Mm-hm.")
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
    monkeypatch.setattr(appmain, "AUTO_ENCOURAGER_QUIET_S", 100.0)
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
    """RESUME AUTO: auto.acknowledged carries every pending text and the
    snapshot versions; the machine returns to exactly OPEN; auto.resumed
    is written; the D2 revision runs (the agenda reprioritises through
    the CDS, no new mechanism). Then the SAME action text re-fires on the
    next pass and pauses again — a fresh acknowledgement is needed, and
    both are on the record."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [["When did the chest pain first start?"], ["Any nausea?"]]
    _engine_with_alarms(engine, {2: [ECG], 3: [ECG], 4: []})
    with live(gate) as s:
        _pause_from_open(s, engine, monkeypatch)
        assert s.auto["controller"].paused_from.value == "open"
        seen = _ack(s, "resume")
        assert seen[-1]["type"] == "auto_acknowledged"
        assert seen[-1]["resolution"] == "resume" and seen[-1]["actions"] == ["Bedside ECG now"]
        assert seen[-1]["phase"] == "open"
        assert s.phase.value == "open", "the exact prior phase"
        assert s.auto["controller"].pending_actions == frozenset()
        assert s.auto["controller"].acknowledged_actions == frozenset({"Bedside ECG now"})
        assert s.auto["revision"] in ("requested", "running"), "the D2 revision is asked for at once"
        # The revision (pass 3) re-fires the SAME text: paused again — the
        # ratchet — and needs a fresh acknowledgement.
        for _ in range(30):
            if s.phase.value == "paused_urgent":
                break
            s.probe()
        assert s.phase.value == "paused_urgent"
        assert s.auto["controller"].pending_actions == frozenset({"Bedside ECG now"})
        seen = _ack(s, "resume")
        assert seen[-1]["type"] == "auto_acknowledged"
        assert s.phase.value == "open"
        cid = _stop(s)
    acks = _audit("auto.acknowledged", s.session_id)
    assert [a["resolution"] for a in acks] == ["resume", "resume"]
    assert acks[0]["actions"] == ["Bedside ECG now"] and acks[0]["assessment_versions"] == [2]
    assert acks[1]["assessment_versions"] == [3]
    assert acks[0]["paused_from"] == "open"
    resumed = _audit("auto.resumed", s.session_id)
    assert [r["phase"] for r in resumed] == ["open", "open"]
    phases = [(d["from"], d["to"], d["trigger"]) for d in _audit("auto.phase", s.session_id)]
    assert phases.count(("paused_urgent", "open", "acknowledge_resume")) == 2
    assert phases.count(("open", "paused_urgent", "urgent_alarm")) == 2
    # The consultation-linked summary carries both, for the review page.
    from app import audit as audit_mod
    summary = asyncio.run(audit_mod.for_subject("consultation", cid, "auto.acknowledgements"))
    assert len(summary) == 1
    assert [a["resolution"] for a in summary[0]["detail"]["acknowledgements"]] == ["resume", "resume"]


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
