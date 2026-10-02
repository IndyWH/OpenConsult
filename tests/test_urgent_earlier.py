"""The earlier alarm, server half (owner decision 2026-10-02, after Task
3f): an urgent action that was shown and then drops out of a CDS pass
stays on the live page as a historical item, so a quiet pass is not read
as the all-clear. In 495 the alarm fired at pass 2, went quiet at pass 3
and came back at pass 4; for those 45 seconds the panel was empty.

Pinned here: the rule itself (`urgent_earlier`, points 2-5 of the
decision), its wiring over the real socket — the earlier alarm travels
beside the assessment in the `cds` message, never inside it; a page that
reconnects is told the current state; one `urgent.dropped_out` row when
an alarm drops out with nothing arranged — and that it changes nothing
about the pause: no pause, no pending action, no change to what an
acknowledgement covers.

The harness is tests/auto_harness.py (a scripted engine standing in for
MedGemma).
"""

from __future__ import annotations

import json
import time

import pytest

from app import main as appmain
from app.main import urgent_earlier
from auto_harness import (_assessment, _audit, _client_for, _collect_until, _make_user,  # noqa: F401
                          _stop, _until, gate, live, needs_db)

ECG = {"action": "Bedside ECG now", "reason": "exclude ACS"}
CALL = {"action": "Call 999", "reason": "possible STEMI"}


def _pass(actions=(), arranged=False):
    assessment = _assessment(["Q?"])
    assessment["urgent_actions"] = [dict(a) for a in actions]
    assessment["urgency_check"]["already_done_or_arranged"] = arranged
    assessment["urgency_check"]["time_critical_possible"] = bool(actions) or arranged
    return assessment


# ==========================================================================
# The rule (points 2-5), pure

def test_the_rule_never_fired_shows_nothing():
    assert urgent_earlier(_pass(), None) is None
    assert urgent_earlier(None, None) is None


def test_the_rule_fire_then_empty_shows_every_action_with_its_reason_and_time():
    last = {"actions": [ECG, CALL], "at_audio_s": 84.3}
    assert urgent_earlier(_pass(), last) == {"actions": [ECG, CALL], "last_flagged_s": 84.3}


def test_the_rule_a_live_alarm_replaces_the_earlier_one():
    last = {"actions": [ECG], "at_audio_s": 84.3}
    assert urgent_earlier(_pass([CALL]), last) is None
    assert urgent_earlier(_pass([ECG]), last) is None


def test_the_rule_arranged_clears_it():
    last = {"actions": [ECG], "at_audio_s": 84.3}
    assert urgent_earlier(_pass(arranged=True), last) is None


def test_the_rule_returns_a_copy_the_page_cannot_alias():
    last = {"actions": [dict(ECG)], "at_audio_s": 84.3}
    shown = urgent_earlier(_pass(), last)
    shown["actions"][0]["action"] = "changed"
    assert last["actions"][0]["action"] == "Bedside ECG now"


# ==========================================================================
# Over the socket

LONG = ("I have had this crushing central chest pain for an hour and it goes into my "
        "left arm and jaw and I feel sick. ") * 2


def _script(engine, script):
    """`script` maps pass number (1-based) → (urgent_actions, arranged); a
    pass not in it is quiet and unarranged."""
    async def update(transcript, previous=None):
        if engine.gate_event is not None:
            await engine.gate_event.wait()
        engine.updates.append(transcript)
        actions, arranged = script.get(len(engine.updates), ((), False))
        assessment = _pass(actions, arranged)
        assessment["reasoning"] = f"pass {len(engine.updates)}"
        return assessment
    engine.update = update


def _land(s, n):
    """Commit enough transcript for a pass, tick until pass `n`'s `cds`
    message arrives, and return it."""
    def _inject():
        s.entry["transcript_parts"].append(LONG)
    s.ws.portal.call(_inject)
    for _ in range(60):
        for m in s.probe():
            if m.get("type") == "cds" and m["assessment"]["reasoning"] == f"pass {n}":
                return m
        time.sleep(0.02)
    raise AssertionError(f"pass {n} did not land")


@needs_db
@pytest.mark.parametrize("auto_gate", [True, False])
def test_fire_then_empty_shows_the_earlier_alarm(gate, monkeypatch, auto_gate):
    """With the auto-mode gate up or down: the alarm fires, the next pass
    is quiet and unarranged → the cds message carries the earlier alarm
    (every action, its reason, the audio time of the pass that last
    flagged it) and one urgent.dropped_out row is written; a further quiet
    pass keeps showing it and writes no second row."""
    monkeypatch.setattr(appmain, "AUTO_MODE_ENABLED", auto_gate)
    _script(gate.cds_engine, {1: ((ECG, CALL), False)})
    with live(gate) as s:
        first = _land(s, 1)
        assert [a["action"] for a in first["assessment"]["urgent_actions"]] == [
            "Bedside ECG now", "Call 999"]
        assert first["urgent_earlier"] is None
        flagged_at = s.entry["urgent_first_fired"]["Bedside ECG now"]

        second = _land(s, 2)
        assert second["assessment"]["urgent_actions"] == []
        assert second["urgent_earlier"] == {"actions": [ECG, CALL], "last_flagged_s": flagged_at}
        # Beside the assessment, never in it: the assessment is the next
        # pass's `previous`, and the earlier alarm never reaches a model.
        assert "urgent_earlier" not in s.entry["assessment"]
        assert "Bedside ECG now" not in json.dumps(s.entry["assessment"])

        third = _land(s, 3)
        assert third["urgent_earlier"] == second["urgent_earlier"]
        _stop(s)
    rows = _audit("urgent.dropped_out", s.session_id)
    assert len(rows) == 1
    assert rows[0]["actions"] == ["Bedside ECG now", "Call 999"]
    assert rows[0]["last_flagged_s"] == flagged_at
    assert rows[0]["assessment_version"] == 2


@needs_db
def test_fire_empty_fire_again_clears_it_and_the_next_drop_shows_the_newer_list(gate):
    _script(gate.cds_engine, {1: ((ECG,), False), 3: ((CALL,), False)})
    with live(gate) as s:
        _land(s, 1)
        assert _land(s, 2)["urgent_earlier"]["actions"] == [ECG]
        third = _land(s, 3)
        assert [a["action"] for a in third["assessment"]["urgent_actions"]] == ["Call 999"]
        assert third["urgent_earlier"] is None, "a live alarm replaces the earlier one"
        refired_at = s.entry["urgent_last"]["at_audio_s"]
        fourth = _land(s, 4)
        assert fourth["urgent_earlier"] == {"actions": [CALL], "last_flagged_s": refired_at}
        _stop(s)
    rows = _audit("urgent.dropped_out", s.session_id)
    assert [r["actions"] for r in rows] == [["Bedside ECG now"], ["Call 999"]]


@needs_db
def test_arranged_clears_the_alarm_and_the_earlier_alarm(gate):
    """Arranged at the drop-out: nothing shown, no row. Arranged after an
    earlier alarm is shown: it goes."""
    _script(gate.cds_engine, {1: ((ECG,), False), 2: ((), True), 3: ((), True)})
    with live(gate) as s:
        _land(s, 1)
        assert _land(s, 2)["urgent_earlier"] is None
        assert _land(s, 3)["urgent_earlier"] is None
        _stop(s)
    assert _audit("urgent.dropped_out", s.session_id) == []

    _script(gate.cds_engine, {1: ((ECG,), False), 3: ((), True), 4: ((), True)})
    gate.cds_engine.updates.clear()
    with live(gate) as s:
        _land(s, 1)
        assert _land(s, 2)["urgent_earlier"]["actions"] == [ECG]
        assert _land(s, 3)["urgent_earlier"] is None
        assert _land(s, 4)["urgent_earlier"] is None
        _stop(s)
    assert len(_audit("urgent.dropped_out", s.session_id)) == 1


@needs_db
def test_never_fired_shows_nothing(gate):
    _script(gate.cds_engine, {})
    with live(gate) as s:
        for n in (1, 2, 3):
            assert _land(s, n)["urgent_earlier"] is None
        assert s.entry["urgent_last"] is None
        _stop(s)
    assert _audit("urgent.dropped_out", s.session_id) == []


@needs_db
def test_the_pause_and_pending_lists_are_unchanged_by_an_earlier_alarm(gate):
    """Auto mode on, the alarm pauses it. A quiet pass then shows the
    earlier alarm — and the machine is still paused on exactly the same
    pending list, no auto_pause or auto_standing is sent for it, no second
    auto.paused row is written, and RESUME AUTO acknowledges exactly what
    it acknowledged before. After the resume a further quiet pass, earlier
    alarm still shown, pauses nothing."""
    _script(gate.cds_engine, {1: ((ECG,), False)})
    with live(gate) as s:
        s.to_golden()
        fired = _land(s, 1)
        assert fired["assessment"]["urgent_actions"] == [ECG]
        for _ in range(20):
            if s.phase.value == "paused_urgent":
                break
            s.probe()
        assert s.phase.value == "paused_urgent"
        ctl = s.auto["controller"]
        pending_before = ctl.pending_actions
        acknowledged_before = ctl.acknowledged_actions
        standing_before = s.auto["standing_sent"]
        assert pending_before == frozenset({"Bedside ECG now"})

        def _inject():
            s.entry["transcript_parts"].append(LONG)
        s.ws.portal.call(_inject)
        seen = []
        for _ in range(60):
            seen += s.probe()
            if any(m.get("type") == "cds" and m["assessment"]["reasoning"] == "pass 2" for m in seen):
                break
            time.sleep(0.02)
        quiet = next(m for m in seen if m.get("type") == "cds"
                     and m["assessment"]["reasoning"] == "pass 2")
        assert quiet["urgent_earlier"]["actions"] == [ECG], "the attack reached the page"
        assert not [m for m in seen if m.get("type") in ("auto_pause", "auto_standing")]
        assert s.phase.value == "paused_urgent"
        assert ctl.pending_actions == pending_before
        assert ctl.acknowledged_actions == acknowledged_before
        assert s.auto["standing_sent"] == standing_before

        s.ws.send_text(json.dumps({"type": "auto_ack", "resolution": "resume"}))
        acked = _until(s.ws, {"auto_acknowledged"})
        assert acked["actions"] == ["Bedside ECG now"]
        assert s.phase.value != "paused_urgent"
        third = _land(s, 3)
        assert third["urgent_earlier"]["actions"] == [ECG]
        assert s.phase.value != "paused_urgent"
        assert ctl.pending_actions == frozenset()
        _stop(s)
    assert len(_audit("auto.paused", s.session_id)) == 1
    assert len(_audit("urgent.dropped_out", s.session_id)) == 1


@needs_db
def test_a_page_that_reconnects_is_told_the_current_state(gate):
    _script(gate.cds_engine, {1: ((ECG,), False)})
    user = _make_user()
    with live(gate, user) as s:
        _land(s, 1)
        shown = _land(s, 2)["urgent_earlier"]
        assert shown["actions"] == [ECG]
        session_id = s.session_id
    client = _client_for(user)
    with client.websocket_connect("/ws/transcribe") as ws2:
        ws2.send_json({"session_id": session_id, "resume": True})
        seen = _collect_until(ws2, {"urgent_earlier"})
        assert seen[-1] == {"type": "urgent_earlier", "earlier": shown}
        ws2.send_text("stop")
        _until(ws2, {"done"})


@needs_db
def test_a_new_session_is_not_sent_the_reconnect_message(gate):
    """Only a reconnect is told; a fresh session has nothing to be told."""
    _script(gate.cds_engine, {})
    with live(gate) as s:
        seen = s.probe()
        assert not [m for m in seen if m.get("type") == "urgent_earlier"]
        _stop(s)
