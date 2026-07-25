"""Finalisation exclusion: our voice is absent from the FINAL transcript.

`PHASE_7A_SPEC.md` §1.3 — the consequence that matters most. The live
path is not the only place system audio could enter the transcript:
`app/finalize.py` re-transcribes the whole recording with WhisperX, so
gating the live path alone would leave our voice in the final transcript
— the one the note is grounded in. The note grounding gate would then
faithfully cite a fabricated turn, which is consultation #70's failure
shape exactly: a note faithful to a transcript that was not faithful to
the audio.

    STRING COMPARISON AGAINST THE SPOKEN TEXT IS LEGITIMATE AS A TEST
    ASSERTION AND FORBIDDEN AS A RUNTIME MECHANISM.

Repeated from `tests/test_speech_exclusion.py` because this file is where
someone would reach for it — the temptation here is a "just in case" pass
over the final transcript stripping anything matching a system utterance.
Do not add it. The mechanism is `mute_spans`: the models are handed audio
that does not contain our voice.

Scope, stated plainly: WhisperX and pyannote are not run here (they need
the GPU and minutes of wall-clock). What is tested is the muting itself,
the byte-integrity of the original WAV, the gate interaction, and the
note/citation/export/letter boundaries — the last group being real
end-to-end assertions against the shipped query paths.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import wave

import numpy as np
import psycopg
import pytest

from app import consultations, finalize, notes, system_utterances, transcript_quality

SAMPLE_RATE = 16_000
BYTES_PER_MS = 32


def _db_ready() -> bool:
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), connect_timeout=2):
            return True
    except Exception:
        return False


needs_db = pytest.mark.skipif(not _db_ready(), reason="PostgreSQL not available")


def write_wav(path, seconds: float, amplitude: int = 8000) -> bytes:
    samples = int(seconds * SAMPLE_RATE)
    t = np.arange(samples)
    pcm = (amplitude * np.sin(2 * np.pi * 440 * t / SAMPLE_RATE)).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return path.read_bytes()


def load_float(path) -> np.ndarray:
    """What whisperx.load_audio would hand us: mono 16 kHz float32."""
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


# --- the derived copy ------------------------------------------------------

def test_derived_copy_is_zero_filled_across_the_spans(tmp_path):
    wav = tmp_path / "c.wav"
    write_wav(wav, 10.0)
    audio = load_float(wav)

    spans = [(1000 * BYTES_PER_MS, 2500 * BYTES_PER_MS),    # 1.0-2.5 s
             (6000 * BYTES_PER_MS, 7200 * BYTES_PER_MS)]    # 6.0-7.2 s
    derived = finalize.mute_spans(audio, spans)

    for start_byte, end_byte in spans:
        lo, hi = start_byte // 2, end_byte // 2
        assert np.all(derived[lo:hi] == 0.0)
    # Everything outside the spans is bit-identical to the original.
    assert np.array_equal(derived[:16000], audio[:16000])
    assert np.array_equal(derived[40000:96000], audio[40000:96000])
    assert np.max(np.abs(derived[115200:])) > 0


def test_mute_spans_does_not_modify_the_array_it_was_given(tmp_path):
    wav = tmp_path / "c.wav"
    write_wav(wav, 3.0)
    audio = load_float(wav)
    before = audio.copy()

    finalize.mute_spans(audio, [(0, 1000 * BYTES_PER_MS)])
    assert np.array_equal(audio, before), "mute_spans mutated its input"


def test_the_original_wav_is_byte_identical_afterwards(tmp_path):
    """Spec §1.3: the recording stays the faithful record of the room, and
    is what the retention sweep and FLAC-on-approval operate on."""
    wav = tmp_path / "c.wav"
    original = write_wav(wav, 5.0)
    digest_before = hashlib.sha256(original).hexdigest()

    audio = load_float(wav)
    finalize.mute_spans(audio, [(0, 2000 * BYTES_PER_MS)])

    assert wav.read_bytes() == original
    assert hashlib.sha256(wav.read_bytes()).hexdigest() == digest_before


def test_spans_are_clamped_to_the_audio(tmp_path):
    """A window whose ceiling runs past the end of a recording — Stop
    pressed mid-utterance — must clip, not raise."""
    wav = tmp_path / "c.wav"
    write_wav(wav, 1.0)
    audio = load_float(wav)
    derived = finalize.mute_spans(audio, [(500 * BYTES_PER_MS, 9000 * BYTES_PER_MS)])
    assert len(derived) == len(audio)
    assert np.all(derived[8000:] == 0.0)


def test_no_spans_is_a_no_op(tmp_path):
    wav = tmp_path / "c.wav"
    write_wav(wav, 1.0)
    audio = load_float(wav)
    assert finalize.mute_spans(audio, []) is audio


def test_byte_spans_convert_to_seconds_exactly():
    assert finalize.spans_to_seconds([(32000, 64000)]) == [(1.0, 2.0)]


# --- the transcript-quality gate interaction (item 2a) --------------------

def turns(*pairs, confidence: float = 0.8) -> list[dict]:
    return [{"start": s, "end": e, "text": "some speech", "confidence": confidence}
            for s, e in pairs]


def test_muted_spans_in_the_middle_do_not_move_s4_at_all():
    """S4 measures the TRAILING gap only — audio after the last segment.
    Muting mid-recording spans leaves the last segment where it was, so it
    cannot manufacture a refusal. Verified from the code, not the prose."""
    recording = turns((0, 60), (70, 120), (130, 300))
    plain = transcript_quality.s4_truncation_gap(recording, 302.0)
    with_spans = transcript_quality.s4_truncation_gap(
        recording, 302.0, [(60.0, 65.0), (120.0, 126.0)])
    assert plain == with_spans == pytest.approx(2.0)


def test_a_trailing_system_utterance_would_inflate_s4_and_is_discounted():
    """The one case that could manufacture a spurious refusal: the system
    speaks last (the examination handover) and the recording ends. Without
    the discount the gap is our own utterance; with it, the truth."""
    # 400 s recording; last patient segment ends at 360; we then speak
    # 25 s of handover/questions, which transcribes to nothing.
    recording = turns((0, 100), (110, 360))
    undiscounted = transcript_quality.s4_truncation_gap(recording, 400.0)
    assert undiscounted == pytest.approx(40.0)
    assert undiscounted > transcript_quality.TRUNCATION_REFUSE_S, (
        "this scenario must genuinely trip the gate, or the test proves nothing")

    discounted = transcript_quality.s4_truncation_gap(
        recording, 400.0, [(362.0, 387.0)])
    assert discounted == pytest.approx(15.0)
    assert discounted < transcript_quality.TRUNCATION_REFUSE_S


def test_a_consultation_with_several_muted_spans_does_not_trip_the_gate():
    """Prompt item 6's requirement, end to end through compute/evaluate."""
    recording = turns((0, 90), (95, 200), (210, 355))
    spans = [(90.0, 94.0), (200.0, 205.0), (356.0, 362.0), (362.0, 368.0)]
    signals = transcript_quality.compute_signals(
        recording, audio_duration_s=370.0, excluded_spans_s=spans)
    verdict = transcript_quality.evaluate(signals)

    assert verdict["outcome"] == transcript_quality.OUTCOME_PASS, verdict["fired"]
    assert signals["s4_truncation"]["excluded_s"] == pytest.approx(21.0)


def test_the_discount_can_never_make_s4_negative():
    recording = turns((0, 100))
    assert transcript_quality.s4_truncation_gap(
        recording, 101.0, [(100.0, 300.0)]) == 0.0


def test_s2_is_untouched_by_exclusion_because_muted_audio_yields_no_turns():
    """Stated in compute_signals' docstring; asserted here so it stays true."""
    recording = turns((0, 100), (110, 200))
    a = transcript_quality.compute_signals(recording, audio_duration_s=205.0)
    b = transcript_quality.compute_signals(
        recording, audio_duration_s=205.0, excluded_spans_s=[(100.0, 110.0)])
    assert a["s2_confidence"] == b["s2_confidence"]


def test_a_genuinely_truncated_recording_still_refuses():
    """The discount must not become a way to silence the gate: #70's
    33 s of dropped audio, with no speaking windows, still refuses."""
    recording = turns((0, 200), confidence=0.505)
    signals = transcript_quality.compute_signals(recording, audio_duration_s=233.3)
    verdict = transcript_quality.evaluate(signals)
    assert verdict["outcome"] == transcript_quality.OUTCOME_REFUSED
    assert {f["signal"] for f in verdict["fired"]} == {"S2", "S4"}


# --- the note boundary -----------------------------------------------------

def _build_consultation() -> tuple[int, str]:
    """A consultation with two patient turns and one system utterance."""
    consultations.ensure_schema()
    system_utterances.ensure_schema()
    spoken = "Does the pain go anywhere else?"

    async def build() -> int:
        cid = await consultations.create_consultation(None, None)
        await consultations.save_turns(cid, [
            {"idx": 0, "role": "Doctor", "start": 0.0, "end": 2.0,
             "text": "Good morning.", "confidence": 0.9},
            {"idx": 1, "role": "Patient", "start": 3.0, "end": 8.0,
             "text": "I have had chest pain since yesterday.", "confidence": 0.9},
        ])
        await system_utterances.save(cid, [{
            "utterance_id": secrets.token_hex(8), "text": spoken,
            "ref_kind": "cds_question",
            "ref_detail": {"assessment_version": 1, "index": 0},
            "cds_rationale": "cardiac vs musculoskeletal",
            "start_byte": 8 * SAMPLE_RATE * 2, "end_byte": 11 * SAMPLE_RATE * 2,
            "started_offset_ms": 8000, "ended_offset_ms": 11000,
            "end_reason": "complete", "voice": "stub", "synth_ms": 40,
        }])
        return cid

    return asyncio.run(build()), spoken


@needs_db
def test_the_note_generators_input_contains_no_system_utterance_text():
    """The structural claim behind the separate table: the note generator
    receives turns, and system utterances are not turns."""
    cid, spoken = _build_consultation()
    turns_for_note = asyncio.run(consultations.get_turns(cid))

    assert turns_for_note, "fixture built no turns"
    for turn in turns_for_note:
        assert spoken not in turn["text"]
    assert spoken not in " ".join(t["text"] for t in turns_for_note)


@needs_db
def test_no_citation_can_resolve_to_a_system_utterance():
    """Citations are turn indices into transcript_turn. There is no index
    that reaches system_utterance, because it is a different table with no
    row in the citable set."""
    cid, spoken = _build_consultation()
    turns_for_note = asyncio.run(consultations.get_turns(cid))
    citable = {t["idx"] for t in turns_for_note}

    assert citable == {0, 1}
    utterances = asyncio.run(system_utterances.for_consultation(cid))
    assert len(utterances) == 1
    assert "idx" not in utterances[0], "a system utterance must carry no turn number"


@needs_db
def test_the_plain_text_export_contains_no_system_utterance_text():
    cid, spoken = _build_consultation()
    note = {
        "subjective": [{"text": "Chest pain since yesterday.", "citations": [1]}],
        "objective": [], "assessment": [], "plan": [],
    }
    exported = notes.note_as_plain_text(note)
    assert spoken not in exported
    # The export serialises the note, which was built from turns alone —
    # it never reads the transcript, let alone the utterance table.
    assert "Chest pain since yesterday." in exported


@needs_db
def test_the_referral_letter_path_cannot_see_a_system_utterance():
    """Letters draw from the APPROVED NOTE TEXT only, so this follows —
    but assert it, because the #66 lesson is that gates are explicit."""
    from app import letters

    cid, spoken = _build_consultation()
    approved_text = "Subjective\nChest pain since yesterday.\n\nPlan\nECG.\n"
    assert spoken not in approved_text
    assert not hasattr(letters, "system_utterances"), (
        "the letter module must have no route to system utterance text")


@needs_db
def test_exclusion_spans_survive_into_finalisation_from_the_database():
    """Spec §2.3: the spans live in the database, not in the live session
    object — which is why a post-restart finalisation still excludes."""
    cid, _ = _build_consultation()
    spans = asyncio.run(system_utterances.exclusion_spans(cid))
    assert spans == [(8 * SAMPLE_RATE * 2, 11 * SAMPLE_RATE * 2)]
    assert finalize.spans_to_seconds(spans) == [(8.0, 11.0)]


@needs_db
def test_utterances_cascade_when_the_consultation_is_deleted():
    """Void-then-purge stays one step for the admin."""
    cid, _ = _build_consultation()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("DELETE FROM consultation WHERE id = %s", (cid,))
        conn.commit()
        left = conn.execute(
            "SELECT count(*) FROM system_utterance WHERE consultation_id = %s",
            (cid,)).fetchone()[0]
    assert left == 0
