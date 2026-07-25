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


# --- what the review page is given ----------------------------------------
#
# Scope note: these test the PAYLOAD and the served markup. They do not
# test the DOM — no browser is driven anywhere in this suite. Whether the
# chips actually disable, the pill actually appears and the audio actually
# plays is what the real-room check in HANDOVER is for.

@needs_db
def test_the_review_payload_carries_utterances_under_a_separate_key():
    """A separate key, matching the separate table. `turns` is what the
    note and its citations read; `system_utterances` is what the grey
    channel reads, and nothing joins them."""
    import secrets as _secrets

    from app import auth
    from fastapi.testclient import TestClient
    from app.main import app

    cid, spoken = _build_consultation()
    doctor = asyncio.run(auth.create_user(
        f"doctor_{_secrets.token_hex(4)}", "test-password-123", "Doctor", "doctor"))
    client = TestClient(app)
    client.cookies.set(auth.COOKIE_NAME, auth.sign_session(doctor["id"]))

    payload = client.get(f"/api/consultations/{cid}").json()
    assert [u["text"] for u in payload["system_utterances"]] == [spoken]
    assert all(spoken not in t["text"] for t in payload["turns"])
    # No turn number on an utterance: it can never be a citation target.
    assert "idx" not in payload["system_utterances"][0]


def test_the_live_page_ships_the_tap_to_ask_controls():
    """Markup presence only — that the affordances exist and the phrase
    tray offers exactly the six approved phrase ids."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    for element in ("speakingBar", "speakStop", "speakError", "discCheck"):
        assert f'id="{element}"' in html, element
    for phrase_id in ("disclosure", "invitation", "mm-hm", "i_see", "go_on",
                      "examination_handover"):
        assert f'data-phrase="{phrase_id}"' in html, phrase_id


def test_the_live_page_sends_references_and_never_text():
    """The client half of hard rule 1: there is no code path in the page
    that puts words into a speak message."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "type: 'speak', ref: ref" in html
    assert "'speak', text" not in html and '"speak", text' not in html


def test_the_mic_cluster_invariant_is_documented_for_session_three():
    """The detector stream arriving with barge-in must never be wired to
    the meter — the meter must keep describing what the server hears."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "never the meter" in html


# --- the hallucination invariant on excluded spans -------------------------
#
# NOT detection of our own voice, and it must never become that. It never
# looks at what a segment SAYS. It asserts a property of a region that is
# provably digital silence, because we zero-filled it ourselves.

def test_a_segment_inside_an_excluded_span_is_dropped():
    recording = turns((0, 5), (6, 9), (12, 20))
    kept, dropped = finalize.drop_segments_in_excluded_spans(
        recording, [(5.5, 10.0)])
    assert [t["start"] for t in kept] == [0, 12]
    assert [t["start"] for t in dropped] == [6]


def test_a_segment_mostly_outside_a_span_is_kept():
    """This assertion used to read the other way, and that is exactly how
    consultation 445 happened: it encoded "any overlap drops the segment"
    as if it were the requirement. A segment 1 s of whose 6 s is muted got
    its words from the other 5 s — it is transcript, not hallucination."""
    recording = turns((0, 6))
    kept, dropped = finalize.drop_segments_in_excluded_spans(
        recording, [(5.0, 8.0)])
    assert dropped == [] and len(kept) == 1


def test_segments_merely_touching_the_boundary_are_kept():
    """Half-open intervals: a segment ending exactly where a span starts
    contains no muted audio."""
    recording = turns((0, 5), (8, 12))
    kept, dropped = finalize.drop_segments_in_excluded_spans(
        recording, [(5.0, 8.0)])
    assert len(kept) == 2 and dropped == []


def test_the_invariant_is_a_no_op_without_spans():
    recording = turns((0, 5))
    kept, dropped = finalize.drop_segments_in_excluded_spans(recording, [])
    assert kept is recording and dropped == []


def test_the_invariant_never_inspects_segment_text():
    """The guard against it silently becoming string matching: a segment
    whose text is exactly what we spoke, OUTSIDE any span, is kept."""
    spoken = "Does the pain go anywhere else?"
    recording = [{"start": 30.0, "end": 33.0, "text": spoken, "confidence": 0.9}]
    kept, dropped = finalize.drop_segments_in_excluded_spans(
        recording, [(5.0, 8.0)])
    assert kept == recording and dropped == []


def test_the_invariant_has_a_pulse_counter():
    """"Should never happen" must be something the sentry can see."""
    from app import monitor

    assert (monitor._DAY_COUNTERS["transcript.silence_hallucination"]
            == "silence_hallucinations_today")


# ===========================================================================
# REGRESSION: consultation 445, 2026-07-25 — "the missing six minutes"
#
# The first real-room test of 7a. The doctor tapped 16 utterances over an
# 11-minute consultation. Finalisation produced FOUR turns ending at
# 4:36, the transcript-quality gate correctly refused on a 360.7 s
# trailing gap, and roughly six minutes of real patient speech — including
# "I have type 2 diabetes and I take metformin" — was gone.
#
# WHAT IT WAS NOT, established by measurement before anything was changed:
#   * Not capture. The original WAV has that speech at full level.
#   * Not the exclusion windows. All 16 spans were well-formed, every
#     end_reason was `complete`, the longest was 8.9 s, none ran to EOF,
#     and the union was 67.36 s — 10.1% of a 669 s recording.
#   * Not the derived copy. Measured directly: it is bit-identical to the
#     original outside those 16 spans, and NOT zero after 4:40.
#   * Not the quality gate. Its arithmetic was exactly right, including
#     the excluded-span discount, and refusing was the correct response to
#     a transcript that had genuinely lost six minutes.
#
# WHAT IT WAS: this invariant. WhisperX's speaker merge joins consecutive
# same-speaker segments into one turn, and it produced a single turn
# spanning 284.874-488.829 s. That 204-second turn CONTAINED four of our
# own short utterances totalling 12.69 s. The original rule dropped a
# segment on ANY overlap, so it discarded all 204 seconds to remove
# 12.69 — sixteen times more transcript than was ever muted.
#
# The numbers below are the real ones, read from `system_utterance` and
# the `transcript.silence_hallucination` audit row. Do not replace them
# with round figures: the point is that this exact case cannot come back.

C445_SPANS_S = [
    (3.50, 4.768), (7.50, 16.361), (95.25, 104.111), (160.75, 169.45),
    (242.75, 245.376), (253.75, 255.691), (271.25, 274.45), (280.50, 284.16),
    (424.75, 425.565), (454.50, 455.45), (469.50, 478.20), (480.50, 482.72),
    (492.75, 495.109), (499.00, 500.20), (511.25, 519.95), (600.50, 603.80),
]
C445_DURATION_S = 669.0
C445_LOST_TURN = {
    "start": 284.874, "end": 488.829, "confidence": 0.8,
    "text": ("I'm not taking any blood thinners, but I have type 2 diabetes "
             "and I take metformin and another medication which has a "
             "difficult name to pronounce. I'm a bit worried because I feel "
             "like having a temperature."),
}


def test_c445_the_lost_turn_is_kept():
    """THE regression. A 204 s turn containing 12.7 s of our own speech is
    transcript, not hallucination, and must survive."""
    kept, dropped = finalize.drop_segments_in_excluded_spans(
        [C445_LOST_TURN], C445_SPANS_S)
    assert dropped == [], (
        "consultation 445 has come back: a turn was discarded for containing "
        "our own utterances")
    assert kept == [C445_LOST_TURN]
    assert "metformin" in kept[0]["text"]


def test_c445_the_overlap_was_a_small_fraction_of_the_turn():
    """6.2% muted. The any-overlap rule could not tell that apart from a
    segment lying wholly inside a span, which is why it had to go."""
    overlap = finalize._overlap_seconds(
        C445_LOST_TURN["start"], C445_LOST_TURN["end"], C445_SPANS_S)
    duration = C445_LOST_TURN["end"] - C445_LOST_TURN["start"]
    assert overlap == pytest.approx(12.69, abs=0.05)
    assert duration == pytest.approx(203.955, abs=0.01)
    assert overlap / duration < 0.07
    assert overlap / duration < finalize.SEGMENT_MUTED_FRACTION


def test_c445_spans_were_all_well_formed():
    """Recorded so the disproved hypothesis stays disproved: the windows
    were never the fault. Every span ends after it starts, none is longer
    than the synthesis cap, and the union is a tenth of the recording."""
    for start, end in C445_SPANS_S:
        assert end > start
        assert end - start <= 20.0        # SPEECH_MAX_UTTERANCE_S
    union = sum(e - s for s, e in C445_SPANS_S)
    assert union == pytest.approx(67.36, abs=0.05)
    assert union / C445_DURATION_S == pytest.approx(0.101, abs=0.002)
    assert max(e for _, e in C445_SPANS_S) < C445_DURATION_S, "no span ran to EOF"


def test_c445_gate_arithmetic_was_correct_and_the_refusal_was_right():
    """The gate is not on trial here. Given the four turns that survived,
    360.7 s was the true discounted gap and refusing was correct."""
    surviving = [{"start": 177.63, "end": 224.52, "text": "x", "confidence": 0.786},
                 {"start": 245.61, "end": 246.57, "text": "x", "confidence": 0.775},
                 {"start": 256.67, "end": 264.94, "text": "x", "confidence": 0.786},
                 {"start": 275.15, "end": 276.43, "text": "x", "confidence": 0.826}]
    gap = transcript_quality.s4_truncation_gap(
        surviving, C445_DURATION_S, C445_SPANS_S)
    assert gap == pytest.approx(360.66, abs=0.05)
    assert gap > transcript_quality.TRUNCATION_REFUSE_S


def test_a_segment_wholly_inside_a_span_is_still_dropped():
    """The invariant must keep working: a real hallucination on muted
    silence lies inside the span, so its fraction is ~1.0."""
    inside = {"start": 470.0, "end": 477.0, "text": "Thank you.", "confidence": 0.3}
    kept, dropped = finalize.drop_segments_in_excluded_spans([inside], C445_SPANS_S)
    assert kept == [] and dropped == [inside]


def test_a_segment_half_muted_is_dropped_at_the_boundary():
    """Majority rule: at or above the fraction, it goes."""
    half = {"start": 465.0, "end": 475.0, "text": "?", "confidence": 0.4}
    _, dropped = finalize.drop_segments_in_excluded_spans([half], C445_SPANS_S)
    assert dropped == [half]      # 5.5s of 10s muted


def test_a_zero_length_segment_is_kept_rather_than_dividing_by_zero():
    odd = {"start": 300.0, "end": 300.0, "text": "", "confidence": 0.5}
    kept, dropped = finalize.drop_segments_in_excluded_spans([odd], C445_SPANS_S)
    assert kept == [odd] and dropped == []


def test_the_invariant_runs_before_the_speaker_merge():
    """Ordering is half the fix. After the merge, a hallucinated fragment
    can be inside a turn spanning minutes; before it, the fragment is
    removed on its own."""
    from pathlib import Path

    source = Path("app/finalize.py").read_text()
    invariant = source.index("raw_segments, hallucinated = drop_segments_in_excluded_spans")
    merge = source.index("# Merge word-assigned segments into speaker turns.")
    assert invariant < merge, "the invariant must run before the merge"


# --- the backstops item 4 argues for ---------------------------------------
#
# Whatever the cause, ONE utterance silenced six minutes of a consultation
# and nothing objected — no limit existed that the damage could exceed.

def test_a_span_longer_than_the_synthesiser_can_produce_is_clamped():
    """By definition wrong: there is no utterance it could correspond to."""
    result = finalize.check_exclusion_limits([(10.0, 400.0)], 669.0)
    (start, end), = result["spans"]
    assert end - start == pytest.approx(finalize.MAX_SPAN_S)
    assert result["anomalies"][0]["kind"] == "span_too_long"
    assert result["anomalies"][0]["was_s"] == pytest.approx(390.0)


def test_the_clamp_is_the_synthesis_cap_plus_the_tail():
    from app import speech as sp

    assert finalize.MAX_SPAN_S == pytest.approx(
        sp.SPEECH_MAX_UTTERANCE_S + sp.SPEECH_EXCLUSION_TAIL_MS / 1000)


def test_an_absurd_excluded_fraction_is_reported():
    spans = [(float(i * 20), float(i * 20 + 15)) for i in range(20)]   # 300s
    result = finalize.check_exclusion_limits(spans, 400.0)
    kinds = [a["kind"] for a in result["anomalies"]]
    assert "excluded_fraction_too_high" in kinds
    assert result["fraction"] == pytest.approx(0.75, abs=0.01)


def test_c445_would_not_have_tripped_the_fraction_limit():
    """Recorded deliberately. 445 sat at 10.1% while being a serious
    incident, so this backstop would NOT have caught it — it is a ceiling
    on absurdity, not a tight bound, and must not be mistaken for one."""
    result = finalize.check_exclusion_limits(C445_SPANS_S, C445_DURATION_S)
    assert result["anomalies"] == []
    assert result["fraction"] == pytest.approx(0.101, abs=0.002)
    assert result["fraction"] < finalize.MAX_EXCLUDED_FRACTION


def test_the_union_is_a_true_union_not_a_sum():
    merged = finalize.merge_spans([(0.0, 5.0), (3.0, 8.0), (20.0, 21.0)])
    assert merged == [(0.0, 8.0), (20.0, 21.0)]
    result = finalize.check_exclusion_limits([(0.0, 5.0), (3.0, 8.0)], 100.0)
    assert result["excluded_s"] == pytest.approx(8.0)   # not 10.0


def test_normal_exclusion_produces_no_anomalies():
    result = finalize.check_exclusion_limits([(10.0, 13.0), (50.0, 58.0)], 600.0)
    assert result["anomalies"] == [] and result["excluded_s"] == pytest.approx(11.0)


def test_the_anomaly_has_a_pulse_counter():
    from app import monitor

    assert (monitor._DAY_COUNTERS["transcript.exclusion_anomaly"]
            == "exclusion_anomalies_today")


# --- the live page must land on the refusal, not spin ----------------------

def test_the_live_page_lands_on_every_terminal_status():
    """Consultation 445: the gate refused, status became
    `unreliable_transcript`, and the poll loop — which enumerated the good
    outcomes — spun forever on "processing…". The doctor waited for a note
    that was never coming.

    The list is now inverted: only in-progress statuses continue. A status
    nobody thought of lands on the review page rather than hanging,
    because a page that says something beats a spinner that says nothing.
    """
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    assert "IN_PROGRESS_STATUSES = ['live', 'queued', 'processing']" in html
    assert "unreliable_transcript:" in html
    # The unknown-status fallback exists and lands.
    assert "finalisation finished (' + row.status + ')" in html


def test_every_status_the_pipeline_sets_is_either_in_progress_or_lands():
    """Guard against the next status being forgotten the same way."""
    from pathlib import Path

    html = Path("app/static/live.html").read_text()
    in_progress = {"live", "queued", "processing"}
    landing = {"awaiting_review", "approved", "failed", "unreliable_transcript"}
    assert transcript_quality.STATUS_UNRELIABLE in landing

    source = Path("app/finalize.py").read_text() + Path("app/main.py").read_text()
    for status in in_progress | landing:
        assert status in html or status in source, status
