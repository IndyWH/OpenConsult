# Phase 5 fine-tune plan — groundwork (no training yet)

> ## DECISION: DEFERRED (2026-07-25, owner)
>
> The Phase 5 fine-tune is **deferred to v2**. The eight sign-offs in §7
> were **deliberately not sought** — this is a decision not to start, not
> a decision stalled awaiting them.
>
> **Rationale.** The pre-registered off-the-shelf investigation is now
> complete through step 6 (adjudication, 2026-07-25 — see
> `evals/2026-07-12_sinhala_asr_recordings_eval.md` § Step 6). Its
> conclusion stands: no off-the-shelf model is usable for code-switched
> clinical Sinhala. The project's remaining pre-Phase-7 obligations take
> priority over acting on that conclusion now.
>
> **The plan below is preserved unchanged** and remains the starting
> point if Sinhala restarts.
>
> **One substantive change, from the adjudication.** The base-model
> choice leads with **`seniruk/whisper-small-si`**, not xlsr-sinhala.
> The CER ranking in the recordings eval favoured xlsr (0.462 vs 0.504);
> adjudicated clinical survival favours seniruk-small **7 to 1**, and
> clinical survival is the metric that matters for this use case. This
> **reverses a ranking the recordings eval reported**. (§4 already made
> seniruk-small Arm A, on CER-proximity and downstream-fit grounds and
> with xlsr rejected as a base; the adjudication now supplies an
> independent and considerably stronger reason for the same choice, so
> §4 needs no edit.)
>
> **Restart conditions.** Sinhala work resumes when a Sinhala arm is
> needed for a demo or study commitment, or when a new candidate model
> or code-switched dataset appears. **Whoever restarts it reads the step
> 6 section of the recordings eval first.**

**Date:** 2026-07-17
**Status:** planning document only. Nothing here has been executed; no
training data has been downloaded beyond what the benchmark already
used. Every item marked **⚠ SIGN-OFF** is the project owner's decision
and blocks the step it sits in.

## 1. What the evidence says must be fixed

From `evals/2026-07-12_sinhala_asr_recordings_eval.md` (the decision
record this plan answers to):

- **Real conversational audio breaks every candidate.** Best real-audio
  CER 0.462 (xlsr-sinhala, fragmentary CTC output) / best Whisper 0.504
  (seniruk-small), against 0.035 on read speech. The off-the-shelf
  landscape is exhausted (post-hoc screen found only duplicates).
- **Code-switching is a total loss: English-term recall 0/106 for every
  fine-tune.** Some transliterations were clean (metformin →
  මෙත්ෆෝමෙන්), at least one dangerous (gliclazide → වික්පසායිල්). The
  downstream pipeline (CDS, notes, RAG) operates on English medical
  vocabulary, so unrecovered terms are lost to the whole product.

So the fine-tune has two targets, in priority order: (1) keep or improve
Sinhala CER on conversational audio; (2) make embedded English medical
terms survive *in Latin script*.

## 2. Candidate training data sources and licences

Licences verified against openslr.org / Hugging Face today (2026-07-17).

| Source | Size | Licence | Role in this plan |
|---|---|---|---|
| OpenSLR **SLR52** (Sinhala ASR training set, Google) | ~185k utterances, ~15 GB | **CC BY-SA 4.0**, © Google 2016–2018; paper citation required | Bulk Sinhala acoustic foundation (training) |
| OpenSLR **SLR30** (Sinhala TTS corpus, Google) | ~700 MB audio | **CC BY-SA 4.0**, © Google 2015–2016 | **Not training** — keep as secondary dev set; it is one of only two public screens we have, and training on it burns it (the Subhaka contamination finding is the cautionary tale) |
| `seniruk/sinscribe-sinhala-stt` (HF dataset behind the front-runner) | undocumented | undeclared; model is Apache 2.0 | Inspect before any use; possibly an SLR re-mix. Not needed if Arm A continues from the model rather than its data |
| Synthetic code-switched set (built by us, §3) | target 10–30 h | ours (see TTS licence caveats in §3) | The code-switching signal (training + dev slice) |
| Own gold recordings (03_si done; 01_si pending; optional new material) | minutes–hours | ours, synthetic scripts, consented actors | **Held-out test** (frozen refs), never training — except optional new purpose-recorded material (§3 T3) |
| Excluded: Common Voice (never collected Sinhala), FLEURS/MMS/Seamless (no si), YouTube/news scraping (licence and consent unacceptable for this project) | | | |

**⚠ SIGN-OFF (licence posture):** CC BY-SA share-alike obligations are
straightforward for internal research use, but if the resulting model
weights are ever *published*, the share-alike question for
corpus-derived weights is unsettled legal ground. Decide now whether
publishing weights is an ambition (affects nothing technical, but the
answer should be on record before training).

## 3. Code-switching data strategy

The measured failure is English medical terms inside Sinhala carrier
speech. No natural corpus covers this; the mock `_si` scripts prove the
register exists and what it sounds like ("pressure එක", "gliclazide 80
උදේට"). Build synthetic data in three tiers:

**Text layer.** Template + slot-filling in the mock-script register:
Sinhala carrier sentences with English clinical slots (drug names,
doses, investigations, units, sign names). Term bank: the curated lists
from all 17 scripts plus a standard drug/investigation list. Optionally
MedGemma (already local) generates carrier-sentence variety; a sampled
human read-through decides whether its Sinhala is natural enough.
**⚠ SIGN-OFF:** owner reads a 50-sentence sample before the text layer
is accepted (naturalness + clinical plausibility — a native-speaker
clinician's judgement, nobody else can make it).

**Audio layer, three tiers:**

- **T1 — TTS.** `facebook/mms-tts-sin` (VITS) is the only offline
  Sinhala TTS with a clear licence — **CC BY-NC 4.0 (non-commercial)**.
  Acceptable for this research prototype, but it taints the trained
  model's commercial future. **⚠ SIGN-OFF.** Note Sinhala TTS cannot
  pronounce the English terms — T1 alone produces carrier sentences
  only; terms come from T2. (Cloud voices — e.g. Azure's si-LK neural
  voices — sound better but their ToS on training-data use likely
  forbids this; treat as excluded unless the owner wants the ToS read
  closely.)
- **T2 — splicing.** Cut English-term audio (from our own English
  recordings, English TTS voices, and a recorded term-list session)
  into Sinhala carriers (SLR52 clips and/or T1 output) with level
  matching, crossfades, and room-tone smoothing. This manufactures the
  exact phenomenon with real acoustics. Known risk: splice artifacts
  become a learnable shortcut ("English word follows a click") —
  mitigate by applying the same crossfade/level perturbations to
  non-term positions in carrier-only clips, so the artifact carries no
  label information.
- **T3 — small gold set.** Owner + a helper read ~200–500 code-switched
  clinical sentences (1–2 recording hours, same setup as the 2026-07-12
  session, capture paused before debriefing per the docket note). The
  highest value per minute of any data in this plan.
  **⚠ SIGN-OFF:** whether to spend that recording time, whose voices,
  and explicit consent for training use.

**Targets keep English terms in Latin script** — that is the entire
point. Reference normalisation identical to the eval harness (NFC,
ZWJ/ZWNJ stripped, punctuation stripped, digits kept).

**Mixing ratio** (starting point, tunable on dev): 70% SLR52 / 25%
synthetic code-switched / 5% gold. The Sinhala bulk guards against
forgetting; the synthetic slice carries the new behaviour.

## 4. Base model choice

| Option | For | Against |
|---|---|---|
| **Arm A: continue from `seniruk/whisper-small-si`** (recommended primary) | Best real-audio Whisper (0.504); already knows Sinhala; Apache 2.0 (verified); cheapest path to the code-switch objective | Training data ("sinscribe") undocumented — unknown overlap with SLR dev sets (contaminates *dev* comparisons, not our test, which post-dates every candidate); its habit of transliterating English must be trained *out* |
| **Arm B: stock `openai/whisper-small`** (clean-provenance arm) | Fully documented start; seniruk proves whisper-small capacity suffices for CER 0.035 read-speech; no inherited transliteration habit | Must learn Sinhala from scratch on SLR52 — more steps, and our recipe may not match seniruk's quality (their 2-epoch run took 41 h on weaker hardware) |
| **Arm C: `large-v3` + LoRA** (conditional stretch) | Capacity headroom; final pass is offline so its slower inference is tolerable | Stock large-v3 loops degenerately on Sinhala (bad starting behaviour); days per run; live-path latency doubtful |
| Rejected as base: xlsr CTC (best CER but fragmentary, no punctuation, needs an LM — poor fit downstream); janiduchamika (≈ seniruk quality, worse contamination profile) | | |

**Recommendation:** run Arms A and B in parallel — whisper-small runs
are cheap on the 4090 and the pair separates "is the recipe right?"
(B) from "is the starting point right?" (A). Arm C only if both
plateau under the gates. **⚠ SIGN-OFF:** the arm plan and the
recommendation to prioritise A.

## 5. Training recipe (sized to the 4090, 24 GB)

- **Framework:** HF `transformers` Seq2SeqTrainer (the standard Whisper
  fine-tune recipe), SLR52 via the same pinned parquet mirror the
  benchmark used; eval during training with jiwer + the harness's exact
  normalisation. Seed 42; config and library versions committed beside
  the results JSON, like every eval so far.
- **whisper-small (Arms A/B, 244 M params):** fp16, per-device batch 16
  with gradient accumulation 2 (effective 32), lr 1e-5 (Arm A: 5e-6 —
  it starts closer), 500 warmup steps, up to 10k steps with early
  stopping on dev CER, SpecAugment on. Fits in ~8–10 GB; a full run is
  an overnight job, several runs per week are realistic.
- **large-v3 LoRA (Arm C, 1.55 B):** 8-bit base + LoRA (r=32, α=64,
  attention projections), batch 4 × accum 8, gradient checkpointing;
  ~16–20 GB; days per run; merge LoRA before conversion.
- **GPU sharing:** training cannot coexist with MedGemma/Ollama —
  `sudo systemctl stop consultation-ai ollama` for the duration (the
  finalize.py VRAM-sequencing lesson, applied to training).
- **Deployment path:** convert with `ct2-transformers-converter` →
  faster-whisper, which serves BOTH transcription paths (live
  `app/transcription.py` and whisperx's backend in `app/finalize.py`).
  How Sinhala consultations are routed to the Sinhala model (language
  toggle? auto-detect?) is a Phase 5 integration decision outside this
  plan's scope, flagged so it isn't forgotten.

## 6. Pre-registered success gates

**Held-out test = the frozen recordings eval, used sparingly.** The
frozen `03_diabetes_review_si` manifest is TEST: evaluated only at
pre-registered checkpoints (each arm's final model, plus at most one
mid-training sanity look per arm), never for tuning. Day-to-day
iteration uses dev sets only: a held-out slice of the synthetic set,
the SLR52 benchmark sample, SLR30 as secondary. **Before any training
starts, record `01_chest_pain_si` and freeze its reference by the same
attestation protocol** — the test then has n=2 recordings and covers a
second register (acute chest pain vs chronic review).
**⚠ SIGN-OFF + scheduling:** the 01_si recording session.

**Gates** (proposed thresholds — **⚠ SIGN-OFF on every number**; the
baselines they beat are in the 2026-07-12 record):

- **G1 — Sinhala accuracy:** corpus CER on the recordings test ≤ 0.35
  (best off-the-shelf: 0.462 fragmentary CTC / 0.504 best Whisper).
- **G2 — code-switching:** mechanical English-term recall ≥ 50% of the
  frozen curated terms (baseline 0/106), AND zero dangerous drug-name
  errors among curated terms — "dangerous" = adjudicated as a plausible
  different drug or clinically misleading form (the gliclazide →
  වික්පසායිල් class), adjudication by the owner exactly as in the
  recordings eval protocol.
- **G3 — no read-speech regression:** SLR52-sample CER ≤ 0.05 for Arm A
  (parity with its base) / ≤ 0.08 for Arm B.
- **G4 — deployability:** CT2-converted model ≥ 5× real time on the
  4090 (live-path budget; the final pass has slack).

**Decision rule:** an arm passing G1–G4 is adopted (best G1 wins, G2
tie-break). If neither small arm passes after one revision cycle each,
escalate to Arm C. If that fails too, the recorded fallback is
seniruk-small + a post-ASR transliteration-mapping workflow (map known
Sinhala-script drug transliterations back to Latin terms), which the
adjudication worksheet already gathers the data for — and the failure
is written up honestly as the Phase 5 outcome.

All evaluation runs: n=1 per model per recording, deterministic
settings, results JSON committed next to this plan — the standards of
the existing eval records.

## 7. Consolidated sign-off checklist (owner)

1. Licence posture: any ambition to publish trained weights? (§2)
2. MMS-TTS non-commercial licence acceptable for T1? (§3)
3. 50-sentence naturalness review of the synthetic text layer. (§3)
4. T3 gold recording session: yes/no, voices, consent. (§3)
5. Arm plan (A primary, B parallel, C conditional). (§4)
6. Record + freeze `01_chest_pain_si` before training starts. (§6)
7. Gate thresholds G1–G4. (§6)
8. Confirmation that test-set discipline (frozen recordings, counted
   looks) is the operating rule for the whole fine-tune effort. (§6)
