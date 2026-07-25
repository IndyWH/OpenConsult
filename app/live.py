"""Per-connection state for live transcription.

Strategy (the rough live pass from PROJECT_PLAN.md):
audio accumulates in a buffer; every couple of seconds the whole buffer is
re-transcribed. Segments that ended comfortably before the buffer's end are
stable, so they are *committed* — sent to the client as final text and their
audio dropped from the buffer. Whatever is still close to "now" is sent as a
provisional partial that later passes may revise.

## Speaking windows (Phase 7a, PHASE_7A_SPEC.md §§1.1–1.3)

Since 2026-07-25 the system can speak into the room, and the guarantee
that makes that safe is enforced here: **system-spoken audio never reaches
the transcriber.** Not by prompt, not by echo cancellation, not by
matching text afterwards — by the server refusing to put that audio in
the buffer in the first place. The server knows precisely when it is
speaking; that knowledge is the mechanism, and it is the only acceptable
one, because a note grounded in a transcript containing our own voice
would faithfully cite words the patient never said.

Two properties of the implementation are load-bearing:

- **The recording keeps the real audio.** `_recording` — the faithful
  record of the room, and what gets written to the WAV — is untouched.
  Only the transcriber's buffer is silenced. The room is recorded as it
  was; the transcript is of the patient alone.
- **The buffer receives silence, not nothing.** Dropping the samples
  would shift every later timestamp relative to the recording, and the
  urgency alarm's first-fired times and the review page's timeline both
  read that clock. Zero-filling keeps buffer time and recording time
  identical.

A window is held as a **byte range on the recording**, not as sequence
numbers: finalisation works on the file, and sequence-to-offset arithmetic
done twice is arithmetic done wrong once. It is also why a window needs no
timer — it carries a byte ceiling from the moment it opens
(`start + synthesised duration + tail`), so a `speak_ended` that never
arrives closes it at exactly the right place anyway.
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from app.transcription import SAMPLE_RATE, LiveTranscriber, Segment

logger = logging.getLogger(__name__)

# Re-transcribe once at least this much new audio has arrived.
PROCESS_INTERVAL_S = 1.5
# A segment is final once it ends this far before the newest audio.
COMMIT_MARGIN_S = 2.0
# Silence housekeeping: if nothing is recognised in a long buffer, keep only
# the tail so the buffer cannot grow without bound.
SILENT_BUFFER_LIMIT_S = 12.0
SILENT_KEEP_TAIL_S = 4.0

# 16 kHz, mono, 16-bit: two bytes per sample, 32 bytes per millisecond.
BYTES_PER_SAMPLE = 2
BYTES_PER_MS = SAMPLE_RATE * BYTES_PER_SAMPLE // 1000


def bytes_to_ms(offset: int) -> int:
    return round(offset / BYTES_PER_MS)


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
        self._recorded_bytes = 0
        # Speaking windows: closed spans, plus the one currently open.
        self._spans: list[dict] = []
        self._open: dict | None = None

    # -- speaking windows ------------------------------------------------

    @property
    def recorded_bytes(self) -> int:
        """Bytes of PCM received so far — the offset the next frame lands at."""
        return self._recorded_bytes

    @property
    def speaking(self) -> bool:
        return self._open is not None

    def open_speaking_window(self, utterance_id: str, duration_ms: int,
                             tail_ms: int) -> int:
        """Begin excluding audio, from wherever the recording has reached.

        Returns the start byte offset. The offset is taken from the
        server's own byte count rather than from the client's declared
        sequence number: WebSocket messages are ordered, so `speak_started`
        arrives before the first frame recorded during playback, and the
        server's count is the thing that actually says what is in the file.

        The window carries a ceiling — `start + duration + tail` — set now,
        so a missing `speak_ended` closes it at exactly the right place
        with no timer and no guess.
        """
        if self._open is not None:
            raise RuntimeError("a speaking window is already open")
        start = self._recorded_bytes
        ceiling = start + duration_ms * BYTES_PER_MS + tail_ms * BYTES_PER_MS
        self._open = {"utterance_id": utterance_id, "start_byte": start,
                      "ceiling_byte": ceiling, "tail_ms": tail_ms,
                      "end_byte": None, "end_reason": None}
        return start

    def close_speaking_window(self, reason: str = "complete") -> dict:
        """End the open window at the current position plus its tail.

        Clamped to the ceiling: audio beyond `start + duration + tail`
        cannot contain our voice, so excluding it would cost patient speech
        for nothing.
        """
        if self._open is None:
            raise RuntimeError("no speaking window is open")
        span = self._open
        end = self._recorded_bytes + span["tail_ms"] * BYTES_PER_MS
        span["end_byte"] = min(end, span["ceiling_byte"])
        span["end_reason"] = reason
        self._spans.append(span)
        self._open = None
        logger.info("Speaking window %s closed (%s): bytes %d-%d",
                    span["utterance_id"], reason, span["start_byte"], span["end_byte"])
        return span

    def speaking_spans(self) -> list[dict]:
        """All windows, with any still-open one closed at its ceiling.

        Called at session end, so an utterance interrupted by a hard
        disconnect still excludes the audio it was speaking over.
        """
        spans = list(self._spans)
        if self._open is not None:
            span = dict(self._open)
            span["end_byte"] = span["ceiling_byte"]
            span["end_reason"] = span["end_reason"] or "window_ceiling"
            spans.append(span)
        return spans

    def _mute_range(self, start: int, end: int) -> tuple[int, int] | None:
        """Byte sub-range of [start, end) that falls inside a live window."""
        if self._open is not None:
            lo = max(start, self._open["start_byte"])
            hi = min(end, self._open["ceiling_byte"])
            return (lo, hi) if lo < hi else None
        if self._spans:
            # Only the most recently closed window can still owe its tail:
            # windows never overlap (one utterance at a time, queue depth
            # zero — spec §2.3), so nothing older can reach this frame.
            span = self._spans[-1]
            lo, hi = max(start, span["start_byte"]), min(end, span["end_byte"])
            return (lo, hi) if lo < hi else None
        return None

    # -- audio -----------------------------------------------------------

    def append_pcm16(self, data: bytes) -> None:
        """Add a chunk of little-endian 16-bit mono 16 kHz PCM.

        The recording gets the real audio; the transcriber's buffer gets
        silence for any part of it we were speaking over. See the module
        docstring — this is the whole guarantee, in four lines.
        """
        start = self._recorded_bytes
        self._recording.append(data)
        self._recorded_bytes = end = start + len(data)

        chunk = (np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0)
        muted = self._mute_range(start, end)
        if muted is not None:
            lo, hi = muted
            chunk[(lo - start) // BYTES_PER_SAMPLE:(hi - start) // BYTES_PER_SAMPLE] = 0.0
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

    @property
    def audio_seconds(self) -> float:
        """Total audio received so far — the session clock."""
        return self._committed_offset_s + self._buffer_seconds

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
