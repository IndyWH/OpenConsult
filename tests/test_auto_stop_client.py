"""The client half of the server-initiated stop (Phase 7c slice 5,
PHASE_7C_SPEC.md §7), EXECUTED under Node: the shipped `onAutoStop` is
lifted verbatim from live.html and driven with stubbed collaborators.

What is pinned: an `auto_stop` for the playing utterance goes through
EXACTLY the Esc/Stop path (stopSpeaking, with the server's reason — the
same cleanup, the same pill, the window closed by the same speak_ended);
a stop for an utterance not yet playing is remembered and the play
command is declined when it comes (no window ever opens); a stop with
nothing playing breaks nothing. The reason travels in the message.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app import system_utterances

NODE = shutil.which("node")
LIVE = Path("app/static/live.html").read_text()


def _extract(start_marker: str, end_marker: str) -> str:
    start = LIVE.index(start_marker)
    return LIVE[start:LIVE.index(end_marker, start) + len(end_marker)]


def _on_auto_stop() -> str:
    return _extract("function onAutoStop(msg) {", "\n}")


_HARNESS = """
%(on_auto_stop)s
let speaking = null;
let serverCancelled = null;
const stops = [];
function stopSpeaking(reason) { stops.push({id: speaking.utterance_id, reason}); speaking = null; }
const out = {};

// Nothing playing: remembered, nothing breaks.
onAutoStop({type: 'auto_stop', reason: 'urgency_pause', utterance_id: 'u-1'});
out.rememberedWhenIdle = serverCancelled;
out.stopsWhenIdle = stops.length;
serverCancelled = null;

// The playing utterance: cut through stopSpeaking with the server's reason.
speaking = {utterance_id: 'u-2', audio: {}, text: 'Mm-hm.'};
onAutoStop({type: 'auto_stop', reason: 'urgency_pause', utterance_id: 'u-2'});
out.cut = stops.slice();
out.speakingAfterCut = speaking;
out.rememberedAfterCut = serverCancelled;

// A stop naming a DIFFERENT utterance than the one playing does not cut
// the wrong one; it is remembered for when that one arrives.
speaking = {utterance_id: 'u-3', audio: {}, text: 'Go on.'};
onAutoStop({type: 'auto_stop', reason: 'urgency_pause', utterance_id: 'u-9'});
out.wrongIdStops = stops.length;
out.wrongIdRemembered = serverCancelled;

// No id at all cuts whatever is playing; no reason falls back to cancelled.
serverCancelled = null;
onAutoStop({type: 'auto_stop'});
out.noIdCut = stops[stops.length - 1];
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_shipped_auto_stop_handler_executed_under_node():
    script = _HARNESS % {"on_auto_stop": _on_auto_stop()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["rememberedWhenIdle"] == "u-1" and out["stopsWhenIdle"] == 0
    assert out["cut"] == [{"id": "u-2", "reason": "urgency_pause"}]
    assert out["speakingAfterCut"] is None
    assert out["rememberedAfterCut"] is None
    assert out["wrongIdStops"] == 1 and out["wrongIdRemembered"] == "u-9"
    assert out["noIdCut"] == {"id": "u-3", "reason": "cancelled"}


def test_the_stop_is_the_esc_stop_path_and_the_reason_is_the_servers_vocabulary():
    """Structural: dispatched to onAutoStop, which owns no Audio and sends
    no speak_ended of its own — stopSpeaking does, exactly as Esc/Stop —
    and the reason this slice sends is one the server records."""
    assert "else if (msg.type === 'auto_stop') { onAutoStop(msg); }" in LIVE
    handler = _on_auto_stop()
    assert "stopSpeaking(reason)" in handler
    assert "speak_ended" not in handler and "new Audio(" not in handler
    assert "urgency_pause" in system_utterances.END_REASONS


def test_a_stop_that_arrives_before_playback_declines_the_play_command():
    """The play command may still be in hand when the stop lands: both
    checks are in onSpeakReady — before play() and again after it resolves
    — so no window opens for a cut utterance."""
    ready = _extract("async function onSpeakReady(msg) {", "\n}")
    assert ready.count("if (serverCancelled === msg.utterance_id) {") == 2
    before, after = ready.split("await audio.play();")
    assert "serverCancelled === msg.utterance_id" in before
    assert "serverCancelled === msg.utterance_id" in after
    assert after.index("serverCancelled === msg.utterance_id") < after.index("speak_started")
    assert "audio.pause()" in after.split("speak_started")[0]
    assert "let serverCancelled = null;" in LIVE
