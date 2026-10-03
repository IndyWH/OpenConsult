"""Task 13 item 6: the two speech-pipeline settings.

SPEECH_PIPELINE chooses whisper (default, today's path) or nemotron;
SPEECH_MAX_SPEAKERS bounds the live diariser and defaults to today's
pyannote count. An unknown pipeline is a configuration error that blocks
recording — never a quiet fallback to whisper.
"""

import os
from pathlib import Path

from app import finalize, speech_pipeline


def test_env_example_carries_both_settings_with_their_defaults():
    env = Path(".env.example").read_text()
    assert "\nSPEECH_PIPELINE=whisper\n" in env
    assert "\nSPEECH_MAX_SPEAKERS=2\n" in env


def test_the_defaults_are_whisper_and_todays_pyannote_count():
    if "SPEECH_PIPELINE" not in os.environ:
        assert speech_pipeline.SPEECH_PIPELINE == "whisper"
    if "SPEECH_MAX_SPEAKERS" not in os.environ:
        # Owner, at approval: the same number of speakers as today's call.
        assert speech_pipeline.SPEECH_MAX_SPEAKERS == finalize.DEFAULT_SPEAKERS == 2


def test_whisper_is_valid_and_is_not_nemotron(monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "whisper")
    assert speech_pipeline.configuration_error() is None
    assert speech_pipeline.uses_nemotron() is False


def test_nemotron_is_valid_and_is_nemotron(monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemotron")
    assert speech_pipeline.configuration_error() is None
    assert speech_pipeline.uses_nemotron() is True


def test_an_unknown_pipeline_is_an_error_and_never_read_as_whisper(monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemo")
    error = speech_pipeline.configuration_error()
    assert error is not None and "'nemo'" in error and "Recording is off" in error
    # Not whisper: the live path must block, not fall back.
    assert speech_pipeline.uses_nemotron() is True


def test_zero_speakers_is_an_error(monkeypatch):
    monkeypatch.setattr(speech_pipeline, "SPEECH_PIPELINE", "nemotron")
    monkeypatch.setattr(speech_pipeline, "SPEECH_MAX_SPEAKERS", 0)
    assert "SPEECH_MAX_SPEAKERS" in speech_pipeline.configuration_error()
