"""Sinhala ASR benchmark: WER/CER with script-aware code-switching metrics.

Phase 5, stage 1 ("benchmark FIRST, train later"). Two modes:

- Benchmark mode (default): a deterministic 500-clip sample of the
  OpenSLR SLR52 test split (via the SPEAK-ASR parquet mirror, pinned
  revision), run against every candidate model.
- Recordings mode (--manifest): the same metrics over a JSONL manifest of
  {"audio": path, "reference": text} rows — this is how the real
  consultation recordings are scored (pre-registered in the eval record).

Metric design (full rationale in evals/2026-07-10_sinhala_asr_benchmark.md):
- Text normalisation: Unicode NFC, ZWJ/ZWNJ stripped, lowercase (Latin
  only — Sinhala has no case), punctuation stripped, whitespace collapsed.
  Digits kept as-is.
- WER over whitespace tokens (primary), CER over characters (secondary —
  fairer to an abugida where one wrong vowel sign shouldn't cost a word).
- Code-switching: every REFERENCE token is classed by script (sinhala /
  latin / digit / mixed / other). Errors from the jiwer alignment are
  attributed to the reference token's class (insertions to the
  hypothesis token's class), giving a per-script WER — latin-class WER is
  the English-term error rate. Strict script match: a correct term
  transliterated into Sinhala script still counts as an error here
  (manual adjudication of transliterated hits is a pre-registered,
  separately-reported step in recordings mode).
- English-term recall: reference Latin tokens of length >= 3 counted as
  recalled iff they appear as Latin tokens in the hypothesis.

Determinism: fixed dataset revision + seed-42 sample; no sampling in any
decoder (Whisper: beam 5, matching the live faster-whisper config; CTC
models: greedy — beams without an LM change nothing); fixed batch
composition; versions logged into the results file.

Usage:
  uv run python scripts/evaluate_sinhala_asr.py                    # full benchmark
  uv run python scripts/evaluate_sinhala_asr.py --limit 3 --models whisper-small
  uv run python scripts/evaluate_sinhala_asr.py --manifest recs.jsonl --models large-v3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

DATASET = "SPEAK-ASR/openslr-sinhala-asr"  # OpenSLR SLR52 parquet mirror
DATASET_REVISION = None  # resolved and recorded at run time
SAMPLE_SEED = 42
SAMPLE_N = 500
BATCH_SIZE = 8
OUT_PATH = Path(__file__).parent.parent / "evals" / "sinhala_asr_results.json"

# key -> (hf id, kind, notes). kind: whisper | ctc | mms
MODELS: dict[str, tuple[str, str, str]] = {
    "whisper-small": ("openai/whisper-small", "whisper", "stock anchor for the small fine-tunes"),
    "whisper-large-v3": ("openai/whisper-large-v3", "whisper", "stock baseline (required)"),
    "whisper-large-v3-turbo": ("openai/whisper-large-v3-turbo", "whisper", "stock, live-path candidate"),
    "lingalingeswaran-small-v3": ("Lingalingeswaran/whisper-small-sinhala_v3", "whisper", "small fine-tune"),
    "seniruk-small": ("seniruk/whisper-small-si", "whisper", "small fine-tune (Sinscribe data)"),
    "janiduchamika-small-185k": ("janiduchamika/whisper-small-sinhala-general-185k", "whisper", "small fine-tune, likely SLR52-trained (CONTAMINATED for this test set)"),
    "subhaka-small": ("Subhaka/whisper-small-Sinhala-Fine_Tune", "whisper", "small fine-tune (2023)"),
    "rrashmini-large-v2": ("RRashmini/whisper-large-v2-sinhala", "whisper", "only large fine-tune found; no tokenizer files -> stock large-v2 processor"),
    # post-hoc additions (2026-07-12, recordings eval): sibling checkpoints of
    # the same RRashmini large-v2 training effort, found after the benchmark;
    # all lack tokenizer files -> same stock large-v2 processor fallback
    "rrashmini-large": ("RRashmini/whisper-large-sinhala", "whisper", "post-hoc: large-v2-based sibling checkpoint (Dec 21 2024)"),
    "rrashmini-large-1": ("RRashmini/whisper-large-sinhala-1", "whisper", "post-hoc: large-v2-based sibling checkpoint (Dec 22 2024)"),
    "rrashmini-large-v2-t1": ("RRashmini/whisper-large-v2-sinhala-t1", "whisper", "post-hoc: large-v2-based sibling checkpoint (Dec 22 2024)"),
    # facebook/mms-1b-all and seamless-m4t-v2 were assessed and EXCLUDED:
    # neither supports Sinhala (checked 2026-07-10; 'sin' absent from the
    # MMS ASR adapter list and from the Seamless language list).
    "xlsr-sinhala": ("SpideyDLK/wav2vec2-large-xls-r-300m-sinhala-low-LR-part1", "ctc", "wav2vec2 XLS-R community fine-tune"),
}

SINHALA_RE = re.compile(r"[඀-෿]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"\d")
# Everything that is not a letter, mark (Sinhala vowel signs are Mn/Mc), digit or space.
_PUNCT_RE = re.compile(r"[^\w\s඀-෿]|_", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("‍", "").replace("‌", "")  # ZWJ/ZWNJ
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def token_class(tok: str) -> str:
    has_sin = bool(SINHALA_RE.search(tok))
    has_lat = bool(LATIN_RE.search(tok))
    if has_sin and has_lat:
        return "mixed"
    if has_sin:
        return "sinhala"
    if has_lat:
        return "latin"
    if DIGIT_RE.search(tok):
        return "digit"
    return "other"


def score_pair(ref: str, hyp: str) -> dict:
    """WER/CER plus per-script-class error attribution for one utterance."""
    import jiwer

    ref_n, hyp_n = normalize(ref), normalize(hyp)
    if not ref_n:
        return {}
    out = jiwer.process_words([ref_n], [hyp_n])
    cer = jiwer.cer([ref_n], [hyp_n])

    ref_toks = ref_n.split()
    hyp_toks = hyp_n.split()
    cls_counts: dict[str, dict[str, int]] = {}

    def bump(cls: str, key: str) -> None:
        cls_counts.setdefault(cls, {"n_ref": 0, "errors": 0})[key] += 1

    for tok in ref_toks:
        bump(token_class(tok), "n_ref")
    for chunk in out.alignments[0]:
        if chunk.type == "equal":
            continue
        if chunk.type in ("substitute", "delete"):
            for tok in ref_toks[chunk.ref_start_idx : chunk.ref_end_idx]:
                bump(token_class(tok), "errors")
        if chunk.type in ("substitute", "insert"):
            # insertions (and the hyp side of substitutions beyond ref
            # length) attributed to the hypothesis token's class
            if chunk.type == "insert":
                for tok in hyp_toks[chunk.hyp_start_idx : chunk.hyp_end_idx]:
                    bump(token_class(tok), "errors")

    latin_ref = [t for t in ref_toks if token_class(t) == "latin" and len(t) >= 3]
    latin_hyp = {t for t in hyp_toks if token_class(t) == "latin"}
    return {
        "wer_counts": {"S": out.substitutions, "D": out.deletions, "I": out.insertions, "N": len(ref_toks)},
        "cer": cer,
        "class_counts": cls_counts,
        "en_terms_ref": latin_ref,
        "en_terms_recalled": [t for t in latin_ref if t in latin_hyp],
    }


def aggregate(per_clip: list[dict]) -> dict:
    S = sum(c["wer_counts"]["S"] for c in per_clip)
    D = sum(c["wer_counts"]["D"] for c in per_clip)
    I = sum(c["wer_counts"]["I"] for c in per_clip)
    N = sum(c["wer_counts"]["N"] for c in per_clip)
    # corpus CER: length-weighted mean of per-clip CER is not exact; we
    # keep per-clip cer and weight by reference char count
    cer_num = sum(c["cer"] * c["_ref_chars"] for c in per_clip)
    cer_den = sum(c["_ref_chars"] for c in per_clip)
    classes: dict[str, dict[str, int]] = {}
    for c in per_clip:
        for cls, v in c["class_counts"].items():
            agg = classes.setdefault(cls, {"n_ref": 0, "errors": 0})
            agg["n_ref"] += v["n_ref"]
            agg["errors"] += v["errors"]
    terms_ref = sum(len(c["en_terms_ref"]) for c in per_clip)
    terms_rec = sum(len(c["en_terms_recalled"]) for c in per_clip)
    return {
        "wer": (S + D + I) / N if N else None,
        "cer": cer_num / cer_den if cer_den else None,
        "per_class_wer": {
            cls: {"error_rate": v["errors"] / v["n_ref"] if v["n_ref"] else None, **v}
            for cls, v in sorted(classes.items())
        },
        "en_term_recall": terms_rec / terms_ref if terms_ref else None,
        "en_terms_total": terms_ref,
        "n_clips": len(per_clip),
        "n_ref_tokens": N,
    }


# ---------------------------------------------------------------- models


def load_whisper(model_id: str):
    from transformers import AutoProcessor, WhisperForConditionalGeneration
    from transformers.generation import GenerationConfig

    try:
        processor = AutoProcessor.from_pretrained(model_id)
    except Exception:
        # RRashmini/whisper-large-v2-sinhala ships no tokenizer files
        processor = AutoProcessor.from_pretrained("openai/whisper-large-v2")
        print(f"  [{model_id}] no processor in repo -> stock whisper-large-v2 processor")
    model = WhisperForConditionalGeneration.from_pretrained(
        model_id, torch_dtype=torch.float16
    ).to("cuda").eval()
    gc = model.generation_config
    if gc is None or gc.lang_to_id is None or not gc.lang_to_id:
        base = "openai/whisper-large-v2" if "large" in model_id.lower() else "openai/whisper-small"
        model.generation_config = GenerationConfig.from_pretrained(base)
        print(f"  [{model_id}] generation_config lacked language map -> {base}'s")

    def transcribe(batch_audio: list) -> list[str]:
        feats = processor(
            [a["array"] for a in batch_audio],
            sampling_rate=16000,
            return_tensors="pt",
            return_attention_mask=True,
        )
        inputs = feats.input_features.to("cuda", torch.float16)
        mask = feats.attention_mask.to("cuda") if "attention_mask" in feats else None
        with torch.no_grad():
            ids = model.generate(
                inputs,
                attention_mask=mask,
                language="sinhala",
                task="transcribe",
                num_beams=5,
                do_sample=False,
                max_new_tokens=200,
            )
        return processor.batch_decode(ids, skip_special_tokens=True)

    return transcribe


def load_ctc(model_id: str, mms_lang: str | None = None):
    from transformers import AutoProcessor, Wav2Vec2ForCTC

    if mms_lang:
        processor = AutoProcessor.from_pretrained(model_id)
        processor.tokenizer.set_target_lang(mms_lang)
        model = Wav2Vec2ForCTC.from_pretrained(model_id, ignore_mismatched_sizes=True)
        model.load_adapter(mms_lang)
    else:
        processor = AutoProcessor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id)
    model = model.to("cuda").eval()  # fp32: CTC heads are small, fp16 buys little

    def transcribe(batch_audio: list) -> list[str]:
        feats = processor(
            [a["array"] for a in batch_audio],
            sampling_rate=16000,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            logits = model(
                feats.input_values.to("cuda"),
                attention_mask=feats.attention_mask.to("cuda"),
            ).logits
        ids = torch.argmax(logits, dim=-1)  # greedy — deterministic
        return processor.batch_decode(ids)

    return transcribe


def load_longform(model_id: str, kind: str):
    """Chunked long-form decoding (recordings mode, clips > 30 s): the
    transformers ASR pipeline with 30 s chunks / 5 s stride. Same models,
    same no-sampling decoding; only the windowing differs — pre-registered
    for the real consultation recordings."""
    from transformers import pipeline

    kwargs: dict = {"chunk_length_s": 30, "stride_length_s": 5, "device": "cuda"}
    if kind == "whisper":
        kwargs["torch_dtype"] = torch.float16
    try:
        pipe = pipeline("automatic-speech-recognition", model=model_id, **kwargs)
    except Exception:
        # RRashmini repo lacks tokenizer files -> stock large-v2 processor
        from transformers import AutoProcessor

        proc = AutoProcessor.from_pretrained("openai/whisper-large-v2")
        pipe = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            tokenizer=proc.tokenizer,
            feature_extractor=proc.feature_extractor,
            **kwargs,
        )
    if kind == "whisper" and not getattr(pipe.model.generation_config, "lang_to_id", None):
        # some fine-tune repos (RRashmini large siblings) ship no
        # generation_config.json; without lang_to_id the `language` argument
        # to generate() raises. Borrow the stock config of the same base.
        from transformers import GenerationConfig

        base = "openai/whisper-large-v2" if "large" in model_id.lower() else "openai/whisper-small"
        borrowed = GenerationConfig.from_pretrained(base)
        pipe.model.generation_config = borrowed
        # the pipeline snapshots its own generation_config at construction and
        # passes it to generate(), overriding the model's — replace both
        pipe.generation_config = borrowed
    gen_kwargs = (
        {"language": "sinhala", "task": "transcribe", "num_beams": 5, "do_sample": False}
        if kind == "whisper"
        else {}
    )

    def transcribe(batch_audio: list) -> list[str]:
        out = []
        for a in batch_audio:
            res = pipe({"raw": a["array"], "sampling_rate": 16000}, generate_kwargs=gen_kwargs) \
                if gen_kwargs else pipe({"raw": a["array"], "sampling_rate": 16000})
            out.append(res["text"])
        return out

    return transcribe


def build_transcriber(key: str, long_form: bool = False):
    model_id, kind, _ = MODELS[key]
    if long_form:
        return load_longform(model_id, kind)
    if kind == "whisper":
        return load_whisper(model_id)
    return load_ctc(model_id)


# ------------------------------------------------------------------ data


def load_benchmark_clips(limit: int | None):
    from datasets import load_dataset
    from huggingface_hub import HfApi, hf_hub_download

    global DATASET_REVISION
    api = HfApi()
    DATASET_REVISION = api.dataset_info(DATASET).sha
    # fetch ONLY the test shards (load_dataset would pull all splits, ~13 GB)
    shards = sorted(
        f
        for f in api.list_repo_files(DATASET, repo_type="dataset", revision=DATASET_REVISION)
        if f.startswith("data/test-") and f.endswith(".parquet")
    )
    local = [
        hf_hub_download(DATASET, f, repo_type="dataset", revision=DATASET_REVISION)
        for f in shards
    ]
    ds = load_dataset("parquet", data_files=local, split="train")
    # decode audio bytes ourselves with soundfile (librosa won't build here)
    from datasets import Audio

    ds = ds.cast_column("audio", Audio(decode=False))
    ds = ds.shuffle(seed=SAMPLE_SEED).select(range(SAMPLE_N))
    if limit:
        ds = ds.select(range(limit))
    return [
        {"id": ex["file_id"], "audio": _decode_audio(ex["audio"]), "reference": ex["text"]}
        for ex in ds
    ]


def _decode_audio(audio: dict) -> dict:
    import io

    import soundfile as sf

    array, sr = sf.read(io.BytesIO(audio["bytes"]), dtype="float32")
    if array.ndim > 1:
        array = array.mean(axis=1)
    if sr != 16000:
        import torchaudio

        array = torchaudio.functional.resample(torch.from_numpy(array), sr, 16000).numpy()
    return {"array": array, "sampling_rate": 16000}


def load_manifest_clips(path: str, limit: int | None):
    import soundfile as sf

    clips = []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        array, sr = sf.read(row["audio"], dtype="float32")
        if array.ndim > 1:
            array = array.mean(axis=1)
        if sr != 16000:
            import torchaudio

            array = torchaudio.functional.resample(
                torch.from_numpy(array), sr, 16000
            ).numpy()
        clips.append(
            {
                "id": row.get("id", Path(row["audio"]).stem),
                "audio": {"array": array, "sampling_rate": 16000},
                "reference": row["reference"],
            }
        )
        if limit and len(clips) >= limit:
            break
    return clips


# ------------------------------------------------------------------ main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated keys (default: all)")
    ap.add_argument("--limit", type=int, help="clips per model (smoke tests)")
    ap.add_argument("--manifest", help="JSONL of {audio, reference} instead of the benchmark set")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    torch.manual_seed(SAMPLE_SEED)
    keys = args.models.split(",") if args.models else list(MODELS)
    unknown = [k for k in keys if k not in MODELS]
    if unknown:
        sys.exit(f"unknown model keys: {unknown} (have: {list(MODELS)})")

    if args.manifest:
        clips = load_manifest_clips(args.manifest, args.limit)
        source = {"kind": "manifest", "path": args.manifest}
    else:
        clips = load_benchmark_clips(args.limit)
        source = {
            "kind": "benchmark",
            "dataset": DATASET,
            "revision": DATASET_REVISION,
            "split": "test",
            "sample": f"shuffle(seed={SAMPLE_SEED}).select(range({SAMPLE_N}))",
        }
    long_form = any(len(c["audio"]["array"]) > 29 * 16000 for c in clips)
    print(f"{len(clips)} clips | long_form={long_form} | models: {keys}", flush=True)

    import importlib.metadata as im

    results: dict = {
        "source": source,
        "versions": {
            p: im.version(p)
            for p in ["transformers", "datasets", "jiwer", "torch"]
        },
        "decoding": "whisper: beam 5, no sampling, language=sinhala, task=transcribe, fp16; ctc: greedy, fp32",
        "long_form": long_form,
        "models": {},
    }

    for key in keys:
        model_id, kind, notes = MODELS[key]
        print(f"\n=== {key} ({model_id}) ===", flush=True)
        try:
            transcribe = build_transcriber(key, long_form=long_form)
        except Exception as e:
            print(f"  LOAD FAILED: {e}", flush=True)
            results["models"][key] = {"model_id": model_id, "error": f"load failed: {e}"}
            continue

        per_clip = []
        rows = []
        for i in range(0, len(clips), BATCH_SIZE):
            batch = clips[i : i + BATCH_SIZE]
            try:
                hyps = transcribe([c["audio"] for c in batch])
            except Exception as e:
                print(f"  batch {i}: FAILED {e}", flush=True)
                hyps = [""] * len(batch)
            for c, hyp in zip(batch, hyps):
                s = score_pair(c["reference"], hyp)
                if not s:
                    continue
                s["_ref_chars"] = len(normalize(c["reference"]))
                per_clip.append(s)
                rows.append(
                    {
                        "id": c["id"],
                        "ref": c["reference"],
                        "hyp": hyp,
                        "wer_counts": s["wer_counts"],
                        "cer": round(s["cer"], 4),
                    }
                )
            if (i // BATCH_SIZE) % 10 == 0:
                done = min(i + BATCH_SIZE, len(clips))
                print(f"  {done}/{len(clips)}", flush=True)

        summary = aggregate(per_clip)
        results["models"][key] = {
            "model_id": model_id,
            "kind": kind,
            "notes": notes,
            **summary,
            "clips": rows,
        }
        print(
            f"  WER {summary['wer']:.3f} | CER {summary['cer']:.3f} | clips {summary['n_clips']}",
            flush=True,
        )

        del transcribe
        torch.cuda.empty_cache()

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\nwrote {args.out}")

    print("\n| Model | Kind | WER | CER | Sinhala-WER | Latin-WER | n latin ref |")
    print("|---|---|---|---|---|---|---|")
    for key in keys:
        m = results["models"][key]
        if "error" in m:
            print(f"| {key} | — | LOAD FAILED | | | | |")
            continue
        pc = m["per_class_wer"]
        sin = pc.get("sinhala", {})
        lat = pc.get("latin", {})
        fmt = lambda v: f"{v:.3f}" if v is not None else "—"
        print(
            f"| {key} | {m['kind']} | {fmt(m['wer'])} | {fmt(m['cer'])} "
            f"| {fmt(sin.get('error_rate'))} | {fmt(lat.get('error_rate'))} | {lat.get('n_ref', 0)} |"
        )


if __name__ == "__main__":
    main()
