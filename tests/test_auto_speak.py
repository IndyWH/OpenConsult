"""The auto speak path (Phase 7c slice 2): server-initiated utterances
through the tap pipeline, with no new mechanism.

PHASE_7C_SPEC.md §3, §4, §9, §11 and the machine-level part of §13. What
is evidence here, and about what:

- **Resolution is the real thing.** `speech.resolve_utterance` is pure
  logic over the phrase table, the template table and the server's own
  agenda log, so every assertion that "the auto path can only say what
  the server already owns" is a genuine test of the shipped mechanism.
  Templates are instantiated SERVER-SIDE ONLY — there is no client
  reference kind for them, asserted below.
- **Synthesis is a real subprocess, stubbed at the command.** As in
  tests/test_speech.py: a fake `TTS_COMMAND` that is a real process
  writing a known-length WAV, because running a subprocess is the
  adapter's job. Pre-synthesis is tested against that, by counting cache
  files.
- **The protocol tests drive /ws/transcribe for real** (Postgres needed;
  they self-skip without it) and issue auto utterances INTO a live
  session through `app.main.issue_auto_speak`, exactly as the slice-3
  wiring will, then play the client's part — `speak_started` /
  `speak_ended` — over the same socket. That is how "auto_speak reuses
  the lifecycle protocol" is shown rather than asserted: the same
  handlers, the same slot, the same row.

Nothing in the running app calls `issue_auto_speak` yet; the tests call
it so that slice 3 wires a path that already holds.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import struct
import sys

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import auth, auto_mode, consultations, speech, system_utterances
from app import main as appmain
from app.auto_mode import (AgendaUtterance, AutoPhase, PhraseUtterance,
                           TemplateUtterance)
from app.live import BYTES_PER_MS
from app.transcription import SAMPLE_RATE


# --- helpers (mirroring tests/test_speech.py) --------------------------------

def fake_command(tmp_path, seconds: float = 1.0, exit_code: int = 0) -> str:
    """A TTS_COMMAND that is a real subprocess writing a known-length WAV."""
    script = tmp_path / f"fake_tts_{secrets.token_hex(4)}.py"
    script.write_text(
        "import sys, wave\n"
        "sys.stdin.buffer.read()\n"
        f"if {exit_code} == 0:\n"
        "    with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        f"        w.writeframes(b'\\x00\\x00' * int({seconds} * 22050))\n"
        f"sys.exit({exit_code})\n")
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"not a real model, the fake command never reads it")
    return f"{sys.executable} {script} --model {{model}} --output-file {{output}}"


def service_with(tmp_path, **kwargs) -> speech.SpeechService:
    return speech.SpeechService(
        voice="test", model_path=str(tmp_path / "voice.onnx"),
        cache_dir=tmp_path / "cache", command=fake_command(tmp_path, **kwargs))


def agenda_with(*questions: str, reasoning: str = "why these questions") -> speech.AgendaLog:
    log = speech.AgendaLog()
    log.record({"questions_to_ask": list(questions), "reasoning": reasoning})
    return log


@pytest.fixture(autouse=True)
def tts_enabled(monkeypatch):
    """Pin the deployment kill-switch ON, as tests/test_speech.py does: every
    service here is an explicit fake command in a tmp dir."""
    monkeypatch.setattr(speech, "TTS_ENABLED", True)


# ==========================================================================
# The whitelist resolves — and only the whitelist (spec §4)

def test_the_anything_else_phrase_is_the_owner_approved_wording_and_is_gated():
    """Spec §4 item 4. A fixed phrase like the others; a question to the
    patient, so the disclosure lock covers it (hard rule 4)."""
    assert speech.PHRASES["anything_else"] == (
        "Is there anything else you wanted to talk about today?")
    assert "anything_else" in speech.DISCLOSURE_GATED_PHRASES
    assert speech.resolve_utterance(PhraseUtterance("anything_else")).text == \
        speech.PHRASES["anything_else"]


def test_the_two_templates_are_the_owner_approved_wording():
    """Spec §4 item 3, verbatim. The words around the slot are what the
    owner approved; the slot is the only variable."""
    assert speech.TEMPLATES == {
        "tell_me_more": "Can you tell me more about {topic}?",
        "affecting_you": "How has {topic} been affecting you?",
    }


def test_a_phrase_utterance_resolves_through_the_phrase_table_like_a_tap():
    """Same table, same {doctor} fill from the server, same refusal of an
    unknown id — the auto path adds no second phrase table."""
    tapped = speech.resolve({"kind": "phrase", "id": "examination_handover"}, doctor="Herath")
    auto = speech.resolve_utterance(PhraseUtterance("examination_handover"), doctor="Herath")
    assert auto == tapped
    assert auto.text == "Thank you — Dr Herath will examine you now."
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(PhraseUtterance("reassurance"))


def test_a_template_utterance_is_instantiated_server_side():
    """The topic goes into the slot and nothing else changes; the record
    carries the template id and the topic so the review page can show
    what was said and from what."""
    for template_id, expected in (
            ("tell_me_more", "Can you tell me more about the chest pain?"),
            ("affecting_you", "How has the chest pain been affecting you?")):
        resolved = speech.resolve_utterance(TemplateUtterance(template_id, "the chest pain"))
        assert resolved.text == expected
        assert resolved.ref_kind == "template"
        assert resolved.ref_detail == {"template_id": template_id, "topic": "the chest pain"}
        assert resolved.cds_rationale == "" and resolved.stale is False


def test_the_topic_slot_is_one_line_and_never_empty():
    """A topic is a noun phrase. Whitespace (newlines included) collapses to
    single spaces, and an empty topic is refused rather than spoken as
    'Can you tell me more about ?'."""
    resolved = speech.resolve_utterance(TemplateUtterance("tell_me_more", "  the\n chest\tpain "))
    assert resolved.text == "Can you tell me more about the chest pain?"
    assert resolved.ref_detail["topic"] == "the chest pain"
    for empty in ("", "   ", "\n"):
        with pytest.raises(speech.SpeechRefused):
            speech.resolve_utterance(TemplateUtterance("tell_me_more", empty))
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(TemplateUtterance("tell_me_more", None))  # type: ignore[arg-type]


def test_an_unknown_template_id_is_refused():
    with pytest.raises(speech.SpeechRefused, match="unknown template id"):
        speech.resolve_utterance(TemplateUtterance("reassure", "the chest pain"))


def test_templates_have_no_client_reference_kind():
    """Instantiation is server-side ONLY (spec §4): the client-facing
    resolver does not know a 'template' kind, so a tap — or a modified
    client — cannot reach the templates or choose a topic."""
    with pytest.raises(speech.SpeechRefused, match="unknown speak.ref kind"):
        speech.resolve({"kind": "template", "template_id": "tell_me_more",
                        "topic": "the chest pain"})
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"kind": "template", "id": "tell_me_more", "topic": "x"})


def test_an_agenda_utterance_resolves_exactly_as_a_doctors_tap():
    """Same versioned AgendaLog, same text, same rationale, same stale rule,
    same refusal to guess at an unresolvable version or a bad index."""
    agenda = agenda_with("Does the pain radiate?", "Any shortness of breath?",
                         reasoning="cardiac vs musculoskeletal")
    tapped = speech.resolve({"kind": "cds_question", "assessment_version": 1, "index": 1},
                            agenda)
    auto = speech.resolve_utterance(AgendaUtterance(assessment_version=1, index=1), agenda)
    assert auto == tapped
    assert auto.text == "Any shortness of breath?"
    assert auto.cds_rationale == "cardiac vs musculoskeletal"
    # Revised off the agenda: allowed and marked stale, as for a tap.
    agenda.record({"questions_to_ask": ["Where exactly is the pain?"], "reasoning": "r2"})
    assert speech.resolve_utterance(AgendaUtterance(1, 0), agenda).stale is True
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(AgendaUtterance(9, 0), agenda)
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(AgendaUtterance(1, 5), agenda)
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(AgendaUtterance(1, 0), None)


@pytest.mark.parametrize("not_an_utterance", [
    "You'll be fine.",
    {"kind": "phrase", "id": "invitation"},
    {"text": "Try not to worry."},
    ("tell_me_more", "the chest pain"),
    None,
    42,
])
def test_free_text_and_anything_else_that_is_not_a_whitelist_type_is_refused(not_an_utterance):
    """Hard rule 1 by construction, second line: the resolver accepts the
    three types and nothing else — not a string, not a client-style ref,
    not a tuple that happens to look like a template. Refused with
    SpeechRefused, the same class as a `speak` carrying text, so the
    caller audits it the same way."""
    with pytest.raises(speech.SpeechRefused):
        speech.resolve_utterance(not_an_utterance)  # type: ignore[arg-type]


def test_the_existing_text_guard_is_untouched():
    """The tap path's guard stands exactly as it was: a ref carrying text
    is refused when unresolvable and ignored when resolvable."""
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"text": "You'll be fine."})
    assert speech.resolve({"kind": "phrase", "id": "invitation",
                           "text": "You'll be fine."}).text == speech.render_phrase("invitation")


def test_the_new_end_reasons_are_in_the_vocabulary():
    """Spec §5 and §7 name them; §11 records them on the row."""
    assert "politeness_abort" in system_utterances.END_REASONS
    assert "urgency_pause" in system_utterances.END_REASONS
    # And nothing that was there has gone.
    for reason in ("complete", "barge_in", "doctor_stop", "cancelled",
                   "failed_to_play", "window_ceiling"):
        assert reason in system_utterances.END_REASONS


# ==========================================================================
# prepare_auto: the same synthesis, plus via/phase/trigger on the record

def test_prepare_auto_registers_an_utterance_carrying_via_phase_and_trigger(tmp_path):
    """Spec §11: the row for an auto utterance carries ref_detail
    {"via": "auto", "phase": ..., "trigger": ...} and cds_rationale from
    the agenda version — on top of the reference detail a tap would have,
    so nothing that reads the row today loses anything."""
    service = service_with(tmp_path, seconds=0.5)
    agenda = agenda_with("Does the pain radiate?", reasoning="cardiac vs musculoskeletal")

    utterance = service.prepare_auto(
        AgendaUtterance(assessment_version=1, index=0), agenda,
        phase=AutoPhase.CLOSED, trigger={"quiet_s": 3.2, "handed_back": False},
        user_id=7, consultation_id=42)

    assert utterance.text == "Does the pain radiate?"
    assert utterance.duration_ms == 500
    assert utterance.ref_kind == "cds_question"
    assert utterance.ref_detail == {
        "assessment_version": 1, "index": 0,
        "via": "auto", "phase": "closed",
        "trigger": {"quiet_s": 3.2, "handed_back": False}}
    assert utterance.cds_rationale == "cardiac vs musculoskeletal"
    assert utterance.user_id == 7 and utterance.consultation_id == 42
    assert service.get(utterance.utterance_id) is utterance


def test_prepare_auto_accepts_the_phase_as_a_string_or_the_enum(tmp_path):
    service = service_with(tmp_path, seconds=0.2)
    a = service.prepare_auto(PhraseUtterance("mm-hm"), phase="golden")
    b = service.prepare_auto(PhraseUtterance("mm-hm"), phase=AutoPhase.GOLDEN)
    assert a.ref_detail["phase"] == b.ref_detail["phase"] == "golden"
    assert a.ref_detail["trigger"] == {}     # absent trigger records as empty, not None


def test_prepare_auto_goes_through_the_same_cache_as_a_tap(tmp_path):
    """The auto path adds no synthesis path: the second request for the same
    words is a cache hit whichever path made the first."""
    service = service_with(tmp_path, seconds=0.3)
    tapped = service.prepare({"kind": "phrase", "id": "go_on"}, None)
    assert tapped.synth_ms > 0 or tapped.synth_ms == 0   # first synthesis (fast fake)
    auto = service.prepare_auto(PhraseUtterance("go_on"), phase="golden")
    assert auto.synth_ms == 0                              # cache hit
    assert auto.text == tapped.text
    assert len(list((tmp_path / "cache").glob("*.wav"))) == 1


def test_prepare_auto_refuses_free_text_before_any_synthesis(tmp_path):
    service = service_with(tmp_path)
    with pytest.raises(speech.SpeechRefused):
        service.prepare_auto("You'll be fine.", phase="open")  # type: ignore[arg-type]
    assert not (tmp_path / "cache").exists(), "nothing may be synthesised for a refused request"


def test_prepare_auto_keeps_the_utterance_cap(tmp_path, monkeypatch):
    """SPEECH_MAX_UTTERANCE_S carries over unchanged (spec §3): an auto
    utterance is refused after synthesis exactly as a tap is."""
    monkeypatch.setattr(speech, "SPEECH_MAX_UTTERANCE_S", 1.0)
    service = service_with(tmp_path, seconds=2.0)
    with pytest.raises(speech.SpeechRefused, match="SPEECH_MAX_UTTERANCE_S"):
        service.prepare_auto(TemplateUtterance("tell_me_more", "the chest pain"), phase="open")


# ==========================================================================
# Pre-synthesis at service start (spec §9)

def _cache_files(tmp_path):
    cache = tmp_path / "cache"
    return sorted(cache.glob("*.wav")) if cache.exists() else []


def test_presynthesis_fills_the_cache_with_every_fixed_phrase_that_has_no_doctor_slot(tmp_path):
    """The encourager latency budget (< 1 s) is met by having the phrase
    already on disk. Every phrase without a per-session slot is
    synthesised at start; the two doctor-named phrases are skipped and
    said so, because there is no one text to warm until a session names
    its doctor."""
    service = service_with(tmp_path, seconds=0.2)
    outcomes = service.presynthesise_phrases()

    named = {pid for pid, text in speech.PHRASES.items() if "{doctor}" in text}
    assert named == {"disclosure", "examination_handover"}
    for pid in speech.PHRASES:
        if pid in named:
            assert outcomes[pid].startswith("skipped"), (pid, outcomes[pid])
        else:
            assert outcomes[pid] == "synthesised", (pid, outcomes[pid])
    assert len(_cache_files(tmp_path)) == len(speech.PHRASES) - len(named)
    # And an encourager is now a cache hit: 0 ms synthesis.
    for encourager in speech.ENCOURAGER_IDS:
        assert service.prepare_auto(PhraseUtterance(encourager), phase="golden").synth_ms == 0
    assert service.prepare_auto(PhraseUtterance("anything_else"), phase="handover").synth_ms == 0


def test_presynthesis_is_idempotent(tmp_path):
    service = service_with(tmp_path, seconds=0.2)
    service.presynthesise_phrases()
    before = _cache_files(tmp_path)
    again = service.presynthesise_phrases()
    assert all(v == "cached" for pid, v in again.items()
               if "{doctor}" not in speech.PHRASES[pid])
    assert _cache_files(tmp_path) == before


def test_presynthesis_never_raises_when_the_synthesiser_is_absent(tmp_path):
    """A machine without Piper starts exactly as before: one log line, no
    exception, nothing on disk."""
    service = speech.SpeechService(voice="test", model_path="",
                                   cache_dir=tmp_path / "cache", command="piper")
    assert not service.available
    outcomes = service.presynthesise_phrases()
    assert set(outcomes) == set(speech.PHRASES)
    assert all(v.startswith("skipped") for v in outcomes.values())
    assert _cache_files(tmp_path) == []


def test_presynthesis_never_raises_when_the_command_fails(tmp_path):
    """A failing command is logged per phrase and the service carries on;
    pre-synthesis is a latency courtesy, not a condition of speaking."""
    service = service_with(tmp_path, exit_code=3)
    outcomes = service.presynthesise_phrases()
    assert all(v.startswith("failed") for pid, v in outcomes.items()
               if "{doctor}" not in speech.PHRASES[pid])
    assert _cache_files(tmp_path) == []
    # A failed synthesis leaves nothing torn in the cache directory either.
    cache = tmp_path / "cache"
    assert not cache.exists() or list(cache.iterdir()) == []


def test_two_synthesisers_on_the_same_text_at_once_both_succeed(tmp_path):
    """Pre-synthesis runs in a background thread, so a warm and a tap can
    be synthesising the same phrase at the same moment. Found 2026-08-16:
    with one temp path per process, one caller installed the other's file
    and then found nothing to read ("synthesis produced no audio"). The
    temp name is now unique per call; both callers succeed and the cache
    holds one file."""
    from concurrent.futures import ThreadPoolExecutor
    script = tmp_path / "slow_tts.py"
    script.write_text(
        "import sys, time, wave\n"
        "sys.stdin.buffer.read()\n"
        "time.sleep(0.2)\n"
        "with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        "    w.writeframes(b'\\x00\\x00' * 2205)\n")
    (tmp_path / "voice.onnx").write_bytes(b"never read")
    service = speech.SpeechService(
        voice="test", model_path=str(tmp_path / "voice.onnx"), cache_dir=tmp_path / "cache",
        command=f"{sys.executable} {script} --model {{model}} --output-file {{output}}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.synthesise("Mm-hm."), range(4)))
    assert all(duration == 100 for _, duration, _ in results)
    assert len(list((tmp_path / "cache").glob("*.wav"))) == 1
    assert list((tmp_path / "cache").glob("*.tmp")) == []


def test_the_app_starts_presynthesis_at_service_start_off_the_loop():
    """Spec §9: 'pre-synthesised into the disk cache at service start'.
    Asserted on the lifespan source: the task is created right after the
    service, through to_thread (never on the loop), and cancelled at
    shutdown."""
    from pathlib import Path
    source = Path("app/main.py").read_text()
    lifespan = source[source.index("async def lifespan("):source.index("async def finalize_worker(")]
    assert "app.state.speech = speech.SpeechService()" in lifespan
    assert "asyncio.to_thread(app.state.speech.presynthesise_phrases)" in lifespan
    assert lifespan.index("speech.SpeechService()") < lifespan.index("presynthesise_phrases")
    assert "app.state.speech_presynth.cancel()" in lifespan[lifespan.index("yield"):]


# ==========================================================================
# Protocol level: an auto utterance through the real socket, same lifecycle
#
# Postgres is required (sessions are real accounts); these self-skip
# without it. The speech service is a REAL SpeechService with a fake
# command in a tmp dir — so cache and cap are exercised — installed on
# app.state and removed again on teardown (the tests/test_speech_exclusion.py
# lesson: app.state is process-global).

def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")

FRAME_SAMPLES = 4000
PATIENT_AMPLITUDE = 3000
TTS_AMPLITUDE = 20000


def _tone(samples: int, amplitude: int) -> bytes:
    t = np.arange(samples)
    return (amplitude * np.sin(2 * np.pi * 440 * t / SAMPLE_RATE)).astype(np.int16).tobytes()


def _frame(seq: int, samples: int, amplitude: int) -> bytes:
    return struct.pack(">I", seq) + _tone(samples, amplitude)


class SilentTranscriber:
    def transcribe(self, buffer):
        return []


class FakeSocket:
    """Collects what the server sends on the auto path. The auto path's
    only outbound message is the play command; the lifecycle then runs
    over the real socket."""

    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role))


def _client_for(user: dict) -> TestClient:
    client = TestClient(appmain.app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


@pytest.fixture()
def auto_state(monkeypatch, tmp_path):
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    state = appmain.app.state
    missing = object()
    installed = {
        "transcriber": SilentTranscriber(),
        "speech": service_with(tmp_path, seconds=1.0),
        "cds_engine": object(),
        "rag": object(),
        "live_sessions": {},
        "finalize_queue": asyncio.Queue(),
    }
    previous = {name: getattr(state, name, missing) for name in installed}
    for name, value in installed.items():
        setattr(state, name, value)
    monkeypatch.setattr(appmain, "RECORDINGS_DIR", tmp_path)
    try:
        yield state
    finally:
        for name, old in previous.items():
            if old is missing:
                delattr(state, name)
            else:
                setattr(state, name, old)


def _drain_until(ws, wanted, limit=60):
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("type") in wanted:
            return message
        if message.get("type") == "speak_refused":
            raise AssertionError(
                f"speak refused while waiting for {wanted}: {message['detail']}")
    raise AssertionError(f"none of {wanted} arrived")


def _disclose(ws):
    ws.send_text(json.dumps({"type": "disclosure_given"}))
    return _drain_until(ws, {"disclosure"})


def _issue(ws, state, session_id, utterance, *, phase="golden", trigger=None):
    """Issue an auto utterance INTO the live session, on the app's own event
    loop (the socket's portal), exactly as the controller wiring will —
    from inside the connection, not from a client message."""
    entry = state.live_sessions[session_id]
    fake = FakeSocket()
    prepared = ws.portal.call(
        lambda: appmain.issue_auto_speak(state, entry, fake, utterance,
                                         phase=phase, trigger=trigger))
    return prepared, fake


def _audit_rows(action: str, limit: int = 5) -> list[dict]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return [r[0] for r in conn.execute(
            "SELECT detail FROM audit_event WHERE action = %s ORDER BY id DESC LIMIT %s",
            (action, limit))]


@needs_db
def test_auto_speak_is_shaped_like_speak_ready_and_runs_the_same_lifecycle(auto_state):
    """Spec §3: the auto path reuses the pipeline end to end. The play
    command has exactly speak_ready's fields under the type auto_speak;
    speak_started/speak_ended over the real socket then open and close
    the same window through the same handlers; the row that lands is a
    system_utterance row like any tap's, with via/phase/trigger on it."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        _disclose(ws)
        # A tap first, so speak_ready's real shape is in hand to compare.
        ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _drain_until(ws, {"speak_ready"})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": ready["utterance_id"], "seq": 1}))
        ws.send_bytes(_frame(1, FRAME_SAMPLES, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": ready["utterance_id"],
                                 "seq": 2, "reason": "complete"}))
        ws.send_bytes(_frame(2, FRAME_SAMPLES, PATIENT_AMPLITUDE))
        _drain_until(ws, {"ack"})

        prepared, fake = _issue(ws, auto_state, session_id, PhraseUtterance("mm-hm"),
                                phase=AutoPhase.GOLDEN, trigger={"quiet_s": 1.8})
        assert [m["type"] for m in fake.sent] == ["auto_speak"]
        auto = fake.sent[0]
        assert set(auto) == set(ready), "auto_speak must carry exactly speak_ready's fields"
        assert auto["utterance_id"] == prepared.utterance_id
        assert auto["text"] == "Mm-hm." and auto["ref_id"] == "mm-hm"
        assert auto["url"] == f"/api/speech/{prepared.utterance_id}.wav"
        assert auto["duration_ms"] == 1000

        # The client's part, unchanged: started, one second of us, ended.
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": prepared.utterance_id, "seq": 3}))
        for seq in range(3, 7):
            ws.send_bytes(_frame(seq, FRAME_SAMPLES, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": prepared.utterance_id,
                                 "seq": 7, "reason": "complete"}))
        ws.send_text("stop")
        done = _drain_until(ws, {"done"})
    cid = done["consultation_id"]

    rows = asyncio.run(system_utterances.for_consultation(cid))
    assert [r["text"] for r in rows] == [speech.render_phrase("invitation"), "Mm-hm."]
    tap_row, auto_row = rows
    assert tap_row["ref_detail"] == {"id": "invitation"}       # the tap path is untouched
    assert auto_row["ref_kind"] == "phrase"
    assert auto_row["ref_detail"] == {"id": "mm-hm", "via": "auto", "phase": "golden",
                                      "trigger": {"quiet_s": 1.8}}
    assert auto_row["end_reason"] == "complete"
    assert auto_row["started_offset_ms"] == 500                # after two 0.25 s frames
    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    assert spans[1] == (16000, 16000 + 4 * 8000 + 200 * BYTES_PER_MS)

    # Audited through the existing speech.* events, via distinguishing them.
    requested = _audit_rows("speech.requested")
    mine = [d for d in requested if d.get("utterance_id") == prepared.utterance_id]
    assert mine and mine[0]["via"] == "auto" and mine[0]["phase"] == "golden"
    assert mine[0]["trigger"] == {"quiet_s": 1.8}


def test_the_message_builder_is_one_function_for_both_paths():
    """Belt and braces on the shape assertion above: speak_ready and
    auto_speak come from the same builder, so they cannot drift."""
    utterance = speech.Utterance(
        utterance_id="abc", text="Go on.", voice="test", wav=b"RIFF",
        duration_ms=300, synth_ms=0, ref_kind="phrase", ref_detail={"id": "go_on"})
    ready = appmain._speak_message(utterance, "speak_ready")
    auto = appmain._speak_message(utterance, "auto_speak")
    assert ready.pop("type") == "speak_ready" and auto.pop("type") == "auto_speak"
    assert ready == auto


@needs_db
def test_an_agenda_question_and_a_template_carry_the_rationale_and_the_topic(auto_state):
    """Spec §11: cds_rationale from the agenda version for an agenda
    question; the template id and topic on the record for a template."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        _disclose(ws)
        entry = auto_state.live_sessions[session_id]
        entry["agenda"].record({"questions_to_ask": ["Does the pain radiate?"],
                                "reasoning": "cardiac vs musculoskeletal"})
        q, fake = _issue(ws, auto_state, session_id, AgendaUtterance(1, 0),
                         phase="closed", trigger={"quiet_s": 3.1, "handed_back": True})
        assert fake.sent[0]["text"] == "Does the pain radiate?"
        ws.send_text(json.dumps({"type": "speak_started", "utterance_id": q.utterance_id, "seq": 1}))
        ws.send_bytes(_frame(1, FRAME_SAMPLES, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": q.utterance_id,
                                 "seq": 2, "reason": "complete"}))
        t, fake = _issue(ws, auto_state, session_id,
                         TemplateUtterance("tell_me_more", "the chest pain"), phase="open")
        assert fake.sent[0]["text"] == "Can you tell me more about the chest pain?"
        assert fake.sent[0]["ref_id"] is None      # a template has no phrase id
        ws.send_text(json.dumps({"type": "speak_started", "utterance_id": t.utterance_id, "seq": 2}))
        ws.send_bytes(_frame(2, FRAME_SAMPLES, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": t.utterance_id,
                                 "seq": 3, "reason": "complete"}))
        ws.send_text("stop")
        done = _drain_until(ws, {"done"})

    rows = asyncio.run(system_utterances.for_consultation(done["consultation_id"]))
    question, template = rows
    assert question["ref_kind"] == "cds_question"
    assert question["cds_rationale"] == "cardiac vs musculoskeletal"
    assert question["ref_detail"] == {"assessment_version": 1, "index": 0, "via": "auto",
                                      "phase": "closed",
                                      "trigger": {"quiet_s": 3.1, "handed_back": True}}
    assert template["ref_kind"] == "template"
    assert template["ref_detail"] == {"template_id": "tell_me_more", "topic": "the chest pain",
                                      "via": "auto", "phase": "open", "trigger": {}}
    assert template["text"] == "Can you tell me more about the chest pain?"


@needs_db
def test_free_text_cannot_be_issued_through_the_auto_path(auto_state):
    """The auto path's equivalent of `speak` carrying text: refused, audited
    as speech.failed with via=auto, and nothing is sent to the client."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        _disclose(ws)
        entry = auto_state.live_sessions[session_id]
        fake = FakeSocket()
        with pytest.raises(speech.SpeechRefused):
            ws.portal.call(lambda: appmain.issue_auto_speak(
                auto_state, entry, fake, "You are having a heart attack.", phase="open"))
        assert fake.sent == []
        assert entry["pending_utterance"] is None
        ws.send_text("stop")
        _drain_until(ws, {"done"})
    failed = _audit_rows("speech.failed")
    assert any(d.get("via") == "auto" and "whitelist" in d.get("reason", "") for d in failed)


@needs_db
def test_one_utterance_at_a_time_holds_across_both_paths(auto_state):
    """A tap in flight refuses an auto utterance; an auto utterance in
    flight refuses a tap. Same slot, same guard (7a spec §2.3)."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        _disclose(ws)
        ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "invitation"}}))
        ready = _drain_until(ws, {"speak_ready"})
        entry = auto_state.live_sessions[session_id]
        with pytest.raises(speech.SpeechRefused, match="already in flight"):
            ws.portal.call(lambda: appmain.issue_auto_speak(
                auto_state, entry, FakeSocket(), PhraseUtterance("mm-hm"), phase="golden"))
        # Release the tap without playing it, then the auto path takes the slot...
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": ready["utterance_id"],
                                 "seq": 1, "reason": "politeness_abort"}))
        prepared, _ = _issue(ws, auto_state, session_id, PhraseUtterance("mm-hm"))
        # ...and a tap is now refused with the same reason.
        ws.send_text(json.dumps({"type": "speak", "ref": {"kind": "phrase", "id": "go_on"}}))
        refused = ws.receive_json()
        while refused.get("type") not in ("speak_refused", "speak_ready"):
            refused = ws.receive_json()
        assert refused["type"] == "speak_refused" and "already in flight" in refused["detail"]
        ws.send_text("stop")
        _drain_until(ws, {"done"})


@needs_db
def test_the_disclosure_lock_covers_the_auto_path(auto_state):
    """Hard rule 4 on the auto path: every question (agenda or template) and
    the gated phrases are refused before the disclosure; the encouragers
    and the disclosure itself are not."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        entry = auto_state.live_sessions[session_id]
        entry["agenda"].record({"questions_to_ask": ["Does the pain radiate?"], "reasoning": "r"})
        gated = [AgendaUtterance(1, 0), TemplateUtterance("tell_me_more", "the pain"),
                 PhraseUtterance("invitation"), PhraseUtterance("anything_else"),
                 PhraseUtterance("examination_handover")]
        for utterance in gated:
            fake = FakeSocket()
            with pytest.raises(speech.SpeechRefused, match="talking to a machine"):
                ws.portal.call(lambda u=utterance, f=fake: appmain.issue_auto_speak(
                    auto_state, entry, f, u, phase="open"))
            assert fake.sent == []
        # Not gated: an encourager, and the disclosure itself.
        prepared, fake = _issue(ws, auto_state, session_id, PhraseUtterance("i_see"))
        assert fake.sent[0]["type"] == "auto_speak"
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": prepared.utterance_id,
                                 "seq": 1, "reason": "politeness_abort"}))
        prepared, fake = _issue(ws, auto_state, session_id, PhraseUtterance("disclosure"),
                                phase="disclosure")
        assert fake.sent[0]["text"].startswith("Hello. I'm a computer")
        ws.send_text("stop")
        _drain_until(ws, {"done"})


@needs_db
def test_a_politeness_abort_leaves_no_span_and_releases_the_slot(auto_state):
    """Spec §5: the client re-checks its own microphone right before playback
    and, if speech has resumed, declines to play — speak_ended with reason
    politeness_abort and no speak_started. Nothing entered the room, so
    the row has no span, the reason is recorded, and the slot is free for
    the next utterance (the requeue itself is slice-3 wiring)."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ws.send_bytes(_frame(1, FRAME_SAMPLES, PATIENT_AMPLITUDE))
        _drain_until(ws, {"ack"})
        first, _ = _issue(ws, auto_state, session_id, PhraseUtterance("go_on"),
                          trigger={"quiet_s": 1.9})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": first.utterance_id,
                                 "seq": 2, "reason": "politeness_abort"}))
        # The slot is released: the next auto utterance is accepted, plays,
        # and its window is the only one recorded.
        second, _ = _issue(ws, auto_state, session_id, PhraseUtterance("mm-hm"),
                           trigger={"quiet_s": 2.4})
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": second.utterance_id, "seq": 2}))
        for seq in range(2, 6):
            ws.send_bytes(_frame(seq, FRAME_SAMPLES, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": second.utterance_id,
                                 "seq": 6, "reason": "complete"}))
        ws.send_text("stop")
        done = _drain_until(ws, {"done"})
    cid = done["consultation_id"]

    rows = asyncio.run(system_utterances.for_consultation(cid))
    by_id = {r["utterance_id"]: r for r in rows}
    aborted, played = by_id[first.utterance_id], by_id[second.utterance_id]
    assert aborted["end_reason"] == "politeness_abort"
    assert aborted["started_offset_ms"] is None and aborted["ended_offset_ms"] is None
    assert aborted["ref_detail"]["trigger"] == {"quiet_s": 1.9}
    assert played["end_reason"] == "complete"
    assert asyncio.run(system_utterances.exclusion_spans(cid)) == [
        (8000, 8000 + 4 * 8000 + 200 * BYTES_PER_MS)]
    aborts = _audit_rows("speech.politeness_abort")
    assert any(d.get("utterance_id") == first.utterance_id and d.get("via") == "auto"
               for d in aborts)


@needs_db
def test_a_politeness_abort_for_the_wrong_or_no_utterance_is_still_refused(auto_state):
    """The no-window acceptance is narrow: only the pending utterance's own
    id, only that reason. Anything else is the refusal it always was."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": "nothing",
                                 "seq": 1, "reason": "politeness_abort"}))
        message = ws.receive_json()
        while message.get("type") not in ("speak_refused",):
            message = ws.receive_json()
        assert "no window open" in message["detail"]
        prepared, _ = _issue(ws, auto_state, session_id, PhraseUtterance("go_on"))
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": "someone-else",
                                 "seq": 1, "reason": "politeness_abort"}))
        message = ws.receive_json()
        while message.get("type") not in ("speak_refused",):
            message = ws.receive_json()
        assert "no window open" in message["detail"]
        entry = auto_state.live_sessions[session_id]
        assert entry["pending_utterance"] is prepared     # still pending: not released
        ws.send_text("stop")
        _drain_until(ws, {"done"})


@needs_db
def test_urgency_pause_is_recorded_like_any_other_end_reason(auto_state):
    """Spec §7 names it; in this slice the server simply records it — the
    window closes where playback stopped, the row carries the reason."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        prepared, _ = _issue(ws, auto_state, session_id, PhraseUtterance("mm-hm"))
        ws.send_text(json.dumps({"type": "speak_started",
                                 "utterance_id": prepared.utterance_id, "seq": 1}))
        ws.send_bytes(_frame(1, FRAME_SAMPLES, TTS_AMPLITUDE))
        _drain_until(ws, {"ack"})
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": prepared.utterance_id,
                                 "seq": 2, "reason": "urgency_pause"}))
        ws.send_text("stop")
        done = _drain_until(ws, {"done"})
    rows = asyncio.run(system_utterances.for_consultation(done["consultation_id"]))
    assert rows[0]["end_reason"] == "urgency_pause"
    assert rows[0]["started_offset_ms"] == 0
    # One 0.25 s frame played, then the tail: the window closes where the
    # cut fell, not at the synthesised length.
    assert asyncio.run(system_utterances.exclusion_spans(done["consultation_id"])) == [
        (0, 8000 + 200 * BYTES_PER_MS)]


@needs_db
def test_the_silence_nudge_cage_holds_on_the_auto_path(auto_state):
    """The nudge stays caged whichever path asks for it: only after the
    invitation has played through, once per consultation."""
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        _disclose(ws)
        entry = auto_state.live_sessions[session_id]
        with pytest.raises(speech.SpeechRefused, match="completed invitation"):
            ws.portal.call(lambda: appmain.issue_auto_speak(
                auto_state, entry, FakeSocket(), PhraseUtterance("silence_nudge"), phase="golden"))
        entry["invitation_completed"] = True
        first, _ = _issue(ws, auto_state, session_id, PhraseUtterance("silence_nudge"))
        assert entry["nudge_used"] is True
        ws.send_text(json.dumps({"type": "speak_ended", "utterance_id": first.utterance_id,
                                 "seq": 1, "reason": "politeness_abort"}))
        with pytest.raises(speech.SpeechRefused, match="already been used"):
            ws.portal.call(lambda: appmain.issue_auto_speak(
                auto_state, entry, FakeSocket(), PhraseUtterance("silence_nudge"), phase="golden"))
        ws.send_text("stop")
        _drain_until(ws, {"done"})


@needs_db
def test_a_synthesis_fault_on_the_auto_path_is_shown_to_the_client_and_raised(auto_state, tmp_path):
    """A dead synthesiser must look like a fault, never like a system that
    chose not to speak — on the auto path as on a tap: speak_refused to
    the client, speech.failed audited with via=auto, and the exception
    reaches the caller."""
    auto_state.speech = service_with(tmp_path, exit_code=2)
    client = _client_for(_make_user("doctor"))
    session_id = secrets.token_hex(8)
    with client.websocket_connect("/ws/transcribe") as ws:
        ws.send_json({"session_id": session_id})
        entry = auto_state.live_sessions[session_id]
        fake = FakeSocket()
        with pytest.raises(speech.SpeechFailed):
            ws.portal.call(lambda: appmain.issue_auto_speak(
                auto_state, entry, fake, PhraseUtterance("mm-hm"), phase="golden"))
        assert [m["type"] for m in fake.sent] == ["speak_refused"]
        assert "synthesis failed" in fake.sent[0]["detail"]
        assert entry["pending_utterance"] is None
        ws.send_text("stop")
        _drain_until(ws, {"done"})
    failed = _audit_rows("speech.failed")
    assert any(d.get("via") == "auto" and "synthesis failed" in d.get("reason", "")
               for d in failed)
