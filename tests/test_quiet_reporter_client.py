"""The client's quiet reporter (Phase 7c slice 3), EXECUTED under Node
(the tests/test_silence_nudge_client.py convention): the shipped
`quietReporter` object is lifted verbatim from live.html and driven with
a fake clock.

PHASE_7C_SPEC.md §5 — measurement client-side, authority server-side.
What is pinned:

- It reports only while the server has confirmed auto mode on, and only
  the thresholds the server configured (speech_config.auto, env-only);
  the page holds no numbers of its own.
- Reports go out when quiet crosses each configured threshold, once per
  threshold per quiet span, and then once a second while the quiet
  lasts — so the server can rotate encouragers on cooldown and run the
  officer without the client deciding anything.
- Activity — room speech, transcript movement, our own playback ending —
  starts a fresh span; while our own utterance plays, nothing is
  reported (busy).
- "Quiet" is the barge-in absolute floor, the same "this is speech"
  number the politeness abort uses (owner decision 2026-08-16), not the
  1e-4 silence floor room noise exceeds. Asserted on the RMS loop's
  source, since the loop itself is not liftable.
- The nudge yields: while the reporter is enabled the nudge's request
  loop returns before it can ask.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
LIVE = Path("app/static/live.html").read_text()


def _reporter() -> str:
    start = LIVE.index("const quietReporter = {")
    return LIVE[start:LIVE.index("\n};", start) + 3]


_HARNESS = """
%(reporter)s
const out = {};
const r = quietReporter;

// Not configured, not enabled: never reports.
out.beforeConfig = r.poll(5000, false);
r.configure({encourager_min_quiet_s: 1.75, eot_quiet_s: 3.0, eot_fallback_s: 5.0});
out.thresholds = r.thresholds.slice();
out.disabled = r.poll(99999, false);          // still disabled

// Enabled: a fresh span begins at the confirmation.
r.enabled = true;
r.activity(1000);
out.t1000 = r.poll(1000, false);              // just went quiet: nothing
out.t2000 = r.poll(2000, false);              // 1.0 s: below the first threshold
out.t2800 = r.poll(2800, false);              // 1.8 s: crosses 1.75 → report
out.t3000 = r.poll(3000, false);              // 0.2 s later: no cadence report yet
out.t3900 = r.poll(3900, false);              // 2.9 s: 1.1 s since last → cadence report
out.t4050 = r.poll(4050, false);              // 3.05 s: crosses 3.0 → report (threshold wins)
out.t4100 = r.poll(4100, false);              // nothing (0.05 s since)
out.t6100 = r.poll(6100, false);              // 5.1 s: crosses 5.0 → report
out.t7050 = r.poll(7050, false);              // 0.95 s since: not yet
out.t7100 = r.poll(7100, false);              // 1.0 s since: cadence report at 6.1 s
out.t8100 = r.poll(8100, false);              // and again: quiet lasts, reports continue
out.crossedAll = r.crossed;

// Our own playback: busy → nothing reported, and the span is not consumed.
out.busy = r.poll(9100, true);
out.afterBusy = r.poll(9100, false);          // same instant, not busy → the report busy withheld

// Activity starts a fresh span: back below the first threshold — and a
// new span NUMBER (G3, 2026-09-09), which is what the server keys on.
out.spanBefore = r.span;
r.activity(10000);
out.spanAfter = r.span;
r.activity(10000, 'playback');
out.spanAfterPlayback = r.span;
out.afterActivityCrossed = r.crossed;
out.t10500 = r.poll(10500, false);            // 0.5 s: nothing
out.t11800 = r.poll(11800, false);            // 1.8 s: first threshold again

// Disabled mid-span (auto off): silent at once.
r.enabled = false;
out.disabledMidSpan = r.poll(20000, false);

// Configure de-duplicates and sorts, and drops nonsense.
r.configure({encourager_min_quiet_s: 3, eot_quiet_s: 1, eot_fallback_s: 3});
out.dedup = r.thresholds.slice();
r.configure({encourager_min_quiet_s: 0, eot_quiet_s: -1, eot_fallback_s: 'x'});
out.nonsense = r.thresholds.slice();
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_shipped_reporter_executed_under_node():
    script = _HARNESS % {"reporter": _reporter()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)

    assert out["beforeConfig"] is None
    assert out["thresholds"] == [1.75, 3.0, 5.0]
    assert out["disabled"] is None, "no report unless the server confirmed auto mode on"

    assert out["t1000"] is None and out["t2000"] is None
    assert out["t2800"] == pytest.approx(1.8)      # first threshold
    assert out["t3000"] is None
    assert out["t3900"] == pytest.approx(2.9)      # 1 Hz cadence while quiet lasts
    assert out["t4050"] == pytest.approx(3.05)     # second threshold
    assert out["t4100"] is None
    assert out["t6100"] == pytest.approx(5.1)      # third threshold
    assert out["t7050"] is None
    assert out["t7100"] == pytest.approx(6.1)      # cadence continues after the last threshold
    assert out["t8100"] == pytest.approx(7.1)
    assert out["crossedAll"] == 3

    assert out["busy"] is None, "our own playback is not the patient's silence"
    assert out["afterBusy"] == pytest.approx(8.1)

    assert out["afterActivityCrossed"] == 0
    # G3 (owner decision 2026-09-09, pilot 489): every activity — the
    # patient's or our own playback — numbers a new span, so a fresh span
    # whose first report equals the previous span's last is still seen.
    assert out["spanAfter"] == out["spanBefore"] + 1
    assert out["spanAfterPlayback"] == out["spanBefore"] + 2
    assert out["t10500"] is None
    assert out["t11800"] == pytest.approx(1.8), "a fresh span crosses the first threshold again"

    assert out["disabledMidSpan"] is None, "auto off silences the reporter at once"

    assert out["dedup"] == [1, 3]
    assert out["nonsense"] == []


def test_the_reporter_is_fed_by_the_existing_rms_loop_at_the_speech_floor():
    """Spec §5: the existing ~10 fps RMS loop feeds it. Activity is speech
    — the barge-in absolute floor — not the 1e-4 silence floor; and the
    report is sent from that loop, only while recording on an open socket."""
    loop = LIVE[LIVE.index("// Level meter: RMS of the analyser"):LIVE.index("refreshDeviceMenu();")]
    assert "if (rms > 1e-4) nudge.activity(now);" in loop         # the nudge, unchanged
    assert "if (rms >= quietReporter.floor) quietReporter.activity(now);" in loop
    # ...and that floor is the SESSION's floor from the room (owner decision
    # 2026-09-09, pilot 488 G2: speech_config.auto.floor, derived from the
    # sound check; the barge-in absolute floor only stands in when the
    # server sent none), copied when the server configures the reporter —
    # the same number the politeness abort compares against (the meter
    # loop itself must never mention the detector —
    # tests/test_barge_in_constraints.py).
    assert "quietReporter.floor = politeness.currentFloor();" in LIVE
    assert "barge" not in loop.lower()
    assert "quietReporter.poll(now, speaking !== null || pendingSpeakText !== '')" in loop
    assert "ws.send(JSON.stringify({type: 'quiet', quiet_s:" in loop
    assert "recording && ws && ws.readyState === WebSocket.OPEN" in loop
    # G6/G11 (owner decision 2026-09-09): every reading feeds the RMS trace,
    # and the report carries the reading, the floor and the trace.
    assert "quietReporter.sample(rms);" in loop
    for field in ("span: quietReporter.span", "rms: Math.round(rms * 1e5) / 1e5", "floor: quietReporter.floor",
                  "trace: quietReporter.trace.slice()", "trace_step_ms: quietReporter.traceStepMs"):
        assert field in loop, field


_TRACE_HARNESS = """
%(reporter)s
const out = {};
const r = quietReporter;
r.configure({encourager_min_quiet_s: 4.0, eot_quiet_s: 2.0, eot_fallback_s: 3.5,
             trace_s: 8.0, trace_step_ms: 100});
out.traceLen = r.traceLen; out.step = r.traceStepMs;
for (let i = 0; i < 100; i++) r.sample(0.001 * i);
out.len = r.trace.length;
out.first = r.trace[0]; out.last = r.trace[r.trace.length - 1];
r.configure({encourager_min_quiet_s: 4.0, eot_quiet_s: 2.0, eot_fallback_s: 3.5, trace_s: 0.5});
out.shortLen = r.traceLen; out.cleared = r.trace.length;
r.sample(0.123456789);
out.rounded = r.trace[0];
r.configure({eot_quiet_s: 2.0, eot_fallback_s: 3.5});
out.defaultLen = r.traceLen;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_rms_trace_is_a_bounded_ring_sized_by_the_server(monkeypatch):
    """G6 (owner decision 2026-09-09): the reporter keeps the last trace_s
    seconds of readings at the meter's step — 80 samples for 8 s at
    100 ms — oldest dropped first, newest last, rounded to the page's RMS
    precision; a reconfigure resizes and clears it; without a length the
    default is 8 s."""
    script = _TRACE_HARNESS % {"reporter": _reporter()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["traceLen"] == 80 and out["step"] == 100
    assert out["len"] == 80
    assert out["first"] == pytest.approx(0.020) and out["last"] == pytest.approx(0.099)
    assert out["shortLen"] == 5 and out["cleared"] == 0
    assert out["rounded"] == 0.12346
    assert out["defaultLen"] == 80


def test_every_activity_source_resets_the_reporter():
    """The nudge's activity sources, all of them: transcript movement
    (final and changed partial) and our own playback ending.

    REPINNED 2026-09-07 (owner decision, pilot 485 E2): our playback ending
    still resets the reporter, and now names itself as the cause
    ('playback'), which every report of that span carries as `since` so the
    server never lets our own voice erase a judged turn end. Every other
    source stays speech."""
    assert LIVE.count("quietReporter.activity(performance.now())") >= 3
    final_block = LIVE[LIVE.index("if (msg.type === 'final') {"):LIVE.index("else if (msg.type === 'partial')")]
    assert "quietReporter.activity(performance.now())" in final_block
    stop = LIVE[LIVE.index("function stopSpeaking(reason, cutLatencyMs) {"):]
    stop = stop[:stop.index("\n}")]
    assert "quietReporter.activity(performance.now(), 'playback')" in stop
    assert LIVE.count("'playback')") == 1, "our own playback is the only 'playback' cause"
    assert "since: quietReporter.since" in LIVE, "every report says what began its span"


def test_the_reporter_is_configured_and_enabled_by_the_server_only():
    """Thresholds arrive in speech_config.auto (sent only when the gate is
    up, server-side env); enablement is the server's auto_toggled echo.
    Nothing on the page can turn it on by itself."""
    assert "quietReporter.configure(msg.auto);" in LIVE
    assert LIVE.count("quietReporter.configure(") == 1
    toggled = LIVE[LIVE.index("else if (msg.type === 'auto_toggled') {"):]
    toggled = toggled[:toggled.index("\n  }")]
    assert "quietReporter.enabled = !!msg.on;" in toggled
    assert "quietReporter.activity(performance.now())" in toggled
    # No other assignment to enabled anywhere in the page.
    assert LIVE.count("quietReporter.enabled = ") == 1
    main = Path("app/main.py").read_text()
    block = main[main.index('speech_config["auto"] = {'):]
    block = block[:block.index("}")]
    # (encourager_quiet_s, the bridge's threshold, was retired 2026-09-09.)
    for key in ("encourager_min_quiet_s", "eot_quiet_s", "eot_fallback_s"):
        assert key in block
    assert "if AUTO_MODE_ENABLED:" in main[main.index("speech_config = {"):main.index('speech_config["auto"]')]


def test_the_reporter_never_requests_an_utterance():
    """Authority stays server-side: the reporter has no path to `speak` and
    no phrase reference in it — it measures and reports, nothing else."""
    src = _reporter()
    assert "requestSpeak" not in src
    assert "speak" not in src.replace("speech_config", "")
    assert "kind:" not in src and "phrase" not in src
