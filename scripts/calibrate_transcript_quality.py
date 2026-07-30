"""Calibration measurements for the finalisation transcript-quality gate.

MEASUREMENT ONLY. This script sets no thresholds, implements no gate, and
changes no application behaviour. It produces the table the project owner
needs in order to fix the S1 and S3 thresholds in §4 of
TRANSCRIPT_QUALITY_GATE_SPEC.md. Choosing those numbers is a clinical
judgement and is the owner's alone.

Scope: the five genuine two-voice recordings made 2026-07-12 through the
live app — consultations 66-69 (known-good English) and 70 (the known-bad
Sinhala one, 03_diabetes_review_si, which produced a hallucinated English
translation and was voided, briefly unvoided, and re-voided).

FIDELITY RULE — the audio is NOT re-transcribed for S2 or S3.  Those
signals are read from the STORED turns in Postgres, because the stored
turns are what the pipeline actually produced and what the doctor
actually saw.  Re-transcribing would measure today's model against
yesterday's incident, which is the wrong comparison; and for #70 the
stored hallucinated transcript IS the object of study.  Only S1 (language
detection) touches the audio, in a single cheap window.

Signals, per §4 of the spec:

  S1  language     detected language + probability (audio, one window)
  S2  confidence   duration-weighted mean per-segment ASR confidence,
                   reported alongside the unweighted mean so the effect
                   of the weighting is visible
  S3  repetition   largest share of total tokens taken by any single
                   4-word n-gram, and the longest run of consecutive
                   identical segment texts
  S4  truncation   gap between the last stored segment's end timestamp
                   and the audio duration

Consultations 66 and 68 captured off-script reader speech after the
scripted close (2026-07-17 deviation report, docket item 6). The owner's
ruling leaves the recordings untouched on disk, so that speech is really
there and moves S2 and S4. Every figure for those two is therefore
reported TWICE — over the full audio and truncated at the scripted close
— and the detected boundary is printed so it can be overridden rather
than trusted silently.

Safety: read-only with respect to consultations. The database session is
opened in a READ ONLY transaction, so the no-writes guarantee is enforced
by Postgres rather than by discipline. Never calls the retention sweep,
never touches the one-active-consultation guard or the finalisation
queue, and never loads MedGemma. The Whisper model used for S1 is loaded
and explicitly released.

Usage:
    uv run python scripts/calibrate_transcript_quality.py
    uv run python scripts/calibrate_transcript_quality.py --skip-language
    uv run python scripts/calibrate_transcript_quality.py --close 66=291.4
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO = Path(__file__).parent.parent
OUT_PATH = REPO / "evals" / "transcript_quality_calibration.json"

# Established by checksum in evals/2026-07-17_recordings_inventory_deviation.md.
CONSULTATIONS: dict[int, str] = {
    66: "01_chest_pain_en",
    67: "02_febrile_child_en",
    68: "03_diabetes_review_en",
    69: "04_asthma_en",
    70: "03_diabetes_review_si",
}

# Only these two captured off-script speech after the scripted close.
NEEDS_TRUNCATION = (66, 68)

KNOWN_BAD = 70  # the Sinhala-through-English-pipeline hallucination

NGRAM_N = 4


# ---------------------------------------------------------------------------
# Metric functions — pure, no I/O, unit-tested on synthetic turns.
# ---------------------------------------------------------------------------

def tokenise(text: str) -> list[str]:
    """Lowercased word tokens. Punctuation is dropped: repetition loops
    reappear with varying punctuation and we are measuring the words."""
    return re.findall(r"\w+", text.lower())


def weighted_mean_confidence(turns: list[dict]) -> float | None:
    """Duration-weighted mean per-segment confidence — S2.

    Weighting by segment duration is the point: an unweighted mean lets a
    short clean segment cancel a long garbled one, which is exactly the
    failure #70 presented.  Returns None when there is no measurable
    duration.

    **Delegates to the pipeline's own implementation** rather than keeping
    a second copy.  This harness and `app/transcript_quality.py` used to
    compute S2 and S4 independently; the moment their arithmetic diverges,
    the calibration stops describing what the pipeline actually does.
    HANDOVER carried work item 2 asks for exactly this collapse (it names
    S1, which is still two paths — that one needs the multi-window
    redesign and is not touched here).
    """
    from app.transcript_quality import s2_weighted_confidence

    return s2_weighted_confidence(turns)


def unweighted_mean_confidence(turns: list[dict]) -> float | None:
    if not turns:
        return None
    return sum(float(t["confidence"]) for t in turns) / len(turns)


def max_ngram_share(turns: list[dict], n: int = NGRAM_N) -> tuple[float, str | None]:
    """Largest share of total tokens accounted for by any single n-gram.

    **Delegates to the pipeline's shared S3** (2026-07-31 — the same
    collapse as S2/S4 above; two copies of the arithmetic and the
    calibration stops describing the pipeline).
    """
    from app.transcript_quality import s3_repetition

    s3 = s3_repetition(turns)
    return s3["max_ngram_share"], s3["max_ngram"]


def max_consecutive_repeats(turns: list[dict]) -> int:
    """Longest run of consecutive segments with identical text.
    Delegates, as above."""
    from app.transcript_quality import s3_repetition

    return s3_repetition(turns)["max_consecutive_identical"]


def truncation_gap(turns: list[dict], audio_duration: float | None,
                   excluded_spans_s: list[tuple[float, float]] | None = None
                   ) -> float | None:
    """Seconds of audio after the last stored segment ends — S4.

    #70 dropped its final 33 s.  Returns None when the audio duration is
    unknown (audio purged), never a fabricated zero.

    Delegates to the pipeline's implementation, for the reason given on
    `weighted_mean_confidence` above.  Since 2026-07-25 that implementation
    also discounts Phase 7a speaking windows, so a consultation where the
    system spoke last is not mistaken for a truncated recording.
    """
    from app.transcript_quality import s4_truncation_gap

    return s4_truncation_gap(turns, audio_duration, excluded_spans_s)


def truncate_turns_at(turns: list[dict], boundary_s: float) -> list[dict]:
    """Turns ending at or before the boundary."""
    return [t for t in turns if float(t["end"]) <= boundary_s + 1e-9]


def find_scripted_close(turns: list[dict], script_path: Path) -> dict | None:
    """Locate the scripted close in the stored turns, mechanically.

    Scores each stored turn by how much of the script's final spoken
    line is CONTAINED in it, not by overall similarity: diarisation
    merges adjacent same-speaker turns, so the closing line frequently
    sits inside a much longer segment where a whole-string similarity
    ratio is dominated by the surrounding text and picks the wrong turn.
    Containment is the right measure for "which segment holds the
    close".  The boundary is that turn's end timestamp.

    Returns the match with its containment score so the caller can print
    it — a low score means the detection should be overridden with
    --close, not trusted.
    """
    from app.mock_scripts import parse_script

    if not script_path.exists() or not turns:
        return None
    script_turns = parse_script(script_path)
    if not script_turns:
        return None
    final_tokens = tokenise(script_turns[-1].text)
    if not final_tokens:
        return None

    best = None
    for turn in turns:
        candidate = tokenise(turn["text"])
        if not candidate:
            continue
        # Matched on TOKEN sequences, not characters: character-level
        # matching scores spurious common substrings ("the", "you", shared
        # letters) and reliably picks the wrong segment.
        matcher = difflib.SequenceMatcher(None, final_tokens, candidate,
                                          autojunk=False)
        matched = sum(block.size for block in matcher.get_matching_blocks())
        containment = matched / len(final_tokens)
        if best is None or containment > best["containment"]:
            best = {
                "idx": turn["idx"],
                "containment": round(min(1.0, containment), 3),
                "boundary_s": float(turn["end"]),
                "text": turn["text"][:90],
            }
    return best


# ---------------------------------------------------------------------------
# I/O — database, audio, model.  Each degrades to a clear absence.
# ---------------------------------------------------------------------------

def fetch_consultations(cids: list[int]) -> dict[int, dict]:
    """Stored turns and audio path per consultation, READ ONLY.

    The transaction is declared READ ONLY so Postgres itself rejects any
    write this script might ever be made to attempt.
    """
    import psycopg
    from dotenv import load_dotenv

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    out: dict[int, dict] = {}
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            for cid in cids:
                cur.execute(
                    "SELECT audio_path, status, voided_at IS NOT NULL"
                    " FROM consultation WHERE id = %s",
                    (cid,),
                )
                row = cur.fetchone()
                if row is None:
                    out[cid] = {"present": False}
                    continue
                cur.execute(
                    "SELECT idx, role, start_s, end_s, text, confidence"
                    " FROM transcript_turn WHERE consultation_id = %s"
                    " ORDER BY idx",
                    (cid,),
                )
                turns = [
                    {"idx": r[0], "role": r[1], "start": r[2], "end": r[3],
                     "text": r[4], "confidence": r[5]}
                    for r in cur.fetchall()
                ]
                out[cid] = {
                    "present": True,
                    "audio_path": row[0],
                    "status": row[1],
                    "voided": row[2],
                    "turns": turns,
                }
        conn.rollback()  # nothing to commit; make that explicit
    return out


def resolve_audio(audio_path: str | None) -> Path | None:
    """The stored path, or its FLAC/WAV sibling (approval compresses to
    FLAC, so an older stored .wav path may now be a .flac on disk)."""
    if not audio_path:
        return None
    path = Path(audio_path)
    if not path.is_absolute():
        path = REPO / path
    if path.exists():
        return path
    for suffix in (".flac", ".wav"):
        sibling = path.with_suffix(suffix)
        if sibling.exists():
            return sibling
    return None


def audio_duration_s(path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        import soundfile
        return float(soundfile.info(str(path)).duration)
    except Exception:  # pragma: no cover - depends on local codecs
        return None


class LanguageDetector:
    """faster-whisper language detection, one window, explicitly released.

    Loaded lazily so the script still runs (reporting language as
    unavailable) on a machine with no model or no GPU, and released in
    close() so nothing stays resident on the 4090 afterwards.  MedGemma
    is never involved.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model = None
        self._model_name = model_name or os.getenv("WHISPER_MODEL", "distil-large-v3")
        self._failed = False

    def _ensure(self) -> None:
        if self._model is not None or self._failed:
            return
        try:
            from app.transcription import _preload_cuda_libraries
            _preload_cuda_libraries()
            from faster_whisper import WhisperModel
            try:
                self._model = WhisperModel(self._model_name, device="cuda",
                                           compute_type="float16")
            except Exception:
                self._model = WhisperModel(self._model_name, device="cpu",
                                           compute_type="int8")
        except Exception as exc:  # pragma: no cover - environment dependent
            print(f"  ! language detection unavailable: {exc}", file=sys.stderr)
            self._failed = True

    def detect_windows(self, path: Path | None) -> dict | None:
        """Multi-window S1 through the ONE shared implementation
        (2026-07-31 — the collapse of the LAST two-path signal): window
        placement and the expected-language fraction are decided in
        `app/transcript_quality.py`; only the model call is supplied
        here, exactly as `app/finalize.py` supplies its own."""
        if path is None:
            return None
        self._ensure()
        if self._model is None:
            return None
        try:
            import soundfile
            from app.transcript_quality import s1_language_windows
            audio, sample_rate = soundfile.read(str(path), dtype="float32")
            if getattr(audio, "ndim", 1) > 1:
                audio = audio.mean(axis=1)

            def _detect(window):
                language, probability, _ = self._model.detect_language(
                    audio=window, language_detection_segments=1)
                return language, float(probability)

            return s1_language_windows(audio, sample_rate, _detect)
        except Exception as exc:  # pragma: no cover - environment dependent
            print(f"  ! language detection failed: {exc}", file=sys.stderr)
            return None

    def close(self) -> None:
        """Release the model rather than leaving it resident."""
        if self._model is None:
            return
        del self._model
        self._model = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover
            pass


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def measure(turns: list[dict], audio_duration: float | None) -> dict:
    from app.transcript_quality import s3_repetition

    s3 = s3_repetition(turns)
    return {
        "segments": len(turns),
        "s2_confidence_weighted": weighted_mean_confidence(turns),
        "s2_confidence_unweighted": unweighted_mean_confidence(turns),
        "s3_max_4gram_share": s3["max_ngram_share"],
        "s3_max_4gram": s3["max_ngram"],
        # §11 redesign (2026-07-31): repetition measured WITHIN segments —
        # the axis #70's loops actually live on. Measure-only.
        "s3_within_segment_share": s3["max_within_segment_share"],
        "s3_within_segment_share_floored": s3["max_within_segment_share_floored"],
        "s3_within_segment_ngram": s3["max_within_segment_ngram"],
        "s3_max_consecutive_identical": s3["max_consecutive_identical"],
        "s4_truncation_gap_s": truncation_gap(turns, audio_duration),
    }


def _fmt(value, spec: str = ".3f") -> str:
    return "—" if value is None else format(value, spec)


def build_rows(data: dict[int, dict], detector: LanguageDetector,
               overrides: dict[int, float],
               consultations_map: dict[int, str] | None = None) -> list[dict]:
    rows: list[dict] = []
    for cid, script in (consultations_map or CONSULTATIONS).items():
        record = data.get(cid, {"present": False})
        entry: dict = {
            "consultation": cid,
            "script": script,
            "expected": "known-bad (Sinhala via English-forced pipeline)"
                        if cid == KNOWN_BAD
                        else ("known-good English" if cid in CONSULTATIONS
                              else "unscripted room consultation"),
        }
        if not record.get("present"):
            entry["available"] = False
            entry["note"] = "consultation row not found in the database"
            rows.append(entry)
            continue

        audio = resolve_audio(record.get("audio_path"))
        duration = audio_duration_s(audio)
        turns = record.get("turns", [])
        entry.update({
            "available": True,
            "status": record.get("status"),
            "voided": record.get("voided"),
            "audio_file": str(audio) if audio else None,
            "audio_present": audio is not None,
            "audio_duration_s": duration,
            "stored_turns": len(turns),
        })

        if audio is None:
            entry["audio_note"] = (
                "AUDIO ABSENT — voided consultations are purge-eligible; "
                "S1 and S4 cannot be computed for this consultation"
                if record.get("voided") else
                "AUDIO ABSENT — S1 and S4 cannot be computed"
            )
        if not turns:
            entry["turns_note"] = "no stored turns — S2 and S3 unavailable"
            rows.append(entry)
            continue

        windows = detector.detect_windows(audio)
        entry["s1_multi_window"] = windows
        # First-window fields survive for row continuity — they are what
        # the single-window S1 always was.
        first = (windows or {}).get("windows") or [{}]
        entry["s1_language"] = first[0].get("language")
        entry["s1_language_probability"] = first[0].get("probability")
        entry["s1_expected_fraction"] = (windows or {}).get("expected_fraction")

        entry["full"] = measure(turns, duration)

        if cid in NEEDS_TRUNCATION:
            if cid in overrides:
                boundary = overrides[cid]
                detected = {"source": "--close override", "boundary_s": boundary}
            else:
                found = find_scripted_close(
                    turns, REPO / "mock_consultations" / f"{script}.md")
                if found is None:
                    entry["truncated_note"] = (
                        "scripted close not detected; full figures only")
                    rows.append(entry)
                    continue
                boundary = found["boundary_s"]
                detected = {"source": "auto-detected", **found}
            entry["scripted_close"] = detected
            kept = truncate_turns_at(turns, boundary)
            entry["truncated"] = measure(kept, boundary)
            dropped = len(turns) - len(kept)
            entry["truncated"]["dropped_segments"] = dropped
            if dropped == 0:
                # The closing line sits in the LAST stored segment, so the
                # off-script speech was merged into it by diarisation and
                # cannot be excluded at segment granularity. Say so rather
                # than presenting an identical "truncated" figure as if it
                # had excluded anything.
                entry["truncated"]["note"] = (
                    "NOT SEPARABLE: the scripted close falls inside the final "
                    "stored segment, so the off-script speech is merged into "
                    "the same segment. No turn-boundary truncation can "
                    "exclude it; these figures equal the full-audio ones. "
                    "Separating them would need word-level timestamps, which "
                    "the stored turns do not carry."
                )
        rows.append(entry)
    return rows


def print_table(rows: list[dict]) -> None:
    print()
    print("# Transcript-quality gate — calibration measurements")
    print()
    print("Measurement only. **No thresholds are set here.** S1 and S3 "
          "thresholds\nare the project owner's to fix, per §4 of "
          "TRANSCRIPT_QUALITY_GATE_SPEC.md.")
    print()
    print("S2/S3 come from the STORED turns (what the pipeline produced and "
          "the\ndoctor saw), never from re-transcription. S1 reads the audio "
          "in one window.")
    print()
    header = ("| Cid | Script | Window | Segs | S1 lang (p) | S1 en-frac | "
              "S2 wtd | S2 unwtd | S3 4-gram | S3 within | S3 run | S4 gap s |")
    print(header)
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        if not row.get("available"):
            print(f"| {row['consultation']} | {row['script']} | — | — | — | — | "
                  f"— | — | — | — | — | — |  <!-- {row.get('note','')} -->")
            continue
        if "full" not in row:
            print(f"| {row['consultation']} | {row['script']} | — | 0 | — | — | — "
                  f"| — | — | — | — | — |  <!-- {row.get('turns_note','')} -->")
            continue
        language = row.get("s1_language")
        probability = row.get("s1_language_probability")
        lang_cell = "—" if language is None else f"{language} ({_fmt(probability,'.2f')})"
        frac_cell = _fmt(row.get("s1_expected_fraction"), ".2f")
        windows = [("full", row["full"])]
        if "truncated" in row:
            windows.append(("to scripted close", row["truncated"]))
        for label, m in windows:
            print(
                f"| {row['consultation']} | {row['script']} | {label} | "
                f"{m['segments']} | {lang_cell if label == 'full' else '↑'} | "
                f"{frac_cell if label == 'full' else '↑'} | "
                f"{_fmt(m['s2_confidence_weighted'])} | "
                f"{_fmt(m['s2_confidence_unweighted'])} | "
                f"{_fmt(m['s3_max_4gram_share'])} | "
                f"{_fmt(m.get('s3_within_segment_share'))} | "
                f"{m['s3_max_consecutive_identical']} | "
                f"{_fmt(m['s4_truncation_gap_s'], '.1f')} |"
            )
    print()
    for row in rows:
        if row.get("audio_note"):
            print(f"- **#{row['consultation']}: {row['audio_note']}**")
        if row.get("scripted_close"):
            sc = row["scripted_close"]
            dropped = row.get("truncated", {}).get("dropped_segments", 0)
            print(f"- #{row['consultation']} scripted close "
                  f"({sc.get('source')}): boundary {sc['boundary_s']:.1f} s"
                  + (f", containment {sc['containment']}, turn {sc['idx']}"
                     if "containment" in sc else "")
                  + f", {dropped} segment(s) after it. Override with "
                    f"--close {row['consultation']}=<seconds> if wrong.")
        note = row.get("truncated", {}).get("note")
        if note:
            print(f"- **#{row['consultation']}: {note}**")
    print()
    print("**Thresholds are deliberately unset.** This script measures; it "
          "does not\njudge. Fixing the S1 and S3 thresholds is a clinical "
          "judgement and is the\nproject owner's alone.")
    print()


def parse_overrides(values: list[str]) -> dict[int, float]:
    out: dict[int, float] = {}
    for value in values or []:
        cid, _, seconds = value.partition("=")
        out[int(cid)] = float(seconds)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-language", action="store_true",
                        help="skip S1 (no model load)")
    parser.add_argument("--close", action="append", metavar="CID=SECONDS",
                        help="override the detected scripted close")
    parser.add_argument("--all-stored", action="store_true",
                        help="measure 66-70 AND every later consultation "
                             "with turns and audio on disk (the 2026-07-31 "
                             "S1/S3 re-calibration scope)")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)

    # Every entry point applies the whole schema, in one order
    # (app/schema.py). Read-only measurement still counts as an entry
    # point: the drift this guards against is a database left in a state
    # no single code path produces.
    from app import schema

    schema.ensure_all()

    consultations_map = dict(CONSULTATIONS)
    if args.all_stored:
        # Everything since the scripted five that still has audio on disk:
        # the wider distribution the S1/S3 candidate thresholds need. The
        # per-cid rows say when audio or turns are missing, so absence is
        # visible rather than silent.
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    "SELECT DISTINCT c.id FROM consultation c"
                    " JOIN transcript_turn t ON t.consultation_id = c.id"
                    " WHERE c.id > %s ORDER BY c.id", (max(CONSULTATIONS),))
                for (cid,) in cur.fetchall():
                    consultations_map.setdefault(cid, "(7a-era, unscripted)")

    try:
        data = fetch_consultations(list(consultations_map))
    except Exception as exc:
        print(f"Database unavailable: {exc}", file=sys.stderr)
        return 1

    detector = LanguageDetector()
    if args.skip_language:
        detector._failed = True  # never loads a model
    try:
        rows = build_rows(data, detector, parse_overrides(args.close),
                          consultations_map)
    finally:
        detector.close()

    print_table(rows)
    payload = {
        "generated_for": "TRANSCRIPT_QUALITY_GATE_SPEC.md §4 threshold setting",
        "measurement_only": True,
        "thresholds_set": False,
        "thresholds_note": ("Deliberately unset. Fixing S1 and S3 thresholds "
                            "is the project owner's clinical judgement."),
        "source_of_s2_s3": "stored transcript_turn rows (no re-transcription)",
        "consultations": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"Raw per-consultation JSON written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
