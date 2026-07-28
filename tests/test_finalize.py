"""Unit tests for the deterministic parts of the finalisation pipeline."""

from app.finalize import attribute_roles
from app.notes import note_as_plain_text


def test_first_speaker_is_doctor():
    turns = [
        {"speaker": "SPEAKER_01", "text": "Good morning, what brings you in?"},
        {"speaker": "SPEAKER_00", "text": "My chest hurts."},
        {"speaker": "SPEAKER_01", "text": "Tell me more."},
    ]
    turns, single_voice = attribute_roles(turns)
    assert [t["role"] for t in turns] == ["Doctor", "Patient", "Doctor"]
    assert all("speaker" not in t for t in turns)
    assert single_voice is False


def test_a_single_speaker_cluster_is_the_patient_and_is_flagged():
    """2026-07-28. pyannote used to be given a fixed num_speakers=2, so one
    human in the room was SPLIT into two clusters and half of that person's
    speech was labelled Doctor — the defect in 446, 447 and 448.

    With the count unpinned, one voice now stays one cluster, and the label
    must not be Doctor. In tap-to-ask the machine asks the questions, so a
    lone human voice is answering them: Patient. This is a DEFAULT, which is
    why the flag matters as much as the label — review must say the roles
    were not determined from the audio.
    """
    turns = [
        {"speaker": "SPEAKER_00", "text": "Oh hi, I have tummy ache."},
        {"speaker": "SPEAKER_00", "text": "No, I don't have any of those symptoms."},
    ]
    turns, single_voice = attribute_roles(turns)
    assert [t["role"] for t in turns] == ["Patient", "Patient"]
    assert single_voice is True
    assert all("speaker" not in t for t in turns)


def test_no_turns_is_not_a_single_voice():
    """An empty transcript has no speaker to be uncertain about; flagging it
    would put a "check the roles" banner on a consultation with no roles."""
    turns, single_voice = attribute_roles([])
    assert turns == []
    assert single_voice is False


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
