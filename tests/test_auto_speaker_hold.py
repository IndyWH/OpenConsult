"""The speaker-count hold for auto runs (owner decision 2026-09-01, solo
pilot defect D6).

In two of the three pilot runs the doctor — alone at the screen after
supervising an auto run — answered "Who spoke?" 41 s and 127 s after
Stop; the 25 s bound (SPEAKER_DECLARATION_WAIT_S) had passed and the
answer was stored, not applied. Pinned here: a consultation in which
auto mode was enabled (an auto.enabled row exists for the session)
holds finalisation for AUTO_SPEAKER_DECLARATION_WAIT_S instead; other
consultations keep the 25 s; the answer releases it at once; on expiry
the existing ignored-declaration path applies unchanged; and the wait
is visible — the `done` message, the consultation API and both pages
say the pipeline is waiting for the speaker count.

Timing is pinned with the two bounds scaled down (the harness has no
worker consuming the finalisation queue, so the waiter stays registered
until the test drives it); the shipped defaults are pinned as values.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

from app import consultations, finalize
from auto_harness import (_audit, _client_for, _collect_until, _make_user, _stop, _until,  # noqa: F401
                          gate, live, needs_db)

pytestmark = needs_db


def _auto_run_and_stop(s):
    s.to_golden()
    s.ws.send_text("stop")
    return _until(s.ws, {"done"})


def test_the_defaults_are_180_s_for_an_auto_run_and_25_s_otherwise():
    if "AUTO_SPEAKER_DECLARATION_WAIT_S" not in os.environ:
        assert finalize.AUTO_SPEAKER_DECLARATION_WAIT_S == 180.0
    if "SPEAKER_DECLARATION_WAIT_S" not in os.environ:
        assert finalize.SPEAKER_DECLARATION_WAIT_S == 25.0
    env = Path(".env.example").read_text()
    assert "\nSPEAKER_DECLARATION_WAIT_S=25\n" in env, "the 25 s bound was absent from .env.example"
    assert "\nAUTO_SPEAKER_DECLARATION_WAIT_S=180\n" in env


def test_an_auto_run_is_still_waiting_past_the_plain_bound_and_released_at_once_on_answer(gate, monkeypatch):
    """The 30 s check, scaled: with the plain bound at 0.25 s and the auto
    bound at 3 s, an auto-run consultation is still waiting at 0.6 s (past
    the plain bound), and the answer releases it immediately."""
    monkeypatch.setattr(finalize, "SPEAKER_DECLARATION_WAIT_S", 0.25)
    monkeypatch.setattr(finalize, "AUTO_SPEAKER_DECLARATION_WAIT_S", 3.0)
    import app.main as appmain
    monkeypatch.setattr(appmain, "AUTO_SPEAKER_DECLARATION_WAIT_S", 3.0)
    with live(gate) as s:
        done = _auto_run_and_stop(s)
    cid = done["consultation_id"]
    assert done["speaker_wait_s"] == 3.0, "the prompt is told how long the hold is"
    assert finalize.declaration_pending(cid) == 3.0
    assert len(_audit("auto.enabled", s.session_id)) == 1, "an auto.enabled row exists for the session"

    async def drive():
        waiting = asyncio.create_task(finalize.await_declaration(cid))
        await asyncio.sleep(0.6)
        assert not waiting.done(), "still waiting past the plain bound"
        assert finalize.declaration_pending(cid) == 3.0
        started = time.perf_counter()
        assert finalize.release_declaration(cid) is True     # what the answer endpoint does
        why = await waiting
        return why, time.perf_counter() - started
    why, took = asyncio.run(drive())
    assert why == "answered" and took < 0.5
    assert finalize.declaration_pending(cid) is None


def test_a_consultation_without_an_auto_run_keeps_the_plain_bound(gate, monkeypatch):
    monkeypatch.setattr(finalize, "SPEAKER_DECLARATION_WAIT_S", 0.25)
    monkeypatch.setattr(finalize, "AUTO_SPEAKER_DECLARATION_WAIT_S", 3.0)
    with live(gate) as s:
        _collect_until(s.ws, {"auto_toggled"})
        s.disclose()                                   # auto never toggled
        s.ws.send_text("stop")
        done = _until(s.ws, {"done"})
    cid = done["consultation_id"]
    assert _audit("auto.enabled", s.session_id) == []
    assert done["speaker_wait_s"] == 0.25
    assert finalize.declaration_pending(cid) == 0.25
    assert asyncio.run(finalize.await_declaration(cid)) == "timeout"


def test_at_expiry_the_ignored_declaration_path_applies_unchanged(gate, monkeypatch):
    """The auto bound expires with no answer: the pipeline goes on with the
    default (two), and a late "only the patient" is stored, not applied —
    declaration_ignored and speaker_labels_unverified, exactly the run-5
    path the pilot exercised end to end in 482."""
    monkeypatch.setattr(finalize, "AUTO_SPEAKER_DECLARATION_WAIT_S", 0.2)
    import app.main as appmain
    monkeypatch.setattr(appmain, "AUTO_SPEAKER_DECLARATION_WAIT_S", 0.2)
    user = _make_user()
    with live(gate, user) as s:
        done = _auto_run_and_stop(s)
    cid = done["consultation_id"]
    assert finalize.declaration_pending(cid) == 0.2
    started = time.perf_counter()
    assert asyncio.run(finalize.await_declaration(cid)) == "timeout"
    assert 0.15 < time.perf_counter() - started < 1.5
    assert finalize.declaration_pending(cid) is None
    # The pipeline's next step, as finalize_consultation does it.
    assert asyncio.run(consultations.speakers_for_diarisation(cid, finalize.DEFAULT_SPEAKERS)) == 2
    body = _client_for(user).post(f"/api/consultations/{cid}/declared-speakers",
                                  json={"count": 1}).json()
    assert body["applied"] is False and body["used"] == 2
    state = asyncio.run(consultations.get_consultation(cid))
    assert state["declaration_ignored"] is True
    assert consultations.speaker_labels_unverified(state) is True


def test_the_consultation_api_says_it_is_waiting_and_the_pages_show_it(gate, monkeypatch):
    monkeypatch.setattr(finalize, "AUTO_SPEAKER_DECLARATION_WAIT_S", 3.0)
    import app.main as appmain
    monkeypatch.setattr(appmain, "AUTO_SPEAKER_DECLARATION_WAIT_S", 3.0)
    user = _make_user()
    with live(gate, user) as s:
        done = _auto_run_and_stop(s)
    cid = done["consultation_id"]
    client = _client_for(user)
    payload = client.get(f"/api/consultations/{cid}").json()
    assert payload["status"] == "queued" and payload["awaiting_declaration"] == 3.0
    client.post(f"/api/consultations/{cid}/declared-speakers", json={"skip": True})
    assert client.get(f"/api/consultations/{cid}").json()["awaiting_declaration"] is None
    created = _audit_created(cid)
    assert created["auto_run"] is True and created["speaker_wait_s"] == 3.0
    review = Path("app/static/review.html").read_text()
    assert "state.awaiting_declaration" in review
    assert "Waiting for your answer to “Who spoke in this " in review
    live_html = Path("app/static/live.html").read_text()
    assert "askSpeakers(msg.consultation_id, msg.speaker_wait_s);" in live_html
    assert 'id="spkWait"' in live_html
    assert "Finalisation is waiting for this answer (up to " in live_html
    assert "waiting for your answer to “Who spoke?” before identifying speakers" in live_html


def _audit_created(cid):
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute("SELECT detail FROM audit_event WHERE action = 'consultation.created'"
                           " AND subject_id = %s ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
    return row[0]
