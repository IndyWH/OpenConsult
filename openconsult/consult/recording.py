"""The recording (R18; D54; spec 15.10, The recording; 15.9 ruling 7):
one WAV file in the recordings folder, written as the sound arrives,
mono 16-bit at the session's rate, and never overwritten. The header's
sizes are patched after every piece, so a file left by a crash or a
dropped connection is still a readable WAV of what was heard. Every
line's times are against the start of this file."""

from __future__ import annotations

import struct
from pathlib import Path

FOLDER = "recordings"
HEADER_BYTES = 44


def header(rate: int, data_bytes: int) -> bytes:
    """A canonical 44-byte WAV header for 16-bit mono PCM."""
    return (b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", data_bytes))


def folder_of(data_folder: Path) -> Path:
    return Path(data_folder) / FOLDER


def file_name(consultation_id: int) -> str:
    return f"consultation_{consultation_id}.wav"


class Recording:
    """Opened for exclusive creation: an existing file is refused, never
    written over (R18; D54)."""

    def __init__(self, path: Path, rate: int):
        if rate <= 0:
            raise ValueError("the rate is samples a second")
        self.path = Path(path)
        self.rate = int(rate)
        self.data_bytes = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "xb")  # noqa: SIM115 - held open while the consultation runs
        self._file.write(header(self.rate, 0))
        self._file.flush()

    @property
    def seconds(self) -> float:
        return self.data_bytes / (2 * self.rate)

    @property
    def open(self) -> bool:
        return not self._file.closed

    def add(self, pcm: bytes) -> None:
        if self._file.closed:
            raise ValueError("the recording is closed")
        even = pcm[: len(pcm) - len(pcm) % 2]
        self._file.seek(HEADER_BYTES + self.data_bytes)
        self._file.write(even)
        self.data_bytes += len(even)
        self._file.seek(0)
        self._file.write(header(self.rate, self.data_bytes))
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.flush()
            self._file.close()


def finish(path: Path) -> int:
    """Patch the header of a file left open by a stopped app from the file's
    own size, so it reads as a whole WAV. Returns the data bytes."""
    path = Path(path)
    size = path.stat().st_size
    data_bytes = max(0, size - HEADER_BYTES)
    with open(path, "r+b") as fh:
        fh.seek(16)
        (_, _, _, rate) = struct.unpack("<IHHI", fh.read(12))
        fh.seek(0)
        fh.write(header(rate, data_bytes))
    return data_bytes
