"""Task 13 item 7, page half: Start waits for the Nemotron engine.

EXECUTED under Node: the shipped `applySpeechStatus` is lifted verbatim
from live.html and driven with stubbed DOM collaborators.

Pinned by execution: while the engine is not ready, Start is disabled and
the server's plain reason is shown beside it; when ready, Start is
enabled and the notice hidden; a running consultation's button is never
touched; an unlinked patient keeps Start disabled whatever the engine
says. Pinned by reading: start() refuses while blocked; the patient
banner respects the block; both server messages are handled.
"""

from __future__ import annotations

import json
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
let SPEECH_BLOCK = null;
let recording = %(recording)s;
const PATIENT = {id: %(patient)s};
const btn = {disabled: true, title: 'Recording needs a linked patient'};
const speechEngineEl = {textContent: '', hidden: true};
%(fn)s
applySpeechStatus(%(status)s);
console.log(JSON.stringify({block: SPEECH_BLOCK, disabled: btn.disabled, title: btn.title,
                            shown: !speechEngineEl.hidden, text: speechEngineEl.textContent}));
"""


def _run(status: dict, *, recording=False, patient=7) -> dict:
    if NODE is None:
        pytest.skip("node not installed")
    js = _HARNESS % {"fn": _extract("function applySpeechStatus(st) {"),
                     "status": json.dumps(status), "recording": json.dumps(recording),
                     "patient": json.dumps(patient)}
    out = subprocess.run([NODE, "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_not_ready_disables_start_and_shows_the_reason_beside_it():
    detail = "The Nemotron speech engine is still loading. Recording can start when it is ready."
    r = _run({"ready": False, "detail": detail})
    assert r == {"block": detail, "disabled": True, "title": detail, "shown": True, "text": detail}


def test_ready_enables_start_and_hides_the_notice():
    r = _run({"ready": True, "detail": None})
    assert r == {"block": None, "disabled": False, "title": "", "shown": False, "text": ""}


def test_a_running_consultation_is_never_touched():
    r = _run({"ready": False, "detail": "engine failed"}, recording=True)
    assert r["block"] == "engine failed"
    assert r["disabled"] is True and r["title"] == "Recording needs a linked patient"  # as it was
    assert r["shown"] is False


def test_no_linked_patient_keeps_start_disabled_even_when_ready():
    r = _run({"ready": True, "detail": None}, patient=None)
    assert r["disabled"] is True


def test_start_refuses_while_blocked_and_the_banner_respects_the_block():
    start = _extract("async function start() {")
    assert "if (SPEECH_BLOCK) return;" in start.split("\n", 4)[2]   # before anything acts
    banner = _extract("async function loadPatientBanner() {")
    assert "btn.disabled = !!SPEECH_BLOCK;" in banner


def test_both_server_messages_are_handled_where_the_doctor_is_looking():
    assert "msg.type === 'speech_unavailable'" in LIVE
    assert "msg.type === 'speech_failed'" in LIVE
    unavailable = LIVE[LIVE.index("msg.type === 'speech_unavailable'"):]
    assert "standDown(msg.detail);" in unavailable[:400]
    assert "applySpeechStatus({ready: false, detail: msg.detail});" in unavailable[:500]
    # The notice sits in Start's status block, under the auto-phase line.
    status = LIVE[LIVE.index('id="status"'):]
    assert 'id="speechEngine"' in status[:1200]
