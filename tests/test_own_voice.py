"""H1 — the machine must not hear its own voice as the patient (owner
decision 2026-09-10, after consultation 491).

In 491 "Let me think for a moment." re-armed itself ten times: the phrase,
heard by the microphone at 0.05–0.23 RMS, restarted the client's quiet
span as patient speech; the server cleared the judged turn end for it; the
3.5 s fallback ended a turn with nothing asked and reset the once-per-wait
guard; and the phrase was said again, every 5.1 s until the pass landed.

Two layers, both pinned here:

- Client (live.html): the RMS path never counts energy as activity while
  our audio is playing or in the 300 ms after it ends; the playback-end
  path is unchanged, so the let_me_think exemption on it now governs.
- Server (app/main.py): a fresh span stamped "speech" whose start falls
  inside one of our own utterance windows (speech.requested to
  speech.spoken, plus 300 ms) is read as playback — the turn end is not
  cleared — and the auto.quiet_report row says own_voice.

Driven over the real socket with the shared harness: the phrase is played
through as the client does, then the H1 report — a fresh "speech" span
that began during the phrase — is sent exactly as a page whose meter
still counts our playback would send it. The attack reaches its target:
the report is fresh, stamped speech, and the server audits it.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

import pytest  # noqa: F401

from app import main as appmain
from app.cds import OfficerVerdict
from auto_harness import (  # noqa: F401 - the fixture is used by name
    Q_ONSET, Q_SLEEP, _audit, _stop, gate, live, needs_db)

pytestmark = needs_db

LIVE = Path("app/static/live.html").read_text()


# --------------------------------------------------------------------------
# The window rule, on its own
# --------------------------------------------------------------------------

def test_a_span_is_ours_from_the_request_to_the_end_plus_the_tail_and_not_beyond():
    """The window runs from speech.requested (the request precedes the
    audio) to the playback's end plus AUTO_OWN_VOICE_TAIL_S; an instant
    before the request or after the tail is the patient's. A window whose
    end was never seen counts only while its utterance is the pending
    one, so a lost speak_ended cannot swallow every later span."""
    entry = {"pending_utterance": None}
    appmain._own_voice_requested(entry, "u1")
    t_req = entry["own_voice"][0]["requested_at"]
    assert appmain._own_voice_at(entry, t_req - 0.01) is None, "before the request: the patient's"
    assert appmain._own_voice_at(entry, t_req + 0.05) is None, "open but not pending: not ours"

    class Pending:
        utterance_id = "u1"
    entry["pending_utterance"] = Pending()
    assert appmain._own_voice_at(entry, t_req + 0.05) == "u1", "open and pending: ours"
    appmain._own_voice_ended(entry, "u1")
    t_end = entry["own_voice"][0]["ended_at"]
    entry["pending_utterance"] = None
    assert appmain._own_voice_at(entry, t_end) == "u1"
    assert appmain._own_voice_at(entry, t_end + appmain.AUTO_OWN_VOICE_TAIL_S - 0.01) == "u1"
    assert appmain._own_voice_at(entry, t_end + appmain.AUTO_OWN_VOICE_TAIL_S + 0.01) is None
    # The list is bounded; the newest windows survive.
    for k in range(20):
        appmain._own_voice_requested(entry, f"w{k}")
    assert len(entry["own_voice"]) == appmain._OWN_VOICE_WINDOWS_KEPT
    assert entry["own_voice"][-1]["utterance_id"] == "w19"


def test_the_client_and_the_server_use_the_same_tail():
    """One number on both sides: the client's OWN_VOICE_TAIL_MS and the
    server's AUTO_OWN_VOICE_TAIL_S are the owner's 300 ms."""
    ms = int(re.search(r"const OWN_VOICE_TAIL_MS = (\d+);", LIVE).group(1))
    assert ms == 300
    assert appmain.AUTO_OWN_VOICE_TAIL_S * 1000 == ms


# --------------------------------------------------------------------------
# The client's meter
# --------------------------------------------------------------------------

def test_the_rms_path_never_counts_our_own_playback_as_activity():
    """The meter's activity call is guarded by ownVoiceNow(now): true
    while `speaking` (our audio is playing) and for OWN_VOICE_TAIL_MS after
    stopSpeaking stamped the playback's end. The playback-end path is as
    it was — 'playback' for every utterance but "Let me think", which
    leaves the span running — so that exemption now actually governs:
    nothing else restarts the span at the phrase."""
    loop = LIVE[LIVE.index("// Level meter: RMS of the analyser"):LIVE.index("refreshDeviceMenu();")]
    assert "if (rms >= quietReporter.floor && !ownVoiceNow(now)) quietReporter.activity(now);" in loop
    assert loop.count("quietReporter.activity(") == 1, "the meter has exactly one activity call"
    guard = LIVE[LIVE.index("function ownVoiceNow(now) {"):]
    guard = guard[:guard.index("\n}") + 2]
    assert "speaking !== null" in guard
    assert "now - lastPlaybackEndMs < OWN_VOICE_TAIL_MS" in guard
    stop = LIVE[LIVE.index("function stopSpeaking(reason, cutLatencyMs) {"):]
    stop = stop[:stop.index("\n}")]
    assert "lastPlaybackEndMs = performance.now();" in stop
    assert stop.index("speaking = null;") < stop.index("lastPlaybackEndMs = performance.now();")
    # The playback-end path, unchanged (tests/test_quiet_reporter_client.py
    # pins the 'playback' cause; here, the exemption it now governs).
    assert "if (refId !== 'let_me_think') {" in stop
    assert "quietReporter.activity(performance.now(), 'playback');" in stop
    assert LIVE.count("lastPlaybackEndMs = ") == 2, "declared once, stamped once (at playback's end)"


# --------------------------------------------------------------------------
# The server, over the socket
# --------------------------------------------------------------------------

def _into_the_empty_wait(s, engine):
    """OPEN, the first question answered, its pass held: the empty-queue
    wait in which "Let me think" is said once. Returns the phrase's
    auto_speak message, played through with the quiet clock kept."""
    s.to_golden()
    s.to_open()
    first = s.wait_for_auto_speak()
    s.play(first["utterance_id"])
    gate_event = s.ws.portal.call(asyncio.Event)
    engine.gate_event = gate_event
    s.turn_end("Tuesday night.")
    assert not s.auto["queue"].has_pending
    assert s.auto["turn_ended"] is True
    heard = []
    q = 3.3
    for _ in range(4):
        q += 0.8
        s.quiet(q)
        heard += [m for m in s.probe() if m.get("type") == "auto_speak"]   # probe plays it through
        if heard:
            break
    assert [m["ref_id"] for m in heard] == ["let_me_think"]
    assert s.auto["think_used"] is True and s.auto["turn_ended"] is True
    return heard[0], gate_event


def _phrase_into_the_mic(s):
    """What a page whose meter still counts our playback sends after the
    phrase: a fresh span, stamped speech, whose start falls inside the
    phrase's window (its end plus the 300 ms tail)."""
    time.sleep(0.15)
    s.since = "speech"
    s.span += 1
    s.quiet(0.1)                        # began 0.1 s ago: inside the phrase's tail
    s.probe()
    return s.span


def test_the_phrase_played_into_the_mic_produces_no_patient_span_and_no_second_let_me_think(gate):
    """H1: the span the phrase's own energy began is read as playback —
    the judged turn end stands (no patient span: span_seq unchanged,
    turn_ended still true), the once-per-wait guard survives it
    (think_used still true), and across the quiet that follows no second
    "Let me think" is issued and no second turn end is written. The
    report is on the record as auto.quiet_report with own_voice true and
    the phrase's utterance id."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_SLEEP]]
    with live(gate) as s:
        phrase, gate_event = _into_the_empty_wait(s, engine)
        span_seq = s.auto["span_seq"]
        turn_ends = len(_audit("auto.turn_ended", s.session_id))
        phrases_heard = len(s.thinking_heard)          # the golden exit's wait may have had one too
        h1_span = _phrase_into_the_mic(s)
        assert s.auto["turn_ended"] is True, "our own voice did not clear the judged turn end"
        assert s.auto["span_seq"] == span_seq, "no patient span began"
        assert s.auto["think_used"] is True, "the once-per-wait guard survived the phrase"
        heard = []
        for q in (2.1, 3.6, 4.4, 5.2, 6.1):
            s.quiet(q)
            heard += [m for m in s.probe() if m.get("type") == "auto_speak"]
            time.sleep(0.02)
        assert heard == [], f"no second phrase and no question in the empty wait: {heard}"
        assert len(s.thinking_heard) == phrases_heard, "no phrase was re-armed"
        assert len(_audit("auto.turn_ended", s.session_id)) == turn_ends, "no turn ended again"
        s.ws.portal.call(gate_event.set)               # the merge adds Q_SLEEP
        nxt = s.wait_for_auto_speak(skip_thinking=False)
        assert nxt["text"] == "Can you tell me more about your sleep?", "the wait ends with the merge"
        _stop(s)
    reports = [r for r in _audit("auto.quiet_report", s.session_id) if r["span"] == h1_span]
    assert reports and reports[0]["fresh"] is True and reports[0]["since"] == "speech", \
        "the attack reached the server: a fresh span stamped speech"
    assert reports[0]["own_voice"] is True
    assert reports[0]["own_voice_utterance"] == phrase["utterance_id"]
    others = [r for r in _audit("auto.quiet_report", s.session_id) if r["span"] != h1_span]
    assert others and all(r["own_voice"] is False for r in others)
    assert [t["reason"] for t in _audit("auto.thinking", s.session_id)].count("empty_queue") == 2, \
        "the golden exit's wait and the answer's: one phrase each, none re-armed"


def test_a_real_patient_utterance_after_the_phrase_still_ends_the_wait(gate):
    """H1 must not deafen the machine: the patient speaking after the
    phrase — a fresh span whose start lies outside our window — is still
    the patient's: the judged turn end is cleared, the patient's span moves
    on, and quiet of the fallback length ends the turn again, a new wait
    in which the phrase may be said once more. The own-voice report just
    before it is still read as ours."""
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET], [Q_SLEEP]]
    with live(gate) as s:
        _phrase, gate_event = _into_the_empty_wait(s, engine)
        span_seq = s.auto["span_seq"]
        turn_ends = len(_audit("auto.turn_ended", s.session_id))
        _phrase_into_the_mic(s)
        assert s.auto["turn_ended"] is True and s.auto["span_seq"] == span_seq
        s.commit_transcript("Sorry — one more thing, it woke me at four.")   # the patient, for real
        s.quiet(0.4)                       # began 0.4 s ago: well outside the phrase's tail
        s.probe()
        assert s.auto["turn_ended"] is False, "the patient's own voice clears the judged turn end"
        assert s.auto["span_seq"] == span_seq + 1, "the patient's span moved on"
        heard = []
        for q in (2.1, 3.6, 4.4):
            s.quiet(q)
            heard += [m for m in s.probe() if m.get("type") == "auto_speak"]
            time.sleep(0.02)
        assert s.auto["turn_ended"] is True, "the new turn ended on the fallback"
        assert len(_audit("auto.turn_ended", s.session_id)) == turn_ends + 1
        assert [m["ref_id"] for m in heard] in ([], ["let_me_think"]), \
            "a new wait: at most one more phrase, never a question from an empty queue"
        s.ws.portal.call(gate_event.set)
        nxt = s.wait_for_auto_speak(skip_thinking=False)
        assert nxt["text"] == "Can you tell me more about your sleep?"
        _stop(s)
    rows = _audit("auto.quiet_report", s.session_id)
    assert [r["own_voice"] for r in rows if r["fresh"]].count(True) == 1, \
        "exactly one span was ours: the phrase's; the patient's was not"
