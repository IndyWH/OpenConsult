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
from auto_harness import (Q_ONSET, OfficerVerdict, TTS_AMPLITUDE, _audit, _collect_until,  # noqa: F401
                          _rows, _stop, _until, gate, live, needs_db)

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
