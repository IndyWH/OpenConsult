"""The Auto pill (Phase 7c slice 6, PHASE_7C_SPEC.md §10 as amended),
EXECUTED under Node where the logic is liftable and pinned on source
where it is not.

What is pinned: the pill exists only when the server's speech_config
carries an auto block (with AUTO_MODE_ENABLED false it is hidden and
nothing on the page can ask for auto mode); it is server-confirmed —
the label, the pressed state and the tap's next meaning follow the
auto_toggled echo, never the tap; the tap sends exactly the message the
server accepts ({"type":"auto","on":bool}); it sits beside Sound check
and Face in the control row; and it carries its reason on itself in
every state (the three standing rules — tests/test_standing_rules.py
covers the rules themselves; this file covers the mechanics).
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
%(apply)s
const classes = new Set();
const attrs = {};
const autoPill = {classList: {toggle(n, on) { on ? classes.add(n) : classes.delete(n); }},
                  setAttribute(k, v) { attrs[k] = v; }};
const autoPillLabel = {textContent: ''};
let autoOn = false, autoPhase = 'off';
let refreshed = 0;
function refreshSpeechControls() { refreshed += 1; }
const out = [];
for (const msg of [{on: true, phase: 'disclosure'}, {on: true, phase: 'golden'},
                   {on: true, phase: 'paused_urgent'}, {on: false, phase: 'off'},
                   {on: false, phase: 'taken_over'}, {on: true}]) {
  applyAutoToggle(msg);
  out.push({label: autoPillLabel.textContent, pressed: attrs['aria-pressed'],
            done: classes.has('done'), on: autoOn, phase: autoPhase});
}
console.log(JSON.stringify({out, refreshed}));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_pill_follows_the_servers_echo_not_the_tap():
    apply = _extract("function applyAutoToggle(msg) {", "\n}")
    result = subprocess.run([NODE, "-e", _HARNESS % {"apply": apply}],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    got = json.loads(result.stdout)
    assert got["out"][0] == {"label": "Auto: on", "pressed": "true", "done": True,
                             "on": True, "phase": "disclosure"}
    assert got["out"][1]["phase"] == "golden"
    assert got["out"][2] == {"label": "Auto: on", "pressed": "true", "done": True,
                             "on": True, "phase": "paused_urgent"}
    assert got["out"][3] == {"label": "Auto: off", "pressed": "false", "done": False,
                             "on": False, "phase": "off"}
    assert got["out"][4]["label"] == "Auto: off" and got["out"][4]["phase"] == "taken_over"
    assert got["out"][5]["on"] is True and got["out"][5]["phase"] == "taken_over"  # phase kept if absent
    assert got["refreshed"] == 6, "every echo re-evaluates the controls"


def test_the_pill_is_hidden_unless_the_server_says_auto_mode_exists():
    """With the gate down speech_config carries no auto block (pinned server-
    side in tests/test_auto_golden.py), and this is the only place the
    page learns auto mode exists."""
    assert 'id="autoPill" type="button" aria-pressed="false" hidden' in LIVE
    config = _extract("else if (msg.type === 'speech_config') {", "\n  }")
    assert "autoAvailable = true;" in config
    assert config.index("if (msg.auto) {") < config.index("autoAvailable = true;")
    assert LIVE.count("autoAvailable = true") == 1
    refresh = _extract("function refreshSpeechControls() {", "\n}")
    assert "autoBtn.hidden = !autoAvailable;" in refresh


def test_the_tap_sends_the_servers_message_and_the_pill_sits_in_the_control_row():
    click = _extract("autoPill.addEventListener('click', () => {", "\n});")
    assert "ws.send(JSON.stringify({type: 'auto', on: !autoOn}));" in click
    # Beside Sound check and Face, in the same control row, same class.
    row = LIVE[LIVE.index('id="soundCheckBtn"'):LIVE.index('id="btn"')]
    assert 'id="facePill"' in row and 'id="autoPill"' in row
    assert row.index('id="facePill"') < row.index('id="autoPill"')
    assert 'class="soundcheck" id="autoPill"' in LIVE
    assert ">Auto: off<" in LIVE
    # The echo drives it.
    toggled = _extract("else if (msg.type === 'auto_toggled') {", "\n  }")
    assert "applyAutoToggle(msg);" in toggled


def test_the_pill_carries_its_reason_in_every_state():
    refresh = _extract("function refreshSpeechControls() {", "\n}")
    block = refresh[refresh.index("const autoBtn"):refresh.index("soundCheckBtn.disabled")]
    assert "autoBtn.disabled = !live;" in block
    assert "Start the consultation first" in block           # cannot act: why
    assert "Stop auto mode now" in block                      # can act, on: what the tap does
    assert "Start auto mode" in block                         # can act, off: what the tap does
