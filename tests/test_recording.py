"""The recording (R18; D54; spec 15.10, The recording): written as the
sound arrives, readable at any moment, never overwritten. The sound here
is made by code."""

import wave

import pytest

from openconsult.consult.recording import HEADER_BYTES, Recording, finish, header
from tests.test_loudness import sine


def test_R18_the_recording_is_written_as_the_sound_arrives_and_is_readable_at_any_moment(tmp_path):
    path = tmp_path / "recordings" / "consultation_1.wav"
    recording = Recording(path, 48000)
    assert path.exists() and path.stat().st_size == HEADER_BYTES
    piece = sine(0.25, -20.0, rate=48000)
    for n in range(1, 5):
        recording.add(piece)
        # Readable mid-way: a WAV of what was heard so far, at the session's rate, mono 16-bit.
        with wave.open(str(path), "rb") as made:
            assert (made.getframerate(), made.getnchannels(), made.getsampwidth()) == (48000, 1, 2)
            assert made.getnframes() == n * 12000
    assert recording.seconds == 1.0
    recording.close()
    assert not recording.open
    with pytest.raises(ValueError):
        recording.add(piece)
    assert path.read_bytes()[:HEADER_BYTES] == header(48000, 4 * len(piece))


def test_R18_D54_an_existing_recording_is_never_written_over(tmp_path):
    path = tmp_path / "consultation_1.wav"
    first = Recording(path, 16000)
    first.add(sine(0.5, -20.0))
    first.close()
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        Recording(path, 16000)
    assert path.read_bytes() == before


def test_1_12_a_file_left_open_by_a_stopped_app_is_finished_from_its_own_size(tmp_path):
    # A crash leaves the header patched to the last piece; a file written by
    # another program with a zero header is finished from its size.
    path = tmp_path / "consultation_2.wav"
    path.write_bytes(header(16000, 0) + sine(1.0, -20.0))
    assert finish(path) == 32000
    with wave.open(str(path), "rb") as made:
        assert made.getnframes() == 16000 and made.getframerate() == 16000
