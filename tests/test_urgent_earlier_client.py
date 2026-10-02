"""The earlier alarm, page half (owner decision 2026-10-02, after Task 3f),
EXECUTED under Node: the shipped `renderCDS`, `appendEarlier`,
`renderEarlier`, `renderPause` and `formatTime` are lifted verbatim from
live.html and driven with stubbed DOM collaborators, in the style of
tests/test_auto_pause_client.py.

Pinned by execution: the page renders exactly what the server sent —
every action with its reason, under "Raised earlier, no longer flagged"
with the time it was last flagged, replaced and never appended to; the
panel stays in the sticky row while an earlier alarm is shown, including
after an acknowledgement clears the pause; and empty is still the good
state — with no live alarm, no earlier alarm and no pause the panel
leaves the page. Pinned by reading: the messages feed it the server's
value; it touches neither the pause, the standing strip nor the
acknowledgements; and its styling is quieter than a live alarm.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
LIVE = Path("app/static/live.html").read_text()


def _extract(start_marker: str, end_marker: str = "\n}") -> str:
    start = LIVE.index(start_marker)
    return LIVE[start:LIVE.index(end_marker, start) + len(end_marker)]


_HARNESS = """
%(fns)s
// Stubbed collaborators: a minimal node with children, classes and text.
function node(tag, cls, text) {
  return {tag, className: cls || '', textContent: text || '', children: [],
          classList: {contains(c) { return (this._n.className || '').split(' ').includes(c); }},
          appendChild(c) { this.children.push(c); return c; },
          removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; },
          set innerHTML(v) { this.children.length = 0; }, get innerHTML() { return ''; }};
}
function el(tag, cls, text) { const n = node(tag, cls, text); n.classList._n = n; return n; }
const urgentListEl = el('ul');
const pauseList = el('ul');
const classes = new Set();
const pauseBanner = {classList: {toggle(name, on) { on ? classes.add(name) : classes.delete(name); }}};
let alarmLive = false, faceOn = false, pausedLive = false, pausePending = [], agendaVersion = null;
let urgentEarlier = null;
// The cds handler's order: the server's value first, then the render.
function onCds(a, earlier) { urgentEarlier = earlier || null; renderCDS(a); }
const rows = [];
function updateStickyRow(alarm, face) { rows.push([alarm, face]); }
function refreshPauseControls() {}
function fillList() {}
function markAskedQuestions() {}
function refreshSpeechControls() {}
const document = {getElementById() { return null; },
                  createTextNode(t) { return {textContent: t}; }};
function shown() {
  return urgentListEl.children.map(c => c.className === 'earlier'
    ? {earlier: c.children[0].textContent,
       items: c.children[1].children.map(li => [li.textContent, li.children[0].textContent])}
    : {live: c.textContent});
}
const out = {};
const ECG = {action: 'Bedside ECG now', reason: 'exclude ACS'};
const CALL = {action: 'Call 999', reason: 'possible STEMI'};

// Pass 1: a live alarm. Pass 2: quiet, the server sends the earlier alarm.
onCds({urgent_actions: [ECG]}, null);
out.live = {shown: shown(), row: rows[rows.length - 1]};
onCds({urgent_actions: []}, {actions: [ECG, CALL], last_flagged_s: 135.4});
out.earlier = {shown: shown(), row: rows[rows.length - 1]};
// Pass 3: quiet again, same earlier alarm — replaced, never appended.
onCds({urgent_actions: []}, {actions: [ECG, CALL], last_flagged_s: 135.4});
out.again = {count: urgentListEl.children.length};
// Pass 4: the alarm is back; the server sends no earlier alarm.
onCds({urgent_actions: [CALL]}, null);
out.back = {shown: shown(), row: rows[rows.length - 1]};
// Pass 5: arranged — nothing live, nothing earlier: the panel leaves.
onCds({urgent_actions: []}, null);
out.arranged = {shown: shown(), row: rows[rows.length - 1]};
// A message without the field (an older server) renders nothing extra.
onCds({urgent_actions: []});
out.absent = {count: urgentListEl.children.length, row: rows[rows.length - 1]};

// Paused, then a quiet pass shows the earlier alarm; the acknowledgement
// clears the pause and the panel STAYS for the earlier alarm.
renderPause(true, ['Bedside ECG now']);
onCds({urgent_actions: []}, {actions: [ECG], last_flagged_s: 61});
out.pausedEarlier = {pending: pausePending.slice(), paused: pausedLive, row: rows[rows.length - 1]};
renderPause(false, []);
out.acked = {shown: shown(), on: classes.has('on'), row: rows[rows.length - 1]};

// A reconnect: the server's current state replaces the page's.
renderEarlier({actions: [CALL], last_flagged_s: 3605});
out.reconnect = {shown: shown(), row: rows[rows.length - 1]};
renderEarlier(null);
out.reconnectNone = {count: urgentListEl.children.length, row: rows[rows.length - 1]};
// A reconnect while a live alarm is listed keeps the live alarm.
onCds({urgent_actions: [ECG]}, null);
renderEarlier(null);
out.reconnectLive = {shown: shown(), row: rows[rows.length - 1]};
console.log(JSON.stringify(out));
"""


def _run() -> dict:
    fns = "\n".join([
        _extract("function renderCDS(a) {"),
        _extract("function appendEarlier(earlier) {"),
        _extract("function renderEarlier(earlier) {"),
        _extract("function renderPause(paused, pending) {"),
        _extract("function formatTime(s) {"),
    ])
    result = subprocess.run([NODE, "-e", _HARNESS % {"fns": fns}], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


LABEL = "Raised earlier, no longer flagged — last flagged at "


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_page_renders_the_servers_earlier_alarm_and_the_panel_follows_it():
    out = _run()
    assert out["live"] == {"shown": [{"live": "Bedside ECG now"}], "row": [True, False]}
    assert out["earlier"] == {
        "shown": [{"earlier": LABEL + "2:15",
                   "items": [["Bedside ECG now", "exclude ACS"], ["Call 999", "possible STEMI"]]}],
        "row": [True, False]}, "every action, each with its reason, the panel kept in the row"
    assert out["again"] == {"count": 1}, "replaced on every pass, never appended"
    assert out["back"] == {"shown": [{"live": "Call 999"}], "row": [True, False]}, (
        "a live alarm again: the earlier one goes")
    assert out["arranged"] == {"shown": [], "row": [False, False]}, "empty is still the good state"
    assert out["absent"] == {"count": 0, "row": [False, False]}


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_an_acknowledgement_leaves_the_earlier_alarm_and_its_panel_in_place():
    out = _run()
    assert out["pausedEarlier"] == {"pending": ["Bedside ECG now"], "paused": True,
                                    "row": [True, False]}
    assert out["acked"]["on"] is False
    assert out["acked"]["shown"] == [{"earlier": LABEL + "1:01",
                                      "items": [["Bedside ECG now", "exclude ACS"]]}]
    assert out["acked"]["row"] == [True, False], (
        "the pause clears; the panel stays because the earlier alarm is in it")


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_a_reconnect_renders_the_servers_current_state():
    out = _run()
    assert out["reconnect"] == {"shown": [{"earlier": LABEL + "60:05",
                                           "items": [["Call 999", "possible STEMI"]]}],
                                "row": [True, False]}
    assert out["reconnectNone"] == {"count": 0, "row": [False, False]}
    assert out["reconnectLive"] == {"shown": [{"live": "Bedside ECG now"}], "row": [True, False]}


def test_the_messages_feed_it_the_servers_value_and_nothing_else():
    assert ("else if (msg.type === 'cds') { urgentEarlier = msg.urgent_earlier || null; "
            "renderCDS(msg.assessment); }") in LIVE
    assert ("else if (msg.type === 'urgent_earlier') { urgentEarlier = msg.earlier || null; "
            "renderEarlier(urgentEarlier); }") in LIVE
    assert len(re.findall(r"(?<!let )urgentEarlier = ", LIVE)) == 2, (
        "written from the two server pushes only")
    assert LIVE.count("renderEarlier(") == 2, "defined once, called from the reconnect push only"
    assert LIVE.count("appendEarlier(") == 3, "defined once, called from renderCDS and renderEarlier"
    render_cds = _extract("function renderCDS(a) {")
    assert render_cds.index("appendEarlier(urgentEarlier);") < render_cds.index("updateStickyRow(alarmLive, faceOn)")


def test_the_earlier_alarm_never_touches_the_pause_the_strip_or_the_acknowledgements():
    """Point 6 of the decision, on the page: rendering it sends nothing,
    and reads or writes neither the pause banner, the pending list nor the
    standing strip."""
    body = _extract("function appendEarlier(earlier) {") + _extract("function renderEarlier(earlier) {")
    for name in ("ws.send", "pausePending", "pauseList", "pauseBanner", "renderPause",
                 "standingStrip", "renderStanding", "auto_ack"):
        assert name not in body, name


def test_it_is_quieter_than_a_live_alarm():
    """No red, soft ink, smaller type than a live alarm's 1.02rem item."""
    rules = {m.group(1).strip(): m.group(2)
             for m in re.finditer(r"(\.urgent li\.earlier[^{]*)\{([^}]*)\}", LIVE)}
    assert ".urgent li.earlier" in rules and ".urgent li.earlier li" in rules
    for selector, body in rules.items():
        assert "--red" not in body and "#C2402F" not in body.upper(), selector
    for selector in (".urgent li.earlier", ".urgent li.earlier li"):
        size = float(re.search(r"font-size:\s*([\d.]+)rem", rules[selector]).group(1))
        assert size < 1.02, selector
        assert "var(--ink-soft)" in rules[selector], selector
        assert "font-weight: 400" in rules[selector], selector
    assert "'Raised earlier, no longer flagged — last flagged at '" in LIVE
