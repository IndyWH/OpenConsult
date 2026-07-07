"""Generate a DISPOSABLE two-voice TTS recording of a mock script.

For interim testing of the audio pipeline (WhisperX + pyannote) only —
synthetic voices are NOT the permanent test set (real recordings are, per
Phase 0). Output goes to data/tts_sample/ (gitignored).

Usage: uv run python scripts/make_tts_sample.py [script.md]
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import wave
from pathlib import Path

import edge_tts

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.mock_scripts import parse_script  # noqa: E402

OUT_DIR = Path("data/tts_sample")
VOICES = {"DOCTOR": "en-GB-RyanNeural", "PATIENT": "en-GB-SoniaNeural",
          "MOTHER": "en-GB-SoniaNeural"}
SAMPLE_RATE = 16_000
GAP_S = 0.4


async def tts_turn(text: str, voice: str, mp3_path: Path) -> None:
    await edge_tts.Communicate(text, voice).save(str(mp3_path))


def mp3_to_pcm(mp3_path: Path) -> bytes:
    """Decode to 16 kHz mono s16le PCM with ffmpeg."""
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(mp3_path), "-ac", "1",
         "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout


async def main() -> None:
    script = Path(sys.argv[1] if len(sys.argv) > 1 else "mock_consultations/04_asthma_en.md")
    turns = parse_script(script)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    silence = b"\x00" * int(2 * SAMPLE_RATE * GAP_S)
    pcm_parts: list[bytes] = []
    for i, turn in enumerate(turns):
        mp3 = OUT_DIR / f"turn_{i:03d}.mp3"
        await tts_turn(turn.text, VOICES[turn.speaker], mp3)
        pcm_parts.append(mp3_to_pcm(mp3))
        pcm_parts.append(silence)
        mp3.unlink()
        print(f"\r{i + 1}/{len(turns)} turns synthesised", end="", flush=True)

    out_path = OUT_DIR / (script.stem + "_tts.wav")
    pcm = b"".join(pcm_parts)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    print(f"\nWrote {out_path} ({len(pcm) / 2 / SAMPLE_RATE:.0f}s)")


if __name__ == "__main__":
    asyncio.run(main())
