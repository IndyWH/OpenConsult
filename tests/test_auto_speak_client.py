"""The client half of the auto speak path (Phase 7c slice 2), EXECUTED
under Node (the tests/test_silence_nudge_client.py convention): the
shipped `politeness` object and `onAutoSpeak` are lifted verbatim from
live.html and driven with stubbed collaborators.

What is pinned, and why:

- `auto_speak` plays through the tap's code path (`onSpeakReady`) — the
  same speak_started/speak_ended reporting, so the server's exclusion
  window opens and closes on an auto utterance with no new mechanism
  (PHASE_7C_SPEC.md §3). Asserted by execution (the stubbed onSpeakReady
  receives the very message) and structurally (onAutoSpeak owns no Audio
  and sends no speak_started of its own).
- The politeness abort (spec §5): immediately before playback the page
  re-checks its own RMS; speech resumed → decline, report speak_ended
  politeness_abort with the utterance id and the reading; quiet → play.
  The threshold is the barge-in ABSOLUTE floor the page already holds
  for "this is speech" — not the 1e-4 silence floor, which room noise
  exceeds — and a null reading (no running analyser) never aborts.

The server side of the same protocol is in tests/test_auto_speak.py.
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


def _politeness() -> str:
    return _extract("const politeness = {", "\n};")


def _on_auto_speak() -> str:
    return _extract("async function onAutoSpeak(msg) {", "\n}")


_HARNESS = """
%(politeness)s
%(on_auto_speak)s

// Stubbed collaborators: the socket, the meter, the barge-in config, and
// the tap path's player. `seq` is the page's last assigned frame number.
const sent = [];
const played = [];
const ws = {send: (m) => sent.push(JSON.parse(m))};
const seq = 41;
let reading = null;
function currentRms() { return reading; }
const bargeIn = {absFloor: 0.02};
async function onSpeakReady(msg) { played.push(msg); }
// The floor from the room (owner decision 2026-09-09, G2): the session's
// floor once speech_config.auto carried one; null = the absolute stand-in.
politeness.floor = null;

const out = {};
(async () => {
  const msg = {type: 'auto_speak', utterance_id: 'u-1', text: 'Mm-hm.',
               duration_ms: 400, url: '/api/speech/u-1.wav', ref_id: 'mm-hm'};

  reading = 0.003;                       // room noise, below the floor
  await onAutoSpeak(msg);
  out.quietPlayed = played.length === 1 && played[0] === msg;
  out.quietSent = sent.length;

  reading = 0.06;                        // speech has resumed
  await onAutoSpeak(msg);
  out.speechPlayed = played.length;      // still 1: not played
  out.speechSent = sent.slice();

  reading = 0.02;                        // exactly the floor: err toward waiting
  await onAutoSpeak(msg);
  out.atFloorPlayed = played.length;

  reading = null;                        // no running analyser
  await onAutoSpeak(msg);
  out.nullPlayed = played.length;        // plays: nothing to be polite to

  bargeIn.absFloor = 0;                  // no floor configured: cannot compare
  reading = 0.5;
  await onAutoSpeak(msg);
  out.noFloorPlayed = played.length;

  politeness.floor = 0.0255;             // the cafe's session floor (G2)
  reading = 0.024;                       // above the old 0.02, under the room's floor
  await onAutoSpeak(msg);
  out.roomFloorPlayed = played.length;   // plays
  reading = 0.0314;                      // 488's reading: above the cafe floor too
  await onAutoSpeak(msg);
  out.roomFloorAborted = sent.length;
  out.currentFloor = politeness.currentFloor();

  out.shouldAbort = [
    politeness.shouldAbort(0.001, 0.02), politeness.shouldAbort(0.02, 0.02),
    politeness.shouldAbort(0.1, 0.02), politeness.shouldAbort(null, 0.02),
    politeness.shouldAbort(0.1, undefined), politeness.shouldAbort(0.1, 0)];
  console.log(JSON.stringify(out));
})();
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_the_shipped_auto_speak_handler_executed_under_node():
    script = _HARNESS % {"politeness": _politeness(), "on_auto_speak": _on_auto_speak()}
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)

    # Quiet room: the message goes to the tap path's player, untouched, and
    # nothing is reported yet — speak_started is onSpeakReady's to send.
    assert out["quietPlayed"] is True
    assert out["quietSent"] == 0

    # Speech resumed: declined, one speak_ended politeness_abort for THIS
    # utterance with the next seq and the reading; not played.
    assert out["speechPlayed"] == 1
    assert out["speechSent"] == [{"type": "speak_ended", "utterance_id": "u-1",
                                  "seq": 42, "reason": "politeness_abort", "rms": 0.06}]

    # The tie-break is "err toward waiting": exactly at the floor aborts.
    assert out["atFloorPlayed"] == 1
    # A page that cannot listen does not invent an abort.
    assert out["nullPlayed"] == 2
    # No floor configured means no comparison, not a permanent abort.
    assert out["noFloorPlayed"] == 3
    # The floor from the room (owner decision 2026-09-09, G2): with the
    # session floor 0.0255 a 0.024 reading plays (it would have aborted at
    # the old absolute 0.02) and 488's 0.0314 still aborts.
    assert out["roomFloorPlayed"] == 4
    assert out["roomFloorAborted"] == 3 and out["currentFloor"] == 0.0255   # the third abort sent

    assert out["shouldAbort"] == [False, True, True, False, False, False]


def test_the_abort_reason_is_the_servers_vocabulary():
    """The client's literal must be one the server records (END_REASONS),
    or the abort would be silently recorded as 'complete'."""
    assert "reason: 'politeness_abort'" in _on_auto_speak()
    assert "politeness_abort" in system_utterances.END_REASONS


def test_auto_speak_is_dispatched_to_the_same_player_as_speak_ready():
    """Structural: the message type is routed to onAutoSpeak, which owns no
    Audio object, opens no window of its own, and hands the message to
    onSpeakReady — the tap's player — so Esc/Stop, the pill and the
    lifecycle reporting are the same code, not a copy of it."""
    assert "else if (msg.type === 'auto_speak') { onAutoSpeak(msg); }" in LIVE
    assert "else if (msg.type === 'speak_ready') { onSpeakReady(msg); }" in LIVE
    handler = _on_auto_speak()
    assert "return onSpeakReady(msg);" in handler
    assert "new Audio(" not in handler
    assert "speak_started" not in handler
    # The check comes BEFORE the hand-off: the last moment before playback.
    assert handler.index("politeness.shouldAbort(") < handler.index("onSpeakReady(msg)")
    assert handler.index("currentRms()") < handler.index("politeness.shouldAbort(")


def test_the_threshold_is_the_barge_in_absolute_floor_not_the_silence_floor():
    """Room noise (0.008–0.011 RMS measured) sits above the 1e-4 silence
    floor; comparing against that would abort every utterance in a real
    room. The page compares against the barge-in absolute floor it is
    already sent in speech_config, whether or not the detector is on."""
    handler = _on_auto_speak()
    # REPINNED 2026-09-09 (owner decision, pilot 488 G2): the number is the
    # session's floor from the room, with the absolute floor as the stand-in.
    assert "politeness.shouldAbort(rms, politeness.currentFloor())" in handler
    assert "return this.floor !== null ? this.floor : bargeIn.absFloor;" in _politeness()
    # No comparison against the silence floor anywhere in the check.
    for code in (handler, _politeness()):
        assert "> 1e-4" not in code and ">= 1e-4" not in code
        assert "nudge." not in code
    # And the server sends that floor regardless of the enabled flag.
    main = Path("app/main.py").read_text()
    assert '"abs_floor": speech.BARGE_IN_RMS_THRESHOLD' in main

