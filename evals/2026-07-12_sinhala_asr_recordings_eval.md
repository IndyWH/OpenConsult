# Sinhala ASR — real-recordings evaluation (pre-registered)

**Date:** 2026-07-12. Executes the pre-registration in
`evals/2026-07-10_sinhala_asr_benchmark.md` § Pre-registration, on the
first real code-switched consultation recording. Raw per-model output:
`evals/sinhala_asr_results_recordings.json`; manifest:
`evals/recordings_manifest_si.jsonl`.

## Test material

One recording so far (the pre-registered set anticipates two; `01_chest_pain_si`
is not yet recorded):

- `mock_consultations/recordings/03_diabetes_review_si.wav` — ~7 min,
  16 kHz mono, two real voices, recorded 2026-07-12 through the live app
  (consultation 70) and copied out of `data/recordings/`.

## Freeze compliance (steps 1 and 5)

- **Reference:** the draft generated 2026-07-11 from the script was
  **declared as-spoken by the project owner (a speaker) — script read
  verbatim, attestation 2026-07-12 — and frozen unchanged.** It was not
  re-checked against the audio by listening.
- **Curated term list:** 12 terms frozen before any model output was
  viewed — `mock_consultations/recordings/refs/03_diabetes_review_si.terms.txt`
  (gliclazide, metformin, HbA1c, cholesterol, diabetes, monofilament,
  blood pressure, losartan, atorvastatin, neuropathy, ulcer, referral).
- **Known wrinkle, recorded for honesty:** because the recording was made
  *through the live app*, the owner incidentally saw the live path's
  (stock distil-large-v3) degenerate transcript during the session,
  before the freeze. That output was near-total garbage (repetition
  loops), the reference was frozen by verbatim attestation rather than
  transcription from audio, and none of the evaluated hypotheses had been
  seen — anchoring risk judged negligible, but it is a deviation from the
  letter of "before any model output is viewed."

## Harness fix required first (long-form path had never run)

The benchmark's clips were all <29 s, so manifest long-form decoding ran
for the first time today — and produced **empty hypotheses for every
model**, which the scorer reported as a uniform WER/CER 1.000 table. A
wrong number that looks like a result. Cause: `whisperx` declares
`torchcodec` as a dependency (it never imports it — audio loads via its
own ffmpeg subprocess); transformers 4.57's chunked ASR pipeline probes
for torchcodec by *package metadata*, then `import torchcodec` throws,
because torchcodec 0.7 cannot load against Ubuntu 26.04's FFmpeg 8
(supports FFmpeg 4–7 only). Fix: exclude torchcodec via a uv dependency
override (`pyproject.toml`), making transformers skip that path;
verified whisperx still imports and a 60 s slice transcribes. The empty
first run was discarded and the results JSON regenerated.

## Results — corpus scores on the one recording (n = 1 clip per model)

CER is primary per the decision rule. 106 Latin-script (English) tokens
in the reference. Benchmark CERs shown for contrast (SLR52 sample).

| Model | CER (recording) | WER | Sinhala-class err | English-term recall (mech.) | SLR52 CER (benchmark) |
|---|---|---|---|---|---|
| **xlsr-sinhala** (CTC) | **0.462** | 0.845 | 0.811 | 0/106 | 0.127 |
| **seniruk-small** | **0.504** | 0.692 | 0.624 | 0/106 | 0.035 |
| rrashmini-large-v2 | 0.523 | 0.754 | 0.699 | 0/106 | 0.105 |
| lingalingeswaran-small-v3 | 0.594 | 0.860 | 0.828 | 0/106 | 0.109 |
| janiduchamika-small-185k | 0.644 | 0.856 | 0.824 | 0/106 | 0.047 |
| subhaka-small | 0.705 | 0.962 | 0.954 | 0/106 | 0.234 |
| whisper-large-v3-turbo (stock) | 0.849 | 0.989 | 0.994 | 19/106 (0.18) | 1.656 |
| whisper-small (stock) | 0.898 | 0.995 | 0.994 | 0/106 | 3.873 |
| whisper-large-v3 (stock) | 1.100 | 1.082 | 1.100 | 0/106 | 3.275 |

## Findings

1. **Every model degrades massively from read speech to real
   conversational consultation audio.** The benchmark front-runner goes
   0.035 → 0.504 corpus CER. Two natural voices, conversational pace,
   turn-taking, and dense code-switching are a different problem from
   short read phrases — exactly the gap the pre-registration predicted the
   public sets could not measure.

   > **Limitation (added 2026-07-25) — this comparison is confounded.**
   > The two cells differ in three ways at once: **delivery** (read vs
   > conversational), **acoustics-plus-speaker** (corpus recordings and
   > speakers vs this project's room, mic and readers), and **content**
   > (monolingual vs code-switched clinical). The 0.035 → 0.504 number
   > is unaffected and stands as measured; what is *not* established by
   > this data is the natural reading of it — that code-switching caused
   > the collapse. That specific attribution needs a decomposition this
   > eval was not designed to provide. A pre-registered experiment to
   > decompose it sits **designed and unrun** at
   > `evals/2026-07-25_sinhala_confound_prereg.md`.
   >
   > **Finding 3 is unaffected by this confound and stands on its own:**
   > the 0/106 mechanical English-term recall is a direct within-recording
   > observation, not a cross-cell comparison, and needs no decomposition.
2. **The ranking reshuffles: the CTC model takes best corpus CER**
   (xlsr-sinhala 0.462), overtaking seniruk-small (0.504, still best
   Whisper). But CER alone flatters CTC output, which is
   punctuation-free and heavily fragmented; seniruk's transcript is
   substantially more readable. WER ranks seniruk first (0.692 vs
   0.845). The decision should weigh the adjudicated term accuracy and
   readability, not CER alone.
3. **Code-switching is the systematic casualty: mechanical English-term
   recall is 0/106 for every Sinhala fine-tune.** Every English clinical
   term was either transliterated into Sinhala script or lost. Spot
   checks show both outcomes: `metformin` → මෙත්ෆෝමෙන් (clean
   transliteration), `cholesterol` → කලස්ට්‍රෝල් (clean),
   `neuropathy` → නිව්රවපති (recognisable), but `gliclazide` →
   වික්පසායිල් / ලිප්ලසායි (mangled beyond safe recognition) — the
   drug-name class the CDS and notes pipeline most depends on.
   Adjudication (step 6) decides what survives: worksheet at
   `evals/adjudication_03_si_worksheet.md` (every curated-term
   occurrence aligned across the top three models). Only stock
   large-v3-turbo keeps any Latin script (18% recall) and it is
   unusable overall.
4. **Stock large-v3 confirms the benchmark's degenerate-loop finding on
   real audio** (CER 1.100 — insertions push it past 1.0). The live
   path's distil-large-v3 produced the same class of garbage during the
   session itself (visible in consultation 70's stored transcript).
5. **Chunked decoding introduces occasional boundary artifacts** —
   duplicated phrases at ~30 s chunk seams (visible in the seniruk
   hypothesis). Same settings as pre-registered; noted as a shared,
   direction-neutral cost across models.

## Decision status (step 7)

Pending the owner's adjudication pass and judgement. What the numbers
already say: with best-in-class corpus CER ≈ 0.46–0.50 and zero
mechanical retention of English clinical terms, no off-the-shelf
candidate meets the intended live use as-is — the pre-registered
fallback (fine-tune on the 4090, per plan §7) is squarely in scope
unless adjudication shows the transliterations are clinically
recoverable. Confounders to weigh before the call: n = 1 recording;
`01_chest_pain_si` not yet recorded; and this recording's audio came
through the app's mic path (recording conditions were not varied).

## Post-hoc addendum: the other RRashmini checkpoints (owner query)

Asked whether a larger seniruk model exists (it does not — that author
published only `whisper-small-si` plus a CPU copy), we found the
benchmark's "only large fine-tune found" understated RRashmini's
catalogue: four sibling repos exist beyond the benchmarked
`whisper-large-v2-sinhala`. Screened post-hoc on the same manifest with
the same harness (results:
`evals/sinhala_asr_results_recordings_posthoc.json`, additions marked in
the harness MODELS dict; NOT part of the pre-registered nine):

| Repo | CER | WER | Verdict |
|---|---|---|---|
| `whisper-large-sinhala` | 0.523 | 0.754 | **identical transcript, character-for-character, to the benchmarked `whisper-large-v2-sinhala`** — same weights, different name |
| `whisper-large-sinhala-1` | 0.710 | 0.855 | identical to `-t1` below |
| `whisper-large-v2-sinhala-t1` | 0.710 | 0.855 | a second, worse checkpoint |
| `whisper-medium-sinhala` | — | — | empty repo, no weights |

Net: no new candidate. The four repos hold two distinct models; the
better one was already in the benchmark and remains behind seniruk-small.

Two more harness fixes shipped for these repos (they also lack
`generation_config.json`): borrow the stock base generation config, and
install it on **both** the model and the pipeline object — the
transformers pipeline snapshots its own copy at construction and passes
it to `generate()`, so replacing only `model.generation_config` silently
does nothing. Both no-ops for properly published models.

## Limitations

- Single recording, single script, n = 1 per model — no variance
  estimate; treat ranks within ~0.05 CER as ties.
- Reference frozen by verbatim attestation, not audio-checked.
- The per-clip CER of a 7-minute recording is one number over ~3.8k
  characters; corpus CER weighting is trivial with one clip.
- Chunk-boundary duplication penalises all models but not equally in
  principle (longer outputs suffer more insertions).

## Step 6 — owner's transliteration adjudication (completed 2026-07-25)

Executes step 6 of the pre-registration in
`evals/2026-07-10_sinhala_asr_benchmark.md` § Pre-registration, over the
worksheet `evals/adjudication_03_si_worksheet.md` — 12 frozen curated
terms, 25 reference occurrences, each aligned against the top three
models.

**The pre-registered outcome measure was kept unchanged:** the binary
*transliteration hit* or *genuine loss*, plus whether the clinical
content survives. No middle band was added. Adjudicated by the project
owner; **no verdicts were pre-filled by the assistant.**

| Term | Model | Verdict | Clinical content survives |
|---|---|---|---|
| gliclazide | seniruk-small | transliteration hit | yes |
| gliclazide | rrashmini-large-v2 | transliteration hit | no |
| gliclazide | xlsr-sinhala | transliteration hit | no |
| metformin | seniruk-small | transliteration hit | yes |
| metformin | rrashmini-large-v2 | transliteration hit | no |
| metformin | xlsr-sinhala | transliteration hit | no |
| HbA1c | seniruk-small | genuine loss | no |
| HbA1c | rrashmini-large-v2 | transliteration hit | no |
| HbA1c | xlsr-sinhala | transliteration hit | no |
| cholesterol | seniruk-small | transliteration hit | yes |
| cholesterol | rrashmini-large-v2 | genuine loss | no |
| cholesterol | xlsr-sinhala | genuine loss | no |
| diabetes | seniruk-small | transliteration hit | yes |
| diabetes | rrashmini-large-v2 | genuine loss | no |
| diabetes | xlsr-sinhala | genuine loss | no |
| monofilament | seniruk-small | transliteration hit | yes |
| monofilament | rrashmini-large-v2 | genuine loss | no |
| monofilament | xlsr-sinhala | genuine loss | no |
| blood pressure | seniruk-small | genuine loss | no |
| blood pressure | rrashmini-large-v2 | genuine loss | no |
| blood pressure | xlsr-sinhala | transliteration hit | yes |
| losartan | seniruk-small | genuine loss | no |
| losartan | rrashmini-large-v2 | genuine loss | no |
| losartan | xlsr-sinhala | genuine loss | no |
| atorvastatin | seniruk-small | genuine loss | no |
| atorvastatin | rrashmini-large-v2 | genuine loss | no |
| atorvastatin | xlsr-sinhala | genuine loss | no |
| neuropathy | seniruk-small | genuine loss | no |
| neuropathy | rrashmini-large-v2 | genuine loss | no |
| neuropathy | xlsr-sinhala | genuine loss | no |
| ulcer | seniruk-small | transliteration hit | yes |
| ulcer | rrashmini-large-v2 | genuine loss | no |
| ulcer | xlsr-sinhala | genuine loss | no |
| referral | seniruk-small | transliteration hit | yes |
| referral | rrashmini-large-v2 | genuine loss | no |
| referral | xlsr-sinhala | genuine loss | no |

**Tallies.** seniruk-small: 7 of 12 transliteration hits, 7 of 12
clinical content survives. rrashmini-large-v2: 3 of 12 hits, 0 of 12
survives. xlsr-sinhala: 4 of 12 hits, 1 of 12 survives.

**Finding 1 — the ranking flips.** Mechanical English-term recall was
0/106 for every model, which scored all three as equally unusable.
Adjudication separates them decisively: seniruk-small recovers
clinically usable content for 7 of 12 curated terms, while the other two
recover 0 and 1. The mechanical metric concealed the only difference
with clinical meaning. This answers the pre-registered question of
whether adjudicated term recovery changes the picture: it changes the
model ranking; it does not change the verdict that off-the-shelf models
are unusable for code-switched clinical Sinhala.

**Finding 2 — four terms are unrecoverable across the entire
off-the-shelf landscape.** `HbA1c`, `losartan`, `atorvastatin` and
`neuropathy` have clinical content surviving in no model. Three of them
— losartan, atorvastatin and neuropathy — are unanimous genuine loss in
all three models. For a diabetes review that is two drug names, the
three-month control marker, and the diagnosis.

**Finding 3 — transliteration hit and clinical survival came apart in 6
of 36 cells.** `gliclazide`, `metformin` and `HbA1c` are transliteration
hits in rrashmini-large-v2 and xlsr-sinhala, yet the owner judged the
clinical content not to survive. A single binary would have scored those
six cells as successes. Keep both fields in any future adjudication.

### Limitations of the adjudication

- **Unblinded:** the adjudication instrument displayed model names.
- Candidate spans were located and romanised **mechanically** by the
  assistant, with the full hypothesis window available for override.
- **Single adjudicator.**
- One recording, 12 curated terms, 25 reference occurrences.

None of this accounts for a 7-versus-0 gap in clinical survival, but the
design should be blinded if the adjudication is ever repeated.

**What followed from this result:** on 2026-07-25 the owner decided that
Consultation AI is **English-only for v1** and closed Phase 5 with this
negative result — recorded in PROJECT_PLAN.md §4 (Scope decision), the
decision header of `evals/2026-07-17_finetune_plan.md`, and HANDOVER.md.
