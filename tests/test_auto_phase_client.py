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
    apply = _extract("function applyAutoPhase(phase) {", "\n}")
    result = subprocess.run([NODE, "-e", _HARNESS % {"labels": labels, "apply": apply}],
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
    assert "else if (msg.type === 'auto_phase') { applyAutoPhase(msg.phase); }" in LIVE
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
