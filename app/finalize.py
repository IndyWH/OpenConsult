"""Post-consultation finalisation pipeline (Phase 2).

Triggered by the Stop button. Steps, in order:

1. UNLOAD MedGemma from the GPU. VRAM sequencing is the critical design
   constraint: the 4090 has 24 GB, MedGemma occupies ~17 GB resident, and
   WhisperX large-v3 + pyannote need ~6-8 GB. They cannot coexist, so the
   pipeline explicitly releases MedGemma (keep_alive=0) and waits for the
   VRAM to drop before loading the audio models.
2. Re-transcribe the full recording with WhisperX large-v3 (word-level
   timestamps + confidence scores).
3. Diarise with pyannote (num_speakers=2) and merge into speaker turns.
4. Free the audio models' VRAM.
5. Attribute roles: first-speaker-is-Doctor heuristic (the doctor opens
   the consultation in every mock script and typical practice); the
   review UI has a swap-roles override for when it guesses wrong.
6. Draft the SOAP note with MedGemma — which reloads onto the now-free
   GPU on its first call.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import time

import httpx

from app import consultations
from app.notes import draft_note

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
CDS_MODEL = os.getenv("CDS_MODEL", "hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M")
WHISPERX_MODEL = os.getenv("WHISPERX_MODEL", "large-v3")
# pyannote 4's default pipeline (community-1) is separately gated; 3.1 is
# the one this machine's HF token has access to.
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")


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


def transcribe_and_diarise(wav_path: str) -> list[dict]:
    """WhisperX + pyannote, returning speaker turns with confidence.

    Blocking and GPU-heavy — run via asyncio.to_thread. Loads its models,
    uses them, and frees them before returning.
    """
    from app.transcription import _preload_cuda_libraries

    _preload_cuda_libraries()  # torch/ctranslate2 need the pip cuDNN wheels

    import torch
    import whisperx

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute = "float16" if device == "cuda" else "int8"

    audio = whisperx.load_audio(wav_path)

    started = time.perf_counter()
    # Silero VAD: whisperx's default pyannote VAD checkpoint is incompatible
    # with the pinned pyannote 3.4 (see pyproject override note).
    model = whisperx.load_model(
        WHISPERX_MODEL, device, compute_type=compute, vad_method="silero"
    )
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
    annotation = diarizer(
        {"waveform": waveform, "sample_rate": 16000}, num_speakers=2
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

    # Merge word-assigned segments into speaker turns.
    turns: list[dict] = []
    for seg in result["segments"]:
        words = seg.get("words", [])
        speakers = [w.get("speaker") for w in words if w.get("speaker")]
        speaker = max(set(speakers), key=speakers.count) if speakers else "SPEAKER_00"
        scores = [w["score"] for w in words if "score" in w]
        confidence = sum(scores) / len(scores) if scores else 0.5
        text = seg["text"].strip()
        if not text:
            continue
        if turns and turns[-1]["speaker"] == speaker:
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

    # Free everything before MedGemma comes back.
    del model, align_model, diarizer, result
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    logger.info("Audio models released")

    for turn in turns:
        turn.pop("weight", None)
        turn["confidence"] = round(turn["confidence"], 3)
    return turns


def attribute_roles(turns: list[dict]) -> list[dict]:
    """First speaker is the Doctor (they open the consultation). The review
    UI provides a swap-roles override for when this heuristic is wrong."""
    if not turns:
        return turns
    doctor_speaker = turns[0]["speaker"]
    for turn in turns:
        turn["role"] = "Doctor" if turn["speaker"] == doctor_speaker else "Patient"
        turn.pop("speaker", None)
    return turns


async def finalize_consultation(cid: int, wav_path: str) -> None:
    """The full pipeline; sets consultation status as it progresses."""
    await consultations.set_status(cid, "processing", audio_path=wav_path)
    try:
        await unload_medgemma()
        turns = await asyncio.to_thread(transcribe_and_diarise, wav_path)
        turns = attribute_roles(turns)
        for i, turn in enumerate(turns):
            turn["idx"] = i
        await consultations.save_turns(cid, turns)

        note = await draft_note(await consultations.get_turns(cid))
        await consultations.save_note(cid, note)
        await consultations.set_status(cid, "awaiting_review")
        logger.info("Consultation %d ready for review", cid)
    except Exception as exc:
        logger.exception("Finalisation failed for consultation %d", cid)
        await consultations.set_status(cid, "failed", error=str(exc))


async def regenerate_note(cid: int) -> None:
    """Re-draft after transcript corrections; keeps prior versions."""
    note = await draft_note(await consultations.get_turns(cid))
    await consultations.save_note(cid, note)
