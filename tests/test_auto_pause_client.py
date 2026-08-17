"""The client half of the urgency pause (Phase 7c slice 5, PHASE_7C_SPEC.md
§7, §10), EXECUTED under Node: the shipped `renderPause` is lifted verbatim
from live.html and driven with stubbed DOM collaborators.

The hard requirement of the slice, pinned by execution: the banner lists
EVERY pending action text the server sent — the whole list, replaced on
every message, never appended to and never only the latest — so an
acknowledgement only ever covers what the doctor actually saw. Also
pinned: the banner shows only while paused, the panel's membership
follows the pause (it outlives a CDS pass that clears the alarm list),
and the message handling feeds it the server's `pending` list on a pause,
a re-fire, a reconnect echo, and clears it on an acknowledgement.
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
%(render)s
// Stubbed collaborators.
function makeList() { return {children: [], innerHTML: '', appendChild(c) { this.children.push(c); },
                              set innerHTML(v) { this.children.length = 0; }, get innerHTML() { return ''; }}; }
const pauseList = makeList();
const urgentListEl = {children: []};
const classes = new Set();
const pauseBanner = {classList: {toggle(name, on) { on ? classes.add(name) : classes.delete(name); }}};
function el(tag, cls, text) { return {tag, cls, text}; }
let alarmLive = false, faceOn = false, pausedLive = false, pausePending = [];
const rows = [];
function updateStickyRow(alarm, face) { rows.push([alarm, face]); }
let refreshed = 0;
function refreshPauseControls() { refreshed += 1; }
const out = {};

renderPause(true, ['Bedside ECG now']);
out.first = {texts: pauseList.children.map(c => c.text), on: classes.has('on'),
             paused: pausedLive, row: rows[rows.length - 1]};
// A widening re-fire: the WHOLE list, replaced.
renderPause(true, ['Bedside ECG now', 'Call 999']);
out.widened = {texts: pauseList.children.map(c => c.text), on: classes.has('on')};
// The alarm list cleared by a later pass while still paused: the panel stays.
urgentListEl.children.length = 0;
renderPause(true, ['Bedside ECG now', 'Call 999']);
out.stillPaused = {row: rows[rows.length - 1]};
// Acknowledged: gone; the panel follows the (empty) alarm list.
renderPause(false, []);
out.cleared = {texts: pauseList.children.map(c => c.text), on: classes.has('on'),
               paused: pausedLive, row: rows[rows.length - 1]};
// Alarm still listed after the ack: the panel stays for the alarm.
urgentListEl.children.push({});
renderPause(false, []);
out.alarmOnly = {row: rows[rows.length - 1]};
out.refreshed = refreshed;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_banner_lists_every_pending_text_and_follows_the_pause():
    render = _extract("function renderPause(paused, pending) {", "\n}")
    result = subprocess.run([NODE, "-e", _HARNESS % {"render": render}],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["first"] == {"texts": ["Bedside ECG now"], "on": True, "paused": True,
                            "row": [True, False]}
    assert out["widened"] == {"texts": ["Bedside ECG now", "Call 999"], "on": True}, (
        "the whole pending list, replaced — never only the latest")
    assert out["stillPaused"]["row"] == [True, False], "the panel outlives a cleared alarm list"
    assert out["cleared"] == {"texts": [], "on": False, "paused": False, "row": [False, False]}
    assert out["alarmOnly"]["row"] == [True, False]
    assert out["refreshed"] == 5


def test_the_messages_feed_the_banner_the_servers_pending_list():
    """auto_pause (first fire and re-fire), the auto_toggled echo while
    paused (reconnect), auto_acknowledged — each hands renderPause the
    server's list; nothing on the page invents or accumulates texts."""
    pause = _extract("else if (msg.type === 'auto_pause') {", "\n  }")
    assert "renderPause(true, msg.pending || []);" in pause
    toggled = _extract("else if (msg.type === 'auto_toggled') {", "\n  }")
    assert "if (msg.phase === 'paused_urgent') renderPause(true, msg.pending || pausePending);" in toggled
    assert "else if (pausedLive) renderPause(false, []);" in toggled
    acked = _extract("else if (msg.type === 'auto_acknowledged') {", "\n  }")
    assert "renderPause(false, []);" in acked
    render = _extract("function renderPause(paused, pending) {", "\n}")
    assert "pauseList.innerHTML = '';" in render         # replaced, never appended
    assert "pausePending.push" not in LIVE
    # The alarm panel's membership considers the pause (renderCDS).
    render_cds = _extract("function renderCDS(a) {", "\n}")
    assert "alarmLive = urgent.length > 0 || pausedLive;" in render_cds
    # The banner is captured through the (detached) urgent box, not by id.
    assert "urgentBoxEl.querySelector('#pauseBanner')" in LIVE
