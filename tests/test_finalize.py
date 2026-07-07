"""Unit tests for the deterministic parts of the finalisation pipeline."""

from app.finalize import attribute_roles
from app.notes import note_as_plain_text


def test_first_speaker_is_doctor():
    turns = [
        {"speaker": "SPEAKER_01", "text": "Good morning, what brings you in?"},
        {"speaker": "SPEAKER_00", "text": "My chest hurts."},
        {"speaker": "SPEAKER_01", "text": "Tell me more."},
    ]
    turns = attribute_roles(turns)
    assert [t["role"] for t in turns] == ["Doctor", "Patient", "Doctor"]
    assert all("speaker" not in t for t in turns)


def test_plain_text_is_emr_friendly():
    note = {
        "subjective": [{"text": "Chest pain x2 weeks", "turns": [1]}],
        "objective": [{"text": "BP 150/95", "turns": [5]}],
        "assessment": [{"text": "Stable angina", "turns": []}],
        "plan": [{"text": "ECG today", "turns": [9]}],
    }
    text = note_as_plain_text(note)
    assert text.splitlines()[0] == "S:"
    assert "  BP 150/95" in text
    assert "*" not in text and "#" not in text and "[" not in text  # no markdown/citations
    assert not text.endswith("\n\n")
