"""Sound files for the bench (spec 15.9, the details of 5c): WAV, 16-bit,
one channel, read with what Python already has, for reading only. The
pieces are those the live page will send, as the self-test cuts them
(13.4 rule 1)."""

from __future__ import annotations

import wave
from pathlib import Path

from openconsult.speech.selftest import PIECE_S, pieces

__all__ = ["PIECE_S", "BadSound", "pieces", "read_wav", "seconds_of"]


class BadSound(Exception):
    """Not WAV, 16-bit, one channel at the rate the list gives."""


def read_wav(path: Path, rate: int) -> bytes:
    """The samples of a WAV file as 16-bit little-endian PCM, once its
    header says one channel, 16 bits and the rate expected."""
    try:
        with wave.open(str(path), "rb") as sound:
            if sound.getnchannels() != 1 or sound.getsampwidth() != 2 or sound.getframerate() != int(rate):
                raise BadSound(f"{path.name}: {sound.getnchannels()} channel(s), {8 * sound.getsampwidth()} bits, "
                               f"{sound.getframerate()} samples a second; expected 1, 16, {rate}")
            return sound.readframes(sound.getnframes())
    except (wave.Error, EOFError) as exc:
        raise BadSound(f"{path.name}: not a WAV file ({exc})") from None


def seconds_of(pcm: bytes, rate: int) -> float:
    return len(pcm) / 2 / int(rate)
