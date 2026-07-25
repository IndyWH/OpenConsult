"""Speech synthesis and reference resolution (app/speech.py, Phase 7a).

What these tests are evidence about, stated plainly because it matters:

- The **reference-only** design is tested for real. Resolution is pure
  logic over the phrase table and the server's own agenda log, so every
  assertion below about "the client cannot supply words" is a genuine
  test of the shipped mechanism.
- **Synthesis itself is not.** piper-tts is an optional dependency and is
  not installed on this machine as of 2026-07-25 (owner decision pending —
  GPL-3.0-or-later, and a lockfile re-resolve). Tests needing real audio
  self-skip, as the Ollama- and corpus-dependent tests already do. The
  cache, duration and cap arithmetic are tested against synthetic WAVs
  built here, which means they test the arithmetic and NOT Piper's
  behaviour. Nobody should read a green run as proof the system can speak.
"""

from __future__ import annotations

import io
import wave

import pytest

from app import speech


# --- helpers ---------------------------------------------------------------

def make_wav(seconds: float, rate: int = 22050) -> bytes:
    """A silent WAV of a known length. Stands in for Piper output in the
    arithmetic tests — it is not, and is not claimed to be, speech."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


def agenda_with(*questions: str, reasoning: str = "why these questions") -> speech.AgendaLog:
    log = speech.AgendaLog()
    log.record({"questions_to_ask": list(questions), "reasoning": reasoning})
    return log


# --- the phrase table ------------------------------------------------------

def test_phrase_table_holds_exactly_the_specified_phrases():
    assert set(speech.PHRASES) == {
        "disclosure", "invitation", "mm-hm", "i_see", "go_on",
        "examination_handover",
    }


def test_spec_quoted_wording_is_verbatim():
    """PHASE_7A_SPEC.md Part 5 quotes four of these exactly. The handover
    line names the doctor, per the build prompt."""
    assert speech.PHRASES["invitation"] == "Please, tell me what's brought you in."
    assert speech.PHRASES["mm-hm"] == "Mm-hm."
    assert speech.PHRASES["i_see"] == "I see."
    assert speech.PHRASES["go_on"] == "Go on."
    assert "Herath" in speech.PHRASES["examination_handover"]
    assert "examine you" in speech.PHRASES["examination_handover"]


def test_disclosure_says_the_patient_is_talking_to_a_machine():
    """Hard rule 4. The exact wording is the owner's to approve; that it
    discloses at all is not negotiable, so assert the substance only."""
    text = speech.PHRASES["disclosure"].lower()
    assert "computer" in text and "not a person" in text


def test_no_phrase_advises_reassures_or_diagnoses():
    """Hard rule 1, as a standing guard on the phrase table: a future
    contributor adding 'Try not to worry' should turn this red."""
    forbidden = ("you should", "you have", "it's probably", "it is probably",
                 "don't worry", "do not worry", "try not to worry",
                 "nothing to worry", "likely", "diagnos", "i think you",
                 "recommend", "you need to take", "it sounds like")
    for phrase_id, text in speech.PHRASES.items():
        lowered = text.lower()
        for bad in forbidden:
            assert bad not in lowered, f"{phrase_id} may be advising: {text!r}"


# --- reference resolution: the client cannot supply words ------------------

def test_phrase_reference_resolves_to_server_text():
    resolution = speech.resolve({"kind": "phrase", "id": "invitation"})
    assert resolution.text == speech.PHRASES["invitation"]
    assert resolution.ref_kind == "phrase"


def test_unknown_phrase_id_is_refused():
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"kind": "phrase", "id": "reassurance"})


def test_a_text_field_in_the_ref_is_ignored_not_honoured():
    """The keystone of hard rule 1's enforcement: even if a client smuggles
    a text field into the ref, resolution reads only the reference and the
    server's own phrase table. There is no code path from client text to
    spoken audio."""
    resolution = speech.resolve(
        {"kind": "phrase", "id": "invitation",
         "text": "You are having a heart attack."})
    assert resolution.text == speech.PHRASES["invitation"]
    assert "heart attack" not in resolution.text


def test_unknown_ref_kind_is_refused():
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"kind": "free_text", "text": "anything at all"})
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({})
    with pytest.raises(speech.SpeechRefused):
        speech.resolve("just a string")


def test_cds_question_resolves_against_the_servers_own_agenda():
    agenda = agenda_with("Does the pain go anywhere else?", "Any shortness of breath?")
    resolution = speech.resolve(
        {"kind": "cds_question", "assessment_version": 1, "index": 1}, agenda)
    assert resolution.text == "Any shortness of breath?"
    assert resolution.ref_detail == {"assessment_version": 1, "index": 1}
    assert resolution.cds_rationale == "why these questions"
    assert resolution.stale is False


def test_cds_question_index_out_of_range_is_refused():
    agenda = agenda_with("Only one question?")
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"kind": "cds_question", "assessment_version": 1, "index": 5},
                       agenda)


def test_unresolvable_assessment_version_is_refused_never_guessed():
    """The server must not substitute another version's wording — that
    would be the server authoring a question the doctor did not tap."""
    agenda = agenda_with("A question")
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"kind": "cds_question", "assessment_version": 99, "index": 0},
                       agenda)


def test_cds_question_needs_a_session_agenda():
    with pytest.raises(speech.SpeechRefused):
        speech.resolve({"kind": "cds_question", "assessment_version": 1, "index": 0})


def test_question_revised_off_the_agenda_is_allowed_and_marked_stale(caplog):
    """Spec §2.1: the panel can lag by a turn, and re-asking an answered
    question is redundant, not unsafe. So it speaks — and says so."""
    agenda = agenda_with("Does the pain radiate?", "Any nausea?")
    agenda.record({"questions_to_ask": ["Any nausea?"], "reasoning": "radiation answered"})

    with caplog.at_level("INFO"):
        resolution = speech.resolve(
            {"kind": "cds_question", "assessment_version": 1, "index": 0}, agenda)

    assert resolution.text == "Does the pain radiate?"
    assert resolution.stale is True
    assert "revised off the agenda" in caplog.text


def test_agenda_history_is_bounded():
    log = speech.AgendaLog(history=3)
    for i in range(10):
        log.record({"questions_to_ask": [f"q{i}"], "reasoning": ""})
    assert log.current_version == 10
    assert log.get(10) is not None and log.get(8) is not None
    assert log.get(7) is None, "old agenda versions must not accumulate forever"


def test_agenda_records_an_empty_assessment_without_crashing():
    log = speech.AgendaLog()
    assert log.record(None) == 1
    assert log.current.questions == ()


# --- cache key and duration arithmetic -------------------------------------

def test_cache_key_covers_both_text_and_voice():
    a = speech.cache_key("Any nausea?", "en_GB-alba-medium")
    assert a == speech.cache_key("Any nausea?", "en_GB-alba-medium")
    assert a != speech.cache_key("Any nausea?", "en_GB-other-medium")
    assert a != speech.cache_key("Any pain?", "en_GB-alba-medium")


def test_wav_duration_is_read_from_the_header():
    assert speech.wav_duration_ms(make_wav(1.5)) == 1500
    assert speech.wav_duration_ms(make_wav(0.25, rate=16000)) == 250


# --- the hard cap ----------------------------------------------------------

def test_absurd_text_is_refused_before_synthesis(tmp_path):
    """The pre-check exists so a pathological agenda string never reaches
    the synthesiser. Note this refuses without Piper installed — proving
    the guard runs before the model is touched."""
    service = speech.SpeechService(model_path="", cache_dir=tmp_path)
    with pytest.raises(speech.SpeechRefused, match="SPEECH_MAX_UTTERANCE_S"):
        service.synthesise("word " * 5000)


def test_empty_text_is_refused(tmp_path):
    service = speech.SpeechService(model_path="", cache_dir=tmp_path)
    with pytest.raises(speech.SpeechRefused):
        service.synthesise("   ")


def test_over_long_synthesis_is_refused_after_the_fact(tmp_path, monkeypatch):
    """The real bound: whatever Piper produced, an utterance longer than
    the cap is refused, because the exclusion window is only as
    trustworthy as its length is known."""
    service = speech.SpeechService(voice="test", model_path="x", cache_dir=tmp_path)

    class FakePiper:
        def synthesize_wav(self, text, wav_file):
            long_wav = make_wav(speech.SPEECH_MAX_UTTERANCE_S + 5)
            with wave.open(io.BytesIO(long_wav), "rb") as src:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(src.getframerate())
                wav_file.writeframes(src.readframes(src.getnframes()))

    monkeypatch.setattr(service, "_load", lambda: FakePiper())
    with pytest.raises(speech.SpeechRefused, match="exceeds"):
        service.synthesise("a short string that synthesises to something long")
    assert list(tmp_path.glob("*.wav")) == [], "an over-cap utterance must not be cached"


# --- the cache -------------------------------------------------------------

def test_synthesis_is_cached_and_the_second_call_does_not_synthesise(tmp_path):
    service = speech.SpeechService(voice="test", model_path="x", cache_dir=tmp_path)
    calls = []

    class FakePiper:
        def synthesize_wav(self, text, wav_file):
            calls.append(text)
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(b"\x00\x00" * 22050)

    service._load = lambda: FakePiper()

    wav_a, duration_a, synth_a = service.synthesise("Any nausea?")
    wav_b, duration_b, synth_b = service.synthesise("Any nausea?")

    assert calls == ["Any nausea?"], "the cache did not prevent a second synthesis"
    assert wav_a == wav_b and duration_a == duration_b == 1000
    assert synth_b == 0, "a cache hit reports no synthesis time"


def test_cache_is_not_shared_across_voices(tmp_path):
    a = speech.SpeechService(voice="voice_a", model_path="x", cache_dir=tmp_path)
    b = speech.SpeechService(voice="voice_b", model_path="x", cache_dir=tmp_path)
    assert a._cache_path("same words") != b._cache_path("same words")


# --- availability ----------------------------------------------------------

def test_service_reports_unavailable_without_a_model_path(tmp_path):
    service = speech.SpeechService(model_path="", cache_dir=tmp_path)
    assert service.available is False
    with pytest.raises(speech.SpeechUnavailable, match="TTS_MODEL_PATH"):
        service.synthesise("Any nausea?")


def test_service_reports_unavailable_for_a_missing_model_file(tmp_path):
    service = speech.SpeechService(model_path=str(tmp_path / "nope.onnx"),
                                   cache_dir=tmp_path)
    assert service.available is False
    with pytest.raises(speech.SpeechUnavailable, match="not found"):
        service.synthesise("Any nausea?")


# --- prepare(): resolution plus synthesis ----------------------------------

def test_prepare_registers_an_utterance_carrying_its_provenance(tmp_path):
    service = speech.SpeechService(voice="test", model_path="x", cache_dir=tmp_path)

    class FakePiper:
        def synthesize_wav(self, text, wav_file):
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(b"\x00\x00" * 11025)

    service._load = lambda: FakePiper()
    agenda = agenda_with("Does the pain radiate?", reasoning="cardiac vs musculoskeletal")

    utterance = service.prepare(
        {"kind": "cds_question", "assessment_version": 1, "index": 0}, agenda,
        user_id=7, consultation_id=42)

    assert utterance.text == "Does the pain radiate?"
    assert utterance.duration_ms == 500
    assert utterance.ref_kind == "cds_question"
    # Hard rule 5 asks for the rationale, not just the question.
    assert utterance.cds_rationale == "cardiac vs musculoskeletal"
    assert utterance.user_id == 7 and utterance.consultation_id == 42
    assert service.get(utterance.utterance_id) is utterance
    assert service.get("not-a-real-id") is None


# --- real Piper, if it is ever installed -----------------------------------

@pytest.mark.skipif(not speech.SpeechService().available,
                    reason="piper-tts / voice model not installed (optional)")
def test_real_synthesis_produces_plausible_audio(tmp_path):
    """Only runs once someone installs Piper and points TTS_MODEL_PATH at a
    voice. Until then the module's synthesis path is UNVERIFIED against the
    real library — the tests above exercise the arithmetic around it."""
    service = speech.SpeechService(cache_dir=tmp_path)
    wav_bytes, duration_ms, synth_ms = service.synthesise(speech.PHRASES["invitation"])
    assert wav_bytes[:4] == b"RIFF"
    assert 500 < duration_ms < speech.SPEECH_MAX_UTTERANCE_S * 1000
    assert (tmp_path / f"{speech.cache_key(speech.PHRASES['invitation'], service.voice)}.wav").exists()


# --- the audio route -------------------------------------------------------
#
# RBAC over HTTP. These need Postgres (sessions are real accounts) and so
# self-skip without it, like the rest of the suite.

import asyncio      # noqa: E402
import os           # noqa: E402
import secrets      # noqa: E402

import psycopg      # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402

from app import auth   # noqa: E402


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def _make_user(role: str) -> dict:
    auth.ensure_schema()
    return asyncio.run(auth.create_user(
        f"{role}_{secrets.token_hex(4)}", "test-password-123", role.title(), role))


def _client_for(user: dict) -> TestClient:
    from app.main import app

    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(user["id"]))
    return client


def _register(user_id: int) -> speech.Utterance:
    """Put a prepared utterance in the running app's service, without Piper."""
    from app.main import app

    if not hasattr(app.state, "speech"):
        app.state.speech = speech.SpeechService()
    utterance = speech.Utterance(
        utterance_id=secrets.token_hex(8), text=speech.PHRASES["invitation"],
        voice="test", wav=make_wav(1.0), duration_ms=1000, synth_ms=5,
        ref_kind="phrase", ref_detail={"id": "invitation"}, user_id=user_id)
    app.state.speech._utterances[utterance.utterance_id] = utterance
    return utterance


@needs_db
def test_owner_can_fetch_their_utterance_audio():
    doctor = _make_user("doctor")
    utterance = _register(doctor["id"])
    response = _client_for(doctor).get(f"/api/speech/{utterance.utterance_id}.wav")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"


@needs_db
def test_another_doctor_cannot_fetch_someone_elses_utterance():
    owner = _make_user("doctor")
    other = _make_user("doctor")
    utterance = _register(owner["id"])
    response = _client_for(other).get(f"/api/speech/{utterance.utterance_id}.wav")
    assert response.status_code == 404


@needs_db
def test_receptionist_is_refused_the_audio_route():
    doctor = _make_user("doctor")
    utterance = _register(doctor["id"])
    response = _client_for(_make_user("receptionist")).get(
        f"/api/speech/{utterance.utterance_id}.wav")
    assert response.status_code == 403


@needs_db
def test_logged_out_is_refused_the_audio_route():
    from app.main import app

    doctor = _make_user("doctor")
    utterance = _register(doctor["id"])
    response = TestClient(app).get(f"/api/speech/{utterance.utterance_id}.wav")
    assert response.status_code in (401, 403)


@needs_db
def test_unknown_utterance_id_is_404_not_a_confirmation():
    """Unknown and foreign ids answer alike, so the endpoint does not tell
    a prober which utterance ids exist."""
    doctor = _make_user("doctor")
    response = _client_for(doctor).get("/api/speech/deadbeefdeadbeef.wav")
    assert response.status_code == 404
