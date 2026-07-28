"""Session 3 sticky row — revised variant A, owner-approved 2026-07-28.

Urgent actions LEFT, face RIGHT, page scrolling beneath, so an unresolved
red-flag alarm is on screen at every scroll position. These tests assert
POSITION and CONTAINER MEMBERSHIP, not mere existence — consultation
447's lesson: the Stop control existed the whole time; what failed was
where it was. The presence logic is EXECUTED under Node (all four
combinations), the same convention as tests/test_live_transcript_order.py.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path("app/static/live.html").read_text()
NODE = shutil.which("node")


# --- geometry and placement, from the source ------------------------------

def _sticky_css() -> str:
    start = SOURCE.index(".stickyrow {")
    return SOURCE[start:SOURCE.index("}", start)]


def test_the_row_is_sticky_not_in_flow():
    css = _sticky_css()
    assert "position: sticky" in css, (
        "the row must stay on screen while the page scrolls — an urgent "
        "alarm in normal flow scrolls away exactly when it matters (447)")
    assert re.search(r"top:\s*\d+px", css)


def test_two_column_geometry_urgent_left_face_right():
    css = _sticky_css()
    assert "grid-template-columns: 1fr 1fr" in css
    # Markup order IS the column order: left half holds the urgent box,
    # right half the face card. Positions never swap.
    row = SOURCE.index('id="stickyRow"')
    left = SOURCE.index('id="stickyLeft"')
    urgent = SOURCE.index('id="urgentBox"')
    right = SOURCE.index('id="stickyRight"')
    facep = SOURCE.index('id="facePane"')
    stack = SOURCE.index('<div class="stack">')
    assert row < left < urgent < right < facep < stack, (
        "urgent must be the LEFT half and face the RIGHT, both inside the "
        "sticky row, which sits before (outside) the scrolling stack")


def test_urgent_panel_is_not_in_the_scrolling_stack():
    stack_html = SOURCE[SOURCE.index('<div class="stack">'):]
    assert 'id="urgentBox"' not in stack_html, (
        "the alarm's home is the sticky row — an urgent panel back inside "
        "the stack scrolls out of sight, which is the defect this layout "
        "exists to fix")


def test_clicks_pass_through_empty_halves():
    css = _sticky_css()
    assert "pointer-events: none" in css
    cards = SOURCE[SOURCE.index(".stickyrow .urgent"):]
    cards = cards[:cards.index("}")]
    assert "pointer-events: auto" in cards


def test_layering_stays_below_the_header_and_away_from_the_speaking_bar():
    css = _sticky_css()
    z = int(re.search(r"z-index:\s*(\d+)", css).group(1))
    assert z < 5, "must sit below the app header (theme.css z 5)"
    assert z < 60, "and far below the speaking bar (hard rule 3's control)"


def test_sizing_is_commented_as_interim():
    region = SOURCE[SOURCE.index("STICKY TOP ROW"):SOURCE.index(".stickyrow {")]
    assert "INTERIM" in region.upper()


# --- presence logic, executed (all four combinations) ----------------------

def _extract_update_sticky_row() -> str:
    start = SOURCE.index("function updateStickyRow(")
    return SOURCE[start:SOURCE.index("\n}", start) + 2]


_HARNESS = """
function makeNode(name) {
  return {
    name, parentNode: null, children: [],
    appendChild(c) { if (c.parentNode) c.parentNode.removeChild(c);
                     c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { const i = this.children.indexOf(c);
                     if (i >= 0) this.children.splice(i, 1);
                     c.parentNode = null; return c; },
    insertBefore(node, before) { if (node.parentNode) node.parentNode.removeChild(node);
                                 node.parentNode = this;
                                 const at = this.children.indexOf(before);
                                 this.children.splice(at < 0 ? this.children.length : at, 0, node);
                                 return node; },
  };
}
const body = makeNode('body');
const stickyRow = makeNode('stickyRow');
const stickyLeft = makeNode('stickyLeft');
const stickyRight = makeNode('stickyRight');
const urgentBoxEl = makeNode('urgentBox');
const facePane = makeNode('facePane');
const stackEl = makeNode('stack');
body.appendChild(stackEl);
stickyRow.appendChild(stickyLeft);
stickyRow.appendChild(stickyRight);

%(fn)s

const out = [];
for (const [alarm, face] of [[false,false],[true,false],[false,true],[true,true],[false,false]]) {
  updateStickyRow(alarm, face);
  out.push({
    alarm, face,
    rowInDom: stickyRow.parentNode === body,
    rowBeforeStack: body.children.indexOf(stickyRow) !== -1
      && body.children.indexOf(stickyRow) < body.children.indexOf(stackEl),
    urgentParent: urgentBoxEl.parentNode ? urgentBoxEl.parentNode.name : null,
    faceParent: facePane.parentNode ? facePane.parentNode.name : null,
  });
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_presence_logic_all_four_combinations_membership_not_visibility():
    script = _HARNESS % {"fn": _extract_update_sticky_row()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    states = json.loads(result.stdout)

    neither, alarm_only, face_only, both, back_to_neither = states

    # neither → the whole row is absent from the DOM
    assert neither["rowInDom"] is False
    assert neither["urgentParent"] is None and neither["faceParent"] is None

    # alarm only → urgent in the LEFT half, face half empty, row present
    assert alarm_only["rowInDom"] and alarm_only["rowBeforeStack"]
    assert alarm_only["urgentParent"] == "stickyLeft"
    assert alarm_only["faceParent"] is None

    # face only → face in the RIGHT half, alarm's home left empty —
    # positions never swap
    assert face_only["rowInDom"] and face_only["rowBeforeStack"]
    assert face_only["faceParent"] == "stickyRight"
    assert face_only["urgentParent"] is None

    # both → both cards, each in its own half
    assert both["urgentParent"] == "stickyLeft"
    assert both["faceParent"] == "stickyRight"

    # and the row leaves the DOM again when both clear
    assert back_to_neither["rowInDom"] is False


def test_render_cds_routes_the_alarm_through_the_membership_model():
    render = SOURCE[SOURCE.index("function renderCDS("):]
    render = render[:render.index("\n}")]
    assert "updateStickyRow(alarmLive, faceOn)" in render
    assert "style.display" not in render.split("urgentListEl")[0], (
        "the urgent panel's state is membership, not a display toggle")


def test_the_face_off_toggle_lives_on_the_card_and_off_is_final():
    card = SOURCE[SOURCE.index('id="stickyRight"'):SOURCE.index('<div class="stack">')]
    assert 'id="faceToggle"' in card, "the toggle lives on the face card"
    handler = SOURCE[SOURCE.index("faceToggle.addEventListener"):]
    handler = handler[:handler.index("});") + 3]
    assert "on: false" in handler, (
        "the card's toggle only turns the face OFF; the on-path is the "
        "disclosure auto-on, and a manual off is final for the session")
