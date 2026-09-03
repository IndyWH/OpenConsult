"""The phase indicator and the Handover control (Phase 7c slice 6,
PHASE_7C_SPEC.md §6, §10) — the client half. `applyAutoPhase` is
EXECUTED under Node; the rest is pinned on source.

Pinned: the indicator names the phase in the doctor's words (Golden
minutes / Open questions / Closed questions / Paused — urgent / Handing
over), follows the server's live auto_phase push and the auto_toggled
echo, and is hidden unless auto mode is on; the Handover control is
visible only while auto is on AND the machine is listening (golden,
open, closed), sends {"type":"auto_handover"}, sits beside the Auto
pill, and carries its reason on itself.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
LIVE = Path("app/static/live.html").read_text()


def _extract(start_marker: str, end_marker: str) -> str:
    start = LIVE.index(start_marker)
    return LIVE[start:LIVE.index(end_marker, start) + len(end_marker)]


_HARNESS = """
%(labels)s
%(countdown)s
%(apply)s
const box = {hidden: true, textContent: ''};
const document = {getElementById(id) { return id === 'autoPhase' ? box : null; }};
let autoOn = true, autoPhase = 'off', refreshed = 0;
function refreshSpeechControls() { refreshed += 1; }
const out = {};
for (const p of ['disclosure', 'invitation', 'golden', 'open', 'closed', 'paused_urgent', 'handover']) {
  applyAutoPhase(p);
  out[p] = {hidden: box.hidden, text: box.textContent};
}
applyAutoPhase('taken_over');
out.taken_over = {hidden: box.hidden, text: box.textContent};
autoOn = false;
applyAutoPhase('golden');
out.offGolden = {hidden: box.hidden, text: box.textContent};
applyAutoPhase(undefined);
out.keptPhase = autoPhase;
console.log(JSON.stringify({out, refreshed}));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_indicator_names_the_phase_and_hides_when_off():
    labels = _extract("const AUTO_PHASE_LABELS = {", "\n};")
    countdown = _extract("const goldenCountdown = {", "\n};")
    apply = _extract("function applyAutoPhase(phase) {", "\n}")
    result = subprocess.run([NODE, "-e", _HARNESS % {"labels": labels, "apply": apply,
                                                     "countdown": countdown}],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    got = json.loads(result.stdout)["out"]
    assert got["golden"] == {"hidden": False, "text": "Auto mode: Golden minutes"}
    assert got["open"]["text"] == "Auto mode: Open questions"
    assert got["closed"]["text"] == "Auto mode: Closed questions"
    assert got["paused_urgent"]["text"] == "Auto mode: Paused — urgent"
    assert got["handover"]["text"] == "Auto mode: Handing over"
    assert got["disclosure"]["hidden"] is False and got["invitation"]["hidden"] is False
    assert got["taken_over"] == {"hidden": True, "text": ""}, "no label for a run that has ended"
    assert got["offGolden"] == {"hidden": True, "text": ""}, "hidden unless auto mode is on"
    assert got["keptPhase"] == "golden"


def test_the_indicator_is_driven_by_the_live_push_and_the_echo():
    handler = _extract("else if (msg.type === 'auto_phase') {", "\n  }")
    assert "applyAutoPhase(msg.phase);" in handler
    assert "goldenCountdown.onPhase(msg.phase, msg.golden_spent, performance.now());" in handler
    toggle = _extract("function applyAutoToggle(msg) {", "\n}")
    assert "applyAutoPhase(autoPhase);" in toggle
    assert 'id="autoPhase"' in LIVE
    status = LIVE[LIVE.index('id="status"'):]
    assert 'id="autoPhase"' in status[:600], "on the status line"


def test_the_handover_control_shows_only_while_listening_and_sends_the_message():
    row = LIVE[LIVE.index('id="soundCheckBtn"'):LIVE.index('id="btn"')]
    assert 'id="handoverBtn"' in row and row.index('id="autoPill"') < row.index('id="handoverBtn"')
    assert 'id="handoverBtn" type="button" hidden' in LIVE
    assert ">Hand over<" in LIVE
    refresh = _extract("function refreshSpeechControls() {", "\n}")
    assert "const listening = autoOn && ['golden', 'open', 'closed'].includes(autoPhase);" in refresh
    assert "handover.hidden = !(autoAvailable && listening);" in refresh
    assert "handover.disabled = !live;" in refresh
    assert "Reconnecting — handover waits" in refresh
    click = _extract("handoverBtn.addEventListener('click', () => {", "\n});")
    assert "ws.send(JSON.stringify({type: 'auto_handover'}));" in click


# --------------------------------------------------------------------------
# The golden countdown (owner decision 2026-09-01, pilot D7)

_COUNTDOWN_HARNESS = """
%(labels)s
%(countdown)s
%(apply)s
const box = {hidden: true, textContent: ''};
const document = {getElementById(id) { return id === 'autoPhase' ? box : null; }};
let autoOn = true, autoPhase = 'off';
function refreshSpeechControls() {}
// performance.now() is stubbed so the harness owns the clock.
let clock = 0;
const performance = {now() { return clock; }};
goldenCountdown.configure({golden_s: 90});
const out = [];
function at(ms, phase, spent) {
  clock = ms;
  if (phase) goldenCountdown.onPhase(phase, spent, clock);
  applyAutoPhase(phase);
  out.push({t: ms / 1000, remaining: goldenCountdown.remaining(clock), text: box.textContent});
}
// Consultation 482's shape, on the server's own numbers.
at(0, 'golden', 0);                 // GOLDEN entered, nothing spent
at(20000);                          // a tick
at(55700, 'paused_urgent', 55.7);   // paused after 55.7 s: the push's spent includes it
at(70000);                          // held while paused
at(80000, 'golden', 55.7);          // RESUME AUTO: spent unchanged, counting again
at(82000, 'paused_urgent', 57.7);   // re-paused 2.0 s later
at(90000, 'golden', 57.7);          // resumed again
at(100000);                         // 10 s into the third stretch
at(122300, 'open', 57.7);           // exit: cleared
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_countdown_after_a_pause_and_resume_equals_the_server_arithmetic():
    """The client's remaining seconds follow the server's golden_spent:
    90 − spent − time in GOLDEN, counting down in GOLDEN, frozen while
    PAUSED_URGENT, cleared on exit. The 482 arithmetic: 55.7 + 2.0 spent,
    so 10 s into the third stretch 22.3 s remain, and the window ran out
    at 32.3 s in — exactly what the server audited."""
    labels = _extract("const AUTO_PHASE_LABELS = {", "\n};")
    countdown = _extract("const goldenCountdown = {", "\n};")
    apply = _extract("function applyAutoPhase(phase) {", "\n}")
    result = subprocess.run([NODE, "-e", _COUNTDOWN_HARNESS % {
        "labels": labels, "countdown": countdown, "apply": apply}],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    got = json.loads(result.stdout)
    by_t = {row["t"]: row for row in got}
    assert by_t[0]["remaining"] == 90 and by_t[0]["text"] == "Auto mode: Golden minutes · 90 s left"
    assert abs(by_t[20]["remaining"] - 70) < 1e-9
    assert abs(by_t[55.7]["remaining"] - 34.3) < 1e-9, "frozen at 90 − 55.7"
    assert abs(by_t[70]["remaining"] - 34.3) < 1e-9, "still frozen while paused"
    assert "held, 34 s left" in by_t[70]["text"] and by_t[70]["text"].startswith("Auto mode: Paused — urgent")
    assert abs(by_t[80]["remaining"] - 34.3) < 1e-9, "resumed: counting from where it left off"
    assert abs(by_t[82]["remaining"] - 32.3) < 1e-9
    assert abs(by_t[90]["remaining"] - 32.3) < 1e-9
    assert abs(by_t[100]["remaining"] - 22.3) < 1e-9, "90 − 57.7 − 10, the server's arithmetic"
    assert by_t[100]["text"] == "Auto mode: Golden minutes · 22 s left"
    assert by_t[122.3]["remaining"] is None and by_t[122.3]["text"] == "Auto mode: Open questions"


def test_the_countdown_is_configured_from_the_server_and_cleared_when_auto_goes_off():
    assert "goldenCountdown.configure(msg.auto);" in LIVE
    toggled = LIVE[LIVE.index("else if (msg.type === 'auto_toggled') {"):]
    toggled = toggled[:toggled.index("\n  }")]
    assert "if (!msg.on) goldenCountdown.clear();" in toggled
    assert "setInterval(() => {\n  if (autoOn && goldenCountdown.remaining(performance.now()) !== null) applyAutoPhase();\n}, 1000);" in LIVE
