"""Made-up recordings for the speech bench's tests: a few seconds of made
sound as WAV, with a banked list beside them. Nothing here is a
recording of anyone."""

from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

from tests.test_loudness import silence, sine

SCRIPT = """# A made-up script

**Fictional patient:** Someone Made-up, 40

**DOCTOR:** Any chest pain at rest, or when you climb the stairs?
**PATIENT:** No chest pain at rest. I take metformin and co-codamol.
**DOCTOR:** *(nods)* Your blood pressure is one hundred and fifty over ninety five.
**PATIENT:** Is that high?
**DOCTOR:** If the pain comes at rest, go straight to the hospital. Understood?
**PATIENT:** Understood, doctor.
"""
SCRIPT_SHA256 = hashlib.sha256(SCRIPT.encode("utf-8")).hexdigest()


def write_wav(path: Path, pcm: bytes, rate: int = 16000) -> str:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def made_sound(seconds: float = 3.0, rate: int = 16000) -> bytes:
    """Half a second of quiet, then speech-like sound, then quiet."""
    loud = max(0.25, seconds - 1.0)
    return silence(0.5, rate) + sine(loud, -20.0, rate) + silence(seconds - 0.5 - loud, rate)


def entry(name: str, file: str, sha256: str, **over) -> dict:
    made = {"name": name, "file": file, "sha256": sha256, "script": "made_up.md", "script_key": "MU",
            "script_sha256": SCRIPT_SHA256, "date": "2026-10-10", "room": "not known", "microphone": "not known",
            "capture": "not known", "rate": 16000, "channels": 1, "sample_bits": 16, "length_s": 3.0, "speakers": 2,
            "parts": {"DOCTOR": "not known", "PATIENT": "not known"}, "whole": True, "last_speech": None,
            "read_differently": [], "machine_voices": False, "cut_of": None,
            "consent": {"recording": True, "tests_on_this_computer": True, "cloud": []}, "notes": "made up"}
    made.update(over)
    return made


def made_up_recordings(folder: Path, rate: int = 16000, seconds: float = 3.0, extra: list[dict] | None = None) -> Path:
    """Two made-up recordings and their list: one whole, one with consent
    for a made-up cloud service. Returns the folder."""
    folder.mkdir(parents=True, exist_ok=True)
    pcm = made_sound(seconds, rate)
    first = write_wav(folder / "one.wav", pcm, rate)
    second = write_wav(folder / "two.wav", pcm, rate)
    listed = [entry("one", "one.wav", first, rate=rate, length_s=seconds),
              entry("two", "two.wav", second, rate=rate, length_s=seconds, machine_voices=True,
                    consent={"recording": True, "tests_on_this_computer": True, "cloud": ["speechmatics", "assemblyai"]})]
    (folder / "recordings.json").write_text(json.dumps({"recordings": listed + (extra or [])}, indent=1), encoding="utf-8")
    return folder


def scripts_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "scripts"
    folder.mkdir(parents=True, exist_ok=True)
    # As bytes, the bytes SCRIPT_SHA256 is taken from: text mode would write
    # each line break as two bytes on Windows, and the bench would refuse it.
    (folder / "made_up.md").write_bytes(SCRIPT.encode("utf-8"))
    return folder
