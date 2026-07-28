"""Post-consultation finalisation pipeline (Phase 2).

Triggered by the Stop button. Steps, in order:

1. UNLOAD MedGemma from the GPU. VRAM sequencing is the critical design
   constraint: the 4090 has 24 GB, MedGemma occupies ~17 GB resident, and
   WhisperX large-v3 + pyannote need ~6-8 GB. They cannot coexist, so the
   pipeline explicitly releases MedGemma (keep_alive=0) and waits for the
   VRAM to drop before loading the audio models.
2. Re-transcribe the full recording with WhisperX large-v3 (word-level
   timestamps + confidence scores).
3. Diarise with pyannote using an EXACT speaker count the doctor declared at
   Stop (DEFAULT_SPEAKERS when they did not), and merge into speaker turns —
   except on a single cluster, where segment boundaries are kept.
4. Free the audio models' VRAM.
5. Attribute roles. Two clusters: first-speaker-is-Doctor — a heuristic
   whose premise 7a has falsified, see attribute_roles. One cluster: every
   turn is Patient, and the consultation is flagged single_voice_detected
   so review says the roles are unverified. The review UI has a
   whole-transcript swap AND per-turn role correction.
6. Run the transcript-quality gate (app/transcript_quality.py) — BEFORE
   the note call, so a refusal costs no MedGemma time. Signals are stored
   on every consultation; S2 (low confidence) and S4 (truncation) refuse
   independently. See TRANSCRIPT_QUALITY_GATE_SPEC.md §11.
7. Draft the SOAP note with MedGemma — which reloads onto the now-free
   GPU on its first call.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import time

import httpx

from app import audit, consultations, speech, system_utterances, transcript_quality
from app.notes import draft_note

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
CDS_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")
WHISPERX_MODEL = os.getenv("WHISPERX_MODEL", "large-v3")
# pyannote 4's default pipeline (community-1) is separately gated; 3.1 is
# the one this machine's HF token has access to.
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")

# How many people spoke, when the doctor did not say (owner decision
# 2026-07-28). Two is today's behaviour and is correct on four of the five real
# two-person recordings, so a defaulted consultation behaves exactly as it did
# before this work.
#
# The count is DECLARED, not detected, and the reasoning is measured rather
# than assumed. `num_speakers=2` alone split a lone voice in two (446, 447,
# 448). Replacing it with a permitted range let pyannote choose, and choosing
# is what it cannot do reliably on this data: 447 stayed at two clusters when
# allowed one, and recording 66 — two real people — collapsed to one. Every
# row of that table resolves once the count is stated: 447 is right if forced
# to one, 66 is right if forced to two.
#
# So the human in the room is authoritative and the machine corroborates,
# which is the sound check's pattern. Per-turn role correction stays as the
# backstop, because a declaration can be mis-tapped.
DEFAULT_SPEAKERS = 2


async def unload_medgemma() -> None:
    """Release MedGemma's ~17 GB (keep_alive=0 evicts it) and wait for it."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": CDS_MODEL, "messages": [], "keep_alive": 0},
        )
        for _ in range(30):
            ps = (await client.get(f"{OLLAMA_URL}/api/ps")).json()
            if not any(m["name"].startswith(CDS_MODEL) for m in ps.get("models", [])):
                logger.info("MedGemma unloaded")
                return
            await asyncio.sleep(1)
    logger.warning("MedGemma still resident after 30s — proceeding anyway")


SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2


def mute_spans(audio, spans: list[tuple[int, int]]):
    """A DERIVED COPY of the audio with the given byte spans zero-filled.

    Phase 7a, PHASE_7A_SPEC.md §1.3. The live path is not the only place
    the system's own voice could enter the transcript: this function
    re-transcribes the whole recording, so gating the live path alone
    would leave our voice in the FINAL transcript — the one the note is
    grounded in, and the one the grounding gate would then faithfully cite.

    Spans are byte offsets into the WAV's PCM data, straight from
    `system_utterance`. `whisperx.load_audio` returns mono 16 kHz float32,
    the same layout the recording was written in, so a byte offset is a
    sample index doubled — no resampling, no drift.

    **The original array is copied, and the file on disk is never touched.**
    The WAV stays byte-intact as the faithful record of the room, and is
    what the retention sweep and the FLAC-on-approval step operate on.
    """
    if not spans:
        return audio
    derived = audio.copy()
    total = len(derived)
    for start_byte, end_byte in spans:
        lo = max(0, int(start_byte) // BYTES_PER_SAMPLE)
        hi = min(total, int(end_byte) // BYTES_PER_SAMPLE)
        if hi > lo:
            derived[lo:hi] = 0.0
    return derived


def spans_to_seconds(spans: list[tuple[int, int]]) -> list[tuple[float, float]]:
    """Byte spans → second spans, for the transcript-quality gate."""
    divisor = float(SAMPLE_RATE * BYTES_PER_SAMPLE)
    return [(start / divisor, end / divisor) for start, end in spans]


# --- backstops on exclusion (consultation 445) -----------------------------
#
# The lesson of 445 is not only its specific cause. ONE utterance silenced
# six minutes of a consultation and nothing objected — no limit existed
# that the damage could exceed. These two convert an invisible over-reach
# into something that announces itself, whatever the next cause turns out
# to be.

# No single span may be longer than the longest utterance the synthesiser
# will ever produce, plus the tail. A span longer than that is by
# definition wrong: there is no utterance it could correspond to.
MAX_SPAN_S = (speech.SPEECH_MAX_UTTERANCE_S
              + speech.SPEECH_EXCLUSION_TAIL_MS / 1000.0)

# The union of excluded spans as a fraction of the recording. 445 sat at
# 10.1% while being a serious incident, so this is a ceiling on absurdity
# rather than a tight bound — owner-tunable.
MAX_EXCLUDED_FRACTION = float(os.getenv("MAX_EXCLUDED_FRACTION", "0.25"))


def merge_spans(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Overlapping/adjacent spans merged, so a union is a true union.

    Windows cannot overlap by construction (one utterance at a time), but
    the union is what the fraction check measures and it must not be
    inflated by double-counting if that ever changes.
    """
    merged: list[list[float]] = []
    for start, end in sorted((float(a), float(b)) for a, b in spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def check_exclusion_limits(spans_s: list[tuple[float, float]],
                           audio_duration_s: float | None) -> dict:
    """Clamp over-long spans and report on the total excluded fraction.

    Returns {"spans": clamped, "anomalies": [...], "excluded_s", "fraction"}.
    An anomaly is a fact for the audit log, not a refusal: the transcript
    gate already decides whether a damaged transcript may be drafted from,
    and a second refusal path would be a second thing to get wrong.
    """
    anomalies: list[dict] = []
    clamped: list[tuple[float, float]] = []
    for start, end in spans_s:
        if end - start > MAX_SPAN_S:
            anomalies.append({
                "kind": "span_too_long", "start_s": round(start, 3),
                "was_s": round(end - start, 3), "clamped_to_s": MAX_SPAN_S,
            })
            end = start + MAX_SPAN_S
        clamped.append((start, end))

    union = merge_spans(clamped)
    excluded = sum(b - a for a, b in union)
    fraction = (excluded / audio_duration_s) if audio_duration_s else 0.0
    if fraction > MAX_EXCLUDED_FRACTION:
        anomalies.append({
            "kind": "excluded_fraction_too_high",
            "excluded_s": round(excluded, 2),
            "audio_duration_s": round(float(audio_duration_s or 0), 2),
            "fraction": round(fraction, 4),
            "limit": MAX_EXCLUDED_FRACTION,
        })
    return {"spans": clamped, "anomalies": anomalies,
            "excluded_s": round(excluded, 2), "fraction": round(fraction, 4)}


# A segment is discarded only when MOST of it lies inside muted audio.
#
# This threshold is the whole lesson of consultation 445 (2026-07-25). The
# first version of this invariant dropped a segment on ANY overlap, which
# is correct reasoning for a segment straddling a boundary and
# catastrophic for one that CONTAINS a span. In 445 a 204-second turn
# contained four short utterances totalling 12.7 s; the any-overlap rule
# threw away all 204 seconds to remove 12.7 — sixteen times more
# transcript than was ever muted — and six minutes of a real consultation
# with it.
#
# The invariant's actual purpose is "nothing may be transcribed FROM a
# muted region". A hallucination on silence lies wholly inside a span, so
# its overlap fraction is ~1.0. A genuine turn that merely contains a
# span got its words from the real audio around it, so its fraction is
# small — 6.2% in 445's case.
SEGMENT_MUTED_FRACTION = float(os.getenv("SEGMENT_MUTED_FRACTION", "0.5"))


def _overlap_seconds(start: float, end: float,
                     spans: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(end, b) - max(start, a)) for a, b in spans)


def drop_segments_in_excluded_spans(
    turns: list[dict], excluded_spans_s: list[tuple[float, float]]
) -> tuple[list[dict], list[dict]]:
    """Invariant check: nothing may be transcribed from a muted span.

    **This is NOT detection of our own voice, and must never become that.**
    It does not look at what a segment says and never compares it to
    anything the system spoke. It asserts a property of a region that is
    *provably digital silence* — we zero-filled it ourselves a few lines
    above, in `mute_spans`. A segment lying inside one is not "probably our
    voice"; it is output with no input, which is a Whisper hallucination
    on silence.

    Why an invariant rather than a hope: zero-filled digital silence is a
    known hallucination trigger for Whisper. WhisperX runs silero VAD
    first, which should emit no speech regions on pure zeros, so this
    should rarely fire. That is exactly the kind of claim that deserves a
    check rather than a comment — and one that is visible when it is
    wrong, hence the anomaly count and audit event at the call site.

    If it ever fires on a segment that is genuinely inside a span, the fix
    under consideration is filling with very low-level noise instead of
    pure zeros. Do not change the fill pre-emptively.

    **Discards only segments that are MOSTLY muted** (see
    `SEGMENT_MUTED_FRACTION` above, and consultation 445). Applied to raw
    segments before the speaker merge, so a hallucinated fragment is
    removed on its own rather than taking a legitimate turn with it.

    Returns (kept, dropped).
    """
    if not excluded_spans_s:
        return turns, []
    kept, dropped = [], []
    for turn in turns:
        start, end = float(turn.get("start", 0)), float(turn.get("end", 0))
        duration = end - start
        if duration <= 0:
            kept.append(turn)
            continue
        fraction = _overlap_seconds(start, end, excluded_spans_s) / duration
        (dropped if fraction >= SEGMENT_MUTED_FRACTION else kept).append(turn)
    return kept, dropped


def transcribe_and_diarise(wav_path: str,
                           exclusion_spans: list[tuple[int, int]] | None = None,
                           num_speakers: int = DEFAULT_SPEAKERS,
                           ) -> list[dict]:
    """WhisperX + pyannote, returning speaker turns with confidence.

    Blocking and GPU-heavy — run via asyncio.to_thread. Loads its models,
    uses them, and frees them before returning.

    `num_speakers` is an EXACT count, declared rather than detected — see
    DEFAULT_SPEAKERS and the module docstring for why the detected range was
    tried, measured and abandoned.

    `exclusion_spans` are Phase 7a speaking windows as byte offsets. The
    models are handed a muted derived copy; WhisperX and pyannote cannot
    hear what is not there. `audio_duration_s` is deliberately taken from
    the FULL recording — muting does not shorten the audio, and S4's
    trailing-gap arithmetic depends on the real duration.
    """
    from app.transcription import _preload_cuda_libraries

    _preload_cuda_libraries()  # torch/ctranslate2 need the pip cuDNN wheels

    import torch
    import whisperx

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute = "float16" if device == "cuda" else "int8"

    audio = whisperx.load_audio(wav_path)
    audio_duration_s = len(audio) / SAMPLE_RATE

    # Backstops before anything is muted (consultation 445): clamp any
    # span longer than the synthesiser could possibly produce, and notice
    # when the union covers an absurd share of the recording.
    limits = check_exclusion_limits(
        spans_to_seconds(exclusion_spans or []), audio_duration_s)
    for anomaly in limits["anomalies"]:
        logger.error("Exclusion anomaly (%s): %s", anomaly["kind"], anomaly)
    exclusion_spans = [(int(a * SAMPLE_RATE * BYTES_PER_SAMPLE),
                        int(b * SAMPLE_RATE * BYTES_PER_SAMPLE))
                       for a, b in limits["spans"]]

    # From here on every model sees the derived copy only. The original
    # array is untouched, and the file was never opened for writing.
    audio = mute_spans(audio, exclusion_spans or [])
    if exclusion_spans:
        logger.info("Excluding %d system-speech span(s) from the final "
                    "transcript (%.1fs of %.1fs)", len(exclusion_spans),
                    sum(e - s for s, e in exclusion_spans)
                    / (SAMPLE_RATE * BYTES_PER_SAMPLE), audio_duration_s)

    started = time.perf_counter()
    # Silero VAD: whisperx's default pyannote VAD checkpoint is incompatible
    # with the pinned pyannote 3.4 (see pyproject override note).
    # Same clinical initial prompt as the live path: the 2026-07-17
    # recordings deviation report measured the cost of its absence here —
    # drug names failed at nearly every mention in the final pass
    # (gliclazide 0/3, salbutamol, losartan) while the prompted live path
    # was built precisely against that class of error.
    from app.transcription import CLINICAL_INITIAL_PROMPT

    model = whisperx.load_model(
        WHISPERX_MODEL, device, compute_type=compute, vad_method="silero",
        asr_options={"initial_prompt": CLINICAL_INITIAL_PROMPT},
    )
    # S1 for the transcript-quality gate, taken here because the model is
    # already loaded — one window, no extra load, and it must happen
    # BEFORE the forced-English transcribe below. Measured only: it does
    # not act (spec §11 — it returns English at p=0.90 for #70).
    detected_language, language_probability = None, None
    try:
        detected_language, language_probability, _ = model.model.detect_language(
            audio=audio, language_detection_segments=1)
    except Exception:  # pragma: no cover - never block finalisation on a measurement
        logger.warning("Language detection unavailable; S1 recorded as unknown")

    result = model.transcribe(audio, batch_size=8, language="en")

    align_model, metadata = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(
        result["segments"], align_model, metadata, audio, device,
        return_char_alignments=False,
    )

    # Call pyannote directly (not via whisperx's wrapper) so we control the
    # pipeline version and kwargs — see the override note in pyproject.toml.
    import pandas as pd
    from pyannote.audio import Pipeline as PyannotePipeline

    # pyannote 3.4 checkpoints predate torch's weights_only default and
    # contain omegaconf objects; allow full unpickling for this trusted
    # load only, then restore the safe default.
    _torch_load = torch.load
    torch.load = lambda *a, **k: _torch_load(*a, **{**k, "weights_only": False})
    try:
        diarizer = PyannotePipeline.from_pretrained(
            DIARIZATION_MODEL, use_auth_token=True  # token from ~/.cache/huggingface
        ).to(torch.device(device))
    finally:
        torch.load = _torch_load
    waveform = torch.from_numpy(audio[None, :])
    # An EXACT count, DECLARED by the doctor rather than detected — see
    # DEFAULT_SPEAKERS. The range (min_speakers=1, max_speakers=2) was tried
    # on 2026-07-28 and measured: it fixed 448 and 446, failed to fix 447
    # (pyannote still split one voice into two clusters when allowed one), and
    # REGRESSED recording 66 from two clusters to one. Detection is unreliable
    # in both directions on this data, so it is no longer asked to guess.
    annotation = diarizer(
        {"waveform": waveform, "sample_rate": 16000}, num_speakers=num_speakers,
    )
    diarization = pd.DataFrame(
        annotation.itertracks(yield_label=True),
        columns=["segment", "track", "speaker"],
    )
    diarization["start"] = diarization["segment"].apply(lambda s: s.start)
    diarization["end"] = diarization["segment"].apply(lambda s: s.end)
    result = whisperx.assign_word_speakers(diarization, result)
    logger.info(
        "WhisperX+pyannote finished in %.1fs for %.1fs of audio",
        time.perf_counter() - started, len(audio) / 16000,
    )

    # The silence invariant runs HERE, on raw segments, BEFORE the speaker
    # merge below. That ordering is the fix for consultation 445: the merge
    # joins consecutive same-speaker segments into one turn, and a merged
    # turn can legitimately span minutes and contain several of our own
    # utterances. Checking after the merge meant a hallucinated fragment
    # could take 204 seconds of real consultation with it. Checking before
    # removes the fragment on its own.
    excluded_s = spans_to_seconds(exclusion_spans or [])
    raw_segments, hallucinated = drop_segments_in_excluded_spans(
        result["segments"], excluded_s)

    turns = merge_into_turns(raw_segments)

    # Free everything before MedGemma comes back.
    del model, align_model, diarizer, result
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    logger.info("Audio models released")

    for turn in turns:
        turn.pop("weight", None)
        turn["confidence"] = round(turn["confidence"], 3)
    return {"turns": turns, "audio_duration_s": audio_duration_s,
            "detected_language": detected_language,
            "language_probability": language_probability,
            "excluded_spans_s": excluded_s,
            "hallucinated_segments": hallucinated,
            "exclusion_anomalies": limits["anomalies"],
            "excluded_fraction": limits["fraction"]}


def merge_into_turns(raw_segments: list[dict]) -> list[dict]:
    """Group word-assigned ASR segments into speaker turns.

    Consecutive segments from the same cluster become one turn — EXCEPT when
    the whole recording came back as a SINGLE cluster (2026-07-28), in which
    case segment boundaries are kept as they are.

    Why the exception, measured rather than assumed: merging exists to join
    one speaker's consecutive segments, so with one cluster it has nothing to
    join *on* and joins the entire consultation into one turn. Re-checked
    against recording 66 — a genuine two-person consultation that pyannote
    now collapses to one cluster — merging produced a single 300-second turn
    out of 22. That destroys the citation granularity the note depends on and
    leaves the doctor one label to correct where they need twenty-two.

    Same shape as the consultation-445 lesson: the merge is what turns a small
    upstream error into a large downstream one, so the merge is where the
    proportionality rule belongs. Keeping the boundaries asserts less — it
    claims only what the ASR segmented, not a speaker structure nothing
    measured.

    The cost, stated because it is real: single-cluster transcripts come out
    at ASR-segment granularity, which is roughly sentence-level (66 gives 99
    turns, 448 gives 10). Reading is choppier and there are more labels to
    correct. Grouping them by pause length instead would need a threshold
    nobody has calibrated on this room, so it is deliberately not done here.
    """
    single_cluster = len({
        w.get("speaker") for seg in raw_segments
        for w in seg.get("words", []) if w.get("speaker")
    }) <= 1

    turns: list[dict] = []
    for seg in raw_segments:
        words = seg.get("words", [])
        speakers = [w.get("speaker") for w in words if w.get("speaker")]
        speaker = max(set(speakers), key=speakers.count) if speakers else "SPEAKER_00"
        scores = [w["score"] for w in words if "score" in w]
        confidence = sum(scores) / len(scores) if scores else 0.5
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if turns and not single_cluster and turns[-1]["speaker"] == speaker:
            prev = turns[-1]
            total = prev["weight"] + len(words)
            prev["confidence"] = (
                (prev["confidence"] * prev["weight"] + confidence * len(words)) / total
                if total else prev["confidence"]
            )
            prev["weight"] = total
            prev["text"] += " " + text
            prev["end"] = seg["end"]
        else:
            turns.append(
                {"speaker": speaker, "start": seg["start"], "end": seg["end"],
                 "text": text, "confidence": round(confidence, 3), "weight": len(words)}
            )
    return turns


def attribute_roles(turns: list[dict]) -> tuple[list[dict], bool]:
    """Assign Doctor/Patient roles to diarised turns.

    Returns `(turns, single_voice)`. `single_voice` is True when the audio
    yielded only ONE speaker cluster, which the caller records on the
    consultation so the review page can say the roles are unverified.

    TWO CLUSTERS: first speaker is the Doctor. **This premise is falsified
    by Phase 7a and is knowingly left in place for now** — see HANDOVER.
    The docstring used to justify it as "the doctor opens the consultation",
    which was true when a human opened it. In tap-to-ask the MACHINE opens,
    with the disclosure and the invitation, and those are excluded from the
    transcript by construction — so the first *human* voice is frequently
    the patient. Replacing this heuristic is an open design question and
    deliberately not attempted here; the review UI's swap and the new
    per-turn role correction are what stand in for it.

    ONE CLUSTER: every turn is labelled **Patient**, not Doctor.

    The reasoning, recorded because it is a default and not a truth: in
    tap-to-ask the machine asks the questions, so a lone human voice is
    answering them, and in every case observed so far (446, 447, 448) that
    voice was the patient. Labelling them Doctor — which is what the old
    code did, since the first cluster was always the Doctor — was wrong in
    all three. Patient is the better default, and it is still a default:
    **the owner may change it**, and a single-voice consultation always
    raises the review-page notice telling the doctor to check.
    """
    if not turns:
        return turns, False
    speakers = {t["speaker"] for t in turns}
    single_voice = len(speakers) <= 1
    doctor_speaker = turns[0]["speaker"]
    for turn in turns:
        if single_voice:
            turn["role"] = "Patient"
        else:
            turn["role"] = "Doctor" if turn["speaker"] == doctor_speaker else "Patient"
        turn.pop("speaker", None)
    return turns, single_voice


async def finalize_consultation(cid: int, wav_path: str) -> None:
    """The full pipeline; sets consultation status as it progresses."""
    await consultations.set_status(cid, "processing", audio_path=wav_path)
    try:
        await unload_medgemma()
        # Phase 7a: the speaking windows are read from the database, not
        # from a live session object — which is how a connection_lost or
        # post-restart finalisation still excludes our voice (spec §2.3).
        spans = await system_utterances.exclusion_spans(cid)
        # Read LAST, immediately before the audio phase: the doctor is asked
        # how many people spoke as they press Stop, and this gives that answer
        # the whole MedGemma-unload window to arrive. The same call records
        # what was actually used, so a late answer cannot make the row claim it
        # shaped this transcript.
        speakers = await consultations.speakers_for_diarisation(
            cid, DEFAULT_SPEAKERS)
        transcription = await asyncio.to_thread(
            transcribe_and_diarise, wav_path, spans, speakers)

        # The invariant itself now runs inside transcribe_and_diarise, on
        # RAW segments before the speaker merge (see consultation 445).
        # What is left here is the reporting of it.
        excluded_s = transcription.get("excluded_spans_s") or []

        # Exclusion backstops (consultation 445). Audited and counted, not
        # refused: the transcript-quality gate below already decides
        # whether a damaged transcript may be drafted from, and a second
        # refusal path would be a second thing to get wrong. The point is
        # that an over-reach announces itself instead of being invisible.
        for anomaly in (transcription.get("exclusion_anomalies") or []):
            await audit.log(None, "transcript.exclusion_anomaly",
                            "consultation", cid,
                            {**anomaly,
                             "excluded_fraction": transcription.get("excluded_fraction")})

        hallucinated = transcription.get("hallucinated_segments") or []
        if hallucinated:
            logger.error(
                "Consultation %d: %d segment(s) transcribed from muted "
                "silence — dropped. This should not happen; see "
                "drop_segments_in_excluded_spans.", cid, len(hallucinated))
            await audit.log(None, "transcript.silence_hallucination",
                            "consultation", cid,
                            {"dropped": len(hallucinated),
                             "spans": len(excluded_s),
                             "segments": [{"start": t.get("start"),
                                           "end": t.get("end"),
                                           "text": (t.get("text") or "")[:200]}
                                          for t in hallucinated[:10]]})

        turns, single_voice = attribute_roles(transcription["turns"])
        for i, turn in enumerate(turns):
            turn["idx"] = i
        await consultations.save_turns(cid, turns)
        # Recorded on the consultation, not left in a log line: one voice
        # means the roles are a default rather than a measurement, and the
        # review page must say so before anything is signed.
        if single_voice:
            await consultations.set_single_voice(cid)
            await audit.log(None, "transcript.single_voice", "consultation", cid,
                            {"turns": len(turns)})
            logger.warning("Consultation %d: only one speaker cluster — roles "
                           "defaulted to Patient and flagged for review", cid)

        # Transcript-quality gate, BEFORE the note call — a refusal must
        # cost no MedGemma time, and must never produce a draft from a
        # transcript that is not faithful to the audio (spec §1, #70).
        signals = transcript_quality.compute_signals(
            turns,
            audio_duration_s=transcription.get("audio_duration_s"),
            detected_language=transcription.get("detected_language"),
            language_probability=transcription.get("language_probability"),
            # Spec §2.4: the gate must be TOLD about the exclusions. A
            # system utterance at the end of a recording would otherwise
            # look like dropped audio to S4.
            excluded_spans_s=transcription.get("excluded_spans_s"),
        )
        verdict = transcript_quality.evaluate(signals)
        await consultations.save_quality(cid, signals, verdict["outcome"])

        if verdict["outcome"] == transcript_quality.OUTCOME_REFUSED:
            # No note is drafted. Transcript and audio are retained — this
            # is evidence, not rubbish. NOT 'failed': the pipeline worked,
            # the audio did not.
            await consultations.set_status(cid, transcript_quality.STATUS_UNRELIABLE)
            await audit.log(None, "consultation.quality_refused", "consultation",
                            cid, {"fired": verdict["fired"],
                                  "summary": transcript_quality.refusal_summary(
                                      verdict["fired"])})
            logger.warning("Consultation %d refused by the transcript-quality "
                           "gate: %s", cid,
                           transcript_quality.refusal_summary(verdict["fired"]))
            return

        note = await draft_note(await consultations.get_turns(cid))
        await consultations.save_note(cid, note)
        await consultations.set_status(cid, "awaiting_review")
        logger.info("Consultation %d ready for review", cid)
    except Exception as exc:
        logger.exception("Finalisation failed for consultation %d", cid)
        await consultations.set_status(cid, "failed", error=str(exc))
        # System event (no acting user): the monitoring pulse counts these.
        await audit.log(None, "finalisation.failed", "consultation", cid,
                        {"error": str(exc)[:300]})


async def regenerate_note(cid: int) -> None:
    """Re-draft after transcript corrections; keeps prior versions."""
    note = await draft_note(await consultations.get_turns(cid))
    await consultations.save_note(cid, note)
