"""Per-connection state for live transcription.

Strategy (the rough live pass from PROJECT_PLAN.md):
audio accumulates in a buffer; every couple of seconds the whole buffer is
re-transcribed. Segments that ended comfortably before the buffer's end are
stable, so they are *committed* — sent to the client as final text and their
audio dropped from the buffer. Whatever is still close to "now" is sent as a
provisional partial that later passes may revise.
"""

from __future__ import annotations

import asyncio

import numpy as np

from app.transcription import SAMPLE_RATE, LiveTranscriber, Segment

# Re-transcribe once at least this much new audio has arrived.
PROCESS_INTERVAL_S = 1.5
# A segment is final once it ends this far before the newest audio.
COMMIT_MARGIN_S = 2.0
# Silence housekeeping: if nothing is recognised in a long buffer, keep only
# the tail so the buffer cannot grow without bound.
SILENT_BUFFER_LIMIT_S = 12.0
SILENT_KEEP_TAIL_S = 4.0


class LiveSession:
    """Owns the audio buffer and commit logic for one WebSocket connection."""

    def __init__(self, transcriber: LiveTranscriber) -> None:
        self._transcriber = transcriber
        self._buffer = np.zeros(0, dtype=np.float32)
        self._committed_offset_s = 0.0  # audio time already committed and dropped
        self._new_samples = 0
        # Full session audio, kept for the finalisation pipeline (raw audio
        # is retained until finalisation succeeds, per plan).
        self._recording: list[bytes] = []

    def append_pcm16(self, data: bytes) -> None:
        """Add a chunk of little-endian 16-bit mono 16 kHz PCM."""
        self._recording.append(data)
        chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, chunk])
        self._new_samples += len(chunk)

    def save_recording(self, path: str) -> float:
        """Write the whole session's audio as a 16 kHz mono WAV; returns its
        duration in seconds."""
        import wave

        pcm = b"".join(self._recording)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm)
        return len(pcm) / 2 / SAMPLE_RATE

    @property
    def new_audio_seconds(self) -> float:
        return self._new_samples / SAMPLE_RATE

    @property
    def _buffer_seconds(self) -> float:
        return len(self._buffer) / SAMPLE_RATE

    def _absolute(self, seg: Segment) -> Segment:
        """Rebase a buffer-relative segment onto the session clock."""
        return Segment(
            start=round(self._committed_offset_s + seg.start, 2),
            end=round(self._committed_offset_s + seg.end, 2),
            text=seg.text,
        )

    def _drop_buffer_head(self, seconds: float) -> None:
        self._buffer = self._buffer[int(seconds * SAMPLE_RATE) :]
        self._committed_offset_s += seconds

    async def process(self) -> tuple[list[Segment], str]:
        """Transcribe the buffer; return (newly committed segments, partial text)."""
        self._new_samples = 0
        duration = self._buffer_seconds
        if duration < 1.0:
            return [], ""

        segments = await asyncio.to_thread(self._transcriber.transcribe, self._buffer)

        if not segments:
            if duration > SILENT_BUFFER_LIMIT_S:
                self._drop_buffer_head(duration - SILENT_KEEP_TAIL_S)
            return [], ""

        commit_horizon = duration - COMMIT_MARGIN_S
        final = [s for s in segments if s.end <= commit_horizon]
        pending = [s for s in segments if s.end > commit_horizon]
        partial = " ".join(s.text for s in pending)

        committed = [self._absolute(s) for s in final]
        if final:
            self._drop_buffer_head(final[-1].end)
        return committed, partial

    async def flush(self) -> list[Segment]:
        """Session is ending: transcribe whatever remains and commit all of it."""
        if self._buffer_seconds < 0.3:
            return []
        segments = await asyncio.to_thread(self._transcriber.transcribe, self._buffer)
        committed = [self._absolute(s) for s in segments]
        self._buffer = np.zeros(0, dtype=np.float32)
        return committed
