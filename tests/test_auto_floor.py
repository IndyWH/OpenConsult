"""The floor comes from the room (owner decision 2026-09-09, after
consultation 488, pilot diagnostic 487–490 finding G2).

One absolute floor — BARGE_IN_RMS_THRESHOLD, 0.02 — served both the
politeness abort and the client's quiet reporter, and a cafe sits above
it: the sound check's quiet-room peak was 0.0085, the owner's speech
averaged 0.0216, the enable's disclosure aborted at 0.0314, and 94 s of
GOLDEN never saw 3 s of quiet. Now each auto session's floor is derived
from the doctor's newest sound check — noise_floor_rms × AUTO_FLOOR_MARGIN,
clamped to [AUTO_FLOOR_MIN, AUTO_FLOOR_MAX] — sent to the client for the
session, recorded on auto.enabled and on every speech.politeness_abort
row. The quiet flat (0.0031) must yield exactly 0.02, so today's
behaviour there is unchanged.

The pure half is pinned without a database; the wiring half uses the
auto harness (a live session on a real socket, the gate forced up).
"""

from __future__ import annotations

import asyncio
import json
import os

import psycopg
import pytest

from app import audit, speech
from app import main as appmain
from auto_harness import (  # noqa: F401 - the fixture is used by name
    _audit, _collect_until, _make_user, _stop, _until, gate, live, needs_db)


# --- the pure function ---------------------------------------------------------

def test_the_quiet_flat_yields_exactly_the_minimum_so_nothing_changes_there():
    """The flat's sound check (489, row 3238): noise_floor_rms 0.0031.
    0.0031 × 3.0 = 0.0093, under the minimum → clamped to 0.02 exactly —
    the number every run to date has used."""
    floor = speech.auto_floor(0.0031)
    assert floor["floor"] == 0.02
    assert floor["source"] == "sound_check" and floor["clamped"] == "min"
    assert floor["noise_floor_rms"] == 0.0031 and floor["margin"] == 3.0
    assert speech.auto_floor(0.003)["floor"] == 0.02


def test_the_cafe_sound_check_yields_0_0255():
    """The cafe (487/488, row 3168): noise_floor_rms 0.0085 × 3.0 = 0.0255,
    inside the bounds — above the cafe's own speech mean (0.0216) is the
    owner's margin to revisit, and the record will say what it did."""
    floor = speech.auto_floor(0.0085)
    assert floor["floor"] == pytest.approx(0.0255)
    assert floor["clamped"] is None and floor["source"] == "sound_check"


def test_a_very_loud_room_clamps_at_the_maximum():
    floor = speech.auto_floor(0.05)                       # × 3 = 0.15
    assert floor["floor"] == 0.08 and floor["clamped"] == "max"
    assert speech.auto_floor(1.0)["floor"] == 0.08


def test_no_sound_check_falls_back_to_the_minimum_and_says_so():
    floor = speech.auto_floor(None)
    assert floor["floor"] == 0.02 and floor["source"] == "no_sound_check"
    assert floor["noise_floor_rms"] is None and floor["clamped"] is None


def test_the_three_settings_are_env_tunable_and_the_function_honours_overrides():
    """House pattern: the three numbers are UNCALIBRATED GUESSES in
    .env.example, read from env; the function takes them as arguments so
    a calibration script can try others without re-importing."""
    assert (speech.AUTO_FLOOR_MARGIN, speech.AUTO_FLOOR_MIN, speech.AUTO_FLOOR_MAX) == (3.0, 0.02, 0.08)
    env = open(".env.example").read()
    for key in ("AUTO_FLOOR_MARGIN=3.0", "AUTO_FLOOR_MIN=0.02", "AUTO_FLOOR_MAX=0.08"):
        assert key in env, key
    comment = env[env.index("AUTO_FLOOR_MARGIN=") - 700:env.index("AUTO_FLOOR_MARGIN=")]
    assert "UNCALIBRATED GUESS" in comment
    assert speech.auto_floor(0.0085, margin=2.0)["floor"] == 0.02             # 0.017 → the minimum
    assert speech.auto_floor(0.0085, margin=2.0, floor_min=0.01)["floor"] == pytest.approx(0.017)
    assert speech.auto_floor(0.05, floor_max=0.2)["floor"] == pytest.approx(0.15)


# --- the wiring ----------------------------------------------------------------

pytestmark_db = needs_db


def _sound_check(user: dict, noise_floor_rms: float, **extra) -> None:
    asyncio.run(audit.log(user["id"], "speech.sound_check", None, None,
                          {"result": "heard_good", "noise_floor_rms": noise_floor_rms,
                           "peak_rms": 0.22, "device_label": "Default - MacBook Air Speakers",
                           **extra}))


def _abort_rows(utterance_id: str) -> list[dict]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'speech.politeness_abort'"
            " AND detail->>'utterance_id' = %s ORDER BY id", (utterance_id,)).fetchall()
    return [r[0] for r in rows]


@needs_db
def test_the_cafe_session_gets_0_0255_sent_to_the_client_and_recorded_on_enabled_and_the_abort(gate):
    """The cafe's sound check, then a session: speech_config.auto carries
    the session's floor (0.0255, source sound_check); auto.enabled records
    floor, noise_floor_rms and margin (and the check's age); and the
    politeness-abort row carries the floor beside the reading, so the row
    can be read alone. The thresholds' politeness_floor_rms is the same
    number, not the module default."""
    doctor = _make_user()
    _sound_check(doctor, 0.0085)
    with live(gate, user=doctor) as s:
        first = _collect_until(s.ws, {"auto_toggled"})
        config = next(m for m in first if m["type"] == "speech_config")
        assert config["auto"]["floor"] == pytest.approx(0.0255)
        assert config["auto"]["floor_source"] == "sound_check"
        assert s.auto["floor"]["sound_check_age_s"] >= 0.0
        s.toggle(True)                                   # no disclosure: the disclosure is issued
        disclosure = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m.get("type") == "auto_speak")
        s.ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": disclosure["utterance_id"],
                                   "seq": s.seq + 1, "reason": "politeness_abort", "rms": 0.0314}))
        s.probe()
        _stop(s)
    enabled = _audit("auto.enabled", s.session_id)[0]
    assert enabled["floor"] == pytest.approx(0.0255)
    assert enabled["noise_floor_rms"] == 0.0085 and enabled["margin"] == 3.0
    assert enabled["floor_source"] == "sound_check" and enabled["floor_clamped"] is None
    assert enabled["sound_check_age_s"] >= 0.0
    assert enabled["thresholds"]["politeness_floor_rms"] == pytest.approx(0.0255)
    assert enabled["thresholds"]["floor_margin"] == 3.0
    aborts = _abort_rows(disclosure["utterance_id"])
    assert len(aborts) == 1
    assert aborts[0]["rms"] == 0.0314 and aborts[0]["floor"] == pytest.approx(0.0255)


@needs_db
def test_the_quiet_flat_session_is_unchanged_at_0_02(gate):
    doctor = _make_user()
    _sound_check(doctor, 0.0031)
    with live(gate, user=doctor) as s:
        config = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m["type"] == "speech_config")
        assert config["auto"]["floor"] == 0.02
        s.disclose()
        s.toggle(True)
        _collect_until(s.ws, {"auto_toggled"})
        _stop(s)
    enabled = _audit("auto.enabled", s.session_id)[0]
    assert enabled["floor"] == 0.02 and enabled["floor_clamped"] == "min"
    assert enabled["noise_floor_rms"] == 0.0031


@needs_db
def test_a_very_loud_room_clamps_at_the_max_for_the_session(gate):
    doctor = _make_user()
    _sound_check(doctor, 0.05)
    with live(gate, user=doctor) as s:
        config = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m["type"] == "speech_config")
        assert config["auto"]["floor"] == 0.08
        s.disclose()
        s.toggle(True)
        _collect_until(s.ws, {"auto_toggled"})
        _stop(s)
    enabled = _audit("auto.enabled", s.session_id)[0]
    assert enabled["floor"] == 0.08 and enabled["floor_clamped"] == "max"


@needs_db
def test_a_missing_sound_check_falls_back_to_the_minimum_and_audits_that_it_did(gate):
    """A fresh doctor account with no sound check row: the floor is
    AUTO_FLOOR_MIN, the client is told so, and auto.enabled says
    no_sound_check with a null noise floor — never a silent default."""
    with live(gate) as s:
        config = next(m for m in _collect_until(s.ws, {"auto_toggled"}) if m["type"] == "speech_config")
        assert config["auto"]["floor"] == 0.02 and config["auto"]["floor_source"] == "no_sound_check"
        s.disclose()
        s.toggle(True)
        _collect_until(s.ws, {"auto_toggled"})
        _stop(s)
    enabled = _audit("auto.enabled", s.session_id)[0]
    assert enabled["floor"] == 0.02 and enabled["floor_source"] == "no_sound_check"
    assert enabled["noise_floor_rms"] is None and "sound_check_age_s" not in enabled
    assert enabled["thresholds"]["politeness_floor_rms"] == 0.02


def test_the_client_uses_the_session_floor_for_both_the_reporter_and_the_abort():
    """One number on the page for "this is speech": the reporter's floor
    and the politeness abort's are both the session floor the server
    sent, with the barge-in absolute floor only as the stand-in when none
    arrived. The thresholds-in-force record keeps politeness_floor_rms as
    that number."""
    from pathlib import Path
    live_html = Path("app/static/live.html").read_text()
    config = live_html[live_html.index("else if (msg.type === 'speech_config') {"):]
    config = config[:config.index("\n  }")]
    assert "politeness.floor = roomFloor > 0 ? roomFloor : null;" in config
    assert "quietReporter.floor = politeness.currentFloor();" in config
    handler = live_html[live_html.index("async function onAutoSpeak(msg) {"):]
    handler = handler[:handler.index("\n}")]
    assert "politeness.shouldAbort(rms, politeness.currentFloor())" in handler
    assert "bargeIn.absFloor" not in handler, "the abort no longer reads the absolute floor directly"
    assert appmain._thresholds_in_force(0.0255)["politeness_floor_rms"] == 0.0255
