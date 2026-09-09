"""Speech synthesis and reference resolution (app/speech.py, Phase 7a).

What these tests are evidence about, stated plainly because it matters:

- The **reference-only** design is tested for real. Resolution is pure
  logic over the phrase table and the server's own agenda log, so every
  assertion below about "the client cannot supply words" is a genuine
  test of the shipped mechanism.
- **Synthesis is real, but mostly stubbed.** Piper runs as a SUBPROCESS
  from its own environment (there is no `import piper` in the app), so
  most tests here drive a fake command — a real subprocess writing a
  known-length WAV, because running a subprocess is precisely the
  adapter's job and faking at the function boundary would test nothing.
  The handful of `test_real_*` tests do call Piper, and self-skip with a
  clear reason when the command or voice is absent. They are the join
  between the arithmetic everything else trusts and what Piper actually
  produces.
- **Nothing here drives a browser.** The sound-check tests below cover
  classification, the endpoints and the audit row; whether the control
  actually plays audio into a room is what the real-room check in
  HANDOVER is for.
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
        "tell_me_more_short",   # owner decision 2026-09-09, the golden window's second phrasing
        "let_me_think",         # owner decision 2026-09-09, the thinking phrase (replaces the bridge)
        "examination_handover",
        "sound_check",   # spec Part 10, added 2026-07-25
        "silence_nudge",  # session 3, the ONLY autonomous utterance in 7a/7b
        "anything_else",  # Phase 7c §4 item 4, the invitation-class follow-up
    }


def test_the_silence_nudge_wording_is_the_owners_verbatim():
    """Session 3: the owner's wording, word for word — it is a sentence a
    patient hears, so a silent edit is a clinical-communication change."""
    assert speech.PHRASES["silence_nudge"] == (
        "When you're ready, tell me what's brought you in today.")


def test_spec_quoted_wording_is_verbatim():
    """PHASE_7A_SPEC.md Part 5 quotes four of these exactly."""
    assert speech.PHRASES["invitation"] == "Please, tell me what's brought you in."
    assert speech.PHRASES["mm-hm"] == "Mm-hm."
    assert speech.PHRASES["i_see"] == "I see."
    assert speech.PHRASES["go_on"] == "Go on."
    assert speech.render_phrase("examination_handover", "Herath") == \
        "Thank you — Dr Herath will examine you now."


def test_the_approved_disclosure_is_verbatim():
    """Owner-approved 2026-07-25, amended by the owner 2026-07-28 to say
    "them" rather than "him". Asserted word for word, not by substance: this
    is the sentence a patient hears, and a silent edit to it is a
    clinical-communication change nobody signed off."""
    assert speech.render_phrase("disclosure", "Herath") == (
        "Hello. I'm a computer, not a person. I'll ask you some questions "
        "about what's brought you in. Dr Herath is here with you and you "
        "can speak to them at any time.")


def test_the_disclosure_does_not_assume_the_doctor_is_male():
    """The 2026-07-28 amendment, pinned as its own assertion so a revert
    fails loudly rather than reading as a wording tweak. The doctor is a real
    named person and the patient is being told about them."""
    text = speech.render_phrase("disclosure", "Herath")
    assert "speak to them at any time" in text
    assert " him" not in text and " his " not in text


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
            assert bad not in lowered, f"{phrase_id} may be advising: {lowered!r}"


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
        {"display_name": None, "username": "doc2"}) == "doc2"


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
                                                    "examination_handover",
                                                    "silence_nudge",
                                                    "anything_else"}  # 7c: a question
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


def test_the_kill_switch_refuses_regardless_of_a_working_setup(tmp_path, monkeypatch):
    """TTS_ENABLED=false must win over an otherwise working configuration:
    it is how a deployment without a synthesiser (the container, where
    piper is deliberately outside the image) declines to advertise a
    voice it does not have. Never covered before the in-container suite
    made the switch's reach visible."""
    monkeypatch.setattr(speech, "TTS_ENABLED", False)
    service = service_with(tmp_path, seconds=0.5)
    assert service.available is False
    assert service.unavailable_reason() == "TTS_ENABLED=false"
    with pytest.raises(speech.SpeechUnavailable, match="TTS_ENABLED"):
        service.synthesise("Any nausea?")


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


@pytest.fixture(autouse=True)
def tts_enabled(monkeypatch):
    """Pin the deployment kill-switch ON for this file.

    Everything here drives SpeechService through explicit fake commands
    and tmp paths, so none of it needs a real synthesiser — but the
    module-level TTS_ENABLED reads the ambient environment, and a
    deployment that sets it false (the container deliberately ships
    without piper) would short-circuit every construction to the same
    refusal and turn this file's evidence into noise. Found 2026-08-04 by
    the first in-container run. The switch itself is asserted by
    test_the_kill_switch_refuses_regardless_of_a_working_setup, which
    re-patches it off."""
    monkeypatch.setattr(speech, "TTS_ENABLED", True)


@pytest.fixture(autouse=True)
def speech_service():
    """Guarantee a REAL SpeechService on app.state for every test in this file,
    and put back whatever was there before.

    These tests used to depend on collection order twice over (found
    2026-07-28 by running the suite in reverse). `_register` created the
    service lazily and left it behind, so the sound-check tests — which never
    call `_register` — only worked because some earlier test in this file had
    already installed one. Run first, they raised
    `AttributeError: 'State' object has no attribute 'speech'`.

    Depending on another test having set up your state is the same fault as
    leaking state into another test; it just fails in the opposite direction.
    """
    from app.main import app
    from app import speech as speech_module

    missing = object()
    previous = getattr(app.state, "speech", missing)
    if not isinstance(previous, speech_module.SpeechService):
        app.state.speech = speech_module.SpeechService()
    try:
        yield app.state.speech
    finally:
        if previous is missing:
            delattr(app.state, "speech")
        else:
            app.state.speech = previous


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
    """Put a prepared utterance in the running app's service, without Piper.

    The service is provided by the autouse `speech_service` fixture — this used
    to create it lazily and leave it installed for whatever ran next.
    """
    from app.main import app

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


# --- the sound check (spec Part 10) ----------------------------------------
#
# Why it exists, restated because it governs what these tests must prove:
# a dead speaker fails SILENTLY. Playback succeeds, nothing errors, the
# patient hears nothing — and because the exclusion window opens anyway,
# whatever the patient says during that inaudible utterance is dropped
# from the transcript by construction. A dead speaker converts quietly
# into missing transcript.

def test_the_sound_check_never_claims_the_room_heard_it_on_headphones():
    """450 reported "Heard clearly. The room can hear the machine." AND, in the
    same breath, that no sound reached the microphone. Both cannot be true — on
    headphones the ROOM heard nothing and only the doctor did.

    What the human answer establishes is that HE heard it. Whether the room can
    is exactly what an absent acoustic path leaves untested, so the panel must
    not assert it."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    show = html[html.index("function showSoundCheckResult("):]
    show = show[:show.index("\n}")]
    # The room claim survives ONLY where there is an acoustic path.
    assert "'Heard clearly. The room can hear the machine.'" in show
    assert "const headphones = verdict.discrepancy ===" in show
    assert "'You confirmed hearing it clearly.'" in show, (
        "on headphones, report what the doctor confirmed, not what the room did")
    assert "Whether the room can hear the machine was not tested." in show
    assert "expected on headphones" in show   # still not framed as a warning


def test_the_headphones_explanation_is_conditional_unless_the_label_says_so():
    """Session 3 wording fix. In the room on 2026-07-28 the panel said "no
    sound reached the microphone, which is expected on headphones" while the
    recorded output device was the monitor's NVIDIA HD Audio — a notice
    asserting something untrue about the setup teaches the doctor to discount
    it (the single-voice notice lesson, again).

    The message must report what is KNOWN: the doctor's confirmation, the
    measured level, and the output device by name. The flat headphones claim
    survives only when the device label itself indicates headphones; otherwise
    the explanation is the conditional "expected if the output is headphones"."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    show = html[html.index("function showSoundCheckResult("):]
    show = show[:show.index("\n}")]
    # The two variants, keyed on the device label — not on a guess.
    assert "labelSaysHeadphones" in show
    assert "/headphone|headset|earbud|earphone|airpod|buds/i.test(device)" in show
    assert "expected if the output is headphones" in show
    # The flat claim is inside the label-confirmed branch only: the string
    # LITERAL (not the comment retelling the incident) appears exactly
    # once, after the labelSaysHeadphones guard.
    flat = "' — no sound reached the microphone, which is expected on headphones. '"
    assert show.count(flat) == 1
    assert show.index("labelSaysHeadphones") < show.index(flat)
    # The device is still named with every reading.
    assert "' · output: ' + device" in show


def test_every_sound_check_reading_carries_its_output_device():
    """A level without its path is not a measurement. The three readings so far
    — 27 dB, 15 dB, 4 dB — cannot be compared because the audio path differed
    each time and nothing recorded which one it was, which makes them useless
    for setting the thresholds they were collected to set."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    # Displayed with the reading...
    show = html[html.index("function showSoundCheckResult("):]
    show = show[:show.index("\n}")]
    assert "' · output: '" in show
    # ...and resolved to a human-readable LABEL, not the device id that used to
    # be sent (audioCtx.sinkId is empty for the default device, so it recorded
    # nothing at all).
    resolver = html[html.index("async function outputDeviceLabel("):]
    resolver = resolver[:resolver.index("\n}")]
    assert "enumerateDevices()" in resolver
    assert "d.kind === 'audiooutput'" in resolver
    assert "(system default)" in resolver, (
        "the default device must be named, not left blank")
    assert "await outputDeviceLabel(audio)" in html


def test_the_sound_check_phrase_is_the_approved_wording():
    """Deliberately not clinical and not addressed to the patient — it is
    a check spoken in the room and should sound like one (spec 10.4)."""
    assert speech.PHRASES["sound_check"] == \
        "Sound check. If you can hear this clearly, press yes."


def test_the_sound_check_phrase_resolves_like_any_other():
    resolution = speech.resolve({"kind": "phrase", "id": "sound_check"})
    assert resolution.text == speech.PHRASES["sound_check"]
    assert resolution.ref_kind == "phrase"


def test_the_sound_check_phrase_is_not_disclosure_gated():
    """It is spoken before a consultation starts, to the room rather than
    to the patient, so hard rule 4 does not reach it."""
    assert "sound_check" not in speech.DISCLOSURE_GATED_PHRASES


def test_the_sound_check_phrase_synthesises(tmp_path):
    service = service_with(tmp_path, seconds=2.0)
    wav_bytes, duration_ms, _ = service.synthesise(speech.PHRASES["sound_check"])
    assert wav_bytes[:4] == b"RIFF" and duration_ms == 2000


# The four result classes (spec 10.2 table). Pure classification, so all
# four are reachable without a browser, a speaker or a room.

def test_class_heard_good_needs_energy_clearly_above_the_floor_and_a_yes():
    verdict = speech.classify_sound_check(
        noise_floor_rms=2e-4, peak_rms=2e-3, answer="yes")
    assert verdict["result"] == speech.RESULT_HEARD_GOOD
    assert verdict["discrepancy"] is None
    assert verdict["level"]["ratio"] == pytest.approx(10.0)
    assert verdict["level"]["ratio_db"] == pytest.approx(20.0, abs=0.2)


def test_class_heard_faint_is_marginally_above_the_floor():
    """Faint must read differently from silent: it predicts both a patient
    who strains and an unreliable barge-in detector later."""
    verdict = speech.classify_sound_check(
        noise_floor_rms=2e-4, peak_rms=4.4e-4, answer="yes")
    assert verdict["result"] == speech.RESULT_HEARD_FAINT
    assert (speech.SOUND_CHECK_FAINT_RATIO
            <= verdict["level"]["ratio"] < speech.SOUND_CHECK_GOOD_RATIO)


def test_class_not_heard_is_the_doctor_saying_no():
    verdict = speech.classify_sound_check(
        noise_floor_rms=2e-4, peak_rms=1e-6, answer="no")
    assert verdict["result"] == speech.RESULT_NOT_HEARD


def test_class_unverified_when_the_doctor_declines():
    """Recorded as unverified rather than as a pass — the doctor may have
    good reason to skip, and the system does not get to call that a pass."""
    for answer in ("skip", None, ""):
        verdict = speech.classify_sound_check(
            noise_floor_rms=2e-4, peak_rms=2e-3, answer=answer)
        assert verdict["result"] == speech.RESULT_UNVERIFIED
    # The level is still measured and recorded, even unverified.
    assert verdict["level"]["peak_rms"] > 0


def test_headphones_are_not_a_warning():
    """Headphones defeat the acoustic path, so energy absent plus a yes is
    expected. The human answer is authoritative: accept it, record the
    discrepancy, do not warn (spec 10.2)."""
    verdict = speech.classify_sound_check(
        noise_floor_rms=2e-4, peak_rms=0.0, answer="yes")
    assert verdict["result"] == speech.RESULT_HEARD_GOOD
    assert verdict["discrepancy"] == "no_acoustic_path_headphones_likely"


def test_the_human_answer_beats_the_measurement_in_both_directions():
    """Energy present but the doctor says no is still not_heard — the
    discrepancy is recorded rather than argued with."""
    verdict = speech.classify_sound_check(
        noise_floor_rms=2e-4, peak_rms=5e-3, answer="no")
    assert verdict["result"] == speech.RESULT_NOT_HEARD
    assert verdict["discrepancy"] == "energy_present_but_doctor_says_no"


def test_the_silence_floor_is_the_mic_clusters_own_number():
    """Not a new invented threshold: the live page's dead-mic pill already
    treats this RMS as no signal. Reusing it means the two surfaces cannot
    disagree about what silence is."""
    assert speech.SOUND_CHECK_SILENT_RMS == pytest.approx(1e-4)
    from pathlib import Path
    assert "1e-4" in Path("app/static/live.html").read_text()


def test_a_dead_quiet_room_cannot_fake_a_pass_through_the_ratio():
    """In a near-silent room the ratio can be large on noise alone, so the
    absolute floor has to bite as well."""
    verdict = speech.classify_sound_check(
        noise_floor_rms=1e-9, peak_rms=5e-5, answer="yes")
    assert verdict["discrepancy"] == "no_acoustic_path_headphones_likely"


def test_levels_are_recorded_raw_for_later_calibration():
    """Item 4's requirement: scripts/calibrate_barge_in.py should read
    these rather than re-measure, since the loopback level is exactly the
    input its envelope-proportional threshold needs. So the raw numbers
    and the thresholds in force are both stored."""
    verdict = speech.classify_sound_check(
        noise_floor_rms=3e-4, peak_rms=1.5e-3, mean_rms=9e-4, answer="yes")
    level = verdict["level"]
    for field in ("noise_floor_rms", "peak_rms", "mean_rms", "ratio",
                  "ratio_db", "good_ratio", "faint_ratio", "silent_rms"):
        assert field in level, field
    assert level["mean_rms"] == pytest.approx(9e-4)
    assert level["good_ratio"] == speech.SOUND_CHECK_GOOD_RATIO


def test_the_thresholds_are_env_tunable_because_they_are_guesses():
    """They are uncalibrated: nobody has measured this room, speaker or
    microphone. Being env-settable is how the owner sets them from his."""
    assert speech.SOUND_CHECK_GOOD_RATIO > speech.SOUND_CHECK_FAINT_RATIO > 1.0


# --- the sound-check endpoints ---------------------------------------------

@needs_db
def test_sound_check_prepares_an_utterance_and_audits_the_result():
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    from app.main import app
    app.state.live_sessions = {}

    started = client.post("/api/speech/sound-check")
    if started.status_code == 503:
        pytest.skip(f"TTS unavailable: {started.json().get('error')}")
    assert started.status_code == 200
    body = started.json()
    assert body["text"] == speech.PHRASES["sound_check"]
    assert body["url"] == f"/api/speech/{body['utterance_id']}.wav"
    assert body["duration_ms"] > 0
    # And the audio really is fetchable by the doctor who asked for it.
    assert client.get(body["url"]).status_code == 200

    result = client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 2e-4, "peak_rms": 2e-3, "mean_rms": 1e-3,
        "answer": "yes", "device_label": "Speakers (Realtek)"})
    assert result.status_code == 200
    assert result.json()["result"] == speech.RESULT_HEARD_GOOD
    # Echoed back, so the panel shows the device that was RECORDED rather than
    # one the client re-derives: a reading and its audio path must not be able
    # to disagree about which path it was (450 — three readings, 27/15/4 dB,
    # uncomparable because nothing recorded the path).
    assert result.json()["output_device"] == "Speakers (Realtek)"

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        row = conn.execute(
            "SELECT user_id, at, detail FROM audit_event"
            " WHERE action = 'speech.sound_check' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    user_id, at, detail = row
    assert user_id == doctor["id"]
    assert at is not None                       # the timestamp spec 10.5 asks for
    assert detail["result"] == speech.RESULT_HEARD_GOOD
    assert detail["answer"] == "yes"
    assert detail["device_label"] == "Speakers (Realtek)"
    # The measured level, raw, for later calibration.
    assert detail["peak_rms"] == pytest.approx(2e-3)
    assert detail["noise_floor_rms"] == pytest.approx(2e-4)
    assert detail["ratio"] == pytest.approx(10.0)


@needs_db
def test_sound_check_records_the_capture_chain_it_was_measured_through():
    """The device-label lesson applied before it bites twice (2026-07-30):
    a level without its processing chain is not a measurement either. The
    client reports the ec/ns/agc it requested; the row stores it; the
    calibration report pools only within one device AND one chain. Rows
    without the field (pre-change) are handled as incomparable there."""
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    from app.main import app
    app.state.live_sessions = {}

    result = client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 2e-4, "peak_rms": 2e-3, "answer": "yes",
        "device_label": "Speakers (Realtek)",
        "chain": {"ec": False, "ns": True, "agc": True}})
    assert result.status_code == 200

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        detail = conn.execute(
            "SELECT detail FROM audit_event"
            " WHERE action = 'speech.sound_check' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert detail["chain"] == {"ec": False, "ns": True, "agc": True}

    # And the client sends the SAME object that built the capture
    # constraints — the single source, so a stored measurement can never
    # disagree about the chain that made it.
    from pathlib import Path
    html = Path("app/static/live.html").read_text()
    assert "chain: CAPTURE_CHAIN," in html


@needs_db
def test_sound_check_is_refused_during_a_consultation():
    """Spec 10.3. A test phrase inside a live consultation would be a
    system utterance needing the whole exclusion machinery for no clinical
    benefit. The UI disables the button; this is the server saying the
    same thing, because a disabled button is a courtesy and a refusal is a
    rule."""
    from app.main import app

    doctor = _make_user("doctor")
    client = _client_for(doctor)
    app.state.live_sessions = {
        "s1": {"attached": True, "user": doctor},
    }
    try:
        response = client.post("/api/speech/sound-check")
        assert response.status_code == 409
        assert "system utterance" in response.json()["error"]
    finally:
        app.state.live_sessions = {}


@needs_db
def test_another_doctors_live_session_does_not_block_the_check():
    from app.main import app

    doctor, other = _make_user("doctor"), _make_user("doctor")
    client = _client_for(doctor)
    app.state.live_sessions = {"s1": {"attached": True, "user": other}}
    try:
        response = client.post("/api/speech/sound-check")
        assert response.status_code in (200, 503)   # 503 only if TTS is absent
    finally:
        app.state.live_sessions = {}


@needs_db
def test_receptionist_cannot_run_a_sound_check():
    client = _client_for(_make_user("receptionist"))
    assert client.post("/api/speech/sound-check").status_code == 403
    assert client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 1e-4, "peak_rms": 1e-3, "answer": "yes"}
    ).status_code == 403


@needs_db
def test_an_unverified_check_is_audited_as_unverified_not_as_a_pass():
    doctor = _make_user("doctor")
    client = _client_for(doctor)
    response = client.post("/api/speech/sound-check/result", json={
        "noise_floor_rms": 2e-4, "peak_rms": 2e-3, "answer": "skip"})
    assert response.json()["result"] == speech.RESULT_UNVERIFIED

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        detail = conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'speech.sound_check'"
            " ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert detail["result"] == speech.RESULT_UNVERIFIED


def test_the_control_is_labelled_and_is_not_a_cogwheel():
    """Spec 10.2: settings iconography reads as configuration rather than
    as test, and icon-only controls cost a beat on every use."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert 'id="soundCheckBtn"' in html
    assert "<span>Sound check</span>" in html
    assert "cogwheel" not in html.lower() or "not a cogwheel" in html


def test_the_check_measures_from_the_existing_capture_stream():
    """The mic-cluster invariant stands (spec 10.3): one capture, so the
    meter cannot disagree with what the server hears. No second stream
    FOR THE SOUND CHECK.

    AMENDED for 7a session 3, not weakened: this used to assert exactly
    one getUserMedia in the whole page, which was true until the barge-in
    detector landed — the spec (§1.4) requires the detector to open its
    own echo-cancelled stream. The sharper invariant is that the second
    call is the detector's and ONLY the detector's: the sound check and
    the meter still read the shared capture, and any third stream is a
    regression. The detector-vs-meter separation itself is enforced in
    tests/test_barge_in_constraints.py."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "do\n// NOT open a second stream" in html or \
        "NOT open a second stream" in html
    # It reads the shared analyser rather than calling getUserMedia again.
    assert "analyser.getFloatTimeDomainData" in html
    calls = html.count("navigator.mediaDevices.getUserMedia")
    assert calls == 2, f"expected the capture + the detector, found {calls}"
    # The second call is inside the detector section, nowhere else. Since
    # the Part 10 amendment (2026-07-30) it lives in openDetectorStream —
    # the ONE acquisition point shared by the detector and the sound
    # check's residual measurement, so a third stream is still impossible.
    detector = html[html.index("function openDetectorStream"):
                    html.index("function stopBargeDetector")]
    assert detector.count("navigator.mediaDevices.getUserMedia") == 1


def test_the_offer_never_intercepts_a_tap():
    """Consultation 446: the offer SWALLOWED the first question-chip tap
    and showed a banner instead — and only question chips, so phrases
    spoke normally while questions silently did not. Two utterances went
    out all evening, both phrases, no questions at all.

    It is now passive: shown on connect, dismissed by running or skipping,
    and it holds no callback to resume."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "offerSoundCheckThen" not in html, "the interceptor must not return"
    assert "pendingQuestionTap" not in html, "nothing may hold a swallowed tap"
    assert "The offer is PASSIVE. It never intercepts anything." in html
    assert "soundCheckDone = true;   // offered once per session" in html


def test_questions_and_phrases_take_the_same_path():
    """There is no reason a spoken phrase should bypass a check that a
    spoken question does not. Both now call requestSpeak directly."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    qlist = html[html.index("document.getElementById('qList').addEventListener"):]
    qlist = qlist[:qlist.index("});")]
    assert "requestSpeak({kind: 'cds_question'" in qlist
    # Neither path consults the sound check before speaking.
    phrases = html[html.index("document.querySelectorAll('.phrase').forEach(button"):]
    phrases = phrases[:phrases.index("\n});")]
    assert "requestSpeak(" in phrases
    for path in (qlist, phrases):
        assert "soundCheck" not in path, "speaking must not depend on the check"
