# Sinhala ASR benchmark — candidate models for Phase 5

**Date:** 2026-07-10
**Component:** Phase 5 stage 1 ("benchmark FIRST, train later", plan §7):
candidate Sinhala ASR models for replacing the live/final transcription
models, which are English-only today (live `distil-large-v3` has no
Sinhala; the final-pass `large-v3` does, and is benchmarked here).
**Harness:** `scripts/evaluate_sinhala_asr.py`. Raw data:
`evals/sinhala_asr_results.json` (SLR52 set),
`evals/sinhala_asr_results_slr30.json` (SLR30 set).

## Question under test

Which openly available ASR model transcribes Sinhala best — existing
community Whisper fine-tunes, a non-Whisper alternative, or stock
Whisper large-v3 — and is any of them good enough that Phase 5 does not
need its own fine-tune? This public-data benchmark is a *screen*; the
pre-registered evaluation on the project's own consultation recordings
(§ Pre-registration) is what the model decision will actually rest on.

## Finding 0: there is no standard public Sinhala ASR test set

Worth recording before any numbers, because it shaped the whole design:

- **Common Voice has never collected Sinhala.** Not in CV17, not in
  CV22 (138 languages, no `si`). The original benchmarking intent
  ("Common Voice Sinhala test split") is unsatisfiable. Additionally,
  Mozilla removed all Common Voice audio from Hugging Face in October
  2025 (moved to the Mozilla Data Collective).
- **FLEURS (102 languages) has no Sinhala.**
- **Meta MMS-1b-all (1,162 ASR languages) has no Sinhala adapter**, and
  **SeamlessM4T-v2 does not support Sinhala** — both were assessed as
  candidate models and excluded for this reason.

Sinhala ASR evaluation therefore relies on the two Google-collected
OpenSLR corpora, which are also what nearly every community fine-tune
was *trained* on — hence the contamination design below.

## Test sets

| Set | Source | Sample | Character |
|---|---|---|---|
| SLR52 | OpenSLR SLR52 "Large Sinhala ASR training data set" (185,293 crowdsourced utterances), via the `SPEAK-ASR/openslr-sinhala-asr` parquet mirror's test split (18,530 clips), revision pinned in the results JSON | 500 clips, `shuffle(seed=42)` | Many amateur speakers, phone-quality, short read phrases |
| SLR30 | OpenSLR SLR30 Sinhala TTS corpus (1,251 transcribed utterances), downloaded from openslr.org | 250 clips, `random.Random(42).sample` | Few professional speakers, studio quality, 48 kHz (resampled to 16 k) |

Both are *read speech* — neither resembles conversational consultation
audio. That gap is exactly what the real-recordings evaluation closes.

## Train/test contamination, per model

The SPEAK-ASR test split is a re-split of SLR52, not a held-out corpus:
any model trained on "all of SLR52" has seen our SLR52 test rows.
FLEURS would have avoided this but does not exist for Sinhala (above), so
instead: two test sets with different exposure profiles, plus per-model
documentation. **Scores of contaminated models are upper bounds.**

| Model | Training data (as documented) | SLR52 sample | SLR30 sample |
|---|---|---|---|
| `openai/whisper-small` / `large-v3` / `large-v3-turbo` (stock) | Web-scale, undisclosed (680 kh weakly supervised; v3 adds pseudo-labelled) | possible, unverifiable | possible, unverifiable |
| `Lingalingeswaran/whisper-small-sinhala_v3` | Own HF JSON dataset; the v1 card claims "Common Voice 11.0", which cannot be true for Sinhala — provenance unreliable | **likely** (community sets are SLR52-derived) | unknown |
| `seniruk/whisper-small-si` | Own "Sinscribe" dataset, provenance undocumented | unknown | unknown |
| `janiduchamika/whisper-small-sinhala-general-185k` | Undocumented, but 185k = SLR52's exact size and its eval WER (25.0) was computed on a slice of it | **near-certain: trained on the corpus our test rows come from** | unknown |
| `Subhaka/whisper-small-Sinhala-Fine_Tune` | Undocumented (2023) | likely | **near-certain — revealed by results** (10× better on SLR30 than SLR52, verbatim outputs; see finding 3) |
| `RRashmini/whisper-large-v2-sinhala` | Undocumented; only Whisper-large fine-tune found | likely | unknown |
| `SpideyDLK/wav2vec2-large-xls-r-300m-sinhala-low-LR-part1` | Undocumented | likely | unknown |

Excluded candidates: `facebook/mms-1b-all`, `facebook/seamless-m4t-v2-large`
(no Sinhala, see Finding 0); `IAmNotAnanth/wav2vec2-large-xls-r-300m-sinhala`
(its own card reports eval WER = 1.0, i.e. training never converged).

Tomorrow's consultation recordings are recorded *after* every candidate
was published — they are the only test data with zero contamination risk.

## Metric design (and why)

**Normalisation before scoring** (applied identically to reference and
hypothesis): Unicode NFC (Sinhala vowel signs have multiple valid
encodings); zero-width joiner/non-joiner stripped (they toggle ligature
rendering — ශ්‍රී vs ශ්රී — and are inconsistently present in references
themselves); lowercase (affects Latin text only, Sinhala has no case);
punctuation stripped; whitespace collapsed; digits kept as-is.

**WER and CER, both reported.** WER (whitespace tokens) is the headline
metric everyone quotes, but Sinhala compounds are segmented
inconsistently even between correct writers (observed in this run:
reference "හැඳින්වේ", hypothesis "හැඳින් වේ" — same reading, 2 word
errors). CER is fairer to an abugida — one wrong vowel diacritic costs
one character, not a whole word — so **CER is the primary metric for
model comparison** and WER is reported for comparability with published
numbers. CER is corpus-level, weighted by reference character count.

**Code-switching: per-script-class error attribution.** Every reference
token is classed by script — `sinhala` (Sinhala block U+0D80–U+0DFF),
`latin`, `digit`, `mixed`, `other`. The jiwer word alignment then
attributes each substitution/deletion to its reference token's class and
each insertion to the hypothesis token's class, yielding a per-class
error rate. Latin-class error rate *is* the English-term error rate in
code-switched speech — the number Phase 5 cares about, since drug names
and test names ("gliclazide", "HbA1c", "ECG") are exactly what a doctor
cannot afford to lose. Design choices, explicit:

- **Strict script matching.** If the reference has "pressure" and the
  model writes ප්‍රෙෂර් (a correct Sinhala transliteration), that counts
  as an error in the mechanical metric. Rationale: the downstream
  pipeline (CDS prompts, note citations, guideline retrieval) operates
  on English medical vocabulary; a transliterated drug name would not
  match. But because transliteration is *clinically* faithful, the
  pre-registered recordings protocol adds a manual adjudication pass
  that records transliterated hits separately rather than silently
  counting them either way.
- **English-term recall** (mechanical): reference Latin tokens ≥ 3 chars
  counted as recalled iff they appear as Latin tokens in the hypothesis.
  Order-insensitive by design — a term that survives anywhere in the
  utterance is retrievable downstream.
- On these two *read-speech* sets Latin tokens are rare (~1–2% of SLR52
  tokens), so per-class numbers here mainly validate the machinery; the
  real code-switching test is the consultation recordings.

**Determinism:** pinned dataset revision + seed-42 samples; Whisper
decoding beam 5 (matching the live faster-whisper config), no sampling,
no temperature fallback; CTC greedy (deterministic by construction);
fixed batch composition (batch 8, dataset order); library versions
recorded in the results JSON. All models run through one runtime
(transformers) so the comparison measures models, not inference engines.

## Results

CER is primary (see Metric design). Sorted by SLR52 CER. Latin-class
error rate is over only 51 reference tokens (SLR52) / 0 (SLR30) — thin
support, reported for completeness.

| Model | SLR52 WER | SLR52 CER | SLR30 WER | SLR30 CER | Latin-err (SLR52) |
|---|---|---|---|---|---|
| **seniruk-small** | **0.180** | **0.035** | **0.204** | **0.035** | 0.118 |
| janiduchamika-small-185k ⚠ | 0.263 | 0.047 | 0.261 | 0.049 | 0.118 |
| rrashmini-large-v2 | 0.416 | 0.105 | 0.419 | 0.089 | 0.333 |
| lingalingeswaran-small-v3 | 0.423 | 0.109 | 0.445 | 0.092 | 0.392 |
| xlsr-sinhala (wav2vec2) | 0.476 | 0.127 | 0.413 | 0.077 | 1.000 |
| subhaka-small ⚠⚠ | 0.681 | 0.234 | *0.062* | *0.013* | 1.020 |
| whisper-large-v3-turbo (stock) | 2.838 | 1.656 | 2.632 | 1.015 | 5.353 |
| whisper-large-v3 (stock) | 3.564 | 3.275 | 2.286 | 1.995 | 1.000 |
| whisper-small (stock) | 2.030 | 3.873 | 1.799 | 2.085 | 1.059 |

⚠ near-certain SLR52-trained (contamination table) — treat SLR52 score
as an upper bound; its SLR30 score is nearly identical, which argues it
generalises anyway.
⚠⚠ Subhaka's SLR30 score is a *contamination detection*, see finding 3.

### Finding 1: stock Whisper cannot transcribe Sinhala. At all.

Every stock model — including large-v3, the project's current
final-pass model — produces degenerate repetition loops on Sinhala
audio ("මිශ්රණයක් මිශ්රණයක් මිශ්රණයක්…" for a 2-word clip; WER > 1.0
because insertions count). This is not "weak" performance; it is
unusable output on the best-resourced multilingual ASR model available.
Consequence for Phase 5: there is no stock-model shortcut. The live
path's distil-large-v3 is English-only by design, and the final path's
large-v3 has now been shown useless for Sinhala — both must be swapped
for a Sinhala model when Sinhala consultations arrive.

### Finding 2: community whisper-small fine-tunes beat everything

The best model found, `seniruk/whisper-small-si` (WER 0.180 / CER
0.035 on SLR52), is a whisper-**small** fine-tune — it beats the one
large-v2 fine-tune (0.416/0.105) and the XLS-R CTC model. Its scores
are almost identical across the two independent test sets
(CER 0.035 on both), the profile of genuine generalisation rather than
memorisation — though its training data ("Sinscribe") is undocumented,
so contamination of both sets cannot be excluded; the recordings eval
settles it. Residual errors are dominated by spacing/orthographic
variants (හැඳින්වේ vs හැඳින් වේ), which WER punishes and CER absorbs —
visible in the 5× WER-to-CER gap.

### Finding 3: the dual-set design caught a contaminated candidate

`Subhaka/whisper-small-Sinhala-Fine_Tune` scores WER 0.062 / CER 0.013
on the SLR30 sample — 10× better than its own SLR52 score, with
verbatim-perfect transcriptions of rare compounds. That is a
memorisation signature: the model was near-certainly trained on SLR30
(the TTS corpus), which no model card mentions. Its honest number is
the SLR52 one (0.681 — worst fine-tune of the five). This is exactly
the failure mode the two-corpus design was added to expose, and it
validates treating every undocumented fine-tune's single-corpus score
with suspicion — including the winner's.

### Screen decision

All six non-stock candidates advance to the recordings eval (running
them is cheap); `seniruk-small` is the provisional front-runner,
`janiduchamika-small-185k` the strongest challenger. Stock Whisper is
retained only as the required baseline. If the recordings eval
confirms anything like CER ≤ 0.05 on real consultation audio with
acceptable English-term retention, Phase 5 may not need its own
fine-tune at all — the decision rule in the pre-registration applies.

## Pre-registration: scoring the real consultation recordings

Registered **before** any real recording exists (recordings happen this
weekend). The same harness scores them via manifest mode:

1. **References.** For each recording, the as-spoken reference is
   produced by correcting the source mock script
   (`app/mock_scripts.py` parses turns; live-path convention: turn texts
   concatenated in order, no speaker labels) to what was actually said,
   by the speakers, before any model output is viewed. Stored as
   `mock_consultations/recordings/refs/<id>.txt`.
2. **Manifest.** JSONL rows `{"id", "audio", "reference"}`; run
   `uv run python scripts/evaluate_sinhala_asr.py --manifest <file> --out
   evals/sinhala_asr_results_recordings.json`.
3. **Long audio.** Clips > 29 s automatically use chunked long-form
   decoding (transformers ASR pipeline, 30 s chunks, 5 s stride) with
   the same no-sampling settings — the only difference from benchmark
   mode, forced by Whisper's 30 s window.
4. **Metrics.** Identical: normalisation, corpus CER (primary), WER,
   per-script-class error rates, mechanical English-term recall.
5. **Curated term list.** Before viewing any hypothesis, the project
   owner freezes, per recording, the list of clinically load-bearing
   English terms in its reference (drugs, doses, investigations, signs).
   Candidate pool extracted from the routine scripts (01–05):
   ECG, blood pressure, pulse, aspirin, heart attack; dengue,
   paracetamol, platelets, rash; gliclazide, metformin, HbA1c,
   cholesterol, diabetes, monofilament; inhaler, preventer, asthma,
   wheezing, peak flow; ibuprofen, antacid, endoscopy, arrack (context
   word), alarm/warning signs vocabulary. Final list = the subset of
   these (plus any additions) actually present in each as-spoken
   reference.
6. **Adjudication.** For each curated term the model missed
   mechanically, the owner records whether the hypothesis contains a
   Sinhala-script transliteration of it (hit-by-transliteration,
   reported separately) or a genuine loss. Whether transliterated hits
   "count" for model selection is a clinical-workflow judgement — the
   project owner's call, made after seeing the data, and recorded.
7. **Decision rule.** The Phase 5 model choice is made on the
   recordings eval: primary = corpus CER; tie-breaker = curated-term
   accuracy (mechanical + adjudicated); public-benchmark ranks from this
   record are context only. If the best existing model is judged
   insufficient (owner's call against the intended live use), Phase 5
   proceeds to fine-tuning on the 4090 per the plan.
8. **n = 1 per model per recording**, deterministic settings, versions
   logged — same standards as this record.

## Limitations

- Both public test sets are read speech; neither tests conversational
  turn-taking, disfluency, or clinical vocabulary.
- Contamination as tabled above: community fine-tune scores on the
  SLR52 sample are upper bounds; janiduchamika's especially.
- Latin-token support in the public sets is too thin to rank models on
  code-switching — the machinery is validated, the question is deferred
  to the recordings eval.
- No LM fusion / rescoring for the CTC model (scored as shipped).
- Whisper hallucination loops (observed on stock small: "අපි අපි අපි…")
  inflate WER above 1.0; no repetition penalty was applied since none is
  used in the live path either.
- The mirror re-split of SLR52 is speaker-unverified: train/test rows
  may share speakers, flattering all SLR52-trained models further.

## Reproduce

```bash
uv sync
uv run python scripts/evaluate_sinhala_asr.py                 # SLR52 sample
# SLR30: download si_lk.tar.gz + si_lk.lines.txt from openslr.org/30,
# build the manifest (250-row seed-42 sample), then:
uv run python scripts/evaluate_sinhala_asr.py --manifest slr30_manifest.jsonl \
    --out evals/sinhala_asr_results_slr30.json
```
