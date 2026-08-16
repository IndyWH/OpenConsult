"""The client's quiet-window detector, EXECUTED under Node (the
tests/test_live_transcript_order.py convention): the shipped `nudge`
object is lifted verbatim from live.html and driven with a fake clock.
The server enforces the cage regardless (tests/test_speech_autonomy.py);
this covers the half that decides whether to ASK — activity cancels, the
disabled flag means no request, one-shot on the client side too.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")


def _extract_nudge() -> str:
    source = Path("app/static/live.html").read_text()
    start = source.index("const nudge = {")
    return source[start:source.index("\n};", start) + 3]


_HARNESS = """
%(nudge)s
const out = {};

// Armed after the invitation, quiet runs the full window → due fires once.
nudge.windowS = 5;
nudge.arm(1000);
out.dueEarly = nudge.due(3000);                 // 2 s of quiet: not yet
out.dueAfterWindow = nudge.due(6500);           // 5.5 s of quiet: due
out.quiet = nudge.fire(6500);
out.usedAfterFire = nudge.used;
out.dueAfterFire = nudge.due(99999);            // one-shot client-side too
nudge.arm(100000);                              // re-arm attempt after use
out.armedAfterUse = nudge.armed;

// Activity resets the window.
const n2 = Object.assign(Object.create(Object.getPrototypeOf(nudge)),
                         {enabled: true, windowS: 5, armed: false,
                          used: false, quietSince: 0,
                          arm: nudge.arm, activity: nudge.activity,
                          due: nudge.due, fire: nudge.fire});
n2.arm(0);
n2.activity(4000);                              // someone spoke at 4 s
out.dueAtOldDeadline = n2.due(5000);            // old deadline: not due
out.dueAfterFreshQuiet = n2.due(9500);          // 5.5 s after the activity

// Disabled means it never arms, so it is never due and never requests.
const n3 = {enabled: false, windowS: 5, armed: false, used: false,
            quietSince: 0, arm: nudge.arm, activity: nudge.activity,
            due: nudge.due, fire: nudge.fire};
n3.arm(0);
out.disabledArmed = n3.armed;
out.disabledDue = n3.due(999999);

console.log(JSON.stringify(out));
"""


def test_quiet_window_activity_and_flags_executed():
    script = _HARNESS % {"nudge": _extract_nudge()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)

    assert out["dueEarly"] is False
    assert out["dueAfterWindow"] is True
    assert out["quiet"] == pytest.approx(5.5)   # the measured quiet, audited
    assert out["usedAfterFire"] is True
    assert out["dueAfterFire"] is False, "at most once per consultation"
    assert out["armedAfterUse"] is False, "a used nudge cannot re-arm"

    assert out["dueAtOldDeadline"] is False, "activity must reset the window"
    assert out["dueAfterFreshQuiet"] is True

    assert out["disabledArmed"] is False, "disabled flag means no request"
    assert out["disabledDue"] is False


def test_every_activity_source_is_wired():
    """The bias is toward NOT firing: mic energy, transcript movement
    (partial and final), and playback ends must all reset the window."""
    source = Path("app/static/live.html").read_text()
    assert "if (rms > 1e-4) nudge.activity(now);" in source
    assert source.count("nudge.activity(performance.now())") >= 3
    # And the request goes through the NORMAL speak path with its via.
    assert "requestSpeak({kind: 'phrase', id: 'silence_nudge'}" in source
    assert "via: 'silence_nudge'" in source


def _prose(path: str) -> str:
    """Comment text with its wrapping and comment markers flattened, so a
    sentence can be asserted whole across line breaks."""
    text = Path(path).read_text().replace("//", " ").replace("#", " ")
    return " ".join(text.split())


def test_the_nudge_cage_still_holds_outside_auto_mode():
    """Phase 7c slice 3 retired the three guard comments ("do not
    generalise the nudge into an encourager loop"): they existed to block
    exactly that change until 7c's behaviour-policy machinery carried it,
    and slice 3 is that machinery — the client's quiet reporter and the
    controller's encourager loop, dark behind AUTO_MODE_ENABLED. What
    remains pinned is the property that survives the retirement, on both
    sides: with auto mode OFF the nudge is caged and behaves exactly as
    before. The reasoning must still be written down in all three places
    (a rule stripped of its why reads as a style opinion), and the client
    must not request the nudge while the server has confirmed auto mode on.
    """
    for path in ("app/static/live.html", "app/main.py", "app/speech.py"):
        prose = _prose(path)
        assert "ONLY AUTONOMOUS UTTERANCE IN 7a/7b" in prose, path
        assert "the cage holds exactly as before" in prose, path
        assert "AUTO_MODE_ENABLED" in prose, path
        assert "retired in Phase 7c slice 3" in prose, (
            f"{path}: the retirement of the guard must be written down, not silent")
    source = Path("app/static/live.html").read_text()
    # The nudge's own request loop yields to auto mode; the object itself
    # is unchanged (the Node test above executes it verbatim).
    assert "if (quietReporter.enabled) return;" in source
    nudge_loop = source[source.index("if (!nudge.due(now)) return;") - 400:
                        source.index("if (!nudge.due(now)) return;")]
    assert "quietReporter.enabled" in nudge_loop
    # Server side: the cage is the same three refusals, in one function
    # shared by the tap path and the auto path.
    main = Path("app/main.py").read_text()
    cage = main[main.index("def _nudge_refusal("):main.index("def _speak_message(")]
    for reason in ("the silence nudge is disabled",
                   "the silence nudge only follows a completed invitation",
                   "the silence nudge has already been used this consultation"):
        assert reason in cage
