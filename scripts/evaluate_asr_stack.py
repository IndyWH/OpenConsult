"""ASR-stack experiment — could the final pass drop WhisperX? REPORT ONLY.

The question (owner-approved, parked 2026-07-28, scheduled 2026-07-30):
now the project is English-only, could the finalisation pass run on
faster-whisper large-v3 alone — dropping WhisperX and its dependency
scars (the ctranslate2 override, the pyannote pin, the torch
weights_only monkeypatch all exist because of this stack) — without
losing transcript quality? The decision is the OWNER'S; this harness
measures, reports and recommends.

Arms, run strictly sequentially (never both on the GPU at once):

  (a) The current pipeline path, verbatim: `finalize.transcribe_and_diarise`
      — WhisperX large-v3 + alignment + pyannote, exclusion spans muted,
      the silence invariant and the merge exactly as production runs them.
  (b) faster-whisper large-v3 + pyannote directly: segment-level
      timestamps (no alignment pass), per-segment confidence =
      exp(avg_logprob), majority-overlap cluster per segment, then the
      SAME `merge_into_turns` and `attribute_roles` — pseudo-words carry
      the cluster and score so the merge semantics are identical.

Recordings: the scripted set 66–70 (frozen references: the mock scripts
for 66–69, the frozen Sinhala reference for 70 — 70's WER is reported
with the caveat that it measures code-switched audio on English ASR) and
every 7a-era WAV still on disk (cid >= 445). FLAC-archived consultations
are skipped and reported. 66 and 68 carry off-script tail speech (the
2026-07-17 deviation report); it inflates WER equally for both arms, so
comparability holds — stated, not hidden.

Measures per recording and arm: WER against the frozen reference where
one exists; turn count and boundary drift against the STORED turns
(owner-corrected where applicable); role-attribution agreement with the
stored roles on a 0.25 s grid; segment-confidence distributions side by
side — the S2 gate (refuse < 0.60, flag < 0.70) was calibrated on
WhisperX word-score confidences, and arm (b)'s exp(avg_logprob) is a
DIFFERENT measure, so the recalibration cost must be visible.

Safety: OFFLINE — nothing is written to the database (reads only), no
consultation status is touched, and the finalisation queue never sees
this. VRAM follows the pipeline's own pattern: MedGemma is asked to
unload (keep_alive 0, /api/ps polled) before any audio model loads, the
arms run one at a time, and everything is freed at the end; MedGemma
reloads on demand at the next CDS/note call.

Usage:
    uv run python scripts/evaluate_asr_stack.py
    uv run python scripts/evaluate_asr_stack.py --cids 66,448
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import wave as wave_mod
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from app import consultations, finalize, system_utterances  # noqa: E402
from app.mock_scripts import parse_script  # noqa: E402

load_dotenv()

ROOT = Path(__file__).parent.parent
RECORDINGS = ROOT / "data" / "recordings"
OUT_PATH = ROOT / "evals" / "asr_stack_results.json"

# cid -> mock script (verified by byte size against the copies in
# mock_consultations/recordings/, 2026-07-30). 70 is the Sinhala one;
# its reference is the frozen file, not a script parse.
SCRIPTED = {66: "01_chest_pain_en", 67: "02_febrile_child_en",
            68: "03_diabetes_review_en", 69: "04_asthma_en",
            70: "03_diabetes_review_si"}
SI_REFERENCE = (ROOT / "mock_consultations" / "recordings" / "refs"
                / "03_diabetes_review_si.txt")
SEVEN_A_MIN_CID = 445
GRID_S = 0.25          # role-agreement sampling grid
DIARISE_SPEAKERS = 2   # both arms; the declared-count column is per-run
                       # state this harness does not try to reconstruct


# --- text measures (pure, tested) -------------------------------------------

def normalise(text: str) -> list[str]:
    """Lowercased words, punctuation stripped — WER should not count a
    comma against either arm."""
    cleaned = "".join(c.lower() if (c.isalnum() or c.isspace()) else " "
                      for c in text)
    return cleaned.split()


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: Levenshtein over normalised words / |reference|."""
    ref, hyp = normalise(reference), normalise(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i] + [0] * len(hyp)
        for j, hyp_word in enumerate(hyp, start=1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1,
                             previous[j - 1] + (ref_word != hyp_word))
        previous = current
    return previous[-1] / len(ref)


def boundary_drift_s(stored: list[dict], arm: list[dict]) -> float | None:
    """Median distance from each stored turn start to the nearest arm
    turn start — how far the arm's segmentation sits from the record."""
    stored_starts = [float(t.get("start_s", t.get("start", 0))) for t in stored]
    arm_starts = [float(t.get("start", 0)) for t in arm]
    if not stored_starts or not arm_starts:
        return None
    return round(statistics.median(
        min(abs(s - a) for a in arm_starts) for s in stored_starts), 2)


def role_agreement(stored: list[dict], arm: list[dict],
                   grid_s: float = GRID_S) -> float | None:
    """Time-weighted agreement with the stored (owner-corrected) roles,
    sampled on a grid across the stored turns' spans."""
    def role_at(turns, t, start_key, end_key):
        for turn in turns:
            if float(turn.get(start_key, 0)) <= t <= float(turn.get(end_key, 0)):
                return turn.get("role")
        return None

    points = agree = 0
    for turn in stored:
        start = float(turn.get("start_s", turn.get("start", 0)))
        end = float(turn.get("end_s", turn.get("end", 0)))
        t = start
        while t <= end:
            arm_role = role_at(arm, t, "start", "end")
            if arm_role is not None:
                points += 1
                agree += (arm_role == turn.get("role"))
            t += grid_s
    return round(agree / points, 3) if points else None


def confidence_summary(turns: list[dict]) -> dict | None:
    """Distribution + S2-style duration-weighted mean, side-by-side food."""
    confs = [float(t["confidence"]) for t in turns
             if t.get("confidence") is not None]
    if not confs:
        return None
    ordered = sorted(confs)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]  # noqa: E731
    weights = [max(0.0, float(t.get("end", 0)) - float(t.get("start", 0)))
               for t in turns if t.get("confidence") is not None]
    weighted = (sum(c * w for c, w in zip(confs, weights)) / sum(weights)
                if sum(weights) else statistics.mean(confs))
    return {"n": len(confs), "min": round(ordered[0], 3),
            "p25": round(pick(0.25), 3), "median": round(pick(0.5), 3),
            "p75": round(pick(0.75), 3), "max": round(ordered[-1], 3),
            "s2_weighted_mean": round(weighted, 3)}


# --- recordings and references ----------------------------------------------

def load_wav_16k(path: Path) -> np.ndarray:
    with wave_mod.open(str(path), "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def reference_for(cid: int) -> str | None:
    script = SCRIPTED.get(cid)
    if script is None:
        return None
    if cid == 70:
        return SI_REFERENCE.read_text()
    turns = parse_script(ROOT / "mock_consultations" / f"{script}.md")
    return " ".join(t.text for t in turns)


def candidate_cids(requested: list[int] | None) -> tuple[list[int], list[str]]:
    """(cids to run, skip notes). Scripted set + 7a-era WAVs on disk."""
    notes = []
    cids = set(SCRIPTED)
    for path in RECORDINGS.glob("consultation_*.wav"):
        try:
            cid = int(path.stem.split("_")[1])
        except ValueError:
            continue
        if cid >= SEVEN_A_MIN_CID:
            cids.add(cid)
    for path in RECORDINGS.glob("consultation_*.flac"):
        cid = int(path.stem.split("_")[1])
        if cid >= SEVEN_A_MIN_CID:
            notes.append(f"cid {cid}: FLAC archive — skipped (harness reads "
                         "the 16 kHz WAVs the pipeline wrote)")
    present = []
    for cid in sorted(cids):
        if (RECORDINGS / f"consultation_{cid}.wav").exists():
            present.append(cid)
        else:
            notes.append(f"cid {cid}: no WAV on disk — skipped")
    if requested:
        present = [c for c in present if c in requested]
    return present, notes


# --- the arms ---------------------------------------------------------------

def run_arm_a(wav_path: Path, spans: list[tuple[int, int]]) -> list[dict]:
    """The pipeline's own path, verbatim — loads and frees its models."""
    result = finalize.transcribe_and_diarise(
        str(wav_path), spans, DIARISE_SPEAKERS)
    turns = [dict(t) for t in result["turns"]]
    roled, _ = finalize.attribute_roles(turns)
    return roled


class ArmB:
    """faster-whisper large-v3 + pyannote, loaded once, freed at the end."""

    def __init__(self):
        from app.transcription import _preload_cuda_libraries
        _preload_cuda_libraries()
        import torch
        from faster_whisper import WhisperModel
        from pyannote.audio import Pipeline as PyannotePipeline

        self.torch = torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model = WhisperModel("large-v3", device=device,
                                  compute_type="float16" if device == "cuda"
                                  else "int8")
        _torch_load = torch.load
        torch.load = lambda *a, **k: _torch_load(
            *a, **{**k, "weights_only": False})
        try:
            self.diarizer = PyannotePipeline.from_pretrained(
                finalize.DIARIZATION_MODEL, use_auth_token=True
            ).to(torch.device(device))
        finally:
            torch.load = _torch_load

    def run(self, wav_path: Path, spans: list[tuple[int, int]]) -> list[dict]:
        audio = load_wav_16k(wav_path)
        muted = finalize.mute_spans(audio, spans or [])

        segments, _info = self.model.transcribe(
            muted, language="en", beam_size=5)
        raw = [{"start": float(s.start), "end": float(s.end),
                "text": s.text.strip(),
                "confidence": round(math.exp(s.avg_logprob), 3)}
               for s in segments if s.text.strip()]

        waveform = self.torch.from_numpy(muted[None, :])
        annotation = self.diarizer(
            {"waveform": waveform, "sample_rate": 16000},
            num_speakers=DIARISE_SPEAKERS)
        tracks = [(turn.start, turn.end, label) for turn, _, label
                  in annotation.itertracks(yield_label=True)]

        def cluster_for(start: float, end: float) -> str | None:
            overlap: dict[str, float] = {}
            for t_start, t_end, label in tracks:
                shared = min(end, t_end) - max(start, t_start)
                if shared > 0:
                    overlap[label] = overlap.get(label, 0.0) + shared
            return max(overlap, key=overlap.get) if overlap else None

        # Pseudo-words carry cluster + score so merge_into_turns applies
        # with IDENTICAL semantics to the pipeline's — that is the point
        # of the comparison.
        built = []
        for seg in raw:
            cluster = cluster_for(seg["start"], seg["end"])
            built.append({
                "start": seg["start"], "end": seg["end"], "text": seg["text"],
                "words": [{"word": w, "score": seg["confidence"],
                           **({"speaker": cluster} if cluster else {})}
                          for w in seg["text"].split()]})

        # The silence invariant, the same way the pipeline runs it.
        kept, _dropped = finalize.drop_segments_in_excluded_spans(
            built, finalize.spans_to_seconds(spans or []))
        turns = finalize.merge_into_turns(kept)
        for turn in turns:
            turn.pop("weight", None)
            turn["confidence"] = round(turn["confidence"], 3)
        roled, _ = finalize.attribute_roles(turns)
        return roled

    def close(self):
        import gc
        del self.model, self.diarizer
        gc.collect()
        if self.device == "cuda":
            self.torch.cuda.empty_cache()


# --- main -------------------------------------------------------------------

def measures_for(cid: int, arm_turns: list[dict], stored: list[dict],
                 reference: str | None) -> dict:
    text = " ".join(t["text"] for t in arm_turns)
    return {
        "turns": len(arm_turns),
        "wer": round(wer(reference, text), 3) if reference else None,
        "boundary_drift_s": boundary_drift_s(stored, arm_turns),
        "role_agreement": role_agreement(stored, arm_turns),
        "confidence": confidence_summary(arm_turns),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cids", default=None,
                        help="comma-separated subset (default: all candidates)")
    parser.add_argument("--write-baseline", action="store_true",
                        help="overwrite the committed baseline results file — "
                             "re-baselines every future comparison — instead "
                             "of writing a dated file beside it")
    args = parser.parse_args(argv or [])
    requested = ([int(c) for c in args.cids.split(",")]
                 if args.cids else None)

    cids, notes = candidate_cids(requested)
    print(f"Recordings: {cids}")
    for note in notes:
        print(f"  {note}")

    # The pipeline's own VRAM pattern: MedGemma out before audio models in.
    try:
        asyncio.run(finalize.unload_medgemma())
    except Exception as exc:  # noqa: BLE001 - Ollama may simply be down
        print(f"  (MedGemma unload skipped: {exc})")

    stored_turns = {c: asyncio.run(consultations.get_turns(c)) for c in cids}
    spans = {c: asyncio.run(system_utterances.exclusion_spans(c))
             for c in cids}
    references = {c: reference_for(c) for c in cids}

    results: dict[int, dict] = {c: {} for c in cids}

    print("\nArm (a): WhisperX large-v3 + alignment + pyannote "
          "(the pipeline path, verbatim)")
    for cid in cids:
        turns = run_arm_a(RECORDINGS / f"consultation_{cid}.wav", spans[cid])
        results[cid]["whisperx"] = measures_for(
            cid, turns, stored_turns[cid], references[cid])
        print(f"  cid {cid}: {results[cid]['whisperx']}")

    print("\nArm (b): faster-whisper large-v3 + pyannote, "
          "merge_into_turns applied the same way")
    arm_b = ArmB()
    try:
        for cid in cids:
            turns = arm_b.run(RECORDINGS / f"consultation_{cid}.wav",
                              spans[cid])
            results[cid]["faster_whisper"] = measures_for(
                cid, turns, stored_turns[cid], references[cid])
            print(f"  cid {cid}: {results[cid]['faster_whisper']}")
    finally:
        arm_b.close()

    payload = {
        "note": "REPORT ONLY — offline comparison, nothing written to the "
                "database. Arm (a) is the production path verbatim; arm (b) "
                "is faster-whisper large-v3 + pyannote with the same merge. "
                "Stored turns (owner-corrected where applicable) are the "
                "role/boundary reference; frozen scripts the WER reference. "
                "70 is code-switched Sinhala on English ASR — its WER is a "
                "known-bad case in both arms, kept for symmetry.",
        "speakers": DIARISE_SPEAKERS,
        "skipped": notes,
        "stored_turn_counts": {c: len(stored_turns[c]) for c in cids},
        "results": {str(c): results[c] for c in cids},
    }
    out_path = OUT_PATH if args.write_baseline else OUT_PATH.with_name(
        f"{OUT_PATH.stem}_{date.today().isoformat()}{OUT_PATH.suffix}")
    out_path.write_text(json.dumps(payload, indent=1))
    print(f"\nWritten: {out_path}")
    if not args.write_baseline:
        print(f"Baseline evals/{OUT_PATH.name} untouched. Compare:\n"
              f"  diff evals/{OUT_PATH.name} evals/{out_path.name}")

    print("\n| cid | ref | WER a/b | turns stored/a/b | drift a/b (s) "
          "| roles a/b | S2 a/b |")
    print("|---|---|---|---|---|---|---|")
    for cid in cids:
        a, b = results[cid]["whisperx"], results[cid]["faster_whisper"]
        fmt2 = lambda v: "—" if v is None else f"{v}"  # noqa: E731
        s2 = lambda m: "—" if not m["confidence"] else m["confidence"]["s2_weighted_mean"]  # noqa: E731
        print(f"| {cid} | {SCRIPTED.get(cid, '7a-era')} "
              f"| {fmt2(a['wer'])}/{fmt2(b['wer'])} "
              f"| {len(stored_turns[cid])}/{a['turns']}/{b['turns']} "
              f"| {fmt2(a['boundary_drift_s'])}/{fmt2(b['boundary_drift_s'])} "
              f"| {fmt2(a['role_agreement'])}/{fmt2(b['role_agreement'])} "
              f"| {s2(a)}/{s2(b)} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
