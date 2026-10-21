"""The recording kept as Opus (spec 15.11 ruling 7; R18; R30). After
Stop's final step the WAV written as the sound arrived is converted to
Ogg Opus, mono at 32 kbps with the voice setting, the new file is
decoded back by the same converter and its length set against the WAV's
within DURATION_TOLERANCE_S, and only then is the WAV removed and the
format recorded. A failure leaves the WAV, removes any part-written
Ogg, and records the reason, shown on the consultation's page. The
converter is ffmpeg: the one the imageio-ffmpeg package carries for
Linux, macOS and Windows, found by uv, or else the computer's own on
the path; the room check reports which, or none. Every line's time is
against the file's start, so the player plays the same from either."""

from __future__ import annotations

import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from openconsult import words

# Decoded Opus against the WAV: on this machine a made 1 s and a made
# 7.37 s WAV came back to the sample (ffmpeg n9.0.2, 21 Oct 2026); Opus
# frames are 20 ms and the decoder trims the encoder's pre-skip (6.5 ms)
# and its end padding. 0.1 s is five frames: far above that, far below
# a lost stretch of speech.
DURATION_TOLERANCE_S = 0.1
DECODE_RATE = 48000
ENCODE_ARGS = ["-ac", "1", "-c:a", "libopus", "-b:a", "32k", "-application", "voip"]
COMMAND_TIMEOUT_S = 600
PACKAGE, SYSTEM = "package", "system"


@dataclass(frozen=True)
class Converter:
    """One ffmpeg: where it came from, its path and its version."""
    path: str
    source: str        # package or system
    version: str

    def encode(self, wav: Path, ogg: Path, run: Callable = subprocess.run) -> str | None:
        """None when the Ogg was written, else the reason."""
        try:
            done = run([self.path, "-y", "-loglevel", "error", "-i", str(wav), *ENCODE_ARGS, str(ogg)],
                       capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return str(error)
        return None if done.returncode == 0 else (done.stderr.strip() or f"exit code {done.returncode}")

    def decoded_seconds(self, ogg: Path, run: Callable = subprocess.run) -> float | None:
        """The seconds the file plays for: decoded to raw 16-bit mono at
        48,000 a second on a pipe, the bytes counted. None when it cannot
        be decoded."""
        try:
            done = run([self.path, "-loglevel", "error", "-i", str(ogg), "-f", "s16le", "-ar", str(DECODE_RATE), "-ac", "1", "-"],
                       capture_output=True, timeout=COMMAND_TIMEOUT_S)
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        return len(done.stdout) / (2 * DECODE_RATE)


def _package_exe() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:          # no binary for this system, or the package absent
        return None


def version_of(path: str, run: Callable = subprocess.run) -> str | None:
    """The version from ffmpeg -version, or None when it will not run or
    its build has no Opus encoder."""
    try:
        done = run([path, "-version"], capture_output=True, text=True, timeout=30)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 or "libopus" not in done.stdout:
        return None
    first = done.stdout.splitlines()[0] if done.stdout else ""
    parts = first.split()
    return parts[2] if len(parts) > 2 and parts[0] == "ffmpeg" else first.strip() or None


def find_converter(which: Callable = shutil.which, package: Callable = _package_exe,
                   run: Callable = subprocess.run) -> Converter | None:
    """The package's ffmpeg first, the same on the three systems; else the
    computer's own on the path; else none. Each must run and hold libopus."""
    for source, path in ((PACKAGE, package()), (SYSTEM, which("ffmpeg"))):
        if path:
            version = version_of(path, run)
            if version:
                return Converter(path, source, version)
    return None


# ------------------------------------------------------------- the job

def wav_seconds(path: Path) -> float:
    """From the header, as the recording module writes it."""
    with open(path, "rb") as fh:
        fh.seek(24)
        (rate,) = struct.unpack("<I", fh.read(4))
    data_bytes = max(0, path.stat().st_size - 44)
    return data_bytes / (2 * rate) if rate else 0.0


@dataclass(frozen=True)
class Outcome:
    ok: bool
    file_name: str | None       # the Ogg's name when ok
    reason: str | None
    wav_bytes: int = 0
    ogg_bytes: int = 0
    wav_s: float = 0.0
    ogg_s: float = 0.0


def convert_file(converter: Converter | None, wav: Path, tolerance_s: float = DURATION_TOLERANCE_S) -> Outcome:
    """The WAV to an Ogg beside it; the check; the WAV removed only after
    the check passed. A failure leaves the WAV and no Ogg."""
    if converter is None:
        return Outcome(False, None, words.CONVERSION_NO_CONVERTER)
    if not wav.is_file():
        return Outcome(False, None, words.CONVERSION_NO_WAV)
    ogg = wav.with_suffix(".ogg")
    wav_s, wav_bytes = wav_seconds(wav), wav.stat().st_size
    reason = converter.encode(wav, ogg)
    if reason is None:
        ogg_s = converter.decoded_seconds(ogg)
        if ogg_s is None:
            reason = words.CONVERSION_NOT_PLAYABLE
        elif abs(ogg_s - wav_s) > tolerance_s:
            reason = words.CONVERSION_LENGTH_DIFFERS.format(wav=f"{wav_s:.2f}", opus=f"{ogg_s:.2f}")
    if reason is not None:
        if ogg.exists():
            ogg.unlink()
        return Outcome(False, None, reason, wav_bytes, 0, wav_s, 0.0)
    ogg_bytes = ogg.stat().st_size
    wav.unlink()
    return Outcome(True, ogg.name, None, wav_bytes, ogg_bytes, wav_s, ogg_s)


def convert_consultation(c) -> Outcome | None:
    """The job after Stop's final step (ruling 7): the row names the file,
    the outcome goes to the row and the audit log. None when there is no
    recording to convert."""
    from openconsult.consult.recording import folder_of
    row = c.rows.get(c.id)
    if not row or not row["recording_file"] or not row["recording_file"].endswith(".wav"):
        return None
    outcome = convert_file(c.converter, folder_of(c.data_folder) / row["recording_file"])
    if c.converter is None:
        # Nothing was attempted: the page says why the WAV stays; the start's decision line already says no converter was found.
        c.rows.set(c.id, recording_format="wav", conversion_failure=outcome.reason)
        return outcome
    if outcome.ok:
        c.rows.set(c.id, recording_file=outcome.file_name, recording_format="opus", conversion_failure=None)
        c.audit.record("recording.converted", f"consultation {c.id}: {outcome.wav_bytes} bytes WAV to {outcome.ogg_bytes} "
                                              f"bytes Opus, {outcome.ogg_s:.2f} s")
    else:
        c.rows.set(c.id, recording_format="wav", conversion_failure=outcome.reason)
        c.audit.record("recording.conversion_failed", f"consultation {c.id}: {outcome.reason}")
    return outcome
