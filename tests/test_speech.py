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
import secrets
import sys
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
    """PHASE_7A_SPEC.md Part 5 quotes four of these exactly."""
    assert speech.PHRASES["invitation"] == "Please, tell me what's brought you in."
    assert speech.PHRASES["mm-hm"] == "Mm-hm."
    assert speech.PHRASES["i_see"] == "I see."
    assert speech.PHRASES["go_on"] == "Go on."
    assert speech.render_phrase("examination_handover", "Herath") == \
        "Thank you — Dr Herath will examine you now."


def test_the_approved_disclosure_is_verbatim():
    """Owner-approved 2026-07-25. Asserted word for word, not by substance:
    this is the sentence a patient hears, and a silent edit to it is a
    clinical-communication change nobody signed off."""
    assert speech.render_phrase("disclosure", "Herath") == (
        "Hello. I'm a computer, not a person. I'll ask you some questions "
        "about what's brought you in. Dr Herath is here with you and you "
        "can speak to him at any time.")


def test_the_disclosure_says_nothing_about_interrupting():
    """Deliberate: it must stay true whether or not barge-in is enabled,
    and constant across the face study's arms. Session 3 must not add an
    interruption line."""
    text = speech.PHRASES["disclosure"].lower()
    for word in ("interrupt", "stop me", "cut in", "talk over"):
        assert word not in text


def test_no_phrase_advises_reassures_or_diagnoses():
    """Hard rule 1, as a standing guard on the phrase table: a future
    contributor adding 'Try not to worry' should turn this red."""
    forbidden = ("you should", "you have", "it's probably", "it is probably",
                 "don't worry", "do not worry", "try not to worry",
                 "nothing to worry", "likely", "diagnos", "i think you",
                 "recommend", "you need to take", "it sounds like")
    for phrase_id in speech.PHRASES:
        lowered = speech.render_phrase(phrase_id, "Herath").lower()
        for bad in forbidden:
            assert bad not in lowered, f"{phrase_id} may be advising: {text!r}"


# --- the doctor's name, interpolated server-side ---------------------------

def test_the_doctor_name_comes_from_the_account_display_name():
    assert speech.doctor_name_for(
        {"display_name": "Herath", "username": "herath"}) == "Herath"


def test_the_doctor_name_falls_back_to_the_username():
    """Every account has a username (NOT NULL, unique), so there is always
    something true to say. Reported to the owner rather than prettified."""
    assert speech.doctor_name_for(
        {"display_name": "", "username": "herath"}) == "herath"
    assert speech.doctor_name_for(
        {"display_name": None, "username": "vicky"}) == "vicky"


def test_no_title_is_ever_invented_from_the_account_data():
    """The 'Dr' comes from the phrase template, never from a transform on
    the name. No active account carries a title today."""
    assert "Dr" not in speech.doctor_name_for(
        {"display_name": "Herath", "username": "herath"})
    assert speech.render_phrase("examination_handover", "Herath").startswith(
        "Thank you — Dr Herath")


def test_a_missing_user_still_yields_a_sayable_line():
    assert speech.doctor_name_for(None) == "the doctor"
    assert "Dr the doctor" in speech.render_phrase("disclosure", None)


def test_phrases_without_a_doctor_field_are_unaffected():
    for phrase_id in ("invitation", "mm-hm", "i_see", "go_on"):
        assert speech.render_phrase(phrase_id, "Herath") == speech.PHRASES[phrase_id]


def test_the_name_is_not_client_supplied():
    """resolve() takes the doctor as a server-side argument; nothing in the
    ref can influence it."""
    resolution = speech.resolve(
        {"kind": "phrase", "id": "examination_handover", "doctor": "Kildare"},
        None, "Herath")
    assert "Herath" in resolution.text and "Kildare" not in resolution.text


def test_different_doctors_get_different_cache_entries():
    """The rendered text is the cache key's input, so two doctors cannot
    be served each other's audio."""
    a = speech.cache_key(speech.render_phrase("disclosure", "Herath"), "v")
    b = speech.cache_key(speech.render_phrase("disclosure", "Victoria"), "v")
    assert a != b


def test_the_disclosure_gate_list_exempts_the_encouragers():
    """Gating "mm-hm" would make the lock feel like a nuisance rather than
    a rule; it is not a clinical interaction."""
    assert set(speech.DISCLOSURE_GATED_PHRASES) == {"invitation",
                                                    "examination_handover"}
    for encourager in speech.ENCOURAGER_IDS:
        assert encourager not in speech.DISCLOSURE_GATED_PHRASES
    assert "disclosure" not in speech.DISCLOSURE_GATED_PHRASES, (
        "the disclosure cannot require itself")


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


def fake_command(tmp_path, seconds: float = 1.0, exit_code: int = 0,
                 stderr: str = "", sleep: float = 0.0, write: bool = True) -> str:
    """A TTS_COMMAND that is a real subprocess, standing in for Piper.

    Deliberately a real process rather than a monkeypatched method: the
    adapter's job IS running a subprocess, so faking at the function
    boundary would test nothing about the part that can actually fail.
    """
    script = tmp_path / f"fake_tts_{secrets.token_hex(4)}.py"
    script.write_text(
        "import sys, time, wave\n"
        f"time.sleep({sleep})\n"
        "sys.stdin.buffer.read()\n"
        f"if {write!r}:\n"
        "    with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        f"        w.writeframes(b'\\x00\\x00' * int({seconds} * 22050))\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({exit_code})\n")
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"not a real model, the fake command never reads it")
    return f"{sys.executable} {script} --model {{model}} --output-file {{output}}"


def service_with(tmp_path, **kwargs) -> speech.SpeechService:
    return speech.SpeechService(
        voice="test", model_path=str(tmp_path / "voice.onnx"),
        cache_dir=tmp_path / "cache", command=fake_command(tmp_path, **kwargs))


def test_over_long_synthesis_is_refused_after_the_fact(tmp_path):
    """The real bound: whatever the synthesiser produced, an utterance
    longer than the cap is refused, because the exclusion window is only as
    trustworthy as its length is known."""
    service = service_with(tmp_path, seconds=speech.SPEECH_MAX_UTTERANCE_S + 5)
    with pytest.raises(speech.SpeechRefused, match="exceeds"):
        service.synthesise("a short string that synthesises to something long")
    assert list((tmp_path / "cache").glob("*.wav")) == [], \
        "an over-cap utterance must not be cached"


def test_a_failed_command_raises_and_never_degrades_to_silence(tmp_path):
    """A dead speaker must look like a fault. Silence that looks like a
    choice is the failure mode this guards against."""
    service = service_with(tmp_path, exit_code=3, stderr="espeak-ng data missing")
    with pytest.raises(speech.SpeechFailed, match="exited 3"):
        service.synthesise("Any nausea?")
    assert "espeak-ng data missing" in _last_error(service)


def _last_error(service) -> str:
    try:
        service.synthesise("Any nausea?")
    except speech.SpeechFailed as exc:
        return str(exc)
    return ""


def test_a_command_producing_no_audio_is_a_failure_not_an_empty_wav(tmp_path):
    service = service_with(tmp_path, write=False)
    with pytest.raises(speech.SpeechFailed, match="no audio"):
        service.synthesise("Any nausea?")


def test_a_hanging_command_times_out(tmp_path, monkeypatch):
    monkeypatch.setattr(speech, "TTS_TIMEOUT_S", 0.5)
    service = service_with(tmp_path, sleep=5.0)
    with pytest.raises(speech.SpeechFailed, match="timed out"):
        service.synthesise("Any nausea?")


def test_a_failed_synthesis_leaves_nothing_in_the_cache(tmp_path):
    service = service_with(tmp_path, exit_code=1)
    with pytest.raises(speech.SpeechFailed):
        service.synthesise("Any nausea?")
    cache = tmp_path / "cache"
    assert list(cache.glob("*")) == [], "a failed synthesis left files behind"


def test_the_text_goes_on_stdin_never_on_argv(tmp_path):
    """argv is world-readable in /proc, and a consultation's questions are
    clinical content. The command template must carry no text placeholder."""
    assert "{text}" not in speech.TTS_COMMAND
    script = tmp_path / "echo_argv.py"
    script.write_text(
        "import sys, wave\n"
        "text = sys.stdin.buffer.read().decode()\n"
        "assert text.strip() not in ' '.join(sys.argv), 'text leaked into argv'\n"
        "with wave.open(sys.argv[sys.argv.index('--output-file') + 1], 'wb') as w:\n"
        "    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)\n"
        "    w.writeframes(b'\\x00\\x00' * 22050)\n")
    model = tmp_path / "voice.onnx"; model.write_bytes(b"x")
    service = speech.SpeechService(
        voice="test", model_path=str(model), cache_dir=tmp_path / "cache",
        command=f"{sys.executable} {script} --model {{model}} --output-file {{output}}")
    wav_bytes, duration_ms, _ = service.synthesise("Does the pain radiate?")
    assert duration_ms == 1000


def test_no_cuda_flag_is_passed(tmp_path):
    """finalize.py's VRAM sequencing assumes sole ownership of the card."""
    assert "--cuda" not in speech.TTS_COMMAND


# --- the cache -------------------------------------------------------------

def test_synthesis_is_cached_and_the_second_call_does_not_synthesise(tmp_path):
    service = service_with(tmp_path)
    wav_a, duration_a, synth_a = service.synthesise("Any nausea?")
    wav_b, duration_b, synth_b = service.synthesise("Any nausea?")

    assert wav_a == wav_b and duration_a == duration_b == 1000
    assert synth_a > 0, "a cache miss should report real synthesis time"
    assert synth_b == 0, "a cache hit reports no synthesis time"


def test_cache_is_not_shared_across_voices(tmp_path):
    a = speech.SpeechService(voice="voice_a", model_path="x", cache_dir=tmp_path)
    b = speech.SpeechService(voice="voice_b", model_path="x", cache_dir=tmp_path)
    assert a._cache_path("same words") != b._cache_path("same words")


# --- availability ----------------------------------------------------------

def test_service_reports_unavailable_without_a_model_path(tmp_path):
    service = speech.SpeechService(model_path="", cache_dir=tmp_path)
    assert service.available is False
    assert "TTS_MODEL_PATH" in service.unavailable_reason()
    with pytest.raises(speech.SpeechUnavailable, match="TTS_MODEL_PATH"):
        service.synthesise("Any nausea?")


def test_service_reports_unavailable_for_a_missing_model_file(tmp_path):
    service = speech.SpeechService(model_path=str(tmp_path / "nope.onnx"),
                                   cache_dir=tmp_path)
    assert service.available is False
    with pytest.raises(speech.SpeechUnavailable, match="not found"):
        service.synthesise("Any nausea?")


def test_service_reports_unavailable_for_a_missing_command(tmp_path):
    """The reason names the fix, because the doctor sees this text."""
    model = tmp_path / "voice.onnx"; model.write_bytes(b"x")
    service = speech.SpeechService(
        model_path=str(model), cache_dir=tmp_path,
        command="definitely-not-installed --model {model} --output-file {output}")
    assert service.available is False
    assert "definitely-not-installed" in service.unavailable_reason()
    assert "uv tool install" in service.unavailable_reason()


# --- prepare(): resolution plus synthesis ----------------------------------

def test_prepare_registers_an_utterance_carrying_its_provenance(tmp_path):
    service = service_with(tmp_path, seconds=0.5)
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


# --- real Piper ------------------------------------------------------------
#
# This is THE JOIN between the arithmetic the synthetic-WAV tests exercise
# and what Piper actually does. Everything above proves the adapter handles
# a subprocess correctly; only this proves the numbers describe real audio.

_REAL = speech.SpeechService()


@pytest.mark.skipif(
    not _REAL.available,
    reason=f"real TTS unavailable: {_REAL.unavailable_reason()}")
def test_real_synthesis_produces_plausible_audio(tmp_path):
    service = speech.SpeechService(cache_dir=tmp_path)
    question = "Does the pain go anywhere else, or does it stay in one place?"
    wav_bytes, duration_ms, synth_ms = service.synthesise(question)

    assert wav_bytes[:4] == b"RIFF"
    assert 1000 < duration_ms < speech.SPEECH_MAX_UTTERANCE_S * 1000
    assert synth_ms > 0
    assert (tmp_path / f"{speech.cache_key(question, service.voice)}.wav").exists()


@pytest.mark.skipif(
    not _REAL.available,
    reason=f"real TTS unavailable: {_REAL.unavailable_reason()}")
def test_real_wav_duration_matches_the_arithmetic_the_other_tests_use(tmp_path):
    """The join. wav_duration_ms() is what sets the exclusion window's
    ceiling, and every synthetic-WAV test above trusts it. Here it is
    applied to audio Piper genuinely produced, and cross-checked against
    the WAV header read independently."""
    service = speech.SpeechService(cache_dir=tmp_path)
    wav_bytes, duration_ms, _ = service.synthesise(speech.PHRASES["invitation"])

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        independent_ms = round(1000 * w.getnframes() / w.getframerate())
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
    assert duration_ms == independent_ms

    # And the exclusion arithmetic downstream: the window ceiling is
    # duration + tail, in bytes of 16 kHz mono PCM.
    from app.live import BYTES_PER_MS
    ceiling_bytes = (duration_ms + speech.SPEECH_EXCLUSION_TAIL_MS) * BYTES_PER_MS
    assert ceiling_bytes > duration_ms * BYTES_PER_MS


@pytest.mark.skipif(
    not _REAL.available,
    reason=f"real TTS unavailable: {_REAL.unavailable_reason()}")
def test_real_synthesis_is_cached_so_the_second_tap_is_instant(tmp_path):
    service = speech.SpeechService(cache_dir=tmp_path)
    _, _, cold_ms = service.synthesise(speech.PHRASES["go_on"])
    _, _, warm_ms = service.synthesise(speech.PHRASES["go_on"])
    assert cold_ms > 0 and warm_ms == 0


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
