"""H3 — the quiet span starts at silence, not at the transcript's arrival
(owner decision 2026-09-10, after consultation 491).

The streaming transcriber commits an answer's last segment 2.1-3.7 s after
its last word (491: mean 2.95 s); the client restarted the reporter's span
on every final and changed partial, so every answer waited that much
longer than the 3.5 s rule — the whole of 489/490's "trailing energy".

Pinned here, the final/partial branches of live.html's onWsMessage lifted
verbatim and EXECUTED under Node (the tests/test_quiet_reporter_client.py
convention) around the shipped quietReporter and a stub nudge:

- a final arriving 3 s after the last energy does not move the span
  start: the next report counts the quiet from the energy, not the final;
- a changed partial does not either;
- the nudge still resets on both (its rule is inherited by nothing now).

And, over the real socket, the auto.turn_ended row's transcript numbers:
the last transcribed word's end, the span start, their difference, and
the transcriber's own commit latency — what the next run measures.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from app.cds import OfficerVerdict
from app.transcription import Segment
from auto_harness import (  # noqa: F401 - the fixture is used by name
    Q_ONSET, _audit, _stop, gate, live, needs_db)

NODE = shutil.which("node")
LIVE = Path("app/static/live.html").read_text()


def _reporter() -> str:
    start = LIVE.index("const quietReporter = {")
    return LIVE[start:LIVE.index("\n};", start) + 3]


def _transcript_branches() -> str:
    """The final and partial branches of onWsMessage, verbatim."""
    start = LIVE.index("  if (msg.type === 'final') {")
    return LIVE[start:LIVE.index("  else if (msg.type === 'speech_config')")]


_HARNESS = """
%(reporter)s
let clock = 0;
const performance = {now: () => clock};
const nudge = {calls: [], activity(now) { this.calls.push(now); }};
const partialEl = {textContent: ''};
function addFinal(msg) {}
let lastPartialText = '';
function onWsMessage(msg) {
%(branches)s
}
const out = {};
const r = quietReporter;
r.configure({encourager_min_quiet_s: 4.0, eot_quiet_s: 2.0, eot_fallback_s: 3.5});
r.enabled = true;

// The patient's last word ends at 1000: the meter saw energy until then.
r.activity(1000);
out.spanAtEnergy = r.span;
// 2.5 s later the reporter reports quiet of 2.5 s (the 2.0 threshold).
clock = 3500; out.report1 = r.poll(3500, false);
// The final arrives 3 s after the last energy.
clock = 4000; onWsMessage({type: 'final', text: 'Tuesday night.', start: 0.2, end: 1.0});
out.quietSinceAfterFinal = r.quietSince;
out.spanAfterFinal = r.span;
out.nudgeAfterFinal = nudge.calls.slice();
// The next report, 3.6 s after the energy: quiet is counted from the energy.
clock = 4600; out.report2 = r.poll(4600, false);
// A changed partial does not move it either; the nudge sees it.
clock = 4700; onWsMessage({type: 'partial', text: 'and then'});
out.quietSinceAfterPartial = r.quietSince;
out.spanAfterPartial = r.span;
out.nudgeAfterPartial = nudge.calls.slice();
// An unchanged partial is nothing to anyone; an empty one too.
clock = 4800; onWsMessage({type: 'partial', text: 'and then'});
onWsMessage({type: 'partial', text: ''});
out.nudgeAfterRepeat = nudge.calls.slice();
clock = 5700; out.report3 = r.poll(5700, false);
// Energy is still activity: a fresh span.
r.activity(6000);
out.spanAfterEnergy = r.span; out.quietSinceAfterEnergy = r.quietSince;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_a_final_arriving_3s_after_the_last_energy_does_not_move_the_span_start():
    script = _HARNESS % {"reporter": _reporter(), "branches": _transcript_branches()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["report1"] == pytest.approx(2.5)
    assert out["quietSinceAfterFinal"] == 1000, "the span still starts at the last energy"
    assert out["spanAfterFinal"] == out["spanAtEnergy"], "no new span at the final"
    assert out["report2"] == pytest.approx(3.6), "quiet counted from the energy, across the final"
    assert out["quietSinceAfterPartial"] == 1000 and out["spanAfterPartial"] == out["spanAtEnergy"]
    assert out["report3"] == pytest.approx(4.7)
    assert out["spanAfterEnergy"] == out["spanAtEnergy"] + 1 and out["quietSinceAfterEnergy"] == 6000


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_nudge_still_resets_on_transcript_movement():
    """The nudge's rule is the nudge's: a final and a changed partial are
    activity for it (a phantom partial suppressing the nudge is
    acceptable, the reverse is not); a repeated or empty partial is not."""
    script = _HARNESS % {"reporter": _reporter(), "branches": _transcript_branches()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["nudgeAfterFinal"] == [4000]
    assert out["nudgeAfterPartial"] == [4000, 4700]
    assert out["nudgeAfterRepeat"] == [4000, 4700]


def test_the_branches_lifted_are_the_shipped_ones():
    """The harness runs the real branches: they name the nudge twice and
    the reporter never (tests/test_quiet_reporter_client.py pins the same
    on the whole page)."""
    branches = _transcript_branches()
    assert branches.count("nudge.activity(performance.now())") == 2
    assert "quietReporter" not in branches.replace("H3", "")   # only the comment may mention it


# --------------------------------------------------------------------------
# The record: auto.turn_ended's transcript numbers
# --------------------------------------------------------------------------

class OneFinalTranscriber:
    """Silent until armed; then commits one segment, once — the answer's
    last words, as the streaming transcriber would some seconds after
    they were spoken."""

    def __init__(self):
        self.armed = False
        self.done = False

    def transcribe(self, buffer):
        if self.armed and not self.done:
            self.done = True
            return [Segment(start=0.1, end=0.5, text="Tuesday night.")]
        return []


@needs_db
def test_the_turn_ended_row_carries_the_last_word_end_the_span_start_and_the_commit_latency(gate):
    """When a final has been committed and a span reported, the answer's
    auto.turn_ended row carries last_word_end_s (the session clock),
    span_start_s (the report's audio time minus its quiet), their
    difference last_word_to_span_start_s, and commit_latency_s — the
    final's arrival on the session clock minus its last word's end, at
    least the transcriber's commit margin. (The golden exit's turn end is
    on auto.phase, not here, so the answer's is the first turn_ended row;
    before any final the two headline keys are present and null.)"""
    transcriber = OneFinalTranscriber()
    gate.transcriber = transcriber
    engine = gate.cds_engine
    engine.verdicts = [OfficerVerdict(True, True), OfficerVerdict(True, False)]
    engine.agendas = [[Q_ONSET]]
    with live(gate) as s:
        s.to_golden()
        s.to_open()                                  # a turn end before any final
        first = s.wait_for_auto_speak()
        s.play(first["utterance_id"])
        transcriber.armed = True
        for _ in range(40):                          # frames until the final commits
            s.probe()
            if s.entry.get("last_final") is not None:
                break
            time.sleep(0.01)
        last_final = s.entry.get("last_final")
        assert last_final is not None, "the attack reached its target: a final was committed"
        s.turn_end("Tuesday night.", quiet=3.2)
        assert s.auto["turn_ended"] is True
        span_start = s.auto["span_start"]
        _stop(s)
    rows = _audit("auto.turn_ended", s.session_id)
    assert len(rows) >= 1
    after = rows[-1]
    assert after["answer"] is True
    assert after["last_word_end_s"] == round(last_final["end"], 2)
    assert after["span_start_s"] == round(span_start["audio_s"], 2)
    assert after["last_word_to_span_start_s"] == pytest.approx(
        round(span_start["audio_s"] - last_final["end"], 2), abs=0.011)
    assert after["commit_latency_s"] == pytest.approx(
        round(last_final["committed_at_audio_s"] - last_final["end"], 2), abs=0.011)
    assert after["commit_latency_s"] >= 2.0, "the commit margin: a final always trails its words"
    assert after["last_final_age_s"] >= 0
